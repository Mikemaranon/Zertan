use std::{
    fs,
    path::{Path, PathBuf},
    sync::Mutex,
};

use chrono::{SecondsFormat, Utc};
use directories::ProjectDirs;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use tauri::{
    utils::config::WebviewUrl,
    webview::WebviewWindowBuilder,
    AppHandle, Manager, WindowEvent,
};
use url::Url;
use uuid::Uuid;

const APP_SCHEME: &str = "http";
const DEFAULT_THEME: &str = "light";
const THEME_STORAGE_VERSION: u8 = 2;

#[cfg(target_os = "linux")]
fn configure_linux_runtime() {
    let defaults = [
        ("WEBKIT_DISABLE_COMPOSITING_MODE", "1"),
        ("WEBKIT_DISABLE_DMABUF_RENDERER", "1"),
        ("GDK_BACKEND", "x11"),
    ];

    for (key, value) in defaults {
        if std::env::var_os(key).is_none() {
            std::env::set_var(key, value);
        }
    }
}

#[cfg(not(target_os = "linux"))]
fn configure_linux_runtime() {}

#[derive(Default)]
struct AppState {
    store_guard: Mutex<()>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct StoredServer {
    id: String,
    name: String,
    host: String,
    port: u16,
    added_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ClientPreferences {
    #[serde(default = "default_theme_string")]
    theme: String,
    #[serde(default)]
    theme_version: u8,
    #[serde(default)]
    theme_updated_at: String,
}

impl Default for ClientPreferences {
    fn default() -> Self {
        Self {
            theme: default_theme_string(),
            theme_version: THEME_STORAGE_VERSION,
            theme_updated_at: String::new(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
struct ClientStore {
    #[serde(default)]
    servers: Vec<StoredServer>,
    #[serde(default)]
    preferences: ClientPreferences,
}

#[derive(Debug, Serialize)]
struct ServerSummary {
    id: String,
    name: String,
    host: String,
    port: u16,
    added_at: String,
}

#[derive(Debug, Deserialize)]
struct SaveServerPayload {
    name: String,
    host: String,
    port: u16,
}

#[derive(Debug, Serialize)]
struct ConnectionResult {
    id: String,
    name: String,
    base_url: String,
}

#[derive(Debug, Deserialize)]
struct ApiCheckPayload {
    status: String,
    service: String,
}

fn default_theme_string() -> String {
    DEFAULT_THEME.to_string()
}

fn normalize_theme_id(value: &str) -> &'static str {
    match value {
        "light" => "light",
        "dark" => "dark",
        "graphite" => "graphite",
        "sage" => "sage",
        "north-sea" => "north-sea",
        _ => DEFAULT_THEME,
    }
}

fn normalize_store(store: &mut ClientStore) {
    if store.preferences.theme_version < THEME_STORAGE_VERSION && store.preferences.theme == "graphite" {
        store.preferences.theme = "dark".to_string();
    }
    store.preferences.theme = normalize_theme_id(&store.preferences.theme).to_string();
    store.preferences.theme_version = THEME_STORAGE_VERSION;
}

fn parse_store(raw: &str) -> Result<ClientStore, String> {
    let mut store: ClientStore =
        serde_json::from_str(raw).map_err(|error| format!("Invalid client server store: {error}"))?;
    normalize_store(&mut store);
    Ok(store)
}

#[tauri::command]
fn list_servers(_app: AppHandle, state: tauri::State<'_, AppState>) -> Result<Vec<ServerSummary>, String> {
    let _guard = state.store_guard.lock().map_err(|_| "Server store is busy.".to_string())?;
    let mut servers = read_store()?.servers;
    servers.sort_by(|left, right| right.added_at.cmp(&left.added_at));
    Ok(servers
        .into_iter()
        .map(|server| ServerSummary {
            id: server.id,
            name: server.name,
            host: server.host,
            port: server.port,
            added_at: server.added_at,
        })
        .collect())
}

#[tauri::command]
fn get_client_theme(_app: AppHandle, state: tauri::State<'_, AppState>) -> Result<String, String> {
    let _guard = state.store_guard.lock().map_err(|_| "Server store is busy.".to_string())?;
    Ok(read_store()?.preferences.theme)
}

#[tauri::command]
fn set_client_theme(_app: AppHandle, state: tauri::State<'_, AppState>, theme: String) -> Result<String, String> {
    let _guard = state.store_guard.lock().map_err(|_| "Server store is busy.".to_string())?;
    let mut store = read_store()?;
    store.preferences.theme = normalize_theme_id(&theme).to_string();
    store.preferences.theme_version = THEME_STORAGE_VERSION;
    store.preferences.theme_updated_at = now_iso();
    write_store(&store)?;
    Ok(store.preferences.theme)
}

#[tauri::command]
fn save_server(
    _app: AppHandle,
    state: tauri::State<'_, AppState>,
    payload: SaveServerPayload,
) -> Result<ServerSummary, String> {
    let _guard = state.store_guard.lock().map_err(|_| "Server store is busy.".to_string())?;
    validate_server_payload(&payload)?;

    let mut store = read_store()?;
    let normalized_host = payload.host.trim().to_lowercase();
    let duplicate = store
        .servers
        .iter()
        .any(|item| item.host.eq_ignore_ascii_case(&normalized_host) && item.port == payload.port);
    if duplicate {
        return Err("That host and port combination is already registered.".to_string());
    }

    let server = StoredServer {
        id: Uuid::new_v4().to_string(),
        name: payload.name.trim().to_string(),
        host: payload.host.trim().to_string(),
        port: payload.port,
        added_at: now_iso(),
    };

    store.servers.push(server.clone());
    write_store(&store)?;
    Ok(ServerSummary {
        id: server.id,
        name: server.name,
        host: server.host,
        port: server.port,
        added_at: server.added_at,
    })
}

#[tauri::command]
fn delete_server(_app: AppHandle, state: tauri::State<'_, AppState>, server_id: String) -> Result<(), String> {
    let _guard = state.store_guard.lock().map_err(|_| "Server store is busy.".to_string())?;
    let mut store = read_store()?;
    let previous_len = store.servers.len();
    store.servers.retain(|server| server.id != server_id);
    if previous_len == store.servers.len() {
        return Err("Server not found.".to_string());
    }
    write_store(&store)?;
    Ok(())
}

#[tauri::command]
async fn connect_to_server(
    app: AppHandle,
    state: tauri::State<'_, AppState>,
    server_id: String,
) -> Result<ConnectionResult, String> {
    let (server, theme, theme_updated_at) = {
        let _guard = state.store_guard.lock().map_err(|_| "Server store is busy.".to_string())?;
        let store = read_store()?;
        let server = store
            .servers
            .into_iter()
            .find(|item| item.id == server_id)
            .ok_or_else(|| "Server not found.".to_string())?;
        (server, store.preferences.theme, store.preferences.theme_updated_at)
    };

    let base_url = format!("{APP_SCHEME}://{}:{}", server.host, server.port);
    verify_remote_server(&base_url).await?;
    open_workspace_window(&app, &server, &base_url, &theme, &theme_updated_at)?;

    Ok(ConnectionResult {
        id: server.id,
        name: server.name,
        base_url,
    })
}

fn open_workspace_window(
    app: &AppHandle,
    server: &StoredServer,
    base_url: &str,
    theme: &str,
    theme_updated_at: &str,
) -> Result<(), String> {
    if let Some(existing) = app.get_webview_window("workspace") {
        let _ = existing.destroy();
    }

    let selector = app
        .get_webview_window("main")
        .ok_or_else(|| "The selector window is not available.".to_string())?;
    selector.hide().map_err(|error| error.to_string())?;

    let target_url = Url::parse(&format!("{base_url}/home")).map_err(|error| error.to_string())?;
    let profile_path = webview_profile_path(server)?;
    fs::create_dir_all(&profile_path).map_err(|error| error.to_string())?;

    let selector_for_close = selector.clone();
    let init_script = workspace_theme_init_script(theme, theme_updated_at).map_err(|error| error.to_string())?;

    let workspace_builder = WebviewWindowBuilder::new(app, "workspace", WebviewUrl::External(target_url))
        .title(&format!("Zertan | {}", server.name))
        .center()
        .inner_size(1360.0, 900.0)
        .data_directory(profile_path)
        .initialization_script(&init_script);

    let workspace = match workspace_builder.build() {
        Ok(window) => window,
        Err(error) => {
            let _ = selector.show();
            return Err(error.to_string());
        }
    };

    workspace.on_window_event(move |event| {
        if matches!(event, WindowEvent::Destroyed) {
            let _ = selector_for_close.show();
            let _ = selector_for_close.set_focus();
        }
    });

    workspace.show().map_err(|error| error.to_string())?;
    workspace.set_focus().map_err(|error| error.to_string())?;
    Ok(())
}

fn workspace_theme_init_script(theme: &str, theme_updated_at: &str) -> Result<String, serde_json::Error> {
    let theme_json = serde_json::to_string(normalize_theme_id(theme))?;
    let theme_updated_at_json = serde_json::to_string(theme_updated_at.trim())?;
    Ok(format!(
        r#"
            (() => {{
                const storageKey = "zertan.theme";
                const migrationKey = "zertan.theme.version";
                const updatedAtKey = "zertan.theme.updated_at";
                const migrationVersion = "{THEME_STORAGE_VERSION}";
                const validThemes = new Set(["light", "dark", "graphite", "sage", "north-sea"]);
                const nativeTheme = validThemes.has({theme_json}) ? {theme_json} : "light";
                const nativeUpdatedAt = typeof {theme_updated_at_json} === "string" ? {theme_updated_at_json}.trim() : "";

                let resolvedTheme = nativeTheme;
                let resolvedUpdatedAt = nativeUpdatedAt;

                try {{
                    const storedVersion = window.localStorage.getItem(migrationKey);
                    const storedTheme = window.localStorage.getItem(storageKey);
                    const storedUpdatedAt = (window.localStorage.getItem(updatedAtKey) || "").trim();
                    const migratedStoredTheme =
                        storedVersion !== migrationVersion && storedTheme === "graphite"
                            ? "dark"
                            : (validThemes.has(storedTheme) ? storedTheme : "");

                    if (migratedStoredTheme) {{
                        if (storedUpdatedAt && nativeUpdatedAt) {{
                            resolvedTheme = storedUpdatedAt >= nativeUpdatedAt ? migratedStoredTheme : nativeTheme;
                            resolvedUpdatedAt = storedUpdatedAt >= nativeUpdatedAt ? storedUpdatedAt : nativeUpdatedAt;
                        }} else if (storedUpdatedAt) {{
                            resolvedTheme = migratedStoredTheme;
                            resolvedUpdatedAt = storedUpdatedAt;
                        }}
                    }}
                }} catch (_error) {{}}

                if (!resolvedUpdatedAt) {{
                    resolvedUpdatedAt = new Date().toISOString();
                }}

                window.__ZERTAN_TAURI_THEME = resolvedTheme;
                window.__ZERTAN_TAURI_THEME_UPDATED_AT = resolvedUpdatedAt;
                window.__ZERTAN_TAURI_THEME_BRIDGE__ = {{
                    getThemeState() {{
                        return {{
                            theme: window.__ZERTAN_TAURI_THEME,
                            updatedAt: window.__ZERTAN_TAURI_THEME_UPDATED_AT || ""
                        }};
                    }},
                    async setTheme(nextTheme) {{
                        const normalizedTheme = validThemes.has(nextTheme) ? nextTheme : "light";
                        const nextUpdatedAt = new Date().toISOString();

                        if (typeof window.__TAURI__?.core?.invoke === "function") {{
                            const persistedTheme = await window.__TAURI__.core.invoke("set_client_theme", {{
                                theme: normalizedTheme
                            }});
                            window.__ZERTAN_TAURI_THEME = validThemes.has(persistedTheme) ? persistedTheme : normalizedTheme;
                            window.__ZERTAN_TAURI_THEME_UPDATED_AT = nextUpdatedAt;
                        }} else {{
                            window.__ZERTAN_TAURI_THEME = normalizedTheme;
                            window.__ZERTAN_TAURI_THEME_UPDATED_AT = nextUpdatedAt;
                        }}

                        try {{
                            document.documentElement.dataset.theme = window.__ZERTAN_TAURI_THEME;
                            window.localStorage.setItem(storageKey, window.__ZERTAN_TAURI_THEME);
                            window.localStorage.setItem(migrationKey, migrationVersion);
                            window.localStorage.setItem(updatedAtKey, window.__ZERTAN_TAURI_THEME_UPDATED_AT);
                        }} catch (_error) {{}}

                        return {{
                            theme: window.__ZERTAN_TAURI_THEME,
                            updatedAt: window.__ZERTAN_TAURI_THEME_UPDATED_AT
                        }};
                    }}
                }};

                try {{
                    document.documentElement.dataset.theme = window.__ZERTAN_TAURI_THEME;
                    window.localStorage.setItem(storageKey, window.__ZERTAN_TAURI_THEME);
                    window.localStorage.setItem(migrationKey, migrationVersion);
                    window.localStorage.setItem(updatedAtKey, window.__ZERTAN_TAURI_THEME_UPDATED_AT);
                }} catch (_error) {{}}
            }})();
        "#
    ))
}

async fn verify_remote_server(base_url: &str) -> Result<(), String> {
    let client = Client::builder()
        .timeout(std::time::Duration::from_secs(4))
        .build()
        .map_err(|error| error.to_string())?;
    let response = client
        .get(format!("{base_url}/api/check"))
        .send()
        .await
        .map_err(|error| format!("Could not reach {base_url}: {error}"))?;

    if !response.status().is_success() {
        return Err(format!("{base_url} answered with HTTP {}.", response.status()));
    }

    let payload: ApiCheckPayload = response
        .json()
        .await
        .map_err(|error| format!("Unexpected health response from {base_url}: {error}"))?;
    if payload.status != "ok" || payload.service != "zertan" {
        return Err(format!("{base_url} is reachable, but it does not identify as Zertan."));
    }

    Ok(())
}

fn validate_server_payload(payload: &SaveServerPayload) -> Result<(), String> {
    if payload.name.trim().is_empty() {
        return Err("Server name is required.".to_string());
    }
    if payload.host.trim().is_empty() {
        return Err("IP or DNS is required.".to_string());
    }
    if payload.port == 0 {
        return Err("Port must be between 1 and 65535.".to_string());
    }
    Ok(())
}

fn read_store() -> Result<ClientStore, String> {
    let path = store_path()?;
    read_store_from_path(&path)
}

fn read_store_from_path(path: &Path) -> Result<ClientStore, String> {
    if !path.exists() {
        return Ok(ClientStore::default());
    }
    let raw = fs::read_to_string(path).map_err(|error| error.to_string())?;
    parse_store(&raw)
}

fn write_store(store: &ClientStore) -> Result<(), String> {
    let path = store_path()?;
    write_store_to_path(&path, store)
}

fn write_store_to_path(path: &Path, store: &ClientStore) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    let payload = serde_json::to_string_pretty(store).map_err(|error| error.to_string())?;
    fs::write(path, payload).map_err(|error| error.to_string())
}

fn webview_profile_path(server: &StoredServer) -> Result<PathBuf, String> {
    Ok(data_root()?.join("profiles").join(&server.id))
}

fn store_path() -> Result<PathBuf, String> {
    Ok(data_root()?.join("servers.json"))
}

fn data_root() -> Result<PathBuf, String> {
    ProjectDirs::from("local", "Zertan", "ZertanClient")
        .map(|dirs| dirs.data_local_dir().to_path_buf())
        .ok_or_else(|| "Could not resolve the Zertan Client data directory.".to_string())
}

fn now_iso() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Secs, true)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    configure_linux_runtime();

    tauri::Builder::default()
        .manage(AppState::default())
        .invoke_handler(tauri::generate_handler![
            list_servers,
            get_client_theme,
            set_client_theme,
            save_server,
            delete_server,
            connect_to_server
        ])
        .run(tauri::generate_context!())
        .expect("error while running Zertan Client");
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_store_path(name: &str) -> PathBuf {
        std::env::temp_dir().join(format!("zertan-client-store-{name}-{}.json", Uuid::new_v4()))
    }

    fn sample_server() -> StoredServer {
        StoredServer {
            id: "server-1".to_string(),
            name: "Local".to_string(),
            host: "127.0.0.1".to_string(),
            port: 5050,
            added_at: "2026-03-31T10:00:00Z".to_string(),
        }
    }

    #[test]
    fn parse_store_supports_legacy_payload_without_preferences() {
        let store = parse_store(
            r#"{
                "servers": [
                    {
                        "id": "server-1",
                        "name": "Local",
                        "host": "127.0.0.1",
                        "port": 5050,
                        "added_at": "2026-03-31T10:00:00Z"
                    }
                ]
            }"#,
        )
        .expect("legacy store should deserialize");

        assert_eq!(store.servers.len(), 1);
        assert_eq!(store.preferences.theme, "light");
        assert_eq!(store.preferences.theme_version, THEME_STORAGE_VERSION);
        assert_equal_maybe_empty(&store.preferences.theme_updated_at);
    }

    #[test]
    fn parse_store_falls_back_when_theme_is_invalid() {
        let store = parse_store(
            r#"{
                "servers": [],
                "preferences": {
                    "theme": "midnight"
                }
            }"#,
        )
        .expect("store should deserialize");

        assert_eq!(store.preferences.theme, "light");
        assert_eq!(store.preferences.theme_version, THEME_STORAGE_VERSION);
        assert_equal_maybe_empty(&store.preferences.theme_updated_at);
    }

