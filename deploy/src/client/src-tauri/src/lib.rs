use std::{
    fs,
    path::PathBuf,
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
struct ServerStore {
    servers: Vec<StoredServer>,
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
    let server = {
        let _guard = state.store_guard.lock().map_err(|_| "Server store is busy.".to_string())?;
        let store = read_store()?;
        store
            .servers
            .into_iter()
            .find(|item| item.id == server_id)
            .ok_or_else(|| "Server not found.".to_string())?
    };

    let base_url = format!("{APP_SCHEME}://{}:{}", server.host, server.port);
    verify_remote_server(&base_url).await?;
    open_workspace_window(&app, &server, &base_url)?;

    Ok(ConnectionResult {
        id: server.id,
        name: server.name,
        base_url,
    })
}

fn open_workspace_window(app: &AppHandle, server: &StoredServer, base_url: &str) -> Result<(), String> {
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

    let workspace_builder = WebviewWindowBuilder::new(app, "workspace", WebviewUrl::External(target_url))
        .title(&format!("Zertan | {}", server.name))
        .center()
        .inner_size(1360.0, 900.0)
        .min_inner_size(1100.0, 720.0)
        .data_directory(profile_path);

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

fn read_store() -> Result<ServerStore, String> {
    let path = store_path()?;
    if !path.exists() {
        return Ok(ServerStore { servers: Vec::new() });
    }
    let raw = fs::read_to_string(path).map_err(|error| error.to_string())?;
    serde_json::from_str(&raw).map_err(|error| format!("Invalid client server store: {error}"))
}

fn write_store(store: &ServerStore) -> Result<(), String> {
    let path = store_path()?;
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
            save_server,
            delete_server,
            connect_to_server
        ])
        .run(tauri::generate_context!())
        .expect("error while running Zertan Client");
}
