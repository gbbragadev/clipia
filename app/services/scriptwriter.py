import json

import anthropic

from app.config import settings

SCRIPT_PROMPT = """Gere um roteiro para video curto (short/reels) sobre: {topic}

Estilo: {style}
Duracao alvo: {duration} segundos (aproximadamente {word_count} palavras)
Idioma: Portugues brasileiro (pt-BR)

Retorne APENAS JSON valido com esta estrutura:
{{
  "title": "titulo curto e chamativo",
  "narration": "texto completo da narracao em pt-BR",
  "scenes": [
    {{
      "text": "trecho da narracao para esta cena",
      "keywords_en": ["english", "search", "terms"],
      "duration_hint": 8
    }}
  ],
  "hashtags": ["#shorts", "#tag"]
}}

Regras:
- A narracao deve ser envolvente e natural, como se falasse diretamente com o espectador
- Divida em 3-6 cenas de 5-15 segundos cada
- Keywords em ingles para busca de stock footage
- Nao use emojis na narracao
- Comece com um gancho forte nos primeiros 3 segundos"""


def generate_script(topic: str, style: str, duration_target: int) -> dict:
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    word_count = int(duration_target * 2.5)

    message = client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": SCRIPT_PROMPT.format(
                topic=topic,
                style=style,
                duration=duration_target,
                word_count=word_count,
            ),
        }],
    )

    raw = message.content[0].text
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(raw)