    #[test]
    fn parse_store_migrates_legacy_graphite_theme_to_dark() {
        let store = parse_store(
            r#"{
                "servers": [],
                "preferences": {
                    "theme": "graphite"
                }
            }"#,
        )
        .expect("store should deserialize");

        assert_eq!(store.preferences.theme, "dark");
        assert_eq!(store.preferences.theme_version, THEME_STORAGE_VERSION);
        assert_equal_maybe_empty(&store.preferences.theme_updated_at);
    }

    #[test]
    fn write_and_read_store_preserves_theme_and_servers() {
        let path = temp_store_path("theme");
        let store = ClientStore {
            servers: vec![sample_server()],
            preferences: ClientPreferences {
                theme: "graphite".to_string(),
                theme_version: THEME_STORAGE_VERSION,
                theme_updated_at: "2026-03-31T11:00:00Z".to_string(),
            },
        };

        write_store_to_path(&path, &store).expect("store should write");
        let reloaded = read_store_from_path(&path).expect("store should reload");

        assert_eq!(reloaded.preferences.theme, "graphite");
        assert_eq!(reloaded.servers.len(), 1);
        assert_eq!(reloaded.preferences.theme_updated_at, "2026-03-31T11:00:00Z");

        let _ = fs::remove_file(path);
    }

    #[test]
    fn workspace_init_script_injects_normalized_theme() {
        let script = workspace_theme_init_script("dark", "2026-03-31T11:00:00Z").expect("script should build");
        assert!(script.contains("\"dark\""));
        assert!(script.contains("__ZERTAN_TAURI_THEME_BRIDGE__"));
        assert!(script.contains("zertan.theme.updated_at"));

        let graphite_script =
            workspace_theme_init_script("graphite", "2026-03-31T11:00:00Z").expect("graphite script should build");
        assert!(graphite_script.contains("\"graphite\""));
        assert!(graphite_script.contains("zertan.theme.version"));

        let fallback_script =
            workspace_theme_init_script("unknown", "").expect("fallback script should build");
        assert!(fallback_script.contains("\"light\""));
    }

    fn assert_equal_maybe_empty(value: &str) {
        assert!(value.is_empty() || value.contains('T'));
    }
}
