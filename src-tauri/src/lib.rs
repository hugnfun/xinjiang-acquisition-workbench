// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
use tauri::Manager;

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run(sidecar_port: u16) {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(move |app| {
            // Inject the sidecar port into the frontend as a window global so the
            // React api client (`src/api/client.ts`) can talk to the sidecar this
            // Rust process spawned. The port is a free port we bound and passed to
            // the sidecar via `--port`.
            #[cfg(debug_assertions)]
            {
                if let Some(main_window) = app.get_webview_window("main") {
                    let _ = main_window.eval(&format!(
                        "window.__SIDECAR_PORT__ = {};",
                        sidecar_port
                    ));
                }
            }
            #[cfg(not(debug_assertions))]
            {
                let _ = (app, sidecar_port);
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![greet])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
