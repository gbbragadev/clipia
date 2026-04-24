from unittest.mock import MagicMock, patch

import pytest

from app.services.scriptwriter import generate_script

FAKE_CLAUDE_RESPONSE = """
{
  "title": "Teste",
  "narration": "Narração de teste completa com seis cenas distintas.",
  "scenes": [
    {"text": "cena 1", "visual_hint": "sala vitoriana", "duration_hint": 5},
    {"text": "cena 2", "visual_hint": "rua londres 1880", "duration_hint": 5},
    {"text": "cena 3", "visual_hint": "porto noturno", "duration_hint": 5},
    {"text": "cena 4", "visual_hint": "manuscrito antigo", "duration_hint": 5},
    {"text": "cena 5", "visual_hint": "retrato sepia homem", "duration_hint": 5},
    {"text": "cena 6", "visual_hint": "lapide no cemiterio", "duration_hint": 5}
  ],
  "hashtags": ["#shorts"]
}
"""


def _mock_anthropic(body: str = FAKE_CLAUDE_RESPONSE):
    msg = MagicMock()
    msg.content = [MagicMock(text=body)]
    client = MagicMock()
    client.messages.create.return_value = msg
    return client


def test_visual_hint_instruction_appears_for_ai_image_template():
    with patch("app.services.scriptwriter.anthropic.Anthropic") as cls:
        client = _mock_anthropic()
        cls.return_value = client
        generate_script("Titanic", "dramático", 30, "novelinha_historica")

    sent_prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "VISUAL_HINT" in sent_prompt.upper()
    assert "visual_hint" in sent_prompt


def test_visual_hint_instruction_absent_for_stock_template():
    stock_response = (
        FAKE_CLAUDE_RESPONSE.replace('"visual_hint": "sala vitoriana", ', "")
        .replace('"visual_hint": "rua londres 1880", ', "")
        .replace('"visual_hint": "porto noturno", ', "")
        .replace('"visual_hint": "manuscrito antigo", ', "")
        .replace('"visual_hint": "retrato sepia homem", ', "")
        .replace('"visual_hint": "lapide no cemiterio", ', "")
    )

    with patch("app.services.scriptwriter.anthropic.Anthropic") as cls:
        client = _mock_anthropic(stock_response)
        cls.return_value = client
        generate_script("teste", "informativo", 30, "stock_narration")

    sent_prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "VISUAL_HINT" not in sent_prompt.upper()


def test_script_preserves_visual_hint_in_output():
    with patch("app.services.scriptwriter.anthropic.Anthropic") as cls:
        cls.return_value = _mock_anthropic()
        script = generate_script("tema", "estilo", 30, "novelinha_historica")

    assert all("visual_hint" in s for s in script["scenes"])
    assert script["scenes"][0]["visual_hint"] == "sala vitoriana"


EMPTY_HINT_RESPONSE = """
{
  "title": "Teste",
  "narration": "narracao",
  "scenes": [
    {"text": "c1", "visual_hint": "", "duration_hint": 5},
    {"text": "c2", "visual_hint": "x", "duration_hint": 5},
    {"text": "c3", "visual_hint": "y", "duration_hint": 5},
    {"text": "c4", "visual_hint": "z", "duration_hint": 5},
    {"text": "c5", "visual_hint": "w", "duration_hint": 5},
    {"text": "c6", "visual_hint": "v", "duration_hint": 5}
  ],
  "hashtags": []
}
"""


def test_raises_when_visual_hint_empty_for_ai_image():
    from app.services.scriptwriter import ScriptValidationError

    with patch("app.services.scriptwriter.anthropic.Anthropic") as cls:
        client = _mock_anthropic(EMPTY_HINT_RESPONSE)
        cls.return_value = client
        with pytest.raises(ScriptValidationError):
            generate_script("tema", "estilo", 30, "novelinha_historica")
