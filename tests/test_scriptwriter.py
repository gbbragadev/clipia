import json
from unittest.mock import MagicMock, patch

from app.services.scriptwriter import generate_script


def test_generate_script_returns_valid_structure():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "title": "Curiosidades do Oceano",
        "narration": "Voce sabia que o oceano cobre mais de setenta por cento da Terra?",
        "scenes": [
            {
                "text": "Voce sabia que o oceano cobre mais de setenta por cento da Terra?",
                "keywords_en": ["ocean", "earth", "planet"],
                "duration_hint": 8,
            }
        ],
        "hashtags": ["#shorts", "#oceano"],
    }))]

    with patch("app.services.scriptwriter.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = mock_response
        result = generate_script("curiosidades do oceano", "educational", 45)

    assert "title" in result
    assert "narration" in result
    assert "scenes" in result
    assert len(result["scenes"]) >= 1
    assert "keywords_en" in result["scenes"][0]
