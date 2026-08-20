(function () {
  "use strict";

  const datiElemento = document.getElementById("wiki-dati");
  const svg = document.getElementById("wiki-grafo");
  if (!datiElemento || !svg) return;

  const dati = JSON.parse(datiElemento.textContent || "{}");
  const nodi = Array.isArray(dati.nodi) ? dati.nodi : [];
  const archi = Array.isArray(dati.archi) ? dati.archi : [];
  const dettaglio = document.getElementById("wiki-dettaglio");
  const filtri = [...document.querySelectorAll(".wiki-filtri input[type=checkbox]")];
  const namespace = "http://www.w3.org/2000/svg";

  function elemento(nome, attributi) {
    const creato = document.createElementNS(namespace, nome);
    Object.entries(attributi || {}).forEach(([chiave, valore]) => creato.setAttribute(chiave, valore));
    return creato;
  }

  function tipiAttivi() {
    return new Set(filtri.filter((filtro) => filtro.checked).map((filtro) => filtro.value));
  }

  function grado(id) {
    return archi.reduce((totale, arco) => totale + Number(arco.origine === id || arco.destinazione === id), 0);
  }

  function posizione(nodo, indice, totale) {
    const centroX = 500;
    const centroY = 340;
    const raggio = nodo.tipo === "concetto" ? 145 : nodo.tipo === "fonte" ? 295 : 410;
    const schiacciamento = nodo.tipo === "concetto" ? 0.78 : 0.70;
    const angolo = (Math.PI * 2 * indice / Math.max(1, totale)) - Math.PI / 2;
    return { x: centroX + Math.cos(angolo) * raggio, y: centroY + Math.sin(angolo) * raggio * schiacciamento };
  }

  function mostraDettaglio(nodo, vicini) {
    dettaglio.replaceChildren();
    const titolo = document.createElement("strong");
    titolo.textContent = nodo.etichetta;
    const tipo = document.createElement("span");
    tipo.textContent = nodo.tipo;
    const testo = document.createElement("p");
    testo.textContent = vicini.length ? vicini.map((voce) => voce.etichetta).join(" · ") : "—";
    dettaglio.append(titolo, tipo, testo);
    const pagina = document.getElementById("pagina-" + nodo.id);
    if (pagina) pagina.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function disegna() {
    svg.replaceChildren();
    const attivi = tipiAttivi();
    const candidati = nodi
      .filter((nodo) => attivi.has(nodo.tipo))
      .sort((a, b) => Number(b.tipo === "concetto") - Number(a.tipo === "concetto") || grado(b.id) - grado(a.id))
      .slice(0, 100);
    const perTipo = new Map();
    candidati.forEach((nodo) => {
      if (!perTipo.has(nodo.tipo)) perTipo.set(nodo.tipo, []);
      perTipo.get(nodo.tipo).push(nodo);
    });
    const posizioni = new Map();
    perTipo.forEach((gruppo) => gruppo.forEach((nodo, indice) => posizioni.set(nodo.id, posizione(nodo, indice, gruppo.length))));

    const archiVisibili = archi.filter((arco) => posizioni.has(arco.origine) && posizioni.has(arco.destinazione));
    archiVisibili.forEach((arco) => {
      const origine = posizioni.get(arco.origine);
      const destinazione = posizioni.get(arco.destinazione);
      const linea = elemento("line", { x1: origine.x, y1: origine.y, x2: destinazione.x, y2: destinazione.y, class: "wiki-arco" });
      linea.dataset.origine = arco.origine;
      linea.dataset.destinazione = arco.destinazione;
      const titolo = elemento("title");
      titolo.textContent = arco.tipo;
      linea.appendChild(titolo);
      svg.appendChild(linea);
    });

    candidati.forEach((nodo) => {
      const posizioneNodo = posizioni.get(nodo.id);
      const gruppo = elemento("g", { class: "wiki-nodo wiki-nodo-" + nodo.tipo, tabindex: "0", role: "button" });
      gruppo.dataset.id = nodo.id;
      gruppo.setAttribute("aria-label", nodo.etichetta);
      const cerchio = elemento("circle", { cx: posizioneNodo.x, cy: posizioneNodo.y, r: nodo.tipo === "concetto" ? 10 : 6 });
      const titolo = elemento("title");
      titolo.textContent = nodo.etichetta;
      cerchio.appendChild(titolo);
      gruppo.appendChild(cerchio);
      if (nodo.tipo === "concetto" || candidati.length < 28) {
        const etichetta = elemento("text", { x: posizioneNodo.x + 13, y: posizioneNodo.y + 4, class: "wiki-etichetta" });
        etichetta.textContent = nodo.etichetta.length > 34 ? nodo.etichetta.slice(0, 32) + "…" : nodo.etichetta;
        gruppo.appendChild(etichetta);
      }
      const seleziona = function () {
        const collegati = new Set([nodo.id]);
        archiVisibili.forEach((arco) => {
          if (arco.origine === nodo.id) collegati.add(arco.destinazione);
          if (arco.destinazione === nodo.id) collegati.add(arco.origine);
        });
        svg.querySelectorAll(".wiki-nodo").forEach((elementoNodo) => elementoNodo.classList.toggle("attenuato", !collegati.has(elementoNodo.dataset.id)));
        svg.querySelectorAll(".wiki-arco").forEach((elementoArco) => elementoArco.classList.toggle("attenuato", elementoArco.dataset.origine !== nodo.id && elementoArco.dataset.destinazione !== nodo.id));
        mostraDettaglio(nodo, candidati.filter((voce) => voce.id !== nodo.id && collegati.has(voce.id)));
      };
      gruppo.addEventListener("click", seleziona);
      gruppo.addEventListener("keydown", (evento) => {
        if (evento.key === "Enter" || evento.key === " ") { evento.preventDefault(); seleziona(); }
      });
      svg.appendChild(gruppo);
    });
  }

  filtri.forEach((filtro) => filtro.addEventListener("change", disegna));
  document.querySelector("[data-wiki-reset]")?.addEventListener("click", function () {
    filtri.forEach((filtro) => { filtro.checked = filtro.value === "concetto" || filtro.value === "fonte"; });
    disegna();
  });

  document.getElementById("wiki-cerca")?.addEventListener("input", function (evento) {
    const termine = evento.target.value.trim().toLocaleLowerCase();
    document.querySelectorAll(".wiki-pagina").forEach((pagina) => {
      pagina.hidden = Boolean(termine) && !pagina.dataset.cerca.includes(termine);
    });
  });

  disegna();
})();
