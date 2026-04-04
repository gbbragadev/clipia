import asyncio
import edge_tts


VOICE = "pt-BR-AntonioNeural"  # Male, natural. Alt: pt-BR-FranciscaNeural (female)


def synthesize_narration(text: str, output_path: str, speaker_wav: str = "") -> str:
    """Generate narration audio using Microsoft Edge TTS (neural voices)."""
    asyncio.run(_generate(text, output_path))
    return output_path


async def _generate(text: str, output_path: str) -> None:
    communicate = edge_tts.Communicate(text, VOICE, rate="-5%")
    await communicate.save(output_path)
