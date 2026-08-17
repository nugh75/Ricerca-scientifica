const KEY = "litreview_first_run_done";

export function isFirstRunDone(): boolean {
  return localStorage.getItem(KEY) === "1";
}

export function markFirstRunDone(): void {
  localStorage.setItem(KEY, "1");
}
