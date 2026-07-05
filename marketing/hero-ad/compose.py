"""Compose do hero ad ClipIA (1080x1920@30).

Estagios:
  segs   -> constroi S1..S6 em renders/tmp
  chain  -> xfades por estagio (tpad+xfade) + concats -> renders/video-silent.mp4
  finish -> legendas ASS + mix de audio -> renders/hero-nosting.mp4
Uso: python compose.py [segs|chain|finish|all]
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
CLIPS = HERE / "clips"
CAPS = HERE / "captures"
AUD = HERE / "audio"
REN = HERE / "renders"
TMP = REN / "tmp"
TMP.mkdir(parents=True, exist_ok=True)
OUTPUT_JOB = Path(r"C:\Dev\clipia\storage\output\8f4686a3-07ed-4c32-a4a0-dc9ec29e60fb.mp4")
FONTS = r"C:\Dev\clipia\frontend\node_modules\geist\dist\fonts\geist-sans"

ENC = ["-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p", "-an", "-r", "30"]


def run(cmd, label):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ERRO {label}:\n{r.stderr[-900:]}")
        sys.exit(1)
    print(f"  ok {label}")


def dur(path):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
    )
    return float(r.stdout.strip())


def cover(src, out, target_dur, src_dur=None, start=0.0, zoom_drift=0.0):
    """Fullscreen cover 1080x1920; opcionalmente slowdown para target e drift de zoom."""
    f = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    if src_dur and abs(src_dur - target_dur) > 0.05:
        f += f",setpts=PTS*{target_dur / src_dur:.5f}"
    f += ",fps=30"
    if zoom_drift:
        frames = int(target_dur * 30)
        f += (
            f",zoompan=z='1+{zoom_drift}*on/{frames}':d=1"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30"
        )
    cmd = ["ffmpeg", "-y", "-ss", str(start), "-i", str(src), "-vf", f, *ENC, str(out)]
    run(cmd, out.name)
    # apara com precisao pos-slowdown
    trim(out, target_dur)


def trim(path, t):
    tmp = path.with_suffix(".trim.mp4")
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(path),
            "-t",
            str(t),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "17",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(tmp),
        ],
        f"trim {path.name}",
    )
    tmp.replace(path)


def card(src, out, target_dur, start, fg_h=1700, zoom_drift=0.03, fg_w=None):
    """Apresentacao em card: fundo blur cover + captura nitida centrada + drift."""
    fg = f"scale=-2:{fg_h}" if not fg_w else f"scale={fg_w}:-2"
    frames = int(target_dur * 30)
    f = (
        f"[0:v]split[bg][fg];"
        f"[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        f"gblur=sigma=42,eq=brightness=-0.22:saturation=1.1[bgb];"
        f"[fg]{fg}[fgs];"
        f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2:format=auto,fps=30,"
        f"zoompan=z='1+{zoom_drift}*on/{frames}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-t",
            str(target_dur),
            "-i",
            str(src),
            "-filter_complex",
            f,
            *ENC,
            str(out),
        ],
        out.name,
    )


def concat(files, out):
    lst = TMP / "concat.txt"
    lst.write_text("".join(f"file '{f.as_posix()}'\n" for f in files), encoding="utf-8")
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
            "-an",
            str(out),
        ],
        f"concat {out.name}",
    )


def xfade(a, b, out, transition, d):
    off = dur(a)
    apad = TMP / (a.stem + "_pad.mp4")
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(a),
            "-vf",
            f"tpad=stop_mode=clone:stop_duration={d}",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "17",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(apad),
        ],
        f"tpad {a.name}",
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(apad),
            "-i",
            str(b),
            "-filter_complex",
            f"[0:v][1:v]xfade=transition={transition}:duration={d}:offset={off}",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "17",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(out),
        ],
        f"xfade {transition} -> {out.name}",
    )


def segs():
    print("[segs]")
    cover(CLIPS / "b1-coral.mp4", TMP / "s1.mp4", 7.0, src_dur=5.0)
    cover(CLIPS / "b2-coral.mp4", TMP / "s2.mp4", 7.0, src_dur=6.0)
    card(CAPS / "cap-trends.webm", TMP / "s3a.mp4", 5.4, start=3.2)
    card(CAPS / "cap-dashboard.webm", TMP / "s3b.mp4", 2.2, start=7.0)
    card(OUTPUT_JOB, TMP / "s3c.mp4", 6.0, start=0.5)
    card(CAPS / "cap-editor-desktop.webm", TMP / "s4.mp4", 8.4, start=9.0, fg_w=1020, fg_h=None, zoom_drift=0.05)
    cover(CLIPS / "b5-coral.mp4", TMP / "s5.mp4", 5.9, src_dur=6.0)
    # CTA: png estatico -> video com fade-in e settle de zoom
    run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-framerate",
            "30",
            "-t",
            "5.5",
            "-i",
            str(REN / "cta.png"),
            "-vf",
            "scale=1188:2112,zoompan=z='max(1.10-0.10*on/60,1.0)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30,fade=t=in:st=0:d=0.25",
            *ENC,
            str(TMP / "s6.mp4"),
        ],
        "s6 (CTA)",
    )


def chain():
    print("[chain]")
    concat([TMP / "s3b.mp4", TMP / "s3a.mp4", TMP / "s3c.mp4"], TMP / "s3.mp4")
    xfade(TMP / "s1.mp4", TMP / "s2.mp4", TMP / "x1.mp4", "dissolve", 0.5)
    xfade(TMP / "x1.mp4", TMP / "s3.mp4", TMP / "x2.mp4", "fadeblack", 0.4)
    xfade(TMP / "x2.mp4", TMP / "s4.mp4", TMP / "x3.mp4", "dissolve", 0.4)
    concat([TMP / "x3.mp4", TMP / "s5.mp4"], TMP / "x4.mp4")
    xfade(TMP / "x4.mp4", TMP / "s6.mp4", REN / "video-silent.mp4", "fadeblack", 0.3)
    print(f"  video-silent: {dur(REN / 'video-silent.mp4'):.2f}s")


def finish():
    print("[finish]")
    total = dur(REN / "video-silent.mp4")
    ass = (REN / "captions.ass").as_posix().replace(":", r"\:")
    fonts = FONTS.replace("\\", "/").replace(":", r"\:")
    # 1) legendas queimadas
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(REN / "video-silent.mp4"),
            "-vf",
            f"subtitles='{ass}':fontsdir='{fonts}'",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "17",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(TMP / "video-caps.mp4"),
        ],
        "legendas",
    )
    # 2) mix: VO + musica (sidechain duck) + SFX posicionados
    sfx = [
        ("sfx-whoosh.mp3", 6600, 0.55),
        ("sfx-whoosh.mp3", 13500, 0.55),
        ("sfx-keys.mp3", 14300, 0.45),
        ("sfx-click.mp3", 21500, 0.7),
        ("sfx-whoosh.mp3", 27300, 0.5),
        ("sfx-riser.mp3", 39300, 0.7),
        ("sfx-impact.mp3", 41850, 0.85),
        ("sfx-click.mp3", 43900, 0.6),
    ]
    inputs = ["-i", str(AUD / "vo3-carla.mp3"), "-i", str(AUD / "music.mp3")]
    for name, _, _ in sfx:
        inputs += ["-i", str(AUD / name)]
    fc = [
        "[0:a]aresample=48000,asplit=2[vo][voSC]",
        f"[1:a]aresample=48000,atrim=0:{total},volume=0.55,afade=t=in:st=0:d=0.8,"
        f"afade=t=out:st={total - 1.4:.2f}:d=1.4[mu]",
        "[mu][voSC]sidechaincompress=threshold=0.035:ratio=7:attack=25:release=420[mud]",
    ]
    mix_ins = "[vo][mud]"
    for i, (name, delay, vol) in enumerate(sfx):
        fc.append(f"[{i + 2}:a]aresample=48000,volume={vol},adelay={delay}|{delay}[sf{i}]")
        mix_ins += f"[sf{i}]"
    fc.append(f"{mix_ins}amix=inputs={len(sfx) + 2}:normalize=0[premix]")
    fc.append("[premix]loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
    run(
        [
            "ffmpeg",
            "-y",
            *inputs,
            "-filter_complex",
            ";".join(fc),
            "-map",
            "[aout]",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-t",
            str(total),
            str(TMP / "mix.m4a"),
        ],
        "mix de audio",
    )
    # 3) mux
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(TMP / "video-caps.mp4"),
            "-i",
            str(TMP / "mix.m4a"),
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(REN / "hero-nosting.mp4"),
        ],
        "mux final",
    )
    print(f"  hero-nosting.mp4: {dur(REN / 'hero-nosting.mp4'):.2f}s")


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    if stage in ("segs", "all"):
        segs()
    if stage in ("chain", "all"):
        chain()
    if stage in ("finish", "all"):
        finish()
