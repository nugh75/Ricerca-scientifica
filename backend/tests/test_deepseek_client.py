import pytest

from litreview.deepseek_client import DeepSeekClient


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeCompletion:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, reply="canned reply"):
        self.reply = reply
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return FakeCompletion(self.reply)


class FakeChat:
    def __init__(self, reply="canned reply"):
        self.completions = FakeCompletions(reply)


class FakeOpenAIClient:
    def __init__(self, reply="canned reply"):
        self.chat = FakeChat(reply)


def test_analyze_summary_sends_prompt_and_returns_content():
    fake = FakeOpenAIClient(reply="This is a summary.")
    client = DeepSeekClient(api_key="sk-test", client=fake)
    result = client.analyze("summary", "full article text", title="T", authors=["A"], year=2020)
    assert result == "This is a summary."
    messages = fake.chat.completions.last_kwargs["messages"]
    assert "full article text" in messages[0]["content"]
    assert fake.chat.completions.last_kwargs["model"] == "deepseek-chat"


def test_analyze_metadata_mode_uses_metadata_prompt():
    fake = FakeOpenAIClient(reply="{}")
    client = DeepSeekClient(api_key="sk-test", client=fake)
    client.analyze("metadata", "text")
    content = fake.chat.completions.last_kwargs["messages"][0]["content"]
    assert "JSON" in content


def test_analyze_verify_mode_includes_title_authors_year():
    fake = FakeOpenAIClient(reply="SI")
    client = DeepSeekClient(api_key="sk-test", client=fake)
    client.analyze("verify", "text", title="My Title", authors=["Jane Smith"], year=2019)
    content = fake.chat.completions.last_kwargs["messages"][0]["content"]
    assert "My Title" in content
    assert "Jane Smith" in content
    assert "2019" in content


def test_analyze_unknown_mode_raises_value_error():
    fake = FakeOpenAIClient()
    client = DeepSeekClient(api_key="sk-test", client=fake)
    with pytest.raises(ValueError):
        client.analyze("not_a_mode", "text")


def test_chat_includes_article_text_as_system_message_and_history():
    fake = FakeOpenAIClient(reply="assistant reply")
    client = DeepSeekClient(api_key="sk-test", client=fake)
    history = [{"role": "user", "content": "What is the sample size?"}]
    result = client.chat("article full text", history)
    assert result == "assistant reply"
    sent_messages = fake.chat.completions.last_kwargs["messages"]
    assert sent_messages[0]["role"] == "system"
    assert "article full text" in sent_messages[0]["content"]
    assert sent_messages[1:] == history
