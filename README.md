# Auto Video Pipeline IA

> Pipeline autónomo de generación y renderizado programático de video vertical (9:16) para TikTok y YouTube Shorts. Integra scraping de tendencias, redacción asistida con Google Gemini 2.5 Flash, síntesis de voz neuronal (Edge-TTS), alineación temporal por palabra (Faster-Whisper int8), composición con MoviePy 2.x/FFmpeg y panel de moderación en FastAPI con TikTok OAuth 2.0.

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Gemini API](https://img.shields.io/badge/LLM-Gemini%202.5%20Flash-8E75B2?style=flat&logo=google)](https://aistudio.google.com/)
[![FFmpeg](https://img.shields.io/badge/Video-FFmpeg%20%2F%20MoviePy-007808?style=flat&logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📌 Visión General & Flujo de Negocio

La producción consistente de contenido de alta retención para redes sociales suele requerir herramientas fragmentadas y edición manual intensiva. **Auto Video Pipeline IA** unifica todo el ciclo de producción en una arquitectura desacoplada y orientada a eventos locales:

```text
[ Scraper de Tendencias ]  ──►  yt-dlp (Extracción de métricas de engagement)
           │
           ▼
[ Generador de Guiones ]   ──►  Gemini 2.5 Flash + Corpus Histórico (Meditaciones)
           │                    (Schema JSON estricto con Pydantic)
           ▼
[ Síntesis de Voz (TTS) ]  ──►  edge-tts (es-ES-AlvaroNeural con cadencia ajustada)
           │
           ▼
[ Transcriptor & VAD ]     ──►  faster-whisper (Alineación a nivel de palabra en CPU int8)
           │
           ▼
[ Motor de Composición ]   ──►  MoviePy 2.x + Pillow + NumPy + FFmpeg
           │                    - Cortes B-Roll adaptativos por tags semánticos
           │                    - Subtítulos dinámicos estilo Karaoke
           │                    - Audio ducking automático (-20 dB en fondo)
           ▼
[ Panel de Moderación ]    ──►  FastAPI Dashboard (:5678) + SQLite
           │
           ▼
[ TikTok Content API ]     ──►  Publicación programática vía OAuth 2.0 Code Grant