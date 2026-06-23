import {
  definePlugin,
  PanelSection,
  PanelSectionRow,
  DropdownItem,
  SingleDropdownOption,
  ToggleField,
  ButtonItem,
  Field,
  TextField,
  staticClasses,
} from "@decky/ui";
import { callable, toaster } from "@decky/api";

const { useState, useEffect, useMemo, Fragment } = window.SP_REACT;
type VFC<P = {}> = (props: P) => JSX.Element | null;

interface GameInfo {
  appid: number;
  name: string;
  type: string;
  install_path: string | null;
  offered_os: string[];
  installed_os: string[];
  runnable: string[];
  forced_compat_tool: string | null;
  default: string;
  last_actual_tool: string | null;
  last_actual_priority: number | null;
  last_actual_desc: string | null;
}

interface ScanResult {
  ok: boolean;
  error: string | null;
  steam_root: string | null;
  games: GameInfo[];
  game_count: number;
  library_count: number;
  scan_ms: number;
  last_error: string;
  plugin_version: string;
}

type FilterKey =
  | "installedOs"
  | "offeredOs"
  | "runnable"
  | "defaultLaunch"
  | "forcedTool";

interface Filters {
  search: string;
  installedOs: string;
  offeredOs: string;
  runnable: string;
  defaultLaunch: string;
  forcedTool: string;
  includeAll: boolean;
}


const defaultFilters = (): Filters => ({
  search: "",
  installedOs: "all",
  offeredOs: "all",
  runnable: "all",
  defaultLaunch: "all",
  forcedTool: "all",
  includeAll: false,
});

const PLUGIN_TITLE = "Steam Games Info";

const scanGames = callable<[boolean], ScanResult>("scan_games");

let cachedScanResult: ScanResult | null = null;
let cachedFilters: Filters = defaultFilters();
let cachedFiltersExpanded = false;

const formatDisplayText = (text: string): string =>
  text
    .replace(/\bwindows\b/gi, "Windows")
    .replace(/\blinux\b/gi, "Linux")
    .replace(/\bproton\b/gi, "Proton");

const joinValues = (values: string[] | undefined): string =>
  formatDisplayText((values || []).join(", "));

const countActiveFilters = (filters: Filters): number => {
  let count = 0;
  if (filters.search.trim()) {
    count += 1;
  }
  if (filters.installedOs !== "all") {
    count += 1;
  }
  if (filters.offeredOs !== "all") {
    count += 1;
  }
  if (filters.runnable !== "all") {
    count += 1;
  }
  if (filters.defaultLaunch !== "all") {
    count += 1;
  }
  if (filters.forcedTool !== "all") {
    count += 1;
  }
  if (filters.includeAll) {
    count += 1;
  }
  return count;
};

const hasOsToken = (values: string[] | undefined, token: string): boolean => {
  const normalized = (values || []).map((value) => value.toLowerCase());
  if (token === "unknown") {
    return normalized.some((value) => value.includes("unknown")) || normalized.length === 0;
  }
  return normalized.some((value) => value === token || value.includes(token));
};

const matchesInstalledOs = (game: GameInfo, filter: string): boolean => {
  const installed = game.installed_os || [];
  switch (filter) {
    case "all":
      return true;
    case "linux":
      return hasOsToken(installed, "linux");
    case "windows":
      return hasOsToken(installed, "windows");
    case "linux_only":
      return hasOsToken(installed, "linux") && !hasOsToken(installed, "windows");
    case "windows_only":
      return hasOsToken(installed, "windows") && !hasOsToken(installed, "linux");
    case "both":
      return hasOsToken(installed, "linux") && hasOsToken(installed, "windows");
    case "unknown":
      return hasOsToken(installed, "unknown");
    default:
      return true;
  }
};

const matchesOfferedOs = (game: GameInfo, filter: string): boolean => {
  const offered = game.offered_os || [];
  switch (filter) {
    case "all":
      return true;
    case "linux":
      return hasOsToken(offered, "linux");
    case "windows":
      return hasOsToken(offered, "windows");
    case "both":
      return hasOsToken(offered, "linux") && hasOsToken(offered, "windows");
    case "unknown":
      return hasOsToken(offered, "unknown");
    default:
      return true;
  }
};

