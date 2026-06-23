"""Detect installed Steam game builds, runnable platforms, and default launch."""

import glob
import os
import re
import struct

try:
    import vdf
except ImportError:
    vdf = None


def find_steam_root():
    candidates = [
        os.path.expanduser("~/.local/share/Steam"),
        os.path.expanduser("~/.steam/steam"),
        os.path.expanduser("~/.steam/root"),
    ]
    for candidate in candidates:
        if os.path.isfile(os.path.join(candidate, "appcache", "appinfo.vdf")):
            return os.path.realpath(candidate)
    return None


def find_library_dirs(steam_root):
    """Return list of steamapps directories across all libraries."""
    library_file = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")
    dirs = []
    if os.path.isfile(library_file) and vdf is not None:
        data = vdf.load(open(library_file, encoding="utf-8"))
        root = data.get("libraryfolders", data)
        for _key, entry in root.items():
            if isinstance(entry, dict) and "path" in entry:
                steamapps = os.path.join(entry["path"], "steamapps")
                if os.path.isdir(steamapps):
                    dirs.append(os.path.realpath(steamapps))
    own = os.path.realpath(os.path.join(steam_root, "steamapps"))
    if own not in dirs and os.path.isdir(own):
        dirs.append(own)
    seen, out = set(), []
    for directory in dirs:
        if directory not in seen:
            seen.add(directory)
            out.append(directory)
    return out


class AppInfoParser:
    MAGIC_28 = 0x07564428
    MAGIC_29 = 0x07564429

    def __init__(self, path):
        with open(path, "rb") as file_handle:
            self.data = file_handle.read()
        self.pos = 0
        self.magic = self._u32()
        self.universe = self._u32()
        if self.magic not in (self.MAGIC_28, self.MAGIC_29):
            raise ValueError("unsupported appinfo.vdf magic %#x" % self.magic)
        self.string_table = None
        if self.magic == self.MAGIC_29:
            table_off = self._i64()
            self.string_table = self._read_string_table(table_off)

    def _u32(self):
        value = struct.unpack_from("<I", self.data, self.pos)[0]
        self.pos += 4
        return value

    def _i64(self):
        value = struct.unpack_from("<q", self.data, self.pos)[0]
        self.pos += 8
        return value

    def _u64(self):
        value = struct.unpack_from("<Q", self.data, self.pos)[0]
        self.pos += 8
        return value

    def _i32(self):
        value = struct.unpack_from("<i", self.data, self.pos)[0]
        self.pos += 4
        return value

    def _cstr(self):
        end = self.data.index(b"\x00", self.pos)
        string_value = self.data[self.pos:end].decode("utf-8", "replace")
        self.pos = end + 1
        return string_value

    def _read_string_table(self, offset):
        save = self.pos
        self.pos = offset
        count = self._u32()
        strings = [self._cstr() for _ in range(count)]
        self.pos = save
        return strings

    def _key(self):
        if self.string_table is not None:
            return self.string_table[self._u32()]
        return self._cstr()

    def _read_kv(self):
        node = {}
        while True:
            token = self.data[self.pos]
            self.pos += 1
            if token == 0x08:
                return node
            key = self._key()
            if token == 0x00:
                node[key] = self._read_kv()
            elif token == 0x01:
                node[key] = self._cstr()
            elif token == 0x02:
                node[key] = self._i32()
            elif token == 0x07:
                node[key] = self._u64()
            else:
                raise ValueError("unknown KV type %#x at %d" % (token, self.pos))

    def iter_apps(self, wanted=None):
        """Yield (appid, kv_dict) for each app. If wanted is a set, only those."""
        while True:
            appid = self._u32()
            if appid == 0:
                break
            size = self._u32()
            entry_end = self.pos + size
            if wanted is not None and appid not in wanted:
                self.pos = entry_end
                continue
            self._u32()
            self._u32()
            self._u64()
            self.pos += 20
            self._u32()
            if self.magic == self.MAGIC_29:
                self.pos += 20
            kv = self._read_kv()
            if isinstance(kv, dict) and "appinfo" in kv and len(kv) == 1:
                kv = kv["appinfo"]
            yield appid, kv
            self.pos = entry_end


