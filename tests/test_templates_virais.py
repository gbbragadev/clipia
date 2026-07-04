"""Templates virais Q4 (curiosidades em lista + 'Voce Sabia?') — formatos do ICP principal.

Reaproveitam a infra do stock_narration (Pexels + keywords + Edge = 1 credito);
so o prompt de roteiro muda. O gate de valor real e o roteiro sair no formato
(lista numerada com gancho / fato unico) — validado por dogfood, aqui garantimos
o contrato estrutural.
"""

from app.templates import TEMPLATES, get_template


def test_templates_virais_registrados():
    for template_id in ("curiosidades_lista", "voce_sabia"):
        assert template_id in TEMPLATES
        assert get_template(template_id).id == template_id


def test_templates_virais_reusam_pipeline_stock():
    """Pexels + keywords + fullscreen: nenhum caminho novo no worker (custo Edge = 1)."""
    for template_id in ("curiosidades_lista", "voce_sabia"):
        tpl = get_template(template_id)
        assert tpl.media.source == "pexels"
        assert tpl.script.needs_keywords is True
        assert tpl.layout.type == "fullscreen"
        assert tpl.voice.provider == "edge"


def test_prompt_extra_impoe_formato_viral():
    lista = get_template("curiosidades_lista").script.prompt_extra
    assert "LISTA NUMERADA" in lista
    assert "CTA" in lista

    sabia = get_template("voce_sabia").script.prompt_extra
    assert "Voce sabia que" in sabia
    assert "MAXIMO 4 cenas" in sabia
