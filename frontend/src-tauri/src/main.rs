use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use tauri::{Emitter, Manager, RunEvent};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

#[derive(Default)]
struct BackendProcess(Mutex<Option<CommandChild>>);

struct RestartCount(Mutex<u8>);

struct ShuttingDown(AtomicBool);

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
            if let CommandEvent::Terminated(_) = event {
                if app_for_events.state::<ShuttingDown>().0.load(Ordering::SeqCst) {
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
        }
    });
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
        .invoke_handler(tauri::generate_handler![write_export])
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