const matchesRunnable = (game: GameInfo, filter: string): boolean => {
  const runnable = (game.runnable || []).map((value) => value.toLowerCase());
  switch (filter) {
    case "all":
      return true;
    case "native":
      return runnable.some((value) => value.includes("linux (native)"));
    case "proton":
      return runnable.some((value) => value.includes("windows (via proton)"));
    case "none":
      return runnable.some((value) => value === "none" || value === "unknown");
    default:
      return true;
  }
};

const matchesDefaultLaunch = (game: GameInfo, filter: string): boolean => {
  const defaultLaunch = (game.default || "").toLowerCase();
  switch (filter) {
    case "all":
      return true;
    case "native":
      return defaultLaunch.startsWith("linux");
    case "proton":
      return defaultLaunch.includes("proton");
    case "forced":
      return Boolean(game.forced_compat_tool);
    case "unknown":
      return defaultLaunch === "unknown";
    default:
      return true;
  }
};

const matchesForcedTool = (game: GameInfo, filter: string): boolean => {
  switch (filter) {
    case "all":
      return true;
    case "yes":
      return Boolean(game.forced_compat_tool);
    case "no":
      return !game.forced_compat_tool;
    default:
      return true;
  }
};

const matchesSearch = (game: GameInfo, search: string): boolean => {
  const query = search.trim().toLowerCase();
  if (!query) {
    return true;
  }
  if (game.name.toLowerCase().includes(query)) {
    return true;
  }
  return String(game.appid).includes(query);
};

const filterGames = (games: GameInfo[], filters: Filters): GameInfo[] =>
  games.filter(
    (game) =>
      matchesSearch(game, filters.search) &&
      matchesInstalledOs(game, filters.installedOs) &&
      matchesOfferedOs(game, filters.offeredOs) &&
      matchesRunnable(game, filters.runnable) &&
      matchesDefaultLaunch(game, filters.defaultLaunch) &&
      matchesForcedTool(game, filters.forcedTool)
  );

const FILTER_OPTIONS: Record<FilterKey, SingleDropdownOption[]> = {
  installedOs: [
    { data: "all", label: "All installed" },
    { data: "linux", label: "Has Linux build" },
    { data: "windows", label: "Has Windows build" },
    { data: "linux_only", label: "Linux only" },
    { data: "windows_only", label: "Windows only" },
    { data: "both", label: "Both Linux and Windows" },
    { data: "unknown", label: "Unknown" },
  ],
  offeredOs: [
    { data: "all", label: "All offered" },
    { data: "linux", label: "Offers Linux" },
    { data: "windows", label: "Offers Windows" },
    { data: "both", label: "Offers both" },
    { data: "unknown", label: "Unknown" },
  ],
  runnable: [
    { data: "all", label: "All runnable" },
    { data: "native", label: "Native Linux" },
    { data: "proton", label: "Windows via Proton" },
    { data: "none", label: "None / unknown" },
  ],
  defaultLaunch: [
    { data: "all", label: "All defaults" },
    { data: "native", label: "Defaults to native Linux" },
    { data: "proton", label: "Defaults to Proton" },
    { data: "forced", label: "User forced compat tool" },
    { data: "unknown", label: "Unknown" },
  ],
  forcedTool: [
    { data: "all", label: "Any forced tool" },
    { data: "yes", label: "Forced tool set" },
    { data: "no", label: "No forced tool" },
  ],
};

const filterOptionLabel = (key: FilterKey, value: string): string => {
  const label = FILTER_OPTIONS[key].find((option) => option.data === value)?.label;
  return typeof label === "string" ? label : "All";
};

const extractDropdownData = (
  option: unknown,
  options: SingleDropdownOption[]
): string => {
  if (typeof option === "number") {
    return String(options[option]?.data ?? "all");
  }
  if (typeof option === "string") {
    return option;
  }
  if (option && typeof option === "object" && "data" in option) {
    return String((option as SingleDropdownOption).data);
  }
  return "all";
};

const filterLabel = (key: FilterKey): string => {
  switch (key) {
    case "installedOs":
      return "Installed builds";
    case "offeredOs":
      return "Offered builds";
    case "runnable":
      return "Can run";
    case "defaultLaunch":
      return "Default launch";
    case "forcedTool":
      return "Forced compat tool";
    default:
      return "Filter";
  }
};

const detailTextStyle = {
  color: "#8b929a",
  fontSize: "12px",
  lineHeight: "1.5",
} as const;

const pathTextStyle = {
  ...detailTextStyle,
  wordBreak: "break-all",
  overflowWrap: "anywhere",
} as const;

