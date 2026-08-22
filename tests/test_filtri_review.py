from fastapi.testclient import TestClient

from ricerca import history, revisioni
from ricerca.app import app
from ricerca.filtri_review import corrisponde, filtra_record
from ricerca.models import Block, SourceResult, Strategy, Work


client = TestClient(app)


def record(titolo="AI literacy in schools", anno=2024, abstract="Teachers develop AI literacy in primary schools."):
    return {"work": Work(title=titolo, year=anno, abstract=abstract)}


def _ricerca_finta():
    lavori = [
        Work(
            title="AI literacy in teacher education",
            authors=["Ada Rossi"],
            year=2024,
            doi="10.1/a",
            abstract="Teachers develop artificial intelligence literacy.",
            sources=["openalex"],
        ),
        Work(
            title="Responsible AI competence",
            authors=["Luca Bianchi"],
            year=2023,
            doi="10.1/b",
            abstract="A study of responsible AI competence in schools.",
            sources=["openalex"],
        ),
    ]
    return history.salva(
        "AI literacy",
        Strategy([Block("Concetto", ["AI literacy"])]),
        [SourceResult("openalex", "OpenAlex", "AI literacy", works=lavori)],
        lavori,
    )


def _progetto_con_records():
    id_progetto = revisioni.crea("Review AI", "sistematica", ["Ada"])
    revisioni.collega_ricerca(id_progetto, _ricerca_finta())
    return id_progetto


def test_query_vuota_passa_tutto():
    assert corrisponde("", "qualsiasi testo")
    assert corrisponde("   ", "qualsiasi testo")


def test_termine_come_sottostringa_senza_distinguere_maiuscole():
    assert corrisponde("literacy", "AI Literacy in schools")
    assert not corrisponde("litx", "AI Literacy in schools")


def test_and_esige_entrambi_i_termini():
    assert corrisponde("AI AND teacher", "AI and teacher education")
    assert not corrisponde("AI AND teacher", "AI literacy")


def test_or_basta_un_termine():
    assert corrisponde("cat OR dog", "the dog barks")
    assert not corrisponde("cat OR dog", "the bird sings")


def test_not_nega_il_termine_che_segue():
    assert corrisponde("AI NOT teacher", "AI literacy")
    assert not corrisponde("AI NOT teacher", "AI teacher literacy")


def test_precedenza_and_su_or():
    assert corrisponde("cane OR gatto AND nero", "cane bianco")
    assert not corrisponde("cane OR gatto AND nero", "gatto bianco")
    assert corrisponde("cane OR gatto AND nero", "gatto nero")


def test_not_lega_piu_di_and():
    assert corrisponde("a AND NOT b", "a senza la lettera")
    assert not corrisponde("a AND NOT b", "a con la b")


def test_record_senza_filtri_passa():
    assert filtra_record(record(), {})


def test_filtro_anno_include_il_range_ed_esclude_chi_non_ha_anno():
    filtri = {"filtro_anno_da": "2020", "filtro_anno_a": "2024"}
    assert filtra_record(record(anno=2020), filtri)
    assert filtra_record(record(anno=2024), filtri)
    assert not filtra_record(record(anno=2019), filtri)
    assert not filtra_record(record(anno=2025), filtri)
    assert not filtra_record(record(anno=None), filtri)


def test_filtro_keywords_cerca_in_titolo_e_abstract():
    assert filtra_record(record(), {"filtro_keywords": "primary"})          # nell'abstract
    assert filtra_record(record(), {"filtro_keywords": "schools"})          # nel titolo
    assert not filtra_record(record(), {"filtro_keywords": "university"})
    assert filtra_record(record(abstract=None), {"filtro_keywords": "schools"})


def test_filtro_titolo_cerca_solo_nel_titolo():
    voce = record(titolo="cane gatto", abstract="pesce")
    assert filtra_record(voce, {"filtro_titolo": "gatto"})
    assert not filtra_record(voce, {"filtro_titolo": "pesce"})


def test_filtro_abstract_cerca_solo_nell_abstract():
    voce = record(titolo="cane gatto", abstract="pesce")
    assert filtra_record(voce, {"filtro_abstract": "pesce"})
    assert not filtra_record(voce, {"filtro_abstract": "gatto"})
    assert not filtra_record(record(abstract=None), {"filtro_abstract": "pesce"})


def test_i_filtri_si_combinano_in_and():
    filtri = {"filtro_titolo": "AI", "filtro_anno_da": "2023", "filtro_anno_a": "2025", "filtro_abstract": "primary"}
    assert filtra_record(record(), filtri)
    assert not filtra_record(record(anno=2022), filtri)
    assert not filtra_record(record(abstract="altro"), filtri)


def test_i_filtri_del_protocollo_restringono_lo_screening():
    id_progetto = _progetto_con_records()
    revisioni.salva_protocollo(id_progetto, {"filtro_anno_da": "2024"})
    risposta = client.get(f"/revisioni/{id_progetto}")
    assert risposta.status_code == 200
    assert "AI literacy in teacher education" in risposta.text
    assert "Responsible AI competence" not in risposta.text


def test_i_parametri_query_scavalcano_il_protocollo_senza_riscriverlo():
    id_progetto = _progetto_con_records()
    revisioni.salva_protocollo(id_progetto, {"filtro_anno_da": "2024"})
    risposta = client.get(
        f"/revisioni/{id_progetto}", params={"filtro_titolo": "Responsible"}
    )
    assert "Responsible AI competence" in risposta.text
    assert "AI literacy in teacher education" not in risposta.text
    assert revisioni.progetto(id_progetto)["protocollo"]["filtro_anno_da"] == "2024"
