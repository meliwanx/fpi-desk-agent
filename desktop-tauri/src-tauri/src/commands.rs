//! Tauri command handlers — the IPC bridge between frontend and Rust.

use serde::Serialize;
use sha2::{Digest, Sha256};
use tauri::{AppHandle, Emitter, WebviewWindow};
use tauri_plugin_opener::OpenerExt;
use tokio::io::AsyncWriteExt;

use crate::{backend::BackendState, tray, PendingNavigationState};

/// Get the backend URL (http://127.0.0.1:{port}).
#[tauri::command]
pub async fn get_backend_url(state: tauri::State<'_, BackendState>) -> Result<String, String> {
    Ok(state.url().await)
}

/// Get the backend's per-run session bearer token. The token is read
/// from a 0600 file the backend writes on startup, so another local
/// user on the same host cannot obtain it. The frontend attaches it
/// as `Authorization: Bearer ...` on every API request and as a
/// `?token=` query param on EventSource streams (which cannot set
/// custom headers). Never log this value.
#[tauri::command]
pub async fn get_backend_token(state: tauri::State<'_, BackendState>) -> Result<String, String> {
    state.token().await
}

#[tauri::command]
pub async fn get_pending_navigation(
    state: tauri::State<'_, PendingNavigationState>,
) -> Result<Option<String>, String> {
    Ok(state.take().await)
}

/// Minimize the window.
#[tauri::command]
pub fn window_minimize(window: WebviewWindow) -> Result<(), String> {
    window.minimize().map_err(|e| e.to_string())
}

/// Toggle maximize/unmaximize.
#[tauri::command]
pub fn window_maximize(window: WebviewWindow) -> Result<(), String> {
    if window.is_maximized().unwrap_or(false) {
        window.unmaximize().map_err(|e| e.to_string())
    } else {
        window.maximize().map_err(|e| e.to_string())
    }
}

/// Close the window (hides to tray/dock on all platforms).
#[tauri::command]
pub fn window_close(window: WebviewWindow) -> Result<(), String> {
    window.hide().map_err(|e| e.to_string())
}

/// Check if window is maximized.
#[tauri::command]
pub fn is_maximized(window: WebviewWindow) -> Result<bool, String> {
    window.is_maximized().map_err(|e| e.to_string())
}

/// Get the current platform.
#[tauri::command]
pub fn get_platform() -> String {
    std::env::consts::OS.to_string()
}

/// Open a URL in the system default browser.
#[tauri::command]
pub fn open_external(app: AppHandle, url: String) -> Result<(), String> {
    app.opener()
        .open_url(url, None::<&str>)
        .map_err(|e| e.to_string())
}

/// Save a file via a native save dialog.
///
/// Accepts either a `url` (fetched via GET) or raw `data` bytes.
/// WebView2 does not support blob-URL downloads triggered by `<a>.click()`,
/// so we handle file exports through Tauri IPC instead.
#[tauri::command]
pub async fn download_and_save(
    app: AppHandle,
    url: Option<String>,
    data: Option<Vec<u8>>,
    default_name: String,
    default_directory: Option<String>,
) -> Result<bool, String> {
    use tauri_plugin_dialog::DialogExt;

    // Derive filter label + extension from the default filename
    let ext = default_name.rsplit('.').next().unwrap_or("*").to_string();
    let label = ext.to_uppercase();

    // Show native save dialog. When exporting a generated workspace file,
    // start in that file's directory so the default save location stays
    // close to the active workspace instead of the OS downloads folder.
    let (tx, rx) = tokio::sync::oneshot::channel();
    let mut dialog = app
        .dialog()
        .file()
        .set_file_name(&default_name)
        .add_filter(&label, &[&ext]);
    if let Some(default_directory) = default_directory
        .as_deref()
        .filter(|s| !s.trim().is_empty())
    {
        let directory = std::path::Path::new(default_directory);
        if directory.is_dir() {
            dialog = dialog.set_directory(directory);
        }
    }
    dialog.save_file(move |path| {
        let _ = tx.send(path);
    });

    let file_path = rx.await.map_err(|e| format!("Dialog error: {e}"))?;
    let path = match file_path {
        Some(p) => p,
        None => return Ok(false), // User cancelled
    };

    let real_path = path
        .as_path()
        .ok_or_else(|| "Invalid save path".to_string())?;

    // Get bytes: from provided data or by downloading from URL
    let bytes = if let Some(raw) = data {
        raw
    } else if let Some(download_url) = url {
        let response = reqwest::get(&download_url)
            .await
            .map_err(|e| format!("Download failed: {e}"))?;
        response
            .bytes()
            .await
            .map_err(|e| format!("Failed to read response: {e}"))?
            .to_vec()
    } else {
        return Err("Either 'url' or 'data' must be provided".into());
    };

    tokio::fs::write(real_path, &bytes)
        .await
        .map_err(|e| format!("Failed to write file: {e}"))?;

    Ok(true)
}

