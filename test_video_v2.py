"""Phase V2 verification script: Multi-Clip B-Roll + Ken Burns + Active Word Highlighted Subtitles."""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Fix Windows console UTF-8 encoding
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from moviepy import VideoFileClip

from app.core.config import (
    AUDIO_DIR,
    OUTPUT_DIR,
    VIDEO_DIR,
)
from app.core.ai_studio import get_stoic_quote, generate_stoic_script
from app.core.tts_engine import generate_voice
from app.core.transcriber import get_word_timestamps
from app.core.video_builder import render_stoic_video

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("TestVideoV2")


def print_banner(title: str) -> None:
    """Print a styled section header."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


async def main_async() -> None:
    """Execute Video V2 end-to-end pipeline test."""
    total_start = time.time()

    print_banner("ELEVACIÓN VISUAL V2: MULTI-CLIP B-ROLL & SUBTÍTULOS RESALTADOS")

    # 1. Obtener Cita Auténtica del Corpus Histórico
    stoic_data = get_stoic_quote("disciplina")
    quote_text = stoic_data["quote"]
    book_ref = stoic_data.get("book_ref", "Meditaciones")
    print(f"📖 Cita Histórica Seleccionada: \"{quote_text}\" ({book_ref})")

    # 2. Generar Guión Anclado con Gemini
    print_banner("PASO 1: GENERACIÓN DE GUIÓN ANCLADO A LA CITA HISTÓRICA")
    t0 = time.time()
    script = generate_stoic_script(
        theme="la disciplina del guerrero estoico",
        author="Marco Aurelio",
        quote_anchor=f"{quote_text} ({book_ref})",
    )
    print(f"✓ Guión generado en {time.time() - t0:.2f}s:")
    print(f"  • Título: {script['title']}")
    print(f"  • Hook  : \"{script['hook']}\"")
    print(f"  • Body  : \"{script['body']}\"")
    print(f"  • CTA   : \"{script['call_to_action']}\"")

    # 3. Locución TTS con Edge-TTS
    print_banner("PASO 2: GENERACIÓN DE VOZ (EDGE-TTS ÁlvaroNeural)")
    tts_audio_file = AUDIO_DIR / "voice_v2_test.mp3"
    t1 = time.time()
    voice_path = await generate_voice(
        text=script["full_narration"],
        output_path=tts_audio_file,
        voice="es-ES-AlvaroNeural",
        rate="-2%",
    )
    print(f"✓ Audio generado en {time.time() - t1:.2f}s: {voice_path}")

    # 4. Transcripción y Timestamps con Faster-Whisper
    print_banner("PASO 3: EXTRACCIÓN DE TIMESTAMPS POR PALABRA (FASTER-WHISPER)")
    t2 = time.time()
    timestamps = get_word_timestamps(
        audio_path=voice_path,
        model_size="base",
        device="cpu",
        compute_type="int8",
    )
    print(f"✓ {len(timestamps)} palabras transcritas con timestamps precisos en {time.time() - t2:.2f}s.")
    sample_preview = " | ".join(f"{w['word']} ({w['start']:.2f}s-{w['end']:.2f}s)" for w in timestamps[:4])
    print(f"  Muestra: {sample_preview}...")

    # 5. Renderizado V2: B-Roll Multi-Clip + Subtítulos Palabra Activa Resaltada
    print_banner("PASO 4: COMPOSICIÓN MULTI-CLIP B-ROLL Y SUBTÍTULOS KARAOKE (1080x1920)")
    output_v2_video = OUTPUT_DIR / "test_video_v2.mp4"
    ambient_music = AUDIO_DIR / "ambient_stoic.wav"

    t3 = time.time()
    # Pasamos el directorio de videos para activar la concatenación multi-clip
    rendered_file = render_stoic_video(
        audio_path=voice_path,
        transcript_data=timestamps,
        background_clip_path=VIDEO_DIR,  # Carpeta con múltiples clips .mp4
        output_path=output_v2_video,
        music_path=ambient_music,
        target_size=(1080, 1920),
        fps=30,
    )
    print(f"✓ Renderizado completado en {time.time() - t3:.2f}s.")

    # 6. Verificación de Métricas del Video
    print_banner("PASO 5: VERIFICACIÓN TÉCNICA DEL VIDEO FINAL")
    final_clip = VideoFileClip(rendered_file)
    file_bytes = Path(rendered_file).stat().st_size
    file_mb = file_bytes / (1024 * 1024)

    print(f"Archivo Final    : {rendered_file}")
    print(f"Resolución       : {final_clip.size[0]}x{final_clip.size[1]} (9:16 Vertical)")
    print(f"Duración         : {final_clip.duration:.2f} segundos")
    print(f"Framerate        : {final_clip.fps} fps")
    print(f"Canales de Audio : {final_clip.audio.nchannels if final_clip.audio else 0} (Música -20dB + Voz)")
    print(f"Tamaño de Archivo: {file_mb:.2f} MB ({file_bytes:,} bytes)")
    final_clip.close()

    total_time = time.time() - total_start
    print_banner("VERIFICACIÓN V2 COMPLETADA CON ÉXITO")
    print(f"Tiempo Total del Pipeline: {total_time:.2f} segundos")
    print(f"Video disponible en: {output_v2_video.resolve()}\n")


def main() -> None:
    """Synchronous entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nPrueba cancelada por el usuario.")
        sys.exit(1)
    except Exception as exc:
        logger.error("Error durante test_video_v2: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
