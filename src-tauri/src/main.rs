// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::process::{Command, Stdio};

/// Walk up from the current working directory (and from the executable's
/// directory) looking for a folder that contains *both* `.venv/bin/python` and
/// `sidecar/` — that's the project root. Returns `None` if no such ancestor
/// exists (the caller then falls back to `current_dir`).
fn find_project_root() -> Option<PathBuf> {
    let mut candidates: Vec<PathBuf> = Vec::new();
    // 环境变量优先（方便多机器/不同路径），其次硬编码本机路径（release .app
    // 双击启动时 cwd 是 /，walk-up 找不到项目，需要兜底）
    if let Ok(root) = std::env::var("WORKBENCH_PROJECT_ROOT") {
        let p = PathBuf::from(&root);
        if p.join(".venv/bin/python").exists() && p.join("sidecar").is_dir() {
            return Some(p);
        }
    }
    const FALLBACK: &str = "/Users/aicer/Documents/Project/xinjiang-acquisition-workbench";
    let fallback = PathBuf::from(FALLBACK);
    if fallback.join(".venv/bin/python").exists() && fallback.join("sidecar").is_dir() {
        candidates.push(fallback);
    }
    if let Ok(cwd) = std::env::current_dir() {
        candidates.push(cwd);
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            candidates.push(parent.to_path_buf());
        }
    }
    for start in candidates {
        let mut dir: Option<&std::path::Path> = Some(&start);
        while let Some(d) = dir {
            if d.join(".venv/bin/python").exists() && d.join("sidecar").is_dir() {
                return Some(d.to_path_buf());
            }
            dir = d.parent();
        }
    }
    None
}

/// Resolve the python interpreter for the sidecar and the project root to run
/// it from.
///
/// INTEGRATION BUG #1 FIX: the brief defaulted to the global `python3`, but the
/// global `python3` cannot import `sidecar` (it's only installed in `.venv`,
/// and the global interpreter also has a pydantic arch mismatch). Only
/// `.venv/bin/python` works. So: `SIDECAR_PY` env override wins; otherwise we
/// prefer `<project_root>/.venv/bin/python` and only fall back to `python3` if
/// that path is missing.
fn resolve_python() -> (String, PathBuf) {
    let project_root = find_project_root()
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")));
    let py = if let Ok(py) = std::env::var("SIDECAR_PY") {
        py
    } else {
        let candidate = project_root.join(".venv/bin/python");
        if candidate.exists() {
            candidate.to_string_lossy().into_owned()
        } else {
            // DO NOT fall back to global `python3` — the global interpreter's
            // `sidecar` install is stale/unsynced (it kept serving an Anthropic
            // build after we switched to DeepSeek), so a silent fallback
            // produces a working-looking but WRONG sidecar. Fail loudly instead.
            panic!(
                "未找到 .venv/bin/python (在 {})。请先 `python3 -m venv .venv && .venv/bin/pip install -e .[dev]`，或设 SIDECAR_PY 环境变量。",
                project_root.display()
            );
        }
    };
    (py, project_root)
}

/// Bind a free loopback port, spawn the python sidecar with that port, and
/// return the port AND the child handle.
///
/// INTEGRATION BUG #2 FIX: the brief read the sidecar's stdout to discover the
/// port — but we already bound a free port (`TcpListener::bind("127.0.0.1:0")`)
/// and passed it via `--port`, so reading stdout is redundant and the
/// `BufReader` loop risks blocking. Instead: stdout → `Stdio::null()` (we
/// don't need it), stderr → `Stdio::inherit()` (so sidecar errors are visible
/// in the terminal), return the bound port and the Child. No stdout reading.
///
/// KILL-ON-EXIT FIX: previously `std::mem::forget(child)` orphaned the python
/// sidecar (the process kept running after the Tauri app exited). Now we RETURN
/// the Child so the caller can retain it and `.kill()` it on app exit.
fn spawn_sidecar() -> (u16, std::process::Child) {
    let listener = std::net::TcpListener::bind("127.0.0.1:0")
        .expect("failed to bind free port for sidecar");
    let port = listener.local_addr().unwrap().port();
    drop(listener);

    let (py, project_root) = resolve_python();
    let module = std::env::var("SIDECAR_MODULE").unwrap_or_else(|_| "sidecar.app".to_string());

    let child = Command::new(&py)
        .arg("-m")
        .arg(&module)
        .arg("--port")
        .arg(port.to_string())
        .current_dir(&project_root)
        .stdout(Stdio::null())
        .stderr(Stdio::inherit())
        .spawn()
        .expect("failed to spawn sidecar");

    (port, child)
}

fn main() {
    let (port, child) = spawn_sidecar();
    eprintln!("[tauri] sidecar spawned on port {port}, pid {}", child.id());
    tauri_app_lib::run(port, child);
}
