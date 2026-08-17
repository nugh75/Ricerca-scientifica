import { setKey, deleteKey, testKey } from "../api";
import { keyLabel } from "../helpers";

export function renderKeyField(container: HTMLElement, name: string, configured: boolean): void {
  const row = document.createElement("div");
  row.innerHTML = `
    <label>${keyLabel(name)} <span class="badge ${configured ? "badge-ok" : "badge-warn"}">${configured ? "configurato" : "non configurato"}</span></label>
    <input type="text" data-role="value" placeholder="${configured ? "•••••••• (invariato se lasci vuoto)" : ""}" />
    <button data-role="save">Salva</button>
    <button data-role="test">Testa connessione</button>
    <button data-role="delete">Elimina</button>
    <span data-role="message"></span>
  `;
  const input = row.querySelector<HTMLInputElement>("[data-role=value]")!;
  const message = row.querySelector<HTMLSpanElement>("[data-role=message]")!;

  row.querySelector("[data-role=save]")!.addEventListener("click", async () => {
    if (!input.value) return;
    await setKey(name, input.value);
    message.textContent = "Salvato.";
    input.value = "";
  });

  row.querySelector("[data-role=test]")!.addEventListener("click", async () => {
    if (!input.value) {
      message.textContent = "Inserisci un valore da testare.";
      return;
    }
    const result = await testKey(name, input.value);
    message.textContent = result.ok ? "Connessione riuscita." : `Errore: ${result.message}`;
  });

  row.querySelector("[data-role=delete]")!.addEventListener("click", async () => {
    await deleteKey(name);
    message.textContent = "Eliminata.";
  });

  container.appendChild(row);
}
