const STORAGE_KEY = "zertan.theme";
const STORAGE_MIGRATION_KEY = "zertan.theme.version";
const STORAGE_UPDATED_AT_KEY = "zertan.theme.updated_at";
const THEME_STORAGE_VERSION = "2";
export const DEFAULT_THEME = "light";

const THEME_OPTIONS = [
    { id: "light", label: "Light" },
    { id: "dark", label: "Dark" },
    { id: "graphite", label: "Graphite" },
    { id: "sage", label: "Sage" },
    { id: "north-sea", label: "North Sea" },
];

const THEME_IDS = new Set(THEME_OPTIONS.map((theme) => theme.id));

export function getThemeOptions() {
    return THEME_OPTIONS.map((theme) => ({ ...theme }));
}

export function normalizeTheme(theme) {
    return THEME_IDS.has(theme) ? theme : DEFAULT_THEME;
}

export function resolveTheme(theme) {
    return THEME_IDS.has(theme) ? theme : "";
}

function ensureThemeStorageVersion() {
    try {
        window.localStorage.setItem(STORAGE_MIGRATION_KEY, THEME_STORAGE_VERSION);
    } catch (_error) {
        // Ignore storage errors so theming still works in restricted contexts.
    }
}

function nowThemeTimestamp() {
    return new Date().toISOString();
}

function normalizeUpdatedAt(value) {
    return typeof value === "string" && value.trim() ? value.trim() : "";
}

function selectPreferredThemeState(storedState, nativeState) {
    const storedTheme = resolveTheme(storedState?.theme);
    const nativeTheme = resolveTheme(nativeState?.theme);
    const storedUpdatedAt = normalizeUpdatedAt(storedState?.updatedAt);
    const nativeUpdatedAt = normalizeUpdatedAt(nativeState?.updatedAt);

    if (storedTheme && nativeTheme) {
        if (storedUpdatedAt && nativeUpdatedAt) {
            return storedUpdatedAt >= nativeUpdatedAt
                ? { theme: storedTheme, updatedAt: storedUpdatedAt }
                : { theme: nativeTheme, updatedAt: nativeUpdatedAt };
        }
        if (storedUpdatedAt) {
            return { theme: storedTheme, updatedAt: storedUpdatedAt };
        }
        if (nativeUpdatedAt) {
            return { theme: nativeTheme, updatedAt: nativeUpdatedAt };
        }
        return { theme: nativeTheme, updatedAt: "" };
    }

    if (storedTheme) {
        return { theme: storedTheme, updatedAt: storedUpdatedAt };
    }

    if (nativeTheme) {
        return { theme: nativeTheme, updatedAt: nativeUpdatedAt };
    }

    return { theme: DEFAULT_THEME, updatedAt: "" };
}

export function getStoredThemeState() {
    try {
        const storedVersion = window.localStorage.getItem(STORAGE_MIGRATION_KEY);
        const storedTheme = window.localStorage.getItem(STORAGE_KEY);
        const storedUpdatedAt = window.localStorage.getItem(STORAGE_UPDATED_AT_KEY);

        if (storedVersion !== THEME_STORAGE_VERSION && storedTheme === "graphite") {
            window.localStorage.setItem(STORAGE_KEY, "dark");
            ensureThemeStorageVersion();
            return { theme: "dark", updatedAt: normalizeUpdatedAt(storedUpdatedAt) };
        }

        const resolvedTheme = resolveTheme(storedTheme);
        if (resolvedTheme) {
            ensureThemeStorageVersion();
        }
        return { theme: resolvedTheme, updatedAt: normalizeUpdatedAt(storedUpdatedAt) };
    } catch (_error) {
        return { theme: "", updatedAt: "" };
    }
}

export function getStoredTheme() {
    return getStoredThemeState().theme;
}

export function getNativeThemeState() {
    return {
        theme: resolveTheme(window.__ZERTAN_TAURI_THEME),
        updatedAt: normalizeUpdatedAt(window.__ZERTAN_TAURI_THEME_UPDATED_AT),
    };
}

export function getNativeTheme() {
    return getNativeThemeState().theme;
}

export function getBootstrapThemeState() {
    return selectPreferredThemeState(getStoredThemeState(), getNativeThemeState());
}

export function getBootstrapTheme() {
    return getBootstrapThemeState().theme;
}

function applyThemeState(theme, { persist = true, updatedAt = "" } = {}) {
    const resolved = normalizeTheme(theme);
    const resolvedUpdatedAt = normalizeUpdatedAt(updatedAt) || nowThemeTimestamp();
    document.documentElement.dataset.theme = resolved;

    if (persist) {
        try {
            window.localStorage.setItem(STORAGE_KEY, resolved);
            window.localStorage.setItem(STORAGE_MIGRATION_KEY, THEME_STORAGE_VERSION);
            window.localStorage.setItem(STORAGE_UPDATED_AT_KEY, resolvedUpdatedAt);
        } catch (_error) {
            // Ignore storage errors so theming still works in restricted contexts.
        }
    }

    return { theme: resolved, updatedAt: resolvedUpdatedAt };
}

