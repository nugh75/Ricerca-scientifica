from litreview.bib_export import export_bib, make_citekey, to_bibtex


def test_make_citekey_uses_author_year_title():
    key = make_citekey(["Jane Smith"], 2020, "Deep Learning Basics")
    assert key == "Smith2020Deep"


def test_make_citekey_handles_missing_year():
    key = make_citekey(["Jane Smith"], None, "Deep Learning Basics")
    assert key == "SmithndDeep"


def test_make_citekey_handles_empty_authors():
    key = make_citekey([], 2020, "Deep Learning Basics")
    assert key == "Anon2020Deep"


def test_make_citekey_strips_accents_and_punctuation():
    # last whitespace-separated token of authors[0] is "D'Andrea-Bruno";
    # _slug strips the apostrophe and hyphen, and the title's accented
    # first word "Città" normalizes to "Citta".
    key = make_citekey(["Alessandro D'Andrea-Bruno"], 2021, "Città e reti")
    assert key.isascii()
    assert key == "DAndreaBruno2021Citta"


def test_to_bibtex_includes_core_fields():
    article = {
        "bib_key": None,
        "authors": ["Jane Smith", "John Doe"],
        "title": "Deep Learning Basics",
        "year": 2020,
        "doi": "10.1/abc",
    }
    bib = to_bibtex(article)
    assert bib.startswith("@article{Smith2020Deep,")
    assert "author = {Jane Smith and John Doe}" in bib
    assert "title = {Deep Learning Basics}" in bib
    assert "year = {2020}" in bib
    assert "doi = {10.1/abc}" in bib


def test_to_bibtex_uses_explicit_bib_key_if_present():
    article = {
        "bib_key": "custom2020key",
        "authors": ["Jane Smith"],
        "title": "T",
        "year": 2020,
        "doi": None,
    }
    bib = to_bibtex(article)
    assert bib.startswith("@article{custom2020key,")


def test_to_bibtex_omits_empty_optional_fields():
    article = {"bib_key": None, "authors": ["Jane Smith"], "title": "T", "year": None, "doi": None}
    bib = to_bibtex(article)
    assert "doi" not in bib
    assert "year = {}" not in bib


def test_export_bib_joins_multiple_entries():
    articles = [
        {"bib_key": None, "authors": ["A"], "title": "One", "year": 2020, "doi": None},
        {"bib_key": None, "authors": ["B"], "title": "Two", "year": 2021, "doi": None},
    ]
    result = export_bib(articles)
    assert "@article{A2020One" in result
    assert "@article{B2021Two" in result


def test_export_bib_empty_list_returns_empty_string():
    assert export_bib([]) == ""
