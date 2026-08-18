import os

from fastapi.testclient import TestClient

from ricerca import sources
from ricerca.app import app
from ricerca.config import Config
from ricerca.sources import opac_sbn

client = TestClient(app)


def test_semantic_scholar_avvisa_finche_manca_la_chiave():
    fonte = sources.BY_ID["semanticscholar"]
    assert fonte.unavailable_reason(Config()) is None      # si può usare
    assert "429" in fonte.avviso(Config(), "it")           # ma con un limite
    assert fonte.avviso(Config(s2_api_key="k"), "it") is None


def test_openalex_dichiara_il_consumo():
    assert "budget" in sources.BY_ID["openalex"].avviso(Config(), "it")
    assert "budget" in sources.BY_ID["openalex"].avviso(Config(), "en")


def test_le_fonti_senza_limiti_non_avvisano():
    for id_fonte in ("crossref", "pubmed", "europepmc", "arxiv", "doaj"):
        assert sources.BY_ID[id_fonte].avviso(Config()) is None


def test_opac_trova_la_cli_anche_fuori_dal_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(opac_sbn.shutil, "which", lambda _: None)
    assert opac_sbn.trova_binario() is None

    cartella = tmp_path / "go" / "bin"
    cartella.mkdir(parents=True)
    finto = cartella / opac_sbn.BINARY
    finto.write_text("#!/bin/sh\n")
    finto.chmod(0o755)

    assert opac_sbn.trova_binario() == str(finto)
    assert opac_sbn.OpacSbn().unavailable_reason(Config(), "it") is None


def test_un_file_non_eseguibile_non_conta(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(opac_sbn.shutil, "which", lambda _: None)
    cartella = tmp_path / ".local" / "bin"
    cartella.mkdir(parents=True)
    (cartella / opac_sbn.BINARY).write_text("non eseguibile")
    assert opac_sbn.trova_binario() is None


def test_il_pannello_distingue_i_tre_stati():
    pagina = client.get("/impostazioni").text
    assert "ready, with a caveat" in pagina   # Semantic Scholar e OpenAlex
    assert "needs a free key" in pagina       # CORE
    assert "string only" in pagina            # Scopus e Web of Science
