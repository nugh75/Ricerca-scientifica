import { registerRoute } from "../router";
import { listKeys, KNOWN_KEYS } from "../api";
import { renderKeyField } from "./keyField";

registerRoute("/settings", async () => {
  const outlet = document.querySelector<HTMLElement>("#outlet")!;
  outlet.innerHTML = "<h2>Impostazioni</h2><div id=\"settings-keys\"></div>";
  const container = document.querySelector<HTMLElement>("#settings-keys")!;
  const configured = await listKeys();
  for (const name of KNOWN_KEYS) {
    renderKeyField(container, name, Boolean(configured[name]));
  }
});
