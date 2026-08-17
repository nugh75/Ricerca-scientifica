import { registerRoute, navigate } from "../router";
import { KNOWN_KEYS } from "../api";
import { renderKeyField } from "./keyField";
import { markFirstRunDone } from "../firstRun";

registerRoute("/onboarding", () => {
  const outlet = document.querySelector<HTMLElement>("#outlet")!;
  outlet.innerHTML = `
    <h2>Benvenuto in LitReview</h2>
    <p>Configura le chiavi API per le fonti che vuoi usare. Puoi saltare questo passaggio e configurarle più tardi da Impostazioni.</p>
    <div id="onboarding-keys"></div>
    <button id="onboarding-skip">Salta, configuro dopo</button>
    <button id="onboarding-continue">Salva e continua</button>
  `;
  const container = document.querySelector<HTMLElement>("#onboarding-keys")!;
  for (const name of KNOWN_KEYS) {
    renderKeyField(container, name, false);
  }
  const finish = () => {
    markFirstRunDone();
    navigate("/search");
  };
  document.querySelector("#onboarding-skip")!.addEventListener("click", finish);
  document.querySelector("#onboarding-continue")!.addEventListener("click", finish);
});
