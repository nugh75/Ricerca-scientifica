import { registerRoute } from "../router";
import { listKeys, KNOWN_KEYS } from "../api";
import { renderKeyField } from "./keyField";
import { escapeHtml } from "../helpers";

registerRoute("/settings", async () => {
  const outlet = document.querySelector<HTMLElement>("#outlet")!;
  outlet.innerHTML = "<h2>Impostazioni</h2><div id=\"settings-keys\"></div>";
  const container = document.querySelector<HTMLElement>("#settings-keys")!;
  let configured: Record<string, boolean>;
  try {
    configured = await listKeys();
  } catch (err) {
    outlet.innerHTML = `<p class="banner banner-error">Impossibile caricare le chiavi: ${escapeHtml(err instanceof Error ? err.message : String(err))}</p>`;
    return;
  }
  for (const name of KNOWN_KEYS) {
    renderKeyField(container, name, Boolean(configured[name]));
  }
});
