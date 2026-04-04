from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
)

from app.config import settings
from app.services.subtitles import build_subtitle_clips


def compose_short(
    scenes: list[dict],
    media_paths: list[str],
    audio_path: str,
    words: list[dict],
    output_path: str,
) -> str:
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration

    bg_clips = []
    for i, scene in enumerate(scenes):
        if i >= len(media_paths):
            break
        path = media_paths[i]
        if path.lower().endswith((".jpg", ".jpeg", ".png")):
            clip = ImageClip(path).with_duration(scene["duration_hint"])
        else:
            clip = VideoFileClip(path)

        clip = clip.resized(height=settings.VIDEO_HEIGHT)
        if clip.w > settings.VIDEO_WIDTH:
            clip = clip.cropped(
                x_center=clip.w // 2,
                width=settings.VIDEO_WIDTH,
                y_center=clip.h // 2,
                height=settings.VIDEO_HEIGHT,
            )
        max_dur = clip.duration if hasattr(clip, "duration") and clip.duration else scene["duration_hint"]
        clip = clip.with_duration(min(scene["duration_hint"], max_dur))
        bg_clips.append(clip)

    background = concatenate_videoclips(bg_clips)
    if background.duration < total_duration:
        background = background.with_duration(total_duration)

    subtitle_clips = build_subtitle_clips(words, total_duration=total_duration)

    final = CompositeVideoClip(
        [background] + subtitle_clips,
        size=(settings.VIDEO_WIDTH, settings.VIDEO_HEIGHT),
    ).with_audio(audio).with_duration(total_duration)

    final.write_videofile(
        output_path,
        fps=settings.VIDEO_FPS,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
        logger=None,
    )
    return output_path
