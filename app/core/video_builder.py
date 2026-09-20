"""Video Builder V2: Multi-Clip B-Roll, Ken Burns zoom, and Active Word Highlighted Subtitles.

Features:
- Multi-Clip B-Roll concatenation: slices 3-5 second scenes from available videos in assets/video/.
- Ken Burns slow continuous zoom when only a single background video is present.
- Active-word highlighted subtitle animation (Karaoke style: active word #FFD700, others #FFFFFF).
- Clean audio mixing with -20dB background music ducking.
"""

from pathlib import Path
import logging
import os
import random
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from moviepy import (
    VideoFileClip,
    AudioFileClip,
    ImageClip,
    CompositeVideoClip,
    CompositeAudioClip,
    concatenate_videoclips,
    afx,
    vfx,
)

logger = logging.getLogger(__name__)

FONTS_PRIORITY = [
    r"C:\Windows\Fonts\impact.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\seguiui.ttf",
    r"C:\Windows\Fonts\verdana.ttf",
]


def resolve_system_font_path() -> str | None:
    """Find the best available TTF bold font on the system."""
    for font_path in FONTS_PRIORITY:
        if os.path.isabs(font_path) and os.path.exists(font_path):
            return font_path
    return None


def crop_scale_clip_to_frame(
    clip: VideoFileClip,
    target_size: tuple[int, int] = (1080, 1920),
) -> VideoFileClip:
    """Scale and center-crop an individual video clip to exact target resolution."""
    target_w, target_h = target_size
    orig_w, orig_h = clip.size

    scale_factor = max(target_w / orig_w, target_h / orig_h)
    new_w = int(round(orig_w * scale_factor))
    new_h = int(round(orig_h * scale_factor))

    if new_w % 2 != 0:
        new_w += 1
    if new_h % 2 != 0:
        new_h += 1

    scaled = clip.resized(new_size=(new_w, new_h))
    return scaled.cropped(
        width=target_w,
        height=target_h,
        x_center=new_w // 2,
        y_center=new_h // 2,
    )


