"""Backfill de thumbnails: gera output/{id}.jpg para todo MP4 sem poster.

Jobs antigos (anteriores ao thumbnail no finalize) ganham poster retroativo.
Idempotente: pula se o .jpg já existe. Rodar no venv312, raiz do repo:
    python scripts/backfill_thumbnails.py
"""

import subprocess
import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "storage" / "output"


def main() -> int:
    if not OUTPUT_DIR.exists():
        print(f"Sem diretorio de output em {OUTPUT_DIR}")
        return 1
    done = skipped = failed = 0
    for mp4 in sorted(OUTPUT_DIR.glob("*.mp4")):
        jpg = mp4.with_suffix(".jpg")
        if jpg.exists():
            skipped += 1
            continue
        r = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                "1.5",
                "-i",
                str(mp4),
                "-frames:v",
                "1",
                "-vf",
                "scale=360:-2",
                "-q:v",
                "4",
                str(jpg),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode == 0 and jpg.exists():
            done += 1
        else:
            failed += 1
            print(f"FALHA {mp4.name}: {r.stderr[-200:]}")
    print(f"Thumbnails: {done} gerados, {skipped} ja existiam, {failed} falharam")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
