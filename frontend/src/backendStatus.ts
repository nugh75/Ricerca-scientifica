import { listen } from "@tauri-apps/api/event";

export function subscribeToBackendStatus(onDown: () => void, onCrashed: () => void): void {
  listen("backend-down", () => onDown());
  listen("backend-crashed", () => onCrashed());
}