def parse_manifest(path):
    data = vdf.load(open(path, encoding="utf-8"))
    return data.get("AppState", {})


def gather_installed(library_dirs):
    """Return dict appid(int) -> {name, installdir, library, depots:set(int)}."""
    games = {}
    for steamapps_dir in library_dirs:
        for acf_path in glob.glob(os.path.join(steamapps_dir, "appmanifest_*.acf")):
            try:
                state = parse_manifest(acf_path)
            except Exception:
                continue
            appid = int(state.get("appid", 0))
            if not appid:
                continue
            depots = set()
            for depot_id in (state.get("InstalledDepots") or {}).keys():
                try:
                    depots.add(int(depot_id))
                except ValueError:
                    pass
            games[appid] = {
                "name": state.get("name", str(appid)),
                "installdir": state.get("installdir", ""),
                "library": steamapps_dir,
                "installed_depots": depots,
                "acf": acf_path,
            }
    return games


def parse_compat_log(steam_root):
    """Parse compat_log.txt and return the last known tool mapping per appid."""
    log_path = os.path.join(steam_root, "logs", "compat_log.txt")
    result = {}
    if not os.path.isfile(log_path):
        return result
    import re

    pattern = re.compile(
        r'Mapping AppID (\d+) to tool "([^"]+)" with priority (\d+)'
    )
    with open(log_path, encoding="utf-8", errors="replace") as file_handle:
        for line in file_handle:
            match = pattern.search(line)
            if match:
                appid = int(match.group(1))
                tool = match.group(2)
                priority = int(match.group(3))
                result[appid] = {"tool": tool, "priority": priority}
    return result


_OS_NAMES = {"linux": "Linux", "windows": "Windows"}


def format_display_text(text):
    """Capitalize Windows, Linux, and Proton in user-facing strings."""
    if text is None:
        return text
    value = str(text)
    value = re.sub(r"\bwindows\b", "Windows", value, flags=re.I)
    value = re.sub(r"\blinux\b", "Linux", value, flags=re.I)
    value = re.sub(r"\bproton\b", "Proton", value, flags=re.I)
    return value


def format_os_name(name):
    if not name:
        return name
    lower = str(name).lower()
    if lower in _OS_NAMES:
        return _OS_NAMES[lower]
    return format_display_text(name)


def format_os_list(values):
    return [format_os_name(value) for value in values]


def tool_description(tool, priority):
    """Human-readable description of a compat tool entry from the log."""
    native = {
        "native",
        "steamlinuxruntime",
        "steamlinuxruntime_sniper",
        "steamlinuxruntime_soldier",
        "steamlinuxruntime_4",
    }
    if tool in native:
        return "Linux (native)"
    label = tool.replace("_", " ").replace("-", " ")
    source = {
        200: "user override",
        100: "Valve recommendation (strong)",
        85: "Valve SteamPlay compat list",
        75: "automatic (native Linux)",
    }.get(priority, "priority %d" % priority)
    return format_display_text("Windows via %s  [%s]" % (label, source))


def parse_compat_mapping(steam_root):
    config_path = os.path.join(steam_root, "config", "config.vdf")
    mapping = {}
    if not os.path.isfile(config_path):
        return mapping
    data = vdf.load(open(config_path, encoding="utf-8"))
    node = data
    for key in (
        "InstallConfigStore",
        "Software",
        "Valve",
        "Steam",
        "CompatToolMapping",
    ):
        node = (node or {}).get(key) if isinstance(node, dict) else None
        if node is None:
            break
    if node is None:
        node = _ci_dig(
            data,
            ["InstallConfigStore", "Software", "Valve", "Steam", "CompatToolMapping"],
        )
    if isinstance(node, dict):
        for appid, entry in node.items():
            if isinstance(entry, dict):
                mapping[appid] = entry.get("name", "")
    return mapping


def _ci_dig(node, path):
    current = node
    for key in path:
        if not isinstance(current, dict):
            return None
        match = None
        for candidate in current:
            if candidate.lower() == key.lower():
                match = candidate
                break
        if match is None:
            return None
        current = current[match]
    return current


def normalize_os(oslist):
    """oslist string like 'windows', 'linux', 'macos', 'linux,windows'."""
    if not oslist:
        return set()
    return {part.strip().lower() for part in str(oslist).split(",") if part.strip()}


