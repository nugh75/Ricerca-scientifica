import httpx
import respx

from ricerca import search
from ricerca.config import Config
from ricerca.models import Block, Strategy

OQL = "works where title/abstract has (ai literacy)"


@respx.mock
async def test_l_oql_arriva_nel_risultato_della_fonte():
    respx.get(url__startswith="https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json={
            "meta": {"cost_usd": 0.001, "x_query": {"oql": OQL}}, "results": [],
        })
    )
    strategy = Strategy(blocks=[Block("B", ["ai literacy"])])
    results, _ = await search.run(strategy, ["openalex"], 5, Config())
    assert results[0].oql == OQL


def test_il_protocollo_stampa_l_oql():
    from ricerca.export import protocollo, protocollo_testo

    voce = {
        "topic": "ai literacy", "quando": "2026-08-20T10:00:00", "blocchi": [],
        "fonti": [{"id": "openalex", "etichetta": "OpenAlex", "query": "(x)", "trovati": 3, "oql": OQL}],
    }
    assert OQL in protocollo(voce, {})
    assert OQL in protocollo_testo(voce, {})


def test_una_fonte_senza_oql_non_stampa_la_riga():
    from ricerca.export import protocollo

    voce = {
        "topic": "x", "quando": "2026-08-20T10:00:00", "blocchi": [],
        "fonti": [{"id": "pubmed", "etichetta": "PubMed", "query": "(x)", "trovati": 1}],
    }
    assert "OQL" not in protocollo(voce, {})


def test_il_protocollo_stampa_i_filtri_attivi():
    from ricerca.export import protocollo, protocollo_testo

    voce = {
        "topic": "x", "quando": "2026-08-20T10:00:00", "blocchi": [],
        "fonti": [], "filtri": {"lingua": "it", "solo_oa": True, "anno_da": None},
    }
    assert "lingua: it" in protocollo(voce, {})
    assert "solo_oa: True" in protocollo_testo(voce, {})
