import asyncio
import re

import edge_tts


VOICE = "pt-BR-AntonioNeural"
RATE = "-10%"
PITCH = "+5Hz"


def synthesize_narration(text: str, output_path: str, speaker_wav: str = "") -> str:
    """Generate narration with natural prosody using Edge TTS."""
    ssml_text = _add_prosody(text)
    asyncio.run(_generate(ssml_text, output_path))
    return output_path


def _add_prosody(text: str) -> str:
    """Insert SSML breaks after sentences for natural pacing."""
    # Add 400ms pause after sentence-ending punctuation
    text = re.sub(r'([.!?])\s+', r'\1 <break time="400ms"/> ', text)
    # Add shorter pause after commas
    text = re.sub(r'(,)\s+', r'\1 <break time="200ms"/> ', text)
    return text


async def _generate(text: str, output_path: str) -> None:
    communicate = edge_tts.Communicate(
        text,
        VOICE,
        rate=RATE,
        pitch=PITCH,
    )
    await communicate.save(output_path)
