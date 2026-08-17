import { registerRoute } from "../router";
import { searchArticles, addArticle, SOURCES, type SearchResult } from "../api";
import { getConfiguredSources } from "../keysState";
import { buildSearchPayload, escapeHtml } from "../helpers";

registerRoute("/search", async () => {
  const outlet = document.querySelector<HTMLElement>("#outlet")!;
  const configured = await getConfiguredSources();

  outlet.innerHTML = `
    <h2>Ricerca</h2>
    <input id="search-query" placeholder="Query di ricerca" />
    <div id="search-sources">
      ${SOURCES.map((s) => `
        <label>
          <input type="checkbox" value="${s}" ${configured.has(s) ? "checked" : "disabled"} />
          ${s}${configured.has(s) ? "" : " (non configurato)"}
        </label>
      `).join("")}
    </div>
    <button id="search-submit">Cerca</button>
    <div id="search-errors"></div>
    <table id="search-results">
      <thead><tr><th>Titolo</th><th>Autori</th><th>Anno</th><th>Fonte</th><th>OA</th><th></th></tr></thead>
      <tbody></tbody>
    </table>
  `;

  document.querySelector("#search-submit")!.addEventListener("click", async () => {
    const query = document.querySelector<HTMLInputElement>("#search-query")!.value;
    const checked = Array.from(
      document.querySelectorAll<HTMLInputElement>("#search-sources input:checked")
    ).map((el) => el.value);
    const payload = buildSearchPayload(query, checked);
    if (!payload.query) return;

    const errorsBox = document.querySelector<HTMLElement>("#search-errors")!;
    let results;
    let errors;
    try {
      ({ results, errors } = await searchArticles(payload.query, payload.sources));
    } catch (err) {
      errorsBox.innerHTML = `<span class="badge badge-error">Ricerca fallita: ${escapeHtml(err instanceof Error ? err.message : String(err))}</span>`;
      return;
    }

    errorsBox.innerHTML = Object.entries(errors)
      .map(([source, message]) => `<span class="badge badge-error">${escapeHtml(source)}: ${escapeHtml(message)}</span>`)
      .join(" ");

    const tbody = document.querySelector<HTMLElement>("#search-results tbody")!;
    tbody.innerHTML = "";
    results.forEach((r: SearchResult, i: number) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(r.title)}</td>
        <td>${escapeHtml(r.authors.join(", "))}</td>
        <td>${r.year ?? ""}</td>
        <td>${escapeHtml(r.source)}</td>
        <td>${r.oa_pdf_url ? '<span class="badge badge-ok">OA</span>' : ""}</td>
        <td><button data-add="${i}">Aggiungi a libreria</button></td>
      `;
      tbody.appendChild(tr);
      tr.querySelector("button")!.addEventListener("click", async (e) => {
        const btn = e.target as HTMLButtonElement;
        try {
          await addArticle({
            title: r.title,
            authors: r.authors,
            year: r.year,
            doi: r.doi,
            source: r.source,
            abstract: r.abstract,
            oa_pdf_url: r.oa_pdf_url,
          });
          btn.textContent = "Aggiunto";
          btn.disabled = true;
        } catch (err) {
          btn.textContent = `Errore: ${err instanceof Error ? err.message : String(err)}`;
        }
      });
    });
  });
});
