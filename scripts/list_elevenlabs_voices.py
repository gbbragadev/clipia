"""Lista as vozes da conta ElevenLabs com labels completos p/ escolher as do diálogo.

Rode: python -m scripts.list_elevenlabs_voices

`list_voices()` do provider fixa language="multilingual"; aqui vamos direto ao SDK
(client.voices.get_all()) para ver accent/language/description nos labels — é isso que
permite julgar quais vozes soam pt-BR (Fernanda KHmfNHtEjHhLK9eER20w é a feminina conhecida).
"""

import json

from app.services.elevenlabs_provider import _get_client


def main():
    client = _get_client()
    response = client.voices.get_all()
    for v in response.voices:
        labels = v.labels or {}
        # destaca quem parece pt-BR / brasileiro nos labels
        blob = json.dumps(labels, ensure_ascii=False).lower()
        flag = "  <== PT/BR?" if ("portug" in blob or "brazil" in blob or "brasil" in blob) else ""
        print(f"{v.voice_id}\t{v.name}\t[{v.category}]\t{labels}{flag}")


if __name__ == "__main__":
    main()
