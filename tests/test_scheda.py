import httpx
import respx
from fastapi.testclient import TestClient

from ricerca import history
from ricerca.app import app
from ricerca.models import Block, SourceResult, Strategy, Work

client = TestClient(app)


def ricerca_con_record():
    works = [
        Work(title="Teacher AI Literacy for Multilingual Learner Instruction",
             authors=["Chowdhury S", "Alvarez M"], year=2026, doi="10.21203/rs.1",
             venue="Research Square", url="https://esempio.org/1",
             abstract="Testo completo dell'abstract, non troncato.",
             sources=["europepmc", "crossref"]),
        Work(title="Secondo studio", authors=["Rossi M"], year=2024, doi="10.1/2",
             sources=["crossref"]),
    ]
    risultati = [
        SourceResult("europepmc", "Europe PMC", "q1", works=works[:1]),
        SourceResult("crossref", "Crossref", "q2", works=works),
    ]
    return history.salva("t", Strategy([Block("C", ["x"])]), risultati, works)


def test_la_scheda_raccoglie_tutto_quello_che_serve():
    id_ricerca = ricerca_con_record()
    scheda = client.get(f"/scheda/{id_ricerca}/0").text

    assert "Teacher AI Literacy" in scheda
    assert "Chowdhury S; Alvarez M" in scheda          # autori tutti, non «et al.»
    assert "Testo completo" in scheda and "non troncato" in scheda   # abstract intero
    assert "Research Square" in scheda and "10.21203/rs.1" in scheda
    assert "Europe PMC" in scheda and "Crossref" in scheda   # trovato da
    assert "Chowdhury, S., &amp; Alvarez, M. (2026)." in scheda  # citazione APA
    assert "@article{" in scheda                        # BibTeX pronto da copiare
    assert "esempio.org/1" in scheda                    # l'editore si apre da qui


def test_dalla_scheda_si_passa_al_record_vicino():
    id_ricerca = ricerca_con_record()
    prima = client.get(f"/scheda/{id_ricerca}/0").text
    assert f"/scheda/{id_ricerca}/1" in prima
    assert "1 of 2" in prima

    ultima = client.get(f"/scheda/{id_ricerca}/1").text
    assert f"/scheda/{id_ricerca}/2" not in ultima      # non si esce dall'elenco
    assert "2 of 2" in ultima


def test_un_indice_fuori_elenco_non_esplode():
    id_ricerca = ricerca_con_record()
    assert client.get(f"/scheda/{id_ricerca}/99").status_code == 200


def test_il_titolo_nell_elenco_apre_la_scheda():
    id_ricerca = ricerca_con_record()
    elenco = client.post(f"/risultati/{id_ricerca}", data={"vista": "tabella"}).text

    assert f'hx-get="/scheda/{id_ricerca}/0"' in elenco
    assert "showModal()" in elenco
    # il titolo non porta più fuori dall'app
    assert 'href="https://esempio.org/1"' not in elenco


def test_le_correzioni_si_salvano_e_l_originale_resta():
    id_ricerca = ricerca_con_record()

    client.post(f"/scheda/{id_ricerca}/0", data={
        "title": "Teacher AI Literacy for Multilingual Learner Instruction",
        "authors": "Chowdhury, Sadia; Alvarez, Maria",
        "year": "2025", "venue": "Research Square", "doi": "10.21203/rs.1",
    })

    record = history.record(id_ricerca)[0]
    assert record.year == 2025
    assert record.authors == ["Chowdhury, Sadia", "Alvarez, Maria"]
    assert set(record.corretto) == {"year", "authors"}

    originale = history.originale(id_ricerca, 0)
    assert originale.year == 2026 and originale.authors == ["Chowdhury S", "Alvarez M"]


def test_la_scheda_mostra_che_cosa_c_era_prima():
    id_ricerca = ricerca_con_record()
    client.post(f"/scheda/{id_ricerca}/0", data={"year": "2025"})
    scheda = client.get(f"/scheda/{id_ricerca}/0").text
    assert "fixed by hand" in scheda
    assert "was: 2026" in scheda


def test_tornare_al_valore_originale_toglie_la_correzione():
    id_ricerca = ricerca_con_record()
    client.post(f"/scheda/{id_ricerca}/0", data={"year": "2025"})
    client.post(f"/scheda/{id_ricerca}/0", data={"year": "2026"})
    assert history.record(id_ricerca)[0].corretto == []


