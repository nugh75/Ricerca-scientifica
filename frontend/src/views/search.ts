import { registerRoute } from "../router";
import { searchArticles, addArticle, SOURCES, type SearchResult } from "../api";
import { getConfiguredSources } from "../keysState";
import { buildSearchPayload } from "../helpers";

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

    const { results, errors } = await searchArticles(payload.query, payload.sources);

    const errorsBox = document.querySelector<HTMLElement>("#search-errors")!;
    errorsBox.innerHTML = Object.entries(errors)
      .map(([source, message]) => `<span class="badge badge-error">${source}: ${message}</span>`)
      .join(" ");

    const tbody = document.querySelector<HTMLElement>("#search-results tbody")!;
    tbody.innerHTML = "";
    results.forEach((r: SearchResult, i: number) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${r.title}</td>
        <td>${r.authors.join(", ")}</td>
        <td>${r.year ?? ""}</td>
        <td>${r.source}</td>
        <td>${r.oa_pdf_url ? '<span class="badge badge-ok">OA</span>' : ""}</td>
        <td><button data-add="${i}">Aggiungi a libreria</button></td>
      `;
      tbody.appendChild(tr);
      tr.querySelector("button")!.addEventListener("click", async (e) => {
        await addArticle({
          title: r.title,
          authors: r.authors,
          year: r.year,
          doi: r.doi,
          source: r.source,
          abstract: r.abstract,
          oa_pdf_url: r.oa_pdf_url,
        });
        (e.target as HTMLButtonElement).textContent = "Aggiunto";
        (e.target as HTMLButtonElement).disabled = true;
      });
    });
  });
});
