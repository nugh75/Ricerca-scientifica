from fastapi.testclient import TestClient

from ricerca import biblioteca
from ricerca.app import app

client = TestClient(app)


def scrivi_testo(nome, contenuto):
    percorso = biblioteca.cartella() / nome
    percorso.write_text(contenuto, encoding="utf-8")
    return percorso


def test_cerca_trova_le_occorrenze_e_mostra_il_contorno():
    scrivi_testo("uno.txt", "Premessa lunga. Il costrutto di self-efficacy negli insegnanti. Conclusione.")
    scrivi_testo("due.txt", "Testo senza il termine cercato.")

    trovati = biblioteca.cerca("self-efficacy")

    assert len(trovati) == 1
    assert trovati[0]["file"] == "uno.pdf"
    assert "self-efficacy" in trovati[0]["estratto"]


def test_i_documenti_con_piu_occorrenze_vengono_prima():
    scrivi_testo("poche.txt", "misura una volta")
    scrivi_testo("molte.txt", "misura misura misura")
    assert [t["file"] for t in biblioteca.cerca("misura")] == ["molte.pdf", "poche.pdf"]


def test_la_ricerca_non_distingue_maiuscole():
    scrivi_testo("uno.txt", "Self-Efficacy in classe")
    assert biblioteca.cerca("self-efficacy")[0]["occorrenze"] == 1


def test_query_vuota_non_restituisce_nulla():
    scrivi_testo("uno.txt", "qualcosa")
    assert biblioteca.cerca("   ") == []


def test_la_pagina_dice_quando_non_c_e_ancora_nessun_pdf():
    assert "No PDFs downloaded yet" in client.get("/biblioteca").text


def test_la_pagina_mostra_i_risultati():
    scrivi_testo("uno.txt", "Il costrutto di self-efficacy negli insegnanti")
    pagina = client.get("/biblioteca", params={"q": "self-efficacy"})
    assert "uno.pdf" in pagina.text
    assert "self-efficacy" in pagina.text


def test_un_pdf_illeggibile_non_ferma_l_estrazione(tmp_path):
    finto = biblioteca.cartella() / "rotto.pdf"
    finto.write_bytes(b"%PDF-1.7 ma non valido")
    assert biblioteca.estrai(finto) is None


def test_il_risultato_apre_il_pdf_nel_lettore():
    scrivi_testo("uno.txt", "Il costrutto di self-efficacy negli insegnanti")
    (biblioteca.cartella() / "uno.pdf").write_bytes(b"%PDF-1.7 finto")

    pagina = client.get("/biblioteca", params={"q": "self-efficacy"})
    assert 'data-pdf="/biblioteca/uno.pdf/file"' in pagina.text

    risposta = client.get("/biblioteca/uno.pdf/file")
    assert risposta.status_code == 200
    assert risposta.headers["content-type"] == "application/pdf"


def test_la_biblioteca_non_serve_file_fuori_dalla_sua_cartella():
    assert client.get("/biblioteca/mancante.pdf/file").status_code == 404
    assert client.get("/biblioteca/uno.txt/file").status_code == 404
    assert biblioteca.percorso_pdf("../../etc/passwd.pdf") is None
