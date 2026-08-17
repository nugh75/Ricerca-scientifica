import "./style.css";
import { BASE_URL } from "./api";
import { navigate, startRouter } from "./router";
import { subscribeToBackendStatus } from "./backendStatus";
import "./views/settings";
import "./views/onboarding";
import "./views/search";
import "./views/library";
import "./views/articleDetail";
import "./views/export";
import { isFirstRunDone } from "./firstRun";

const app = document.querySelector<HTMLDivElement>("#app")!;

const backendBanner = document.createElement("div");
backendBanner.id = "backend-banner";
document.body.prepend(backendBanner);

subscribeToBackendStatus(
  () => {
    backendBanner.innerHTML = `<div class="banner banner-error">Il backend non risponde. Tentativo di riavvio in corso...</div>`;
  },
  () => {
    backendBanner.innerHTML = `<div class="banner banner-error">Il backend si è arrestato e non è stato possibile riavviarlo. Chiudi e riapri l'applicazione.</div>`;
  }
);

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
  navigate(isFirstRunDone() ? "/search" : "/onboarding");
}

boot();
