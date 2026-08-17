from openai import OpenAI

from .config import DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

PROMPTS = {
    "summary": (
        "Sei un assistente di ricerca. Riassumi il seguente articolo "
        "scientifico in italiano, in 200-300 parole, evidenziando obiettivo, "
        "metodo e risultati principali.\n\nTesto:\n{text}"
    ),
    "metadata": (
        "Estrai dal seguente testo di articolo scientifico i campi: metodo, "
        "campione, risultati_principali, limiti. Rispondi in formato JSON.\n\n"
        "Testo:\n{text}"
    ),
    "verify": (
        "Confronta i metadati dichiarati (titolo: {title}, autori: {authors}, "
        "anno: {year}) con il contenuto del testo estratto dal PDF seguente. "
        "Indica se corrispondono (SI/NO) e perché.\n\nTesto:\n{text}"
    ),
}


class DeepSeekClient:
    def __init__(self, api_key: str, client: OpenAI | None = None):
        self._client = client or OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)

    def analyze(
        self,
        mode: str,
        text: str,
        *,
        title: str = "",
        authors: list[str] | None = None,
        year: int | None = None,
    ) -> str:
        if mode not in PROMPTS:
            raise ValueError(f"unknown mode: {mode}")
        prompt = PROMPTS[mode].format(
            text=text, title=title, authors=", ".join(authors or []), year=year
        )
        response = self._client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    def chat(self, text: str, messages: list[dict]) -> str:
        system = {
            "role": "system",
            "content": f"Rispondi a domande sul seguente articolo:\n\n{text}",
        }
        response = self._client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[system, *messages],
        )
        return response.choices[0].message.content
