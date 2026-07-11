"""Gera legendas ASS word-level (estilo TikTok, palavra ativa em coral).

Chunks de ate 3 palavras; um evento por palavra (ativa colorida).
Termina em 41.5s (o CTA carrega o proprio texto).
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).parent
WORDS = json.loads((HERE / "audio" / "words3-carla.json").read_text(encoding="utf-8"))["words"]
CUTOFF = 41.6
CORAL = r"\c&H385CF0&"  # #F05C38-ish em BGR
WHITE = r"\c&HFFFFFF&"

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Geist,96,&H00FFFFFF,&H00FFFFFF,&H00101014,&H96000000,-1,0,0,0,100,100,0,0,1,5,2,2,60,60,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ts(t):
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def chunks(words):
    out, cur = [], []
    for w in words:
        if w["start"] >= CUTOFF:
            break
        cur.append(w)
        text = w["word"].strip()
        if len(cur) == 3 or re.search(r"[.,!?…:]$", text):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def clean(t):
    return t.strip().upper()


lines = []
for ch in chunks(WORDS):
    for i, w in enumerate(ch):
        parts = []
        for j, x in enumerate(ch):
            col = CORAL if j == i else WHITE
            parts.append(f"{{{col}}}{clean(x['word'])}")
        text = " ".join(parts)
        start = w["start"]
        end = ch[i + 1]["start"] if i + 1 < len(ch) else max(w["end"], w["start"] + 0.12)
        # pop sutil na palavra ativa
        text = r"{\fad(30,0)}" + text
        lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},Cap,,0,0,0,,{text}")

out = HEADER + "\n".join(lines) + "\n"
(HERE / "renders" / "captions.ass").write_text(out, encoding="utf-8-sig")
print(f"captions.ass: {len(lines)} eventos")
