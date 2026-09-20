"""Unified Pipeline Orchestrator connecting Gemini, TTS, Transcriber, Video Builder, and SQLite."""

import asyncio
import logging
from pathlib import Path

from app.core.config import (
    AUDIO_DIR,
    OUTPUT_DIR,
    VIDEO_DIR,
)
from app.core.ai_studio import generate_stoic_script
from app.core.tts_engine import generate_voice
from app.core.transcriber import get_word_timestamps
from app.core.video_builder import render_stoic_video
from app.database.db import (
    init_db,
    insert_video,
    update_video_status,
)

logger = logging.getLogger(__name__)


async def create_video_task(
    theme: str = "el control de las emociones",
    author: str = "Marco Aurelio",
    bg_video_path: str | Path | None = None,
    music_path: str | Path | None = None,
) -> int:
    """Execute the end-to-end autonomous video creation task.

    Workflow:
    1. Generate viral stoic script with Gemini (strict JSON schema).
    2. Save draft record to SQLite with status 'DRAFT'.
    3. Synthesize TTS narration audio using edge-tts.
    4. Extract word-level timestamps using faster-whisper.
    5. Render 9:16 vertical video (1080x1920) with subtitles and -20dB background music.
    6. Update SQLite record with output path and status 'READY_FOR_REVIEW'.
    7. Return the created video ID.

    Args:
        theme: Topic of the video (e.g. "el control de las emociones", "disciplina").
        author: Stoic philosopher name (e.g. "Marco Aurelio", "Séneca").
        bg_video_path: Path to background video footage (.mp4).
        music_path: Optional path to ambient background music (.mp3, .wav).

    Returns:
        The integer ID of the saved and rendered video in the database.

    Raises:
        RuntimeError: If any pipeline step fails.
    """
    init_db()

    # Resolve background video (supports folder for multi-clip B-roll or single file)
    if bg_video_path and Path(bg_video_path).exists():
        resolved_bg = Path(bg_video_path).resolve()
    elif VIDEO_DIR.is_dir() and list(VIDEO_DIR.glob("*.mp4")):
        resolved_bg = VIDEO_DIR.resolve()
    else:
        default_bg = VIDEO_DIR / "stoic_bg.mp4"
        if default_bg.is_file():
            resolved_bg = default_bg.resolve()
        else:
            raise FileNotFoundError(
                f"No background videos found in {VIDEO_DIR} or provided path: '{bg_video_path}'"
            )

    # Resolve optional ambient music
    resolved_music = None
    if music_path and Path(music_path).is_file():
        resolved_music = Path(music_path).resolve()
    else:
        default_music = AUDIO_DIR / "ambient_stoic.wav"
        if default_music.is_file():
            resolved_music = default_music.resolve()

    logger.info("=" * 60)
    logger.info("INICIANDO TAREA DE CREACIÓN DE VIDEO ESTOICO")
    logger.info("Tema: '%s' | Autor: '%s'", theme, author)
    logger.info("Fondo: %s", resolved_bg.name)
    if resolved_music:
        logger.info("Música: %s", resolved_music.name)
    logger.info("=" * 60)

    # Paso 1: Generar Guión con Gemini
    logger.info("[1/5] Generando guión viral con Gemini...")
    script_data = generate_stoic_script(theme=theme, author=author)
    title = script_data.get("title", f"Meditación sobre {theme}")
    narration = script_data["full_narration"]
    caption = script_data["caption"]

    logger.info("Título: '%s'", title)
    logger.info("Hook  : '%s'", script_data.get("hook"))

    # Paso 2: Guardar en Base de Datos como DRAFT
    logger.info("[2/5] Guardando borrador en base de datos SQLite (estado: DRAFT)...")
    video_id = insert_video(
        title=title,
        theme=theme,
        narration=narration,
        caption=caption,
        status="DRAFT",
    )
    logger.info("Registro creado con ID: %d", video_id)

    try:
        # Paso 3: Generar Audio TTS
        audio_output_path = AUDIO_DIR / f"voice_{video_id}.mp3"
        logger.info("[3/5] Generando locución TTS en %s...", audio_output_path.name)
        voice_file = await generate_voice(
            text=narration,
            output_path=audio_output_path,
            voice="es-ES-AlvaroNeural",
            rate="-2%",
        )
        logger.info("Locución generada exitosamente (%s)", voice_file)

        # Paso 4: Extracción de Timestamps con Faster-Whisper
        logger.info("[4/5] Transcribiendo y extrayendo timestamps con faster-whisper...")
        timestamps = get_word_timestamps(
            audio_path=voice_file,
            model_size="base",
            device="cpu",
            compute_type="int8",
        )
        logger.info("Timestamps extraídos: %d palabras", len(timestamps))

        # Paso 5: Renderizado con MoviePy
        rendered_output_path = OUTPUT_DIR / f"video_{video_id}.mp4"
        logger.info("[5/5] Renderizando video vertical 1080x1920 en %s...", rendered_output_path.name)
        final_video_path = render_stoic_video(
            audio_path=voice_file,
            transcript_data=timestamps,
            background_clip_path=resolved_bg,
            output_path=rendered_output_path,
            music_path=resolved_music,
            target_size=(1080, 1920),
            fps=30,
        )

        # Paso 6: Actualizar Base de Datos a READY_FOR_REVIEW
        update_video_status(
            video_id=video_id,
            status="READY_FOR_REVIEW",
            video_path=final_video_path,
        )
        logger.info("=" * 60)
        logger.info("VIDEO ID %d COMPLETADO EXITOSAMENTE", video_id)
        logger.info("Estado actualizado a: READY_FOR_REVIEW")
        logger.info("Archivo final: %s", final_video_path)
        logger.info("=" * 60)

        return video_id

    except Exception as exc:
        logger.error("Error durante el procesamiento del video ID %d: %s", video_id, exc)
        try:
            update_video_status(video_id=video_id, status="REJECTED")
        except Exception:
            pass
        raise RuntimeError(f"Fallo en la tarea de creación de video ID {video_id}: {exc}") from exc


def create_video_task_sync(
    theme: str = "el control de las emociones",
    author: str = "Marco Aurelio",
    bg_video_path: str | Path | None = None,
    music_path: str | Path | None = None,
) -> int:
    """Synchronous wrapper for create_video_task."""
    return asyncio.run(
        create_video_task(
            theme=theme,
            author=author,
            bg_video_path=bg_video_path,
            music_path=music_path,
        )
    )
