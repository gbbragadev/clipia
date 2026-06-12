import json
from unittest.mock import patch

from app.services.scriptwriter import generate_script


def test_generate_script_returns_valid_structure():
    fake = json.dumps(
        {
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
        }
    )

    with patch("app.services.scriptwriter.complete_text", return_value=fake):
        result = generate_script("curiosidades do oceano", "educational", 45)

    assert "title" in result
    assert "narration" in result
    assert "scenes" in result
    assert len(result["scenes"]) >= 1
    assert "keywords_en" in result["scenes"][0]


def test_generate_script_applies_default_fade_transitions():
    fake = json.dumps(
        {
            "title": "T",
            "narration": "abc",
            "scenes": [
                {"text": "a", "keywords_en": [], "duration_hint": 10},
                {"text": "b", "keywords_en": [], "duration_hint": 10},
                {"text": "c", "keywords_en": [], "duration_hint": 10},
            ],
            "hashtags": [],
        }
    )
    with patch("app.services.scriptwriter.complete_text", return_value=fake):
        result = generate_script("tema", "educational", 30)

    scenes = result["scenes"]
    assert "transition" not in scenes[0] or scenes[0].get("transition") in (None, "none")
    assert scenes[1]["transition"] == "fade"
    assert scenes[2]["transition"] == "fade"
