window.ServerConsole = window.ServerConsole || {};

(function (App) {
    App.DEFAULT_THEME = "light";
    App.THEME_STORAGE_KEY = "zertan.server_console.theme";
    App.THEME_OPTIONS = [
        { id: "light", label: "Light" },
        { id: "dark", label: "Dark" },
        { id: "graphite", label: "Graphite" },
        { id: "sage", label: "Sage" },
        { id: "north-sea", label: "North Sea" }
    ];
    App.THEME_IDS = new Set(App.THEME_OPTIONS.map((theme) => theme.id));

    App.normalizeTheme = function (theme) {
        return App.THEME_IDS.has(theme) ? theme : App.DEFAULT_THEME;
    };

    App.NAV_SECTIONS = [
        {
            id: "overview",
            label: "Overview",
            helper: "Instance health, addresses, storage paths, and shortcuts."
        },
        {
            id: "directory",
            label: "Directory",
            helper: "Search users and groups with floating results over the content."
        },
        {
            id: "features",
            label: "Features",
            helper: "Quickly enable or disable site capabilities for the running domain."
        },
        {
            id: "activity",
            label: "API Log",
            helper: "Important API requests made against this server during the current runtime."
        }
    ];

    App.state = {
        section: "overview",
        snapshot: window.__SERVER_CONSOLE_BOOTSTRAP__ || null,
        theme: App.normalizeTheme(window.__SERVER_CONSOLE_THEME__ || document.documentElement.dataset.theme || App.DEFAULT_THEME),
        directoryQuery: "",
        directoryPanelOpen: false,
        activityFilter: "all",
        modalItem: null,
        featureBusy: {},
        stopping: false,
        navOpen: false
    };

    App.runtime = {
        refreshTimer: null,
        refreshInFlight: false,
        renderedSection: null,
        initialized: false
    };

    App.api = function () {
        return window.pywebview && window.pywebview.api ? window.pywebview.api : null;
    };

    App.snapshot = function () {
        return App.state.snapshot || {
            server: {},
            stats: {},
            users: [],
            groups: [],
            features: [],
            activity: []
        };
    };

    App.escapeHtml = function (value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    };

    App.applyTheme = function (theme, options) {
        const resolvedTheme = App.normalizeTheme(theme);
        const persist = !options || options.persist !== false;

        document.documentElement.dataset.theme = resolvedTheme;
        App.state.theme = resolvedTheme;
        window.__SERVER_CONSOLE_THEME__ = resolvedTheme;

        if (persist) {
            try {
                window.localStorage.setItem(App.THEME_STORAGE_KEY, resolvedTheme);
            } catch (_error) {
                // Ignore storage errors so theming still works in restricted contexts.
            }
        }

        return resolvedTheme;
    };

    App.syncThemeSelects = function () {
        const optionsHtml = App.THEME_OPTIONS
            .map((theme) => `<option value="${theme.id}">${theme.label}</option>`)
            .join("");

        document.querySelectorAll("[data-server-console-theme-select]").forEach((select) => {
            if (!select.dataset.themeOptionsReady) {
                select.innerHTML = optionsHtml;
                select.dataset.themeOptionsReady = "true";
            }
            select.value = App.state.theme;
        });
    };
})(window.ServerConsole);
