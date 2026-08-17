from dataclasses import dataclass


@dataclass
class NormalizedResult:
    title: str
    authors: list[str]
    year: int | None
    doi: str | None
    source: str
    abstract: str | None = None
    oa_pdf_url: str | None = None


class SourceError(Exception):
    def __init__(self, source: str, message: str):
        self.source = source
        self.message = message
        super().__init__(f"{source}: {message}")
