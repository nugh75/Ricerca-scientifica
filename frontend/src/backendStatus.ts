import { listen } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/core";

export function subscribeToBackendStatus(onDown: () => void, onCrashed: () => void): void {
  listen("backend-down", () => onDown()).catch(() => {});
  listen("backend-crashed", () => onCrashed()).catch(() => {});
}

export function subscribeToBackendPort(onPort: (port: number) => void): void {
  listen<number>("backend-ready", (event) => onPort(event.payload)).catch(() => {});
}

// The backend can announce its port before the webview subscribes, so ask for
// it directly as well instead of waiting for an event that already fired.
export async function fetchBackendPort(): Promise<number | null> {
  try {
    return (await invoke<number | null>("backend_port")) ?? null;
  } catch {
    return null;
  }
}