const GameRow: VFC<{ game: GameInfo }> = ({ game }) => (
  <PanelSectionRow>
    <Field
      label={`${game.name} (${game.appid})`}
      childrenLayout="below"
      bottomSeparator="standard"
      focusable
      highlightOnFocus
    >
      <div style={detailTextStyle}>
        <div>Offered: {joinValues(game.offered_os)}</div>
        <div>Installed: {joinValues(game.installed_os)}</div>
        <div>Can run: {joinValues(game.runnable)}</div>
        <div>Default: {formatDisplayText(game.default)}</div>
        {game.install_path && (
          <div>
            <div style={{ marginTop: "4px" }}>Install path:</div>
            <div style={pathTextStyle}>{game.install_path}</div>
          </div>
        )}
        {game.forced_compat_tool && (
          <div>
            Forced tool: {formatDisplayText(game.forced_compat_tool)}
          </div>
        )}
        {game.last_actual_desc && (
          <div>Last ran as: {formatDisplayText(game.last_actual_desc)}</div>
        )}
      </div>
    </Field>
  </PanelSectionRow>
);

const SteamGameVersionsContent: VFC = () => {
  const [scanResult, setScanResult] = useState<ScanResult | null>(cachedScanResult);
  const [filters, setFilters] = useState<Filters>(() => ({ ...cachedFilters }));
  const [filtersExpanded, setFiltersExpanded] = useState(cachedFiltersExpanded);
  const [loading, setLoading] = useState(!cachedScanResult);
  const [scanning, setScanning] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const applyFilters = (updater: (current: Filters) => Filters) => {
    setFilters((current) => {
      const next = updater(current);
      cachedFilters = next;
      return next;
    });
  };

  const setFiltersExpandedPersist = (expanded: boolean) => {
    cachedFiltersExpanded = expanded;
    setFiltersExpanded(expanded);
  };

  const runScan = async (includeAll: boolean, showToast = false) => {
    setScanning(true);
    setErrorMessage("");
    try {
      const result = await scanGames(includeAll);
      cachedScanResult = result;
      setScanResult(result);
      if (!result.ok) {
        const message = result.error || result.last_error || "Scan failed";
        setErrorMessage(message);
        toaster.toast({
          title: PLUGIN_TITLE,
          body: message,
        });
      } else if (showToast) {
        toaster.toast({
          title: PLUGIN_TITLE,
          body: `Scanned ${result.game_count} entries in ${result.scan_ms} ms`,
        });
      }
    } catch (error) {
      const message = `Scan failed: ${String(error)}`;
      setErrorMessage(message);
      toaster.toast({
        title: PLUGIN_TITLE,
        body: message,
      });
    } finally {
      setScanning(false);
      setLoading(false);
    }
  };

  useEffect(() => {
    if (cachedScanResult) {
      setScanResult(cachedScanResult);
      setLoading(false);
      return;
    }
    runScan(cachedFilters.includeAll);
  }, []);

  const filteredGames = useMemo(
    () => filterGames(scanResult?.games || [], filters),
    [scanResult, filters]
  );

  const activeFilterCount = useMemo(
    () => countActiveFilters(filters),
    [filters]
  );

  const updateFilter = (key: FilterKey, rawOption: unknown) => {
    const value = extractDropdownData(rawOption, FILTER_OPTIONS[key]);
    setFiltersExpandedPersist(true);
    applyFilters((current) => {
      if (current[key] === value) {
        return current;
      }
      return { ...current, [key]: value };
    });
  };

  const handleIncludeAllToggle = async (enabled: boolean) => {
    if (filters.includeAll === enabled) {
      return;
    }
    applyFilters((current) => ({ ...current, includeAll: enabled }));
    await runScan(enabled, true);
  };

  const handleResetFilters = () => {
    applyFilters(() => defaultFilters());
    setFiltersExpandedPersist(false);
  };

  if (loading) {
    return (
      <PanelSection title="Library">
        <PanelSectionRow>
          <div style={{ color: "#8b929a" }}>Scanning Steam library...</div>
        </PanelSectionRow>
      </PanelSection>
    );
  }

  return (
    <Fragment>
      <PanelSection title="Library">
        <PanelSectionRow>
          <div style={{ color: "#8b929a", fontSize: "12px" }}>
            {scanResult?.ok
              ? `${filteredGames.length} shown of ${scanResult.game_count} scanned | ${scanResult.library_count} libraries | ${scanResult.scan_ms} ms`
              : "Scan failed"}
          </div>
        </PanelSectionRow>

        {scanResult?.steam_root && (
          <PanelSectionRow>
            <div
              style={{
                color: "#8b929a",
                fontSize: "11px",
                wordBreak: "break-all",
              }}
            >
              Steam: {scanResult.steam_root}
            </div>
          </PanelSectionRow>
        )}

        <PanelSectionRow>
          <ButtonItem
            layout="below"
            onClick={() => runScan(filters.includeAll, true)}
            disabled={scanning}
          >
            {scanning ? "Scanning..." : "Rescan library"}
          </ButtonItem>
        </PanelSectionRow>

        {errorMessage && (
          <PanelSectionRow>
            <div
              style={{
                color: "#ff6b6b",
                fontSize: "12px",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {errorMessage}
            </div>
          </PanelSectionRow>
        )}
      </PanelSection>

      <PanelSection title="Filters">
        {!filtersExpanded && (
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={() => setFiltersExpandedPersist(true)}>
              {activeFilterCount > 0
                ? `Show filters (${activeFilterCount} active)`
                : "Show filters"}
            </ButtonItem>
          </PanelSectionRow>
        )}

        {filtersExpanded && (
          <Fragment>
            <PanelSectionRow>
              <Field
                label="Search"
                description="Filter by game name or AppID"
              >
                <TextField
                  value={filters.search}
                  bShowClearAction={true}
                  onChange={(event) => {
                    const next =
                      typeof event === "string"
                        ? event
                        : event?.target?.value ?? "";
                    setFiltersExpandedPersist(true);
                    applyFilters((current) => ({
                      ...current,
                      search: next,
                    }));
                  }}
                />
              </Field>
            </PanelSectionRow>

            {(
              [
                "installedOs",
                "offeredOs",
                "runnable",
                "defaultLaunch",
                "forcedTool",
              ] as FilterKey[]
            ).map((key) => (
              <PanelSectionRow key={key}>
                <DropdownItem
                  label={filterLabel(key)}
                  menuLabel={filterLabel(key)}
                  layout="below"
                  childrenContainerWidth="max"
                  rgOptions={FILTER_OPTIONS[key]}
                  selectedOption={filters[key]}
                  strDefaultLabel={filterOptionLabel(key, filters[key])}
                  onChange={(option) => updateFilter(key, option)}
                />
              </PanelSectionRow>
            ))}

            <PanelSectionRow>
              <ToggleField
                label="Include tools and runtimes"
                description="Show non-game entries (Proton, redistributables, etc.)"
                checked={filters.includeAll}
                onChange={handleIncludeAllToggle}
                disabled={scanning}
              />
            </PanelSectionRow>

            <PanelSectionRow>
              <ButtonItem layout="below" onClick={handleResetFilters}>
                Reset filters
              </ButtonItem>
            </PanelSectionRow>

            <PanelSectionRow>
              <ButtonItem
                layout="below"
                onClick={() => setFiltersExpandedPersist(false)}
              >
                Hide filters
              </ButtonItem>
            </PanelSectionRow>
          </Fragment>
        )}
      </PanelSection>

      <PanelSection title="Games">
        {filteredGames.length === 0 ? (
          <PanelSectionRow>
            <div style={{ color: "#8b929a" }}>No games match current filters.</div>
          </PanelSectionRow>
        ) : (
          filteredGames.map((game) => <GameRow key={game.appid} game={game} />)
        )}
      </PanelSection>

      <PanelSection title="About">
        <PanelSectionRow>
          <Field
            label={PLUGIN_TITLE}
            childrenLayout="below"
            bottomSeparator="standard"
            focusable
            highlightOnFocus
          >
            <div style={detailTextStyle}>
              <div>Version: v{scanResult?.plugin_version ?? "?"}</div>
            </div>
          </Field>
        </PanelSectionRow>
      </PanelSection>
    </Fragment>
  );
};

const SteamGameVersionsIcon: VFC = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" width="1em" height="1em">
    <path d="M4 6h16v2H4V6zm0 5h10v2H4v-2zm0 5h16v2H4v-2zm12-5h4v2h-4v-2z" />
  </svg>
);

export default definePlugin(() => {
  return {
    name: PLUGIN_TITLE,
    title: <div className={staticClasses.Title}>{PLUGIN_TITLE}</div>,
    content: <SteamGameVersionsContent />,
    icon: <SteamGameVersionsIcon />,
  };
});
