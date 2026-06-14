"""Gera o asset de audio do outro (sussurro 'clipia.com.br') e, com --promote,
copia para app/assets/outro/whisper.wav.

Receita travada (validada por WhatsApp 2026-06-14): voz Fernanda (PT-BR),
modelo eleven_v3 com tag [whispers], texto 'clipia.com.br', atempo 1.60x, WAV mono.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from elevenlabs import ElevenLabs

BASE_DIR = Path(__file__).resolve().parent.parent
TAKES_DIR = BASE_DIR / "storage" / "outro_takes"
ASSET_PATH = BASE_DIR / "app" / "assets" / "outro" / "whisper.wav"

VOICE_ID = "KHmfNHtEjHhLK9eER20w"  # Fernanda - PT-BR
MODEL = "eleven_v3"
TEXT = "clipia.com.br"
TEMPO = 1.60


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default=VOICE_ID)
    ap.add_argument("--tempo", type=float, default=TEMPO)
    ap.add_argument("--text", default=TEXT)
    ap.add_argument("--promote", action="store_true", help="copia o resultado p/ o asset oficial")
    args = ap.parse_args()

    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        print("ELEVENLABS_API_KEY ausente", file=sys.stderr)
        return 1

    TAKES_DIR.mkdir(parents=True, exist_ok=True)
    raw_mp3 = TAKES_DIR / "outro_raw.mp3"
    final_wav = TAKES_DIR / "outro_final.wav"

    client = ElevenLabs(api_key=key)
    audio = client.text_to_speech.convert(
        voice_id=args.voice,
        text=f"[whispers] {args.text}",
        model_id=MODEL,
        output_format="mp3_44100_128",
    )
    with open(raw_mp3, "wb") as f:
        for chunk in audio:
            f.write(chunk)
    print(f"TTS gerado: {raw_mp3}")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(raw_mp3),
            "-filter:a",
            f"atempo={args.tempo}",
            "-ar",
            "44100",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(final_wav),
        ],
        check=True,
        capture_output=True,
    )
    dur = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(final_wav)],
        capture_output=True,
        text=True,
    ).stdout.strip()
    print(f"WAV final: {final_wav} ({dur}s)")

    if args.promote:
        ASSET_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(final_wav, ASSET_PATH)
        print(f"Promovido p/ asset oficial: {ASSET_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
