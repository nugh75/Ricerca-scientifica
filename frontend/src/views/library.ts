import { registerRoute, navigate } from "../router";
import { listArticles, downloadPdf, uploadPdf, type Article } from "../api";
import { pdfStatusLabel, escapeHtml } from "../helpers";

registerRoute("/library", async () => {
  const outlet = document.querySelector<HTMLElement>("#outlet")!;
  outlet.innerHTML = `
    <h2>Libreria</h2>
    <a href="#/export">Esporta .bib</a>
    <div id="library-error"></div>
    <table id="library-table">
      <thead><tr><th>Titolo</th><th>Anno</th><th>Fonte</th><th>PDF</th><th></th></tr></thead>
      <tbody></tbody>
    </table>
  `;

  let articles: Article[];
  try {
    articles = await listArticles();
  } catch (err) {
    document.querySelector<HTMLElement>("#library-error")!.innerHTML =
      `<span class="badge badge-error">Impossibile caricare la libreria: ${escapeHtml(err instanceof Error ? err.message : String(err))}</span>`;
    return;
  }

  const tbody = document.querySelector<HTMLElement>("#library-table tbody")!;

  function renderRow(article: Article): void {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><a href="#/article/${article.id}">${escapeHtml(article.title)}</a></td>
      <td>${article.year ?? ""}</td>
      <td>${escapeHtml(article.source)}</td>
      <td>${pdfStatusLabel(article)}</td>
      <td>
        ${article.oa_pdf_url ? `<button data-download="${article.id}">Scarica PDF</button>` : `<input type="file" accept="application/pdf" data-upload="${article.id}" />`}
        <span data-role="row-error"></span>
      </td>
    `;
    tbody.appendChild(tr);

    tr.querySelector("[data-download]")?.addEventListener("click", async () => {
      try {
        await downloadPdf(article.id);
        navigate("/library");
        registerAndRerender();
      } catch (err) {
        tr.querySelector("[data-role=row-error]")!.textContent = `Errore: ${err instanceof Error ? err.message : String(err)}`;
      }
    });

    tr.querySelector("[data-upload]")?.addEventListener("change", async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      try {
        await uploadPdf(article.id, file);
        navigate("/library");
        registerAndRerender();
      } catch (err) {
        tr.querySelector("[data-role=row-error]")!.textContent = `Errore: ${err instanceof Error ? err.message : String(err)}`;
      }
    });
  }

  function registerAndRerender(): void {
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  }

  articles.forEach(renderRow);
});
