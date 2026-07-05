"""Cuts menores derivados do hero (legendas ja queimadas nele).

cutA teaser: 0-13.5 (hook + negacao) + CTA -> ~19s
cutB demo:   13.9-27.7 (voce da um tema ... voz) + CTA -> ~19s
Audio: fade no fim do trecho; CTA fica so com o rabo da musica (fade out).
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
REN = HERE / "renders"
TMP = REN / "tmp"
HERO = REN / "hero-nosting.mp4"
S6 = TMP / "s6.mp4"


def run(cmd, label):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ERRO {label}:\n{r.stderr[-700:]}")
        sys.exit(1)
    print(f"  ok {label}")


def dur(p):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
        capture_output=True,
        text=True,
    )
    return float(r.stdout.strip())


def cut(name, start, end, cta_dur=4.5):
    seg = TMP / f"{name}-seg.mp4"
    body = end - start
    # trecho do hero com fade de video/audio no fim
    run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-t",
            str(body),
            "-i",
            str(HERO),
            "-vf",
            f"fade=t=out:st={body - 0.35}:d=0.35,fps=30",
            "-af",
            f"afade=t=out:st={body - 0.6}:d=0.6",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "17",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(seg),
        ],
        f"{name} corpo",
    )
    # CTA curto com fade-in + audio silencioso (mantem stream de audio p/ concat)
    cta = TMP / f"{name}-cta.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-t",
            str(cta_dur),
            "-i",
            str(S6),
            "-f",
            "lavfi",
            "-t",
            str(cta_dur),
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-vf",
            "fade=t=in:st=0:d=0.3,fps=30",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "17",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(cta),
        ],
        f"{name} cta",
    )
    lst = TMP / f"{name}.txt"
    lst.write_text(f"file '{seg.as_posix()}'\nfile '{cta.as_posix()}'\n", encoding="utf-8")
    out = REN / f"{name}.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(lst),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "17",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(out),
        ],
        f"{name} concat",
    )
    print(f"  {name}.mp4: {dur(out):.1f}s")
    return out


cut("cutA-teaser", 0.0, 13.6)
cut("cutB-demo", 13.9, 27.7)