def test_le_correzioni_finiscono_negli_export():
    id_ricerca = ricerca_con_record()
    client.post(f"/scheda/{id_ricerca}/0", data={"authors": "Chowdhury, Sadia", "year": "2025"})

    bib = client.get(f"/export/{id_ricerca}.bib?campi=anno,titolo,autori").text
    assert "Chowdhury, Sadia" in bib
    assert "year = {2025}" in bib

    apa = client.get(f"/export/{id_ricerca}.apa.txt").text
    assert "(2025)." in apa


def test_la_correzione_lascia_traccia_nel_registro():
    from ricerca import registro

    registro.svuota()
    id_ricerca = ricerca_con_record()
    client.post(f"/scheda/{id_ricerca}/0", data={"year": "2025"})
    assert any("fixed by hand" in v.azione for v in registro.ultime())


def test_l_elenco_segnala_i_record_corretti():
    id_ricerca = ricerca_con_record()
    client.post(f"/scheda/{id_ricerca}/0", data={"year": "2025"})
    elenco = client.post(f"/risultati/{id_ricerca}", data={"vista": "tabella"}).text
    assert "fixed by hand" in elenco


def test_lo_screening_si_fa_anche_dalla_scheda():
    id_ricerca = ricerca_con_record()
    scheda = client.get(f"/scheda/{id_ricerca}/1").text
    assert f'hx-post="/screening/{id_ricerca}/1"' in scheda


def test_un_appunto_resta_con_il_record_e_si_cancella_svuotandolo():
    id_ricerca = ricerca_con_record()

    scheda = client.get(f"/scheda/{id_ricerca}/0").text
    assert "Notes" in scheda

    salvata = client.post(
        f"/scheda/{id_ricerca}/0/nota",
        data={"nota": "  metodo utile per la sezione 3  "},
    )
    assert salvata.status_code == 200
    assert "metodo utile per la sezione 3" in salvata.text
    assert "Note saved" in salvata.headers["HX-Trigger"]

    # Sopravvive alla rilettura e non tocca gli altri record.
    lavori = history.record(id_ricerca)
    assert lavori[0].nota == "metodo utile per la sezione 3"
    assert lavori[1].nota == ""
    assert "metodo utile per la sezione 3" in client.get(f"/scheda/{id_ricerca}/0").text

    svuotata = client.post(f"/scheda/{id_ricerca}/0/nota", data={"nota": "   "})
    assert history.record(id_ricerca)[0].nota == ""
    assert "Note cleared" in svuotata.headers["HX-Trigger"]


def test_l_appunto_esce_nel_csv_quando_lo_si_chiede():
    id_ricerca = ricerca_con_record()
    history.salva_nota(id_ricerca, 0, "campione piccolo")

    csv = client.get(f"/export/{id_ricerca}.csv", params={"campi": "titolo,nota"}).text

    assert "nota" in csv.splitlines()[0]
    assert "campione piccolo" in csv


def test_un_indice_inesistente_non_scrive_appunti():
    id_ricerca = ricerca_con_record()
    assert history.salva_nota(id_ricerca, 99, "niente") == ""
    assert client.post(f"/scheda/{id_ricerca}/99/nota", data={"nota": "x"}).text == ""


def test_la_colonna_dell_appunto_disegna_la_sua_cella():
    """Un campo senza ramo nel template salterebbe la cella e sfalserebbe
    tutte le colonne successive della riga."""

    id_ricerca = ricerca_con_record()
    history.salva_nota(id_ricerca, 0, "da rileggere")

    pagina = client.post(
        f"/risultati/{id_ricerca}", data={"campo": ["titolo", "nota"], "vista": "tabella"}
    ).text

    assert "da rileggere" in pagina

    def conta(html):
        prima_riga = html.split("<tbody>")[1].split("</tr>")[0]
        return html.count("<th>"), prima_riga.count("<td")

    intestazioni, celle = conta(pagina)
    assert celle == intestazioni + 1   # in più la colonna della spunta, senza <th> di testo

    senza = client.post(
        f"/risultati/{id_ricerca}", data={"campo": ["titolo"], "vista": "tabella"}
    ).text
    assert conta(senza) == (intestazioni - 1, celle - 1)
