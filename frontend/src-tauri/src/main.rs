use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use tauri::{Emitter, Manager, RunEvent};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

#[derive(Default)]
struct BackendProcess(Mutex<Option<CommandChild>>);

struct RestartCount(Mutex<u8>);

struct ShuttingDown(AtomicBool);

/// Port the backend announced on stdout, once it is known.
#[derive(Default)]
struct BackendPort(Mutex<Option<u16>>);

/// Set when the sidecar reused a backend that was already running: it exits
/// right after announcing, and that exit is expected rather than a crash.
struct ExternalBackend(AtomicBool);

fn handle_backend_line(app: &tauri::AppHandle, line: &str) {
    if let Some(value) = line.strip_prefix("LITREVIEW_REUSED=") {
        app.state::<ExternalBackend>()
            .0
            .store(value.trim() == "1", Ordering::SeqCst);
    } else if let Some(value) = line.strip_prefix("LITREVIEW_PORT=") {
        if let Ok(port) = value.trim().parse::<u16>() {
            *app.state::<BackendPort>().0.lock().unwrap() = Some(port);
            app.emit("backend-ready", port).ok();
        }
    }
}

fn spawn_backend(app: tauri::AppHandle) {
    let sidecar = app
        .shell()
        .sidecar("litreview-backend")
        .expect("litreview-backend sidecar binary not bundled")
        .env("LITREVIEW_NO_BROWSER", "1");
    let (mut rx, child) = sidecar.spawn().expect("failed to spawn litreview-backend");

    *app.state::<BackendProcess>().0.lock().unwrap() = Some(child);

    let app_for_events = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    for line in String::from_utf8_lossy(&bytes).lines() {
                        handle_backend_line(&app_for_events, line);
                    }
                }
                CommandEvent::Terminated(_) => {
                    if app_for_events.state::<ShuttingDown>().0.load(Ordering::SeqCst) {
                        break;
                    }
                    // the backend we talk to is another process: this exit is the
                    // sidecar stepping aside, not the server going down
                    if app_for_events.state::<ExternalBackend>().0.load(Ordering::SeqCst) {
                        break;
                    }
                    app_for_events.emit("backend-down", ()).ok();
                    let restarts = app_for_events.state::<RestartCount>();
                    let mut count = restarts.0.lock().unwrap();
                    if *count == 0 {
                        *count += 1;
                        drop(count);
                        spawn_backend(app_for_events.clone());
                    } else {
                        app_for_events.emit("backend-crashed", ()).ok();
                    }
                    break;
                }
                _ => {}
            }
        }
    });
}

/// Lets the webview ask for the port directly: the announcement can land before
/// the frontend has subscribed to the event.
#[tauri::command]
fn backend_port(state: tauri::State<'_, BackendPort>) -> Option<u16> {
    *state.0.lock().unwrap()
}

#[tauri::command]
fn write_export(path: String, content: String) -> Result<(), String> {
    std::fs::write(path, content).map_err(|e| e.to_string())
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(BackendProcess::default())
        .manage(RestartCount(Mutex::new(0)))
        .manage(ShuttingDown(AtomicBool::new(false)))
        .manage(BackendPort::default())
        .manage(ExternalBackend(AtomicBool::new(false)))
        .invoke_handler(tauri::generate_handler![write_export, backend_port])
        .setup(|app| {
            spawn_backend(app.handle().clone());
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app_handle, event| {
        if let RunEvent::ExitRequested { .. } = event {
            app_handle.state::<ShuttingDown>().0.store(true, Ordering::SeqCst);
            if let Some(child) = app_handle.state::<BackendProcess>().0.lock().unwrap().take() {
                let _ = child.kill();
            }
        }
    });
}
