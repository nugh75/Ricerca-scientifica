import { registerRoute } from "../router";
import { listArticles, exportBib, type Article } from "../api";
import { buildExportPayload, escapeHtml } from "../helpers";
import { save } from "@tauri-apps/plugin-dialog";
import { invoke } from "@tauri-apps/api/core";

registerRoute("/export", async () => {
  const outlet = document.querySelector<HTMLElement>("#outlet")!;

  let articles: Article[];
  try {
    articles = await listArticles();
  } catch (err) {
    outlet.innerHTML = `<p class="banner banner-error">Impossibile caricare la libreria: ${escapeHtml(err instanceof Error ? err.message : String(err))}</p>`;
    return;
  }

  outlet.innerHTML = `
    <h2>Esporta .bib</h2>
    <ul id="export-list">
      ${articles.map((a) => `<li><label><input type="checkbox" value="${a.id}" /> ${escapeHtml(a.title)}</label></li>`).join("")}
    </ul>
    <button id="export-submit">Esporta .bib</button>
    <p id="export-message"></p>
  `;

  document.querySelector("#export-submit")!.addEventListener("click", async () => {
    const checked = Array.from(
      document.querySelectorAll<HTMLInputElement>("#export-list input:checked")
    ).map((el) => el.value);
    const ids = buildExportPayload(checked);
    if (ids.length === 0) return;

    const message = document.querySelector<HTMLElement>("#export-message")!;
    try {
      const bib = await exportBib(ids);
      const path = await save({ filters: [{ name: "BibTeX", extensions: ["bib"] }] });
      if (!path) return;
      await invoke("write_export", { path, content: bib });
      message.textContent = `Salvato in ${path}`;
    } catch (err) {
      message.textContent = `Errore: ${err instanceof Error ? err.message : String(err)}`;
    }
  });
});