def apply_ken_burns_zoom(
    clip: VideoFileClip,
    duration: float,
    zoom_ratio: float = 0.05,
    target_size: tuple[int, int] = (1080, 1920),
) -> VideoFileClip:
    """Apply a smooth continuous Ken Burns slow zoom to a clip."""
    target_w, target_h = target_size

    # Resize over time
    zoomed = clip.resized(lambda t: 1.0 + zoom_ratio * (t / max(duration, 0.1)))

    def crop_center_frame(get_frame: Any, t: float) -> np.ndarray:
        frame = get_frame(t)
        fh, fw = frame.shape[:2]
        x1 = max(0, (fw - target_w) // 2)
        y1 = max(0, (fh - target_h) // 2)
        return frame[y1 : y1 + target_h, x1 : x1 + target_w]

    return zoomed.transform(crop_center_frame)


def prepare_broll_background(
    bg_input: Path | str | None,
    target_duration: float,
    target_size: tuple[int, int] = (1080, 1920),
) -> tuple[VideoFileClip, list[VideoFileClip]]:
    """Build multi-clip B-roll background or apply Ken Burns slow zoom if single video.

    Returns:
        Tuple of (composed background clip, list of loaded raw clips for resource cleanup).
    """
    opened_clips: list[VideoFileClip] = []

    # Detect available background videos
    video_files: list[Path] = []
    if bg_input:
        p = Path(bg_input).resolve()
        if p.is_dir():
            video_files = list(p.glob("*.mp4"))
        elif p.is_file():
            # Check if directory contains sibling videos
            parent_mp4s = list(p.parent.glob("*.mp4"))
            video_files = parent_mp4s if len(parent_mp4s) > 1 else [p]

    if not video_files:
        raise FileNotFoundError(f"No valid background video files found at {bg_input}")

    # Case A: Multiple video files -> Multi-clip B-Roll with 3-5s scene cuts
    if len(video_files) >= 2:
        logger.info(
            "Multi-Clip B-Roll active: %d clips available. Creating 3-5s scene cuts.",
            len(video_files),
        )
        scene_clips: list[VideoFileClip] = []
        accumulated_time = 0.0

        shuffled_pool = list(video_files)
        random.shuffle(shuffled_pool)
        pool_idx = 0

        while accumulated_time < target_duration:
            chosen_file = shuffled_pool[pool_idx % len(shuffled_pool)]
            pool_idx += 1

            raw_clip = VideoFileClip(str(chosen_file)).without_audio()
            opened_clips.append(raw_clip)

            scene_dur = round(random.uniform(3.0, 4.5), 2)
            remaining_dur = target_duration - accumulated_time
            actual_scene_dur = min(scene_dur, remaining_dur)

            # Pick random subclip window if raw clip is longer than scene
            if raw_clip.duration > actual_scene_dur:
                max_start = max(0.0, raw_clip.duration - actual_scene_dur)
                sub_start = random.uniform(0.0, max_start)
                sub = raw_clip.subclipped(sub_start, sub_start + actual_scene_dur)
            else:
                sub = raw_clip.with_effects([vfx.Loop(duration=actual_scene_dur)])

            cropped_scene = crop_scale_clip_to_frame(sub, target_size=target_size)
            scene_clips.append(cropped_scene)
            accumulated_time += actual_scene_dur

        final_bg = concatenate_videoclips(scene_clips, method="compose")
        return final_bg, opened_clips

    # Case B: Single video -> Looped + Ken Burns continuous slow zoom
    single_file = video_files[0]
    logger.info("Single background clip detected. Applying Ken Burns slow continuous zoom.")
    raw_clip = VideoFileClip(str(single_file)).without_audio()
    opened_clips.append(raw_clip)

    if raw_clip.duration < target_duration:
        base_clip = raw_clip.with_effects([vfx.Loop(duration=target_duration)])
    else:
        base_clip = raw_clip.subclipped(0, target_duration)

    scaled_base = crop_scale_clip_to_frame(base_clip, target_size=target_size)
    ken_burns_bg = apply_ken_burns_zoom(
        scaled_base,
        duration=target_duration,
        zoom_ratio=0.06,
        target_size=target_size,
    )
    return ken_burns_bg, opened_clips


def build_active_word_subtitle_clips(
    transcript_data: list[dict[str, Any]],
    target_size: tuple[int, int] = (1080, 1920),
    font_size: int = 62,
    active_color: str = "#FFD700",  # Intense gold highlight
    inactive_color: str = "#FFFFFF",  # Crisp white
    stroke_color: str = "black",
    stroke_width: int = 5,
    y_position: int = 1120,  # Optimal safe zone for TikTok
    words_per_phrase: int = 3,
) -> list[ImageClip]:
    """Generate dynamic subtitles where words in each phrase stay stable and highlight synchronously."""
    if not transcript_data:
        return []

    target_w, target_h = target_size
    font_path = resolve_system_font_path()
    try:
        font = (
            ImageFont.truetype(font_path, font_size)
            if font_path
            else ImageFont.load_default()
        )
    except Exception:
        font = ImageFont.load_default()

    # 1. Group transcript words into short rhythmic phrases (2-4 words)
    phrases: list[list[dict[str, Any]]] = []
    current_phrase: list[dict[str, Any]] = []

    for i, word_item in enumerate(transcript_data):
        current_phrase.append(word_item)
        word_text = word_item.get("word", "").strip()

        is_full = len(current_phrase) >= words_per_phrase
        ends_punctuation = bool(word_text and word_text[-1] in ".!?;:")
        is_last = i == len(transcript_data) - 1

        if is_full or ends_punctuation or is_last:
            phrases.append(current_phrase)
            current_phrase = []

    subtitle_clips: list[ImageClip] = []

    # 2. Render each phrase with synchronized active word highlighting
    for p_idx, phrase in enumerate(phrases):
        words_text = [w["word"].strip().upper() for w in phrase]

        # Calculate horizontal dimensions
        dummy_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        dummy_draw = ImageDraw.Draw(dummy_img)

        # Measure space width
        space_bbox = dummy_draw.textbbox((0, 0), " ", font=font)
        space_w = space_bbox[2] - space_bbox[0]

        word_widths: list[int] = []
        max_word_h = 0
        for wt in words_text:
            bbox = dummy_draw.textbbox((0, 0), wt, font=font, stroke_width=stroke_width)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            word_widths.append(w)
            if h > max_word_h:
                max_word_h = h

        total_text_width = sum(word_widths) + (len(words_text) - 1) * space_w
        canvas_w = min(target_w - 80, total_text_width + 60)
        canvas_h = max_word_h + stroke_width * 4 + 30

        # Adjust text placement inside canvas
        start_x = max(10, (canvas_w - total_text_width) // 2)
        start_y = 10

        # For each active word in this phrase, render an ImageClip
        for active_idx, active_word_item in enumerate(phrase):
            t_start = float(active_word_item["start"])
            t_end = float(active_word_item["end"])

            # Bridge tiny gap to next word
            if active_idx < len(phrase) - 1:
                next_start = float(phrase[active_idx + 1]["start"])
                if next_start > t_end and (next_start - t_end) <= 0.3:
                    t_end = next_start
            elif p_idx < len(phrases) - 1:
                next_phrase_start = float(phrases[p_idx + 1][0]["start"])
                if next_phrase_start > t_end and (next_phrase_start - t_end) <= 0.25:
                    t_end = next_phrase_start

            duration = max(0.08, t_end - t_start)

            # Draw the frame
            img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            curr_x = start_x
            for w_i, (wt, w_width) in enumerate(zip(words_text, word_widths)):
                fill_color = active_color if w_i == active_idx else inactive_color
                draw.text(
                    (curr_x, start_y),
                    wt,
                    font=font,
                    fill=fill_color,
                    stroke_width=stroke_width,
                    stroke_fill=stroke_color,
                )
                curr_x += w_width + space_w

            clip = (
                ImageClip(np.array(img))
                .with_start(t_start)
                .with_duration(duration)
                .with_position(("center", y_position))
            )
            subtitle_clips.append(clip)

    logger.info("Generated %d dynamic active-word subtitle clips", len(subtitle_clips))
    return subtitle_clips


def mix_audio_tracks(
    voice_audio_path: Path,
    music_audio_path: Path | None,
    target_duration: float,
    music_attenuation_db: float = -20.0,
) -> tuple[CompositeAudioClip | AudioFileClip, list[AudioFileClip]]:
    """Mix primary voiceover with background music ducked by specified decibels."""
    opened_clips: list[AudioFileClip] = []
    voice_clip = AudioFileClip(str(voice_audio_path))
    opened_clips.append(voice_clip)

    if not music_audio_path or not Path(music_audio_path).is_file():
        return voice_clip, opened_clips

    music_clip = AudioFileClip(str(music_audio_path))
    opened_clips.append(music_clip)

    volume_factor = 10.0 ** (music_attenuation_db / 20.0)

    if music_clip.duration < target_duration:
        music_clip = music_clip.with_effects([afx.AudioLoop(duration=target_duration)])
    else:
        music_clip = music_clip.subclipped(0, target_duration)

    music_clip = music_clip.with_effects(
        [
            afx.MultiplyVolume(volume_factor),
            afx.AudioFadeOut(1.2),
        ]
    )

    combined_audio = CompositeAudioClip([voice_clip, music_clip])
    return combined_audio, opened_clips


def render_stoic_video(
    audio_path: str | Path,
    transcript_data: list[dict[str, Any]],
    background_clip_path: str | Path,
    output_path: str | Path,
    music_path: str | Path | None = None,
    target_size: tuple[int, int] = (1080, 1920),
    fps: int = 30,
) -> str:
    """Render high-engagement 9:16 vertical stoic video with Multi-Clip B-Roll and active-word subtitles.

    Args:
        audio_path: Path to TTS voice audio.
        transcript_data: Word-level timestamps from faster-whisper.
        background_clip_path: Path to background video file or folder containing multiple videos.
        output_path: Output file path (.mp4).
        music_path: Optional background music path.
        target_size: Video resolution (1080, 1920).
        fps: Framerate (default 30).

    Returns:
        Resolved string path to rendered video.
    """
    audio_file = Path(audio_path).resolve()
    bg_input = Path(background_clip_path).resolve()
    out_file = Path(output_path).resolve()
    music_file = Path(music_path).resolve() if music_path else None

    if not audio_file.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    out_file.parent.mkdir(parents=True, exist_ok=True)

    bg_clip = None
    final_video = None
    opened_video_clips: list[VideoFileClip] = []
    opened_audio_clips: list[AudioFileClip] = []

    try:
        # Determine total duration
        temp_voice = AudioFileClip(str(audio_file))
        total_duration = temp_voice.duration + 0.4
        temp_voice.close()

        # Step 1: Prepare Multi-Clip B-Roll or Ken Burns Background
        bg_clip, opened_video_clips = prepare_broll_background(
            bg_input=bg_input,
            target_duration=total_duration,
            target_size=target_size,
        )

        # Step 2: Build Active-Word Highlighted Subtitles
        subtitle_clips = build_active_word_subtitle_clips(
            transcript_data=transcript_data,
            target_size=target_size,
            font_size=64,
            active_color="#FFD700",  # Intense glowing gold
            inactive_color="#FFFFFF",  # Pure white
            stroke_color="black",
            stroke_width=5,
            y_position=1140,
            words_per_phrase=3,
        )

        # Step 3: Mix Audio
        final_audio, opened_audio_clips = mix_audio_tracks(
            voice_audio_path=audio_file,
            music_audio_path=music_file,
            target_duration=total_duration,
            music_attenuation_db=-20.0,
        )

        # Step 4: Composite Layers
        final_video = CompositeVideoClip(
            [bg_clip, *subtitle_clips],
            size=target_size,
        ).with_duration(total_duration)

        final_video = final_video.with_audio(final_audio)

        # Step 5: Render Video
        logger.info(
            "Rendering video V2 (B-Roll + Karaoke Subtitles): %s (%.2fs)",
            out_file.name,
            total_duration,
        )
        final_video.write_videofile(
            str(out_file),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            preset="fast",
            threads=4,
            logger=None,
        )

        if not out_file.exists() or out_file.stat().st_size == 0:
            raise RuntimeError(f"Rendered output is missing or 0 bytes: {out_file}")

        logger.info("Video V2 successfully rendered (%d bytes)", out_file.stat().st_size)
        return str(out_file)

    finally:
        # Proper resource disposal
        if bg_clip is not None:
            try:
                bg_clip.close()
            except Exception:
                pass
        if final_video is not None:
            try:
                final_video.close()
            except Exception:
                pass
        for v in opened_video_clips:
            try:
                v.close()
            except Exception:
                pass
        for a in opened_audio_clips:
            try:
                a.close()
            except Exception:
                pass