fn safe_download_name(default_name: &str) -> String {
    let last_segment = default_name
        .trim()
        .rsplit(['/', '\\'])
        .next()
        .unwrap_or("")
        .chars()
        .map(|ch| {
            if ch.is_control() || matches!(ch, ':' | '*' | '?' | '"' | '<' | '>' | '|') {
                '_'
            } else {
                ch
            }
        })
        .collect::<String>();
    let trimmed = last_segment
        .trim_matches(|ch| ch == '.' || ch == ' ')
        .trim();
    if trimmed.is_empty() {
        "fpi-agent-update.bin".to_string()
    } else {
        trimmed.to_string()
    }
}

#[derive(Clone, Serialize)]
struct UpdateDownloadProgress {
    downloaded: u64,
    total: Option<u64>,
    progress: u8,
}

fn emit_update_download_progress(
    app: &AppHandle,
    downloaded: u64,
    total: Option<u64>,
) -> Result<(), String> {
    let progress = total
        .filter(|value| *value > 0)
        .map(|value| ((downloaded.saturating_mul(100) / value).min(100)) as u8)
        .unwrap_or(0);
    app.emit(
        "update-download-progress",
        UpdateDownloadProgress {
            downloaded,
            total,
            progress,
        },
    )
    .map_err(|e| e.to_string())
}

fn open_update_package(app: &AppHandle, file_path: &std::path::Path) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        let _ = app;
        std::process::Command::new(&file_path)
            .arg("/S")
            .spawn()
            .map_err(|e| format!("Failed to start silent installer: {e}"))?;
        return Ok(());
    }

    #[cfg(not(target_os = "windows"))]
    {
        app.opener()
            .open_path(file_path.to_string_lossy().to_string(), None::<&str>)
            .map_err(|e| format!("Failed to open update package: {e}"))
    }
}

/// Download an update package inside the app flow and open it with the OS installer.
#[tauri::command]
pub async fn download_update_and_open(
    app: AppHandle,
    url: String,
    default_name: String,
    expected_sha256: Option<String>,
) -> Result<String, String> {
    let mut response = reqwest::get(&url)
        .await
        .map_err(|e| format!("Download failed: {e}"))?;
    let status = response.status();
    if !status.is_success() {
        return Err(format!("Download failed with status {status}"));
    }

    let update_dir = std::env::temp_dir().join("fpi-agent-updates");
    tokio::fs::create_dir_all(&update_dir)
        .await
        .map_err(|e| format!("Failed to create update directory: {e}"))?;
    let file_path = update_dir.join(safe_download_name(&default_name));
    let mut file = tokio::fs::File::create(&file_path)
        .await
        .map_err(|e| format!("Failed to create update package: {e}"))?;
    let total = response.content_length();
    let mut downloaded = 0_u64;
    let mut hasher = Sha256::new();
    emit_update_download_progress(&app, downloaded, total)?;

    while let Some(chunk) = response
        .chunk()
        .await
        .map_err(|e| format!("Download stream failed: {e}"))?
    {
        file.write_all(&chunk)
            .await
            .map_err(|e| format!("Failed to write update package: {e}"))?;
        hasher.update(&chunk);
        downloaded = downloaded.saturating_add(chunk.len() as u64);
        emit_update_download_progress(&app, downloaded, total)?;
    }
    file.flush()
        .await
        .map_err(|e| format!("Failed to flush update package: {e}"))?;

    let actual_sha256 = format!("{:x}", hasher.finalize());
    if let Some(expected) = expected_sha256
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
    {
        if !actual_sha256.eq_ignore_ascii_case(expected) {
            let _ = tokio::fs::remove_file(&file_path).await;
            return Err(format!(
                "Update package hash mismatch: expected {expected}, got {actual_sha256}"
            ));
        }
    }

    let path_string = file_path.to_string_lossy().to_string();
    open_update_package(&app, &file_path)?;
    Ok(path_string)
}

/// Replace the tray's recent chat list with the given sessions (top first).
#[tauri::command]
pub fn update_tray_recents(app: AppHandle, recents: Vec<tray::TrayRecent>) -> Result<(), String> {
    tray::set_tray_recents(&app, &recents).map_err(|e| e.to_string())
}
