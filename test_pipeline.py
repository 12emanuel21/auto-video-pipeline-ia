"""End-to-end test script for the Stoic TikTok Multimedia Pipeline (Phase 1).

Executes:
1. Sample asset check & generator (ambient audio & background video) if missing.
2. TTS Voice generation (edge-tts).
3. Audio transcription with word-level timestamps (faster-whisper).
4. Vertical video composition (1080x1920, 9:16) with dynamic subtitles and -20dB ducked music.
"""

import asyncio
import logging
import sys
import time
import wave
from pathlib import Path

import numpy as np
from moviepy import VideoClip

from app.core.tts_engine import generate_voice
from app.core.transcriber import get_word_timestamps
from app.core.video_builder import render_stoic_video

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("PipelineTest")

# Famous quote by Marcus Aurelius (Meditations)
DEFAULT_STOIC_QUOTE = (
    "Tienes poder sobre tu mente, no sobre los acontecimientos. "
    "Date cuenta de esto y encontrarás la fuerza."
)


def ensure_default_assets(video_path: Path, music_path: Path) -> None:
    """Ensure baseline stoic background assets exist; generate them if missing."""
    video_path.parent.mkdir(parents=True, exist_ok=True)
    music_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Background video (Cinematic dark textured atmosphere)
    if not video_path.is_file():
        logger.info("Generating default stoic background clip at %s...", video_path)

        def make_frame(t: float) -> np.ndarray:
            # 1080x1920 subtle dark atmospheric texture
            w, h = 1080, 1920
            lum = int(22 + 8 * np.sin(2 * np.pi * t / 5.0))
            frame = np.full((h, w, 3), [lum, lum - 4, max(0, lum - 8)], dtype=np.uint8)
            return frame

        bg_clip = VideoClip(make_frame, duration=5.0)
        bg_clip.write_videofile(
            str(video_path),
            fps=24,
            codec="libx264",
            preset="ultrafast",
            logger=None,
        )
        bg_clip.close()
        logger.info("Background clip created successfully.")

    # 2. Stoic ambient drone music (harmonic meditative drone)
    if not music_path.is_file():
        logger.info("Generating default ambient music track at %s...", music_path)
        sample_rate = 44100
        duration = 10.0
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)

        # Deep warm frequencies (108Hz, 216Hz, 432Hz)
        drone = (
            0.35 * np.sin(2 * np.pi * 108 * t)
            + 0.25 * np.sin(2 * np.pi * 216 * t)
            + 0.12 * np.sin(2 * np.pi * 432 * t)
        )
        drone *= 0.8 + 0.2 * np.sin(2 * np.pi * 0.25 * t)

        fade_len = int(sample_rate * 1.5)
        drone[:fade_len] *= np.linspace(0, 1, fade_len)
        drone[-fade_len:] *= np.linspace(1, 0, fade_len)

        audio_int16 = (drone * 32767).astype(np.int16)
        with wave.open(str(music_path), "w") as wav_out:
            wav_out.setnchannels(1)
            wav_out.setsampwidth(2)
            wav_out.setframerate(sample_rate)
            wav_out.writeframes(audio_int16.tobytes())
        logger.info("Ambient music track created successfully.")


async def run_pipeline(quote_text: str = DEFAULT_STOIC_QUOTE) -> Path:
    """Execute the full autonomous video generation pipeline."""
    start_total_time = time.time()
    base_dir = Path(__file__).resolve().parent

    audio_dir = base_dir / "assets" / "audio"
    video_dir = base_dir / "assets" / "video"
    output_dir = base_dir / "assets" / "output"

    tts_output_path = audio_dir / "stoic_voice.mp3"
    bg_video_path = video_dir / "stoic_bg.mp4"
    ambient_music_path = audio_dir / "ambient_stoic.wav"
    final_video_path = output_dir / "test_video.mp4"

    logger.info("=" * 60)
    logger.info("INICIANDO PIPELINE MULTIMEDIA ESTOICO - FASE 1")
    logger.info("Cita: \"%s\"", quote_text)
    logger.info("=" * 60)

    # Paso 0: Validar/generar assets de fondo
    ensure_default_assets(bg_video_path, ambient_music_path)

    # Paso 1: Generar voz con edge-tts
    logger.info("Paso 1: Sintetizando voz con edge-tts (es-ES-AlvaroNeural)...")
    t0 = time.time()
    voice_file = await generate_voice(
        text=quote_text,
        output_path=tts_output_path,
        voice="es-ES-AlvaroNeural",
        rate="-2%",  # Cadencia estoica pausada y reflexiva
    )
    logger.info("✓ Audio generado en %.2fs: %s", time.time() - t0, voice_file)

    # Paso 2: Transcribir y extraer timestamps palabra por palabra
    logger.info("Paso 2: Extrayendo timestamps con faster-whisper...")
    t1 = time.time()
    word_timestamps = get_word_timestamps(
        audio_path=voice_file,
        model_size="base",
        device="cpu",
        compute_type="int8",
    )
    logger.info(
        "✓ Transcripción completada en %.2fs (%d palabras detectadas)",
        time.time() - t1,
        len(word_timestamps),
    )

    # Muestra de las primeras palabras detectadas
    sample_preview = " | ".join(
        f"{w['word']} ({w['start']:.2f}s - {w['end']:.2f}s)"
        for w in word_timestamps[:4]
    )
    logger.info("Muestra de timestamps: %s ...", sample_preview)

    # Paso 3: Renderizado y composición de video vertical (1080x1920)
    logger.info("Paso 3: Componiendo video vertical 1080x1920 con MoviePy...")
    t2 = time.time()
    rendered_file = render_stoic_video(
        audio_path=voice_file,
        transcript_data=word_timestamps,
        background_clip_path=bg_video_path,
        output_path=final_video_path,
        music_path=ambient_music_path,
        target_size=(1080, 1920),
        fps=30,
    )
    logger.info("✓ Video renderizado en %.2fs: %s", time.time() - t2, rendered_file)

    # Paso 4: Verificación y métricas del archivo final
    final_path = Path(rendered_file)
    if not final_path.is_file() or final_path.stat().st_size == 0:
        raise RuntimeError(f"Error crítico: El video de salida no existe o está vacío: {final_path}")

    file_size_mb = final_path.stat().st_size / (1024 * 1024)
    total_elapsed = time.time() - start_total_time

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETADO CON ÉXITO")
    logger.info("Archivo generado : %s", final_path.resolve())
    logger.info("Tamaño de archivo: %.2f MB (%d bytes)", file_size_mb, final_path.stat().st_size)
    logger.info("Tiempo total     : %.2f segundos", total_elapsed)
    logger.info("=" * 60)

    return final_path


def main() -> None:
    """Entrypoint synchronous wrapper."""
    try:
        asyncio.run(run_pipeline())
    except KeyboardInterrupt:
        logger.warning("Pipeline interrumpido por el usuario.")
        sys.exit(1)
    except Exception as err:
        logger.error("Fallo durante la ejecución del pipeline: %s", err, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
