import "./style.css";
import { BASE_URL } from "./api";
import { navigate, startRouter } from "./router";

const app = document.querySelector<HTMLDivElement>("#app")!;

async function waitForBackend(maxAttempts = 50, delayMs = 300): Promise<boolean> {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const res = await fetch(`${BASE_URL}/docs`);
      if (res.ok) return true;
    } catch {
      // backend not up yet, keep polling
    }
    await new Promise((r) => setTimeout(r, delayMs));
  }
  return false;
}

function renderShell(): void {
  app.innerHTML = `
    <div id="backend-banner"></div>
    <nav>
      <a data-nav="/search">Ricerca</a>
      <a data-nav="/library">Libreria</a>
      <a data-nav="/settings">Impostazioni</a>
    </nav>
    <main id="outlet"></main>
  `;
  app.querySelectorAll<HTMLAnchorElement>("[data-nav]").forEach((a) => {
    a.addEventListener("click", () => navigate(a.dataset.nav!));
  });
  const outlet = document.querySelector<HTMLElement>("#outlet")!;
  startRouter(outlet, () => {
    outlet.innerHTML = "<p>Pagina non trovata.</p>";
  });
}

function renderStarting(): void {
  app.innerHTML = `<main><p>Avvio del motore di ricerca in corso...</p></main>`;
}

async function boot(): Promise<void> {
  renderStarting();
  const ready = await waitForBackend();
  if (!ready) {
    app.innerHTML = `<main><p class="banner banner-error">Impossibile contattare il backend su ${BASE_URL}. Riavvia l'applicazione.</p></main>`;
    return;
  }
  renderShell();
  navigate("/search");
}

boot();
