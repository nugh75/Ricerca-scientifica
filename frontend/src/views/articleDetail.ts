import { registerRoute } from "../router";
import { getArticle, analyze, sendChatMessage, type Article } from "../api";
import { pdfStatusLabel, canAnalyze, escapeHtml } from "../helpers";

const MODES = [
  { id: "summary", label: "Riassunto" },
  { id: "metadata", label: "Estrazione metadati" },
  { id: "verify", label: "Verifica bibliografica" },
] as const;

registerRoute("/article/:id", async ({ id }) => {
  const outlet = document.querySelector<HTMLElement>("#outlet")!;

  let article: Article;
  try {
    article = await getArticle(Number(id));
  } catch (err) {
    outlet.innerHTML = `<p class="banner banner-error">Impossibile caricare l'articolo: ${escapeHtml(err instanceof Error ? err.message : String(err))}</p>`;
    return;
  }

  const analysis: Record<string, string> = article.analysis_json ? JSON.parse(article.analysis_json) : {};
  const ready = canAnalyze(article);

  outlet.innerHTML = `
    <h2>${escapeHtml(article.title)}</h2>
    <p>${escapeHtml(article.authors.join(", "))} — ${article.year ?? "anno sconosciuto"}</p>
    <p>${pdfStatusLabel(article)}</p>
    ${!ready ? '<p class="banner banner-error">Nessun testo estraibile dal PDF: analisi e chat non disponibili.</p>' : ""}

    <h3>Analisi</h3>
    <div id="analysis-buttons">
      ${MODES.map((m) => `<button data-mode="${m.id}" ${ready ? "" : "disabled"}>${m.label}</button>`).join("")}
    </div>
    <div id="analysis-results">
      ${MODES.map((m) => `<section><h4>${m.label}</h4><pre data-result="${m.id}">${escapeHtml(analysis[m.id] ?? "(non ancora eseguita)")}</pre></section>`).join("")}
    </div>

    <h3>Chat</h3>
    <div id="chat-messages"></div>
    <input id="chat-input" ${ready ? "" : "disabled"} placeholder="Fai una domanda sull'articolo" />
    <button id="chat-send" ${ready ? "" : "disabled"}>Invia</button>
  `;

  document.querySelectorAll<HTMLButtonElement>("#analysis-buttons button").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const mode = btn.dataset.mode as "summary" | "metadata" | "verify";
      btn.disabled = true;
      try {
        const res = await analyze(article.id, mode);
        document.querySelector(`[data-result="${mode}"]`)!.textContent = res.result;
      } catch (err) {
        document.querySelector(`[data-result="${mode}"]`)!.textContent = `Errore: ${err instanceof Error ? err.message : String(err)}`;
      } finally {
        btn.disabled = false;
      }
    });
  });

  const chatMessages = document.querySelector<HTMLElement>("#chat-messages")!;
  function renderChat(messages: { role: string; content: string }[]): void {
    chatMessages.innerHTML = messages
      .map((m) => `<p><strong>${m.role === "user" ? "Tu" : "LitReview"}:</strong> ${escapeHtml(m.content)}</p>`)
      .join("");
  }

  document.querySelector("#chat-send")!.addEventListener("click", async () => {
    const input = document.querySelector<HTMLInputElement>("#chat-input")!;
    if (!input.value) return;
    const message = input.value;
    input.value = "";
    try {
      const res = await sendChatMessage(article.id, message);
      renderChat(res.messages);
    } catch (err) {
      chatMessages.innerHTML += `<p class="badge badge-error">Errore: ${escapeHtml(err instanceof Error ? err.message : String(err))}</p>`;
    }
  });
});
