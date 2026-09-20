"""Phase 2 verification script: Gemini AI Studio + SQLite Persistence + Unified Pipeline."""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Fix Windows console encoding for UTF-8 emojis and special characters
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app.core.config import (
    ASSETS_DIR,
    AUDIO_DIR,
    DB_PATH,
    OUTPUT_DIR,
    VIDEO_DIR,
)
from app.core.ai_studio import generate_stoic_script
from app.core.pipeline import create_video_task
from app.database.db import get_video_by_id, get_pending_videos, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("TestStage2")


def print_banner(title: str) -> None:
    """Print a styled section banner."""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


async def main_async() -> None:
    """Run the Stage 2 end-to-end test."""
    start_time = time.time()
    theme = "el control de las emociones"
    author = "Marco Aurelio"

    print_banner("FASE 2: PRUEBA DE CEREBRO IA Y PERSISTENCIA LOCAL")
    logger.info("Tema de prueba : '%s'", theme)
    logger.info("Autor estoico  : '%s'", author)
    logger.info("Base de datos  : %s", DB_PATH)

    # 1. Prueba aislada de Generación de Guión
    print_banner("PASO 1: GENERACIÓN DE GUIÓN CON GEMINI (ESQUEMA ESTRICTO)")
    script = generate_stoic_script(theme=theme, author=author)

    print("\n[JSON Generado por Gemini]:")
    print(json.dumps(script, indent=2, ensure_ascii=False))

    # Validar claves esperadas
    required_keys = {"title", "hook", "body", "call_to_action", "full_narration", "caption"}
    missing_keys = required_keys - set(script.keys())
    if missing_keys:
        raise ValueError(f"Faltan campos requeridos en el JSON: {missing_keys}")
    logger.info("✓ Esquema de guión validado correctamente.")

    # 2. Ejecutar Pipeline Unificado (Guión -> DB -> TTS -> Whisper -> Video 1080x1920 -> DB)
    print_banner("PASO 2: EJECUCIÓN DEL ORQUESTADOR UNIFICADO")
    bg_video = VIDEO_DIR / "stoic_bg.mp4"
    ambient_music = AUDIO_DIR / "ambient_stoic.wav"

    video_id = await create_video_task(
        theme=theme,
        author=author,
        bg_video_path=bg_video,
        music_path=ambient_music,
    )
    logger.info("✓ Orquestador completó la tarea. Video ID generado: %d", video_id)

    # 3. Consulta de Persistencia en Base de Datos SQLite
    print_banner("PASO 3: CONSULTA Y VERIFICACIÓN EN BASE DE DATOS SQLITE")
    video_record = get_video_by_id(video_id)
    if not video_record:
        raise RuntimeError(f"No se encontró el registro para el video ID {video_id} en SQLite.")

    print(f"ID           : {video_record['id']}")
    print(f"Título       : {video_record['title']}")
    print(f"Tema         : {video_record['theme']}")
    print(f"Estado       : {video_record['status']}")
    print(f"Ruta Video   : {video_record['video_path']}")
    print(f"Creado en    : {video_record['created_at']}")
    print(f"Caption      :\n{video_record['caption']}")

    # Validar estado READY_FOR_REVIEW
    if video_record["status"] != "READY_FOR_REVIEW":
        raise AssertionError(
            f"El estado esperado era 'READY_FOR_REVIEW', pero se obtuvo '{video_record['status']}'"
        )
    logger.info("✓ Estado 'READY_FOR_REVIEW' confirmado en SQLite.")

    # Validar existencia física del video
    out_file = Path(video_record["video_path"])
    if not out_file.is_file() or out_file.stat().st_size == 0:
        raise FileNotFoundError(f"El archivo de video final no existe o está vacío: {out_file}")

    file_size_mb = out_file.stat().st_size / (1024 * 1024)
    logger.info(
        "✓ Archivo físico de video verificado: %s (%.2f MB)",
        out_file.name,
        file_size_mb,
    )

    # 4. Comprobar lista de videos pendientes de revisión
    pending = get_pending_videos()
    logger.info("Total de videos pendientes para revisión ('READY_FOR_REVIEW'): %d", len(pending))

    total_duration = time.time() - start_time
    print_banner("FASE 2 COMPLETADA EXITOSAMENTE")
    print(f"Tiempo total de ejecución: {total_duration:.2f} segundos")
    print(f"Video listo para revisión: {out_file.resolve()}")
    print("=" * 70 + "\n")


def main() -> None:
    """Synchronous entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.warning("Prueba interrumpida por el usuario.")
        sys.exit(1)
    except Exception as exc:
        logger.error("Error en prueba de Fase 2: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
