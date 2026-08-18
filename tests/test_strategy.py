from ricerca.models import Block, Strategy
from ricerca.models import Suggestions
from ricerca.strategy import (
    flat_terms,
    heuristic_strategy,
    render,
    strategy_from_form,
    topic_seed,
)


def test_render_mette_i_blocchi_in_and_e_i_termini_in_or(strategy):
    assert render(strategy) == (
        '("AI literacy" OR "AI competence") AND ("teacher" OR "educator")'
    )


def test_render_con_un_solo_blocco():
    assert render(Strategy([Block("x", ["alpha"])])) == '("alpha")'


def test_render_strategia_vuota():
    assert render(Strategy([Block("x", ["  "])])) == ""


def test_flat_terms_elenca_i_termini_senza_operatori(strategy):
    assert flat_terms(strategy) == "AI literacy AI competence teacher educator"


def test_strategy_from_form_ignora_i_blocchi_vuoti():
    result = strategy_from_form(
        ["Concetto", "Vuoto"], ["a, b", "   "], mesh="Literacy, Education"
    )
    assert [b.label for b in result.blocks] == ["Concetto"]
    assert result.blocks[0].terms == ["a", "b"]
    assert result.mesh == ["Literacy", "Education"]


def test_heuristic_strategy_usa_topic_concetti_e_cooccorrenze():
    suggestions = Suggestions(
        topic="AI literacy",
        concepts=[("Literacy", 0.57), ("Pedagogy", 0.1)],
        cooccurring=[("higher education", 7), ("AI literacy", 5)],
        mesh=["Artificial Intelligence"],
    )
    result = heuristic_strategy(suggestions)
    assert result.blocks[0].terms == ["AI literacy", "Literacy"]
    assert "Pedagogy" not in result.blocks[0].terms  # score sotto soglia
    assert result.blocks[1].terms == ["higher education"]  # duplicato del topic escluso
    assert result.mesh == ["Artificial Intelligence"]


def test_topic_seed_tiene_la_frase_breve():
    assert topic_seed("AI literacy") == ["AI literacy"]


def test_topic_seed_scompone_le_frasi_lunghe():
    seed = topic_seed("competenze di intelligenza artificiale negli insegnanti")
    assert seed == ["competenze", "intelligenza", "artificiale", "insegnanti"]


def test_heuristic_non_ripete_le_parole_del_topic_fra_i_correlati():
    suggestions = Suggestions(
        topic="competenze di intelligenza artificiale negli insegnanti",
        concepts=[],
        cooccurring=[("intelligenza artificiale", 9), ("formazione docenti", 4)],
    )
    result = heuristic_strategy(suggestions)
    assert "intelligenza" in result.blocks[0].terms
    assert result.blocks[1].terms == ["formazione docenti"]


def test_le_etichette_dei_blocchi_seguono_la_lingua():
    suggestions = Suggestions(topic="AI literacy", cooccurring=[("higher education", 4)])
    assert [b.label for b in heuristic_strategy(suggestions, "en").blocks] == [
        "Main concept",
        "Related terms",
    ]
    assert heuristic_strategy(suggestions, "it").blocks[0].label == "Concetto principale"
