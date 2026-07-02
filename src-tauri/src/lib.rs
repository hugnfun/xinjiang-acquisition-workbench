// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
use std::sync::Mutex;
use tauri::Manager;

/// Held in Tauri app state so the python sidecar can be killed on app exit.
/// `Option` so the exit handler can `take()` it (kill+wait once, idempotent).
struct SidecarChild(Mutex<Option<std::process::Child>>);

/// The port the sidecar listens on. Frontend pulls it via `invoke("get_sidecar_port")`
/// BEFORE its first fetch — more reliable than the `eval`-injection race (which
/// fired in setup() before the webview's JS had loaded, leaving
/// `window.__SIDECAR_PORT__` undefined and forcing the 8765 fallback → "Load failed").
struct SidecarPort(u16);

/// Tauri command: frontend calls this to learn which port the sidecar is on.
/// Returns the port the Rust process bound and passed to the sidecar via --port.
#[tauri::command]
fn get_sidecar_port(state: tauri::State<SidecarPort>) -> u16 {
    state.0
}

#[cfg(unix)]
mod posix_signal {
    //! SIGTERM/SIGINT → kill the sidecar.
    //!
    //! `RunEvent::ExitRequested` only fires on a GRACEFUL exit (window close /
    //! programmatic quit); a raw SIGTERM/SIGINT (Ctrl+C, `kill <pid>`) bypasses
    //! the Tauri event loop and would orphan the sidecar. This handler runs in
    //! the signal context, `kill(pid, SIGKILL)`s the sidecar directly (a single
    //! async-signal-safe syscall), then restores the default disposition and
    //! re-raises so the process still dies normally. No external crate needed.
    use std::os::raw::c_int;
    use std::sync::atomic::{AtomicI32, Ordering};

    static SIDECAR_PID: AtomicI32 = AtomicI32::new(0);

    extern "C" {
        fn signal(signum: c_int, handler: usize) -> usize;
        fn kill(pid: c_int, sig: c_int) -> c_int;
        fn raise(sig: c_int) -> c_int;
    }
    const SIG_DFL: usize = 0;
    const SIGINT: c_int = 2;
    const SIGTERM: c_int = 15;
    const SIGKILL: c_int = 9;

    extern "C" fn on_signal(sig: c_int) {
        let pid = SIDECAR_PID.load(Ordering::Relaxed);
        if pid > 0 {
            // async-signal-safe: a single kill(2) syscall
            unsafe { kill(pid, SIGKILL); }
        }
        unsafe {
            // restore default disposition and re-raise so the process exits
            signal(sig, SIG_DFL);
            raise(sig);
        }
    }

    pub fn install(child_pid: u32) {
        SIDECAR_PID.store(child_pid as i32, Ordering::SeqCst);
        unsafe {
            signal(SIGINT, on_signal as *const () as usize);
            signal(SIGTERM, on_signal as *const () as usize);
        }
    }
}

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run(sidecar_port: u16, child: std::process::Child) {
    // Install the SIGTERM/SIGINT handler so the sidecar is killed even when the
    // app is terminated by a signal (not just a graceful window close).
    #[cfg(unix)]
    posix_signal::install(child.id());

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(SidecarChild(Mutex::new(Some(child))))
        .manage(SidecarPort(sidecar_port))
        .setup(move |_app| {
            // Port injection is now pull-based: the frontend invokes
            // `get_sidecar_port` before its first fetch (see src/api/client.ts),
            // which reads SidecarPort from app state. No eval race.
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![greet, get_sidecar_port])
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app_handle, event| {
        if let tauri::RunEvent::ExitRequested { .. } = event {
            // Graceful exit: kill + reap the sidecar so it doesn't outlive the app.
            if let Some(state) = app_handle.try_state::<SidecarChild>() {
                if let Ok(mut guard) = state.0.lock() {
                    if let Some(mut child) = guard.take() {
                        let _ = child.kill();
                        let _ = child.wait();
                    }
                }
            }
        }
    });
}