def depot_os_map(app_kv):
    """depotid(int) -> set(os) from appinfo depots config.oslist."""
    out = {}
    depots = app_kv.get("depots") or {}
    for depot_id, depot in depots.items():
        if not isinstance(depot, dict):
            continue
        try:
            depot_id_int = int(depot_id)
        except ValueError:
            continue
        oslist = _ci_dig(depot, ["config", "oslist"])
        out[depot_id_int] = normalize_os(oslist)
    return out


def _exe_os(executable):
    """Infer OS from a launch executable name."""
    executable_lower = (executable or "").lower()
    if executable_lower.endswith((".exe", ".bat", ".cmd", ".msi")):
        return "windows"
    if executable_lower.endswith((".sh", ".x86_64", ".x86", ".elf")):
        return "linux"
    return None


def _is_windows_exe(executable):
    return (executable or "").lower().endswith((".exe", ".bat", ".cmd", ".msi"))


def _resolve_ci(base, relpath):
    """Resolve relpath under base case-insensitively. Return abs path or None."""
    if not base or not os.path.isdir(base):
        return None
    rel = relpath.replace("\\", "/").lstrip("./")
    parts = [part for part in rel.split("/") if part not in ("", ".")]
    current = base
    for part in parts:
        next_path = os.path.join(current, part)
        if os.path.exists(next_path):
            current = next_path
            continue
        try:
            match = None
            with os.scandir(current) as iterator:
                for entry in iterator:
                    if entry.name.lower() == part.lower():
                        match = entry.path
                        break
        except OSError:
            return None
        if match is None:
            return None
        current = match
    return current


def analyze_launches(app_kv, base):
    """Inspect launch entries, cross-checking oslist with the executable type."""
    result = {
        "offered_linux": False,
        "offered_windows": False,
        "installed_linux": False,
        "installed_windows": False,
    }
    launches = _ci_dig(app_kv, ["config", "launch"]) or {}
    if not isinstance(launches, dict):
        return result
    for _launch_id, launch_entry in launches.items():
        if not isinstance(launch_entry, dict):
            continue
        executable = launch_entry.get("executable") or ""
        oss = normalize_os(_ci_dig(launch_entry, ["config", "oslist"]))
        if not oss:
            guess = _exe_os(executable)
            oss = {guess} if guess else set()
        win_exe = _is_windows_exe(executable)
        exists = _resolve_ci(base, executable) is not None if executable else False
        if "linux" in oss and not win_exe:
            result["offered_linux"] = True
            if exists:
                result["installed_linux"] = True
        if "windows" in oss or win_exe:
            result["offered_windows"] = True
            if exists:
                result["installed_windows"] = True
    return result


def all_depot_os(app_kv):
    """Union of every depot's oslist (offered build platforms)."""
    out = set()
    for os_set in depot_os_map(app_kv).values():
        out |= os_set
    return {os_name for os_name in out if os_name in ("windows", "linux")}


def has_compat_prefix(game):
    """True if a Proton prefix exists for this app (Windows build was set up)."""
    prefix_path = os.path.join(game["library"], "compatdata", str(game["appid"]))
    return os.path.isdir(prefix_path)


def _install_base(game):
    if game.get("installdir"):
        return os.path.join(game["library"], "common", game["installdir"])
    return None


