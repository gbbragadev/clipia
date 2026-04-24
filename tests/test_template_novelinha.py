from app.templates import TEMPLATES, get_template


def test_novelinha_historica_is_registered():
    assert "novelinha_historica" in TEMPLATES
    tpl = get_template("novelinha_historica")
    assert tpl.id == "novelinha_historica"


def test_novelinha_uses_ai_image_source():
    tpl = get_template("novelinha_historica")
    assert tpl.media.source == "ai_image"
    assert tpl.media.image_size == "1024x1536"
    assert tpl.media.image_quality == "medium"
    assert tpl.media.ken_burns is True
    assert "fotografia de época" in tpl.media.style_suffix.lower() or "ilustração" in tpl.media.style_suffix.lower()


def test_novelinha_script_needs_visual_hint():
    tpl = get_template("novelinha_historica")
    assert tpl.script.needs_visual_hint is True
    assert tpl.script.needs_keywords is False


def test_novelinha_voice_is_placeholder():
    tpl = get_template("novelinha_historica")
    assert tpl.voice.voice_id == "TODO_VOICE_ID"
