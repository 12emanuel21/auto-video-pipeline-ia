"""Audio transcription engine using faster-whisper for word-level timestamps."""

import os
from pathlib import Path
import logging
from typing import Any

# Disable symlinks warning on Windows for Hugging Face cache
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# Module-level model cache to avoid reloading weights repeatedly
_CACHED_MODELS: dict[str, WhisperModel] = {}


def get_whisper_model(
    model_size: str = "base",
    device: str = "cpu",
    compute_type: str = "int8",
) -> WhisperModel:
    """Retrieve or initialize a cached Faster-Whisper model instance.

    Args:
        model_size: Whisper model size name ('tiny', 'base', 'small', etc.).
        device: Processing device ('cpu', 'cuda').
        compute_type: Quantization type ('int8', 'float16', 'float32').

    Returns:
        WhisperModel instance.
    """
    cache_key = f"{model_size}_{device}_{compute_type}"
    if cache_key not in _CACHED_MODELS:
        logger.info(
            "Loading Faster-Whisper model '%s' on %s (%s)...",
            model_size,
            device,
            compute_type,
        )
        _CACHED_MODELS[cache_key] = WhisperModel(
            model_size_or_path=model_size,
            device=device,
            compute_type=compute_type,
        )
    return _CACHED_MODELS[cache_key]


def get_word_timestamps(
    audio_path: str | Path,
    model_size: str = "base",
    device: str = "cpu",
    compute_type: str = "int8",
    language: str = "es",
) -> list[dict[str, Any]]:
    """Transcribe an audio file and extract precise word-level start and end timestamps.

    Args:
        audio_path: Path to the input audio file (.mp3, .wav, etc.).
        model_size: Model size to use. Default is 'base'.
        device: Device to run inference on ('cpu' or 'cuda').
        compute_type: Computation type, 'int8' recommended for CPU.
        language: Language code for transcription. Default is 'es' (Spanish).

    Returns:
        List of dicts with keys:
            - "word": Cleaned text of the word.
            - "start": Start timestamp in seconds (float).
            - "end": End timestamp in seconds (float).

    Raises:
        FileNotFoundError: If audio_path does not exist.
        RuntimeError: If transcription fails.
    """
    audio_file = Path(audio_path).resolve()
    if not audio_file.is_file():
        raise FileNotFoundError(f"Audio file not found at: {audio_file}")

    logger.info("Transcribing audio for word timestamps: %s", audio_file)

    try:
        model = get_whisper_model(
            model_size=model_size,
            device=device,
            compute_type=compute_type,
        )

        segments, _ = model.transcribe(
            str(audio_file),
            language=language,
            word_timestamps=True,
            vad_filter=True,
        )

        words_data: list[dict[str, Any]] = []
        for segment in segments:
            if not segment.words:
                continue
            for word_obj in segment.words:
                clean_word = word_obj.word.strip()
                if not clean_word:
                    continue
                words_data.append(
                    {
                        "word": clean_word,
                        "start": float(round(word_obj.start, 3)),
                        "end": float(round(word_obj.end, 3)),
                    }
                )

        logger.info("Extracted %d word timestamps from %s", len(words_data), audio_file.name)
        return words_data

    except Exception as exc:
        logger.error("Transcription error on %s: %s", audio_file, exc)
        raise RuntimeError(f"Error during transcription: {exc}") from exc
