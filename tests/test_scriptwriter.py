import json
from unittest.mock import patch

import pytest

from app.services.scriptwriter import ScriptValidationError, _parse_script_json, generate_script


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

    with patch("app.services.scriptwriter.complete_text_ex", return_value=(fake, "openai")):
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
    with patch("app.services.scriptwriter.complete_text_ex", return_value=(fake, "openai")):
        result = generate_script("tema", "educational", 30)

    scenes = result["scenes"]
    assert "transition" not in scenes[0] or scenes[0].get("transition") in (None, "none")
    assert scenes[1]["transition"] == "fade"
    assert scenes[2]["transition"] == "fade"


def test_generate_script_clamps_excessive_scenes():
    """Anti-burn: LLM gerando cenas demais p/ a duracao e clampado (custo de midia paga escala por cena)."""
    scenes = [{"text": f"cena {i}", "keywords_en": [], "duration_hint": 5} for i in range(30)]
    fake = json.dumps({"title": "T", "narration": "n", "scenes": scenes, "hashtags": []})
    with patch("app.services.scriptwriter.complete_text_ex", return_value=(fake, "openai")):
        result = generate_script("tema", "educational", 30)  # 30s -> max(6, ceil(30/4)) = 8
    assert len(result["scenes"]) == 8


def test_generate_script_keeps_scenes_for_long_videos():
    """Videos longos legitimos NAO sao cortados: o clamp e proporcional a duracao, nao um teto fixo."""
    scenes = [{"text": f"cena {i}", "keywords_en": [], "duration_hint": 6} for i in range(20)]
    fake = json.dumps({"title": "T", "narration": "n", "scenes": scenes, "hashtags": []})
    with patch("app.services.scriptwriter.complete_text_ex", return_value=(fake, "openai")):
        result = generate_script("tema", "educational", 180)  # 180s -> min(40, 45) = 40 >= 20, mantem
    assert len(result["scenes"]) == 20


def test_parse_script_json_accepts_clean_json():
    raw = json.dumps({"title": "T", "scenes": [{"duration_hint": 7}]})
    result = _parse_script_json(raw)
    assert result == {"title": "T", "scenes": [{"duration_hint": 7}]}


def test_parse_script_json_recovers_json_wrapped_in_prose():
    raw = (
        "Claro! Aqui esta o roteiro solicitado:\n"
        '{"title": "Oceano", "narration": "texto", "scenes": [{"duration_hint": 8}]}\n'
        "Espero que goste do resultado!"
    )
    result = _parse_script_json(raw)
    assert result["title"] == "Oceano"
    assert result["scenes"][0]["duration_hint"] == 8


def test_parse_script_json_raises_on_completely_invalid_input():
    with pytest.raises(ScriptValidationError) as exc_info:
        _parse_script_json("isso nao tem nenhum objeto json valido aqui")

    msg = str(exc_info.value)
    assert "JSON invalido" in msg
    assert "isso nao tem nenhum objeto json valido aqui" in msg


def test_format_adapt_instruction_in_default_template():
    """Guardrail: prompt deve conter ADAPTACAO DE FORMATO para template default."""
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

    with patch("app.services.scriptwriter.complete_text_ex") as mock_llm:
        mock_llm.return_value = (fake, "openai")
        result = generate_script("curiosidades do oceano", "educational", 45)

    # Verify the LLM was called
    assert mock_llm.called
    # Extract the prompt that was sent to the LLM
    prompt_sent = mock_llm.call_args[0][0]
    assert "ADAPTACAO DE FORMATO" in prompt_sent
    assert result is not None


def test_format_adapt_instruction_in_curiosidades_lista_template():
    """Guardrail: prompt deve conter ADAPTACAO DE FORMATO para template curiosidades_lista."""
    fake = json.dumps(
        {
            "title": "Top 5 Curiosidades",
            "narration": "Voce sabia...",
            "scenes": [
                {
                    "text": "Numero 1: fato um",
                    "keywords_en": ["fact", "curiosity"],
                    "duration_hint": 8,
                }
            ],
            "hashtags": ["#shorts"],
        }
    )

    with patch("app.services.scriptwriter.complete_text_ex") as mock_llm:
        mock_llm.return_value = (fake, "openai")
        result = generate_script("top 5 curiosidades", "educational", 45, template_id="curiosidades_lista")

    # Verify the LLM was called
    assert mock_llm.called
    # Extract the prompt that was sent to the LLM
    prompt_sent = mock_llm.call_args[0][0]
    assert "ADAPTACAO DE FORMATO" in prompt_sent
    assert result is not None