def classify(game, app_kv, forced_tool, this_os="linux"):
    common_oslist = normalize_os(_ci_dig(app_kv, ["common", "oslist"]))
    depot_oses = all_depot_os(app_kv)
    base = _install_base(game)
    launch_analysis = analyze_launches(app_kv, base)

    offered = set()
    if launch_analysis["offered_linux"]:
        offered.add("linux")
    if launch_analysis["offered_windows"]:
        offered.add("windows")
    if not offered:
        offered |= {os_name for os_name in common_oslist if os_name in ("windows", "linux")}
        offered |= depot_oses

    installed_os = set()
    if launch_analysis["installed_linux"]:
        installed_os.add("linux")
    if launch_analysis["installed_windows"]:
        installed_os.add("windows")

    if not installed_os:
        depot_os = depot_os_map(app_kv)
        tagged = set()
        untagged = False
        for depot_id in game["installed_depots"]:
            os_set = depot_os.get(depot_id)
            if os_set:
                tagged |= os_set
            else:
                untagged = True
        tagged = {os_name for os_name in tagged if os_name in ("windows", "linux")}
        if has_compat_prefix(game):
            installed_os.add("windows")
        if tagged == {"linux"}:
            installed_os.add("linux")
        elif tagged and not installed_os:
            installed_os |= tagged
        elif untagged and not installed_os and len(offered) == 1:
            installed_os |= offered

    app_type = str(_ci_dig(app_kv, ["common", "type"]) or "").lower()

    has_native_linux = "linux" in installed_os
    has_windows = "windows" in installed_os

    runnable = set()
    if has_native_linux:
        runnable.add("Linux (native)")
    if has_windows:
        runnable.add("Windows (via Proton)")
    if not runnable and installed_os:
        runnable.add("none")

    if forced_tool:
        default = "Windows (via %s)" % forced_tool
    elif has_native_linux:
        default = "Linux (native)"
    elif has_windows:
        default = "Windows (via Proton, Steam Play default)"
    else:
        default = "unknown"

    return {
        "appid": game["appid"],
        "name": game["name"],
        "type": app_type or "unknown",
        "library": game["library"],
        "install_path": base,
        "offered_os": format_os_list(sorted(offered)) or ["unknown"],
        "installed_os": format_os_list(sorted(installed_os)) or ["unknown"],
        "runnable": [format_display_text(value) for value in sorted(runnable)]
        or ["unknown"],
        "forced_compat_tool": forced_tool or None,
        "default": format_display_text(default),
    }


def scan_installed_games(include_all=False, appid=None):
    """Scan installed Steam games and return structured results."""
    if vdf is None:
        return {
            "ok": False,
            "error": "python module 'vdf' is required",
            "steam_root": None,
            "games": [],
            "game_count": 0,
            "library_count": 0,
        }

    steam_root = find_steam_root()
    if not steam_root:
        return {
            "ok": False,
            "error": "Steam installation not found",
            "steam_root": None,
            "games": [],
            "game_count": 0,
            "library_count": 0,
        }

    try:
        library_dirs = find_library_dirs(steam_root)
        games = gather_installed(library_dirs)
        for app_id, game in games.items():
            game["appid"] = app_id
        if appid is not None:
            games = {key: value for key, value in games.items() if key == appid}

        forced = parse_compat_mapping(steam_root)
        compat_log = parse_compat_log(steam_root)

        parser = AppInfoParser(os.path.join(steam_root, "appcache", "appinfo.vdf"))
        app_kvs = dict(parser.iter_apps(wanted=set(games.keys())))

        results = []
        for app_id, game in sorted(games.items(), key=lambda item: item[1]["name"].lower()):
            app_kv = app_kvs.get(app_id)
            if app_kv is None:
                results.append(
                    {
                        "appid": app_id,
                        "name": game["name"],
                        "type": "unknown",
                        "install_path": _install_base(game),
                        "offered_os": ["unknown"],
                        "installed_os": ["unknown (not in appinfo cache)"],
                        "runnable": ["unknown"],
                        "default": "unknown",
                        "forced_compat_tool": forced.get(str(app_id)),
                        "last_actual_tool": None,
                        "last_actual_priority": None,
                        "last_actual_desc": None,
                    }
                )
                continue

            result = classify(game, app_kv, forced.get(str(app_id)))
            log_entry = compat_log.get(app_id)
            if log_entry:
                result["last_actual_tool"] = log_entry["tool"]
                result["last_actual_priority"] = log_entry["priority"]
                result["last_actual_desc"] = tool_description(
                    log_entry["tool"], log_entry["priority"]
                )
            else:
                result["last_actual_tool"] = None
                result["last_actual_priority"] = None
                result["last_actual_desc"] = None
            results.append(result)

        if not include_all:
            results = [
                result
                for result in results
                if result.get("type") in (None, "game", "unknown")
            ]

        return {
            "ok": True,
            "error": None,
            "steam_root": steam_root,
            "games": results,
            "game_count": len(results),
            "library_count": len(library_dirs),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "steam_root": steam_root,
            "games": [],
            "game_count": 0,
            "library_count": 0,
        }
