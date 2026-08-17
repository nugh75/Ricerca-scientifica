import re
import unicodedata


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]", "", text)


def make_citekey(authors: list[str], year: int | None, title: str) -> str:
    if authors and authors[0].strip():
        last_word = authors[0].split()[-1]
        author_part = _slug(last_word) or "Anon"
    else:
        author_part = "Anon"
    year_part = str(year) if year else "nd"
    title_words = [w for w in re.split(r"\s+", title) if w]
    title_part = _slug(title_words[0]) if title_words else ""
    return f"{author_part}{year_part}{title_part}"


def to_bibtex(article: dict) -> str:
    key = article.get("bib_key") or make_citekey(
        article["authors"], article.get("year"), article["title"]
    )
    authors = " and ".join(article["authors"])
    year = article.get("year")
    fields = [
        ("author", authors),
        ("title", article["title"]),
        ("year", str(year) if year else ""),
        ("doi", article.get("doi") or ""),
    ]
    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields if v)
    return f"@article{{{key},\n{body}\n}}\n"


def export_bib(articles: list[dict]) -> str:
    return "\n".join(to_bibtex(a) for a in articles)
