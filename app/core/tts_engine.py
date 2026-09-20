"""TTS Engine module using edge-tts for high-quality synthetic voice generation."""

from pathlib import Path
import logging
import edge_tts

logger = logging.getLogger(__name__)


async def generate_voice(
    text: str,
    output_path: str | Path,
    voice: str = "es-ES-AlvaroNeural",
    rate: str = "+0%",
    pitch: str = "+0Hz",
) -> str:
    """Generate voiceover audio from text using edge-tts.

    Args:
        text: The text/quote to synthesize into speech.
        output_path: Destination path for the generated audio file (.mp3).
        voice: Microsoft Edge TTS voice model name. Default is "es-ES-AlvaroNeural".
        rate: Speech rate adjustment, e.g. "+0%", "-5%".
        pitch: Speech pitch adjustment, e.g. "+0Hz".

    Returns:
        The resolved string path to the generated audio file.

    Raises:
        ValueError: If text is empty or blank.
        RuntimeError: If audio generation fails.
    """
    clean_text = text.strip()
    if not clean_text:
        raise ValueError("Text to synthesize cannot be empty.")

    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Generating voice with %s -> %s", voice, out_file)

    try:
        communicate = edge_tts.Communicate(
            text=clean_text,
            voice=voice,
            rate=rate,
            pitch=pitch,
        )
        await communicate.save(str(out_file))

        if not out_file.exists() or out_file.stat().st_size == 0:
            raise RuntimeError(f"Generated audio file is missing or empty at {out_file}")

        logger.info("Voice successfully generated (%d bytes)", out_file.stat().st_size)
        return str(out_file)
    except Exception as exc:
        logger.error("Failed to generate TTS audio: %s", exc)
        raise RuntimeError(f"Error during edge-tts synthesis: {exc}") from exc