export function applyTheme(theme, options = {}) {
    return applyThemeState(theme, options).theme;
}

export function bootstrapTheme() {
    const bootstrapState = getBootstrapThemeState();
    return applyThemeState(bootstrapState.theme, { updatedAt: bootstrapState.updatedAt }).theme;
}

export function hasNativeThemeBridge() {
    return typeof window.__ZERTAN_TAURI_THEME_BRIDGE__?.setTheme === "function"
        || typeof window.__TAURI__?.core?.invoke === "function";
}

async function invokeThemeCommand(command, args = {}) {
    return window.__TAURI__.core.invoke(command, args);
}

export async function syncThemeFromNativeStore() {
    if (!hasNativeThemeBridge()) {
        return bootstrapTheme();
    }

    try {
        if (typeof window.__ZERTAN_TAURI_THEME_BRIDGE__?.getThemeState === "function") {
            const nativeState = window.__ZERTAN_TAURI_THEME_BRIDGE__.getThemeState();
            window.__ZERTAN_TAURI_THEME = normalizeTheme(nativeState.theme);
            window.__ZERTAN_TAURI_THEME_UPDATED_AT = normalizeUpdatedAt(nativeState.updatedAt);
            const preferredState = getBootstrapThemeState();
            const nativeTheme = normalizeTheme(nativeState.theme);
            const nativeUpdatedAt = normalizeUpdatedAt(nativeState.updatedAt);

            if (preferredState.theme !== nativeTheme || (preferredState.updatedAt && preferredState.updatedAt !== nativeUpdatedAt)) {
                const persistedState = await window.__ZERTAN_TAURI_THEME_BRIDGE__.setTheme(preferredState.theme);
                const resolvedTheme = normalizeTheme(persistedState?.theme || preferredState.theme);
                const resolvedUpdatedAt = normalizeUpdatedAt(persistedState?.updatedAt) || preferredState.updatedAt;
                window.__ZERTAN_TAURI_THEME = resolvedTheme;
                window.__ZERTAN_TAURI_THEME_UPDATED_AT = resolvedUpdatedAt;
                return applyThemeState(resolvedTheme, { updatedAt: resolvedUpdatedAt }).theme;
            }

            return applyThemeState(preferredState.theme, { updatedAt: preferredState.updatedAt }).theme;
        }

        const nativeTheme = normalizeTheme(await invokeThemeCommand("get_client_theme"));
        window.__ZERTAN_TAURI_THEME = nativeTheme;
        return applyThemeState(nativeTheme).theme;
    } catch (_error) {
        return bootstrapTheme();
    }
}

export async function setActiveTheme(theme) {
    const localState = applyThemeState(theme);

    if (!hasNativeThemeBridge()) {
        return localState.theme;
    }

    try {
        if (typeof window.__ZERTAN_TAURI_THEME_BRIDGE__?.setTheme === "function") {
            const persistedState = await window.__ZERTAN_TAURI_THEME_BRIDGE__.setTheme(localState.theme);
            const resolvedTheme = normalizeTheme(persistedState?.theme || localState.theme);
            const resolvedUpdatedAt = normalizeUpdatedAt(persistedState?.updatedAt) || localState.updatedAt;
            window.__ZERTAN_TAURI_THEME = resolvedTheme;
            window.__ZERTAN_TAURI_THEME_UPDATED_AT = resolvedUpdatedAt;
            return applyThemeState(resolvedTheme, { updatedAt: resolvedUpdatedAt }).theme;
        }

        const persistedTheme = normalizeTheme(await invokeThemeCommand("set_client_theme", { theme: localState.theme }));
        window.__ZERTAN_TAURI_THEME = persistedTheme;
        window.__ZERTAN_TAURI_THEME_UPDATED_AT = localState.updatedAt;
        return applyThemeState(persistedTheme, { updatedAt: localState.updatedAt }).theme;
    } catch (_error) {
        return localState.theme;
    }
}

export function fillThemeSelect(selectNode, activeTheme = getBootstrapTheme()) {
    if (!selectNode) {
        return;
    }

    if (!selectNode.dataset.themeOptionsReady) {
        selectNode.innerHTML = THEME_OPTIONS.map((theme) => `<option value="${theme.id}">${theme.label}</option>`).join("");
        selectNode.dataset.themeOptionsReady = "true";
    }

    selectNode.value = normalizeTheme(activeTheme);
}

export function bindThemeSelect(selectNode, { onApplied = null } = {}) {
    if (!selectNode || selectNode.dataset.themeBound === "true") {
        return;
    }

    fillThemeSelect(selectNode, getBootstrapTheme());
    selectNode.dataset.themeBound = "true";

    selectNode.addEventListener("change", async () => {
        const appliedTheme = await setActiveTheme(selectNode.value);
        fillThemeSelect(selectNode, appliedTheme);
        if (typeof onApplied === "function") {
            onApplied(appliedTheme);
        }
    });
}
