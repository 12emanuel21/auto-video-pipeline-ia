"""Gemini AI Studio integration for generating viral stoic TikTok scripts anchored in historical Meditations."""

import json
import logging
import random
from typing import Any
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from app.core.config import GEMINI_API_KEY, GEMINI_MODEL, BASE_DIR

logger = logging.getLogger(__name__)

QUOTES_JSON_FILE = BASE_DIR / "app" / "database" / "stoic_quotes.json"

SYSTEM_PROMPT = """Actúa como un guionista de élite y estratega de contenido viral especializado en videos cortos (TikTok, Instagram Reels y YouTube Shorts) sobre Estoicismo y superación personal (Marco Aurelio, Séneca, Epicteto).

Tus guiones deben:
1. Tener un gancho magnético e inmediato (0 a 3 segundos) que rompa el patrón del usuario y detenga el scroll instantáneamente.
2. Un desarrollo conciso, contundente y práctico (entre 20 y 35 palabras). Sin rodeos, lenguaje directo y potente.
3. Un Call To Action (pregunta de cierre) que obligue moral o intelectualmente a la audiencia a comentar su postura.
4. Generar 'full_narration' como un texto continuo, natural y con ritmo para ser locutado por TTS (uniendo hook, body y call_to_action con pausas naturales).
5. Crear un caption optimizado para TikTok con llamada a la acción y entre 4 y 6 hashtags estratégicos (#estoicismo #filosofia #marcoaurelio #disciplina, etc.).

Debes responder ÚNICAMENTE en formato JSON con la estructura solicitada."""


class StoicScript(BaseModel):
    """Schema for viral stoic short-form video script."""

    title: str = Field(description="Título corto interno del video")
    hook: str = Field(description="Frase inicial de 0 a 3 segundos para detener el scroll")
    body: str = Field(description="Desarrollo de la lección estoica concisa (20-35 palabras)")
    call_to_action: str = Field(description="Pregunta de cierre para detonar comentarios")
    full_narration: str = Field(
        description="Texto continuo que leerá el narrador TTS (hook + body + call_to_action)"
    )
    caption: str = Field(
        description="Descripción para TikTok con llamada a la acción y 4-6 hashtags estratégicos"
    )


def get_stoic_quote(theme: str | None = None) -> dict[str, Any]:
    """Retrieve an authentic quote from Marcus Aurelius Meditations matching theme, or random."""
    fallback_item = {
        "quote": "Tienes poder sobre tu mente, no sobre los acontecimientos. Date cuenta de esto y encontrarás la fuerza.",
        "book_ref": "Meditaciones, Libro IV, 3",
        "theme": "control_mental",
        "context_hint": "La soberanía sobre el juicio interno."
    }
    if not QUOTES_JSON_FILE.is_file():
        return fallback_item
    try:
        quotes = json.loads(QUOTES_JSON_FILE.read_text(encoding="utf-8"))
        if theme:
            clean_t = theme.lower().replace(" ", "_")
            matching = [
                q for q in quotes
                if q.get("theme") in clean_t or clean_t in q.get("theme", "")
            ]
            if matching:
                return random.choice(matching)
        return random.choice(quotes)
    except Exception as err:
        logger.warning("Error reading stoic_quotes.json: %s", err)
        return fallback_item


def _get_curated_fallback_script(
    theme: str,
    author: str,
    quote_anchor: str | None = None,
) -> dict[str, Any]:
    """Provide a curated high-retention fallback script if Gemini API key is missing or unavailable."""
    theme_clean = theme.strip().lower()
    anchor_text = quote_anchor or f"Como enseñó {author}, no tienes control sobre lo que el mundo te lanza, pero eres el dueño absoluto de tu reacción."
    return {
        "title": f"La regla de oro de {author} sobre {theme_clean}",
        "hook": f"Si {theme_clean} te destruye por dentro, escucha esto ahora mismo.",
        "body": (
            f"Como escribió {author}: {anchor_text} "
            f"Toda tu fuerza reside en dominar tu juicio interno y actuar con calma."
        ),
        "call_to_action": "¿Prefieres ser esclavo de tus impulsos o dueño de tu destino? Te leo.",
        "full_narration": (
            f"Si {theme_clean} te destruye por dentro, escucha esto ahora mismo. "
            f"Como escribió {author}: {anchor_text} "
            f"Toda tu fuerza reside en dominar tu juicio interno y actuar con calma. "
            f"¿Prefieres ser esclavo de tus impulsos o dueño de tu destino? Te leo."
        ),
        "caption": (
            f"Domina tu mente antes de que el mundo te domine a ti. Lección de {author} sobre {theme_clean}.\n"
            f"Comenta tu reflexión abajo 👇\n\n"
            f"#estoicismo #filosofia #{author.lower().replace(' ', '')} #disciplina #mentalidad #crecimientopersonal"
        ),
    }


def generate_stoic_script(
    theme: str = "disciplina",
    author: str = "Marco Aurelio",
    quote_anchor: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
    allow_fallback: bool = True,
) -> dict[str, Any]:
    """Generate a viral stoic script using Gemini AI Studio with strict JSON output.

    Args:
        theme: Theme of the video (e.g. "disciplina", "el control de las emociones").
        author: Stoic philosopher reference (e.g. "Marco Aurelio", "Séneca", "Epicteto").
        quote_anchor: Optional quote from Meditations to anchor the script.
        api_key: Optional Gemini API Key. Defaults to GEMINI_API_KEY from config.
        model_name: Optional Gemini model name. Defaults to GEMINI_MODEL.
        allow_fallback: If True, returns a curated fallback script if all API attempts fail.

    Returns:
        Dictionary adhering strictly to StoicScript schema.
    """
    effective_key = (api_key or GEMINI_API_KEY).strip()
    primary_model = (model_name or GEMINI_MODEL).strip()

    # Automatically select a quote from historical Meditations corpus if not explicitly provided
    if not quote_anchor and "marco" in author.lower():
        selected = get_stoic_quote(theme)
        quote_anchor = f"{selected['quote']} ({selected.get('book_ref', '')})"

    if not effective_key:
        if allow_fallback:
            logger.warning("GEMINI_API_KEY no configurada. Usando guión de fallback.")
            return _get_curated_fallback_script(theme=theme, author=author, quote_anchor=quote_anchor)
        raise ValueError("GEMINI_API_KEY no configurada en .env o entorno.")

    anchor_prompt_part = ""
    if quote_anchor:
        anchor_prompt_part = (
            f"- CITA HISTÓRICA OBLIGATORIA DE ANCLAJE: \"{quote_anchor}\"\n"
            f"  Debes integrar esta cita o su enseñanza nuclear en el 'body' y construir el 'hook' en torno a ella."
        )

    prompt = (
        f"Crea un guión viral para TikTok sobre Estoicismo.\n"
        f"- Tema: {theme}\n"
        f"- Filósofo / Autor: {author}\n"
        f"{anchor_prompt_part}\n"
        f"Asegúrate de respetar estrictamente la estructura JSON solicitada."
    )

    # Candidate models for resilience in case of temporary provider spike/503
    candidate_models = [primary_model, "gemini-3-flash-preview", "gemini-3.6-flash", "gemini-2.5-flash"]
    unique_models = []
    for m in candidate_models:
        if m and m not in unique_models:
            unique_models.append(m)

    client = genai.Client(api_key=effective_key)
    last_error: Exception | None = None

    for candidate in unique_models:
        try:
            logger.info("Generando guión con modelo Gemini '%s'...", candidate)
            response = client.models.generate_content(
                model=candidate,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=StoicScript,
                    temperature=0.75,
                ),
            )

            if not response.text:
                raise RuntimeError(f"Modelo {candidate} devolvió una respuesta vacía.")

            data = json.loads(response.text)
            validated = StoicScript.model_validate(data).model_dump()
            logger.info("✓ Guión generado exitosamente con '%s': '%s'", candidate, validated.get("title"))
            return validated

        except Exception as exc:
            logger.warning("Intento fallido con modelo '%s': %s", candidate, exc)
            last_error = exc
            continue

    if allow_fallback:
        logger.warning("Todos los modelos de Gemini reportaron error. Aplicando guión curado de fallback.")
        return _get_curated_fallback_script(theme=theme, author=author, quote_anchor=quote_anchor)

    raise RuntimeError(f"Error generando guión con Gemini: {last_error}") from last_error


class TrendHooksAnalysis(BaseModel):
    """Schema for viral hooks generated from trend analysis."""
    hooks: list[str] = Field(
        description="Lista de 3 a 5 nuevos ganchos virales (hooks) de 0 a 3 segundos para Marco Aurelio"
    )


def analyze_trends_and_generate_hooks(
    top_trends: list[dict[str, Any]],
    api_key: str | None = None,
    model_name: str | None = None,
    allow_fallback: bool = True,
) -> list[str]:
    """Analyze top engaging stoic videos and generate psychological viral hooks for Marcus Aurelius.

    Args:
        top_trends: List of trending video metadata dicts (title, description, engagement_score).
        api_key: Optional Gemini API key.
        model_name: Optional Gemini model name.
        allow_fallback: Return curated high-performing hooks if Gemini fails.

    Returns:
        List of 3 to 5 psychological hook strings.
    """
    effective_key = (api_key or GEMINI_API_KEY).strip()
    primary_model = (model_name or GEMINI_MODEL).strip()

    fallback_hooks = [
        "Estás sufriendo por cosas que jamás van a suceder, y Marco Aurelio te lo advirtió.",
        "Si no puedes dominar tus emociones hoy, alguien más las usará en tu contra mañana.",
        "La regla de oro de Marco Aurelio para destruir la ansiedad en solo 3 segundos.",
        "Deja de actuar como si tuvieras 1000 años por vivir; la muerte te observa ahora.",
        "El mayor error que cometes al despertar según el emperador Marco Aurelio."
    ]

    if not effective_key:
        logger.warning("GEMINI_API_KEY no configurada. Usando ganchos curados de fallback.")
        return fallback_hooks

    # Format trends for the prompt
    trends_summary = []
    for i, t in enumerate(top_trends[:5], 1):
        title = t.get("title", "")
        desc = t.get("description", "")[:120]
        eng = t.get("engagement_score", 0.0)
        trends_summary.append(f"{i}. Título: \"{title}\" | Engagement: {eng}% | Contexto: {desc}")

    formatted_text = "\n".join(trends_summary) if trends_summary else "Tendencias virales sobre Estoicismo y disciplina personal."

    system_instruction = (
        "Eres un neurocientífico cognitivo y estratega de retención para videos cortos en TikTok. "
        "Analiza por qué funcionaron los videos con más engagement y extrae el desencadenante psicológico "
        "(miedo a la pérdida, confrontación directa, misterio o sabiduría implacable). "
        "Genera entre 3 y 5 nuevos ganchos (hooks) de 0 a 3 segundos adaptados al emperador Marco Aurelio y sus Meditaciones. "
        "Debes responder en formato JSON estricto."
    )

    prompt = (
        f"A continuación tienes los videos con mayor engagement de la comunidad estoica:\n\n"
        f"{formatted_text}\n\n"
        f"Genera entre 3 y 5 nuevos ganchos magnéticos para Marco Aurelio que detengan el scroll inmediatamente."
    )

    candidate_models = [primary_model, "gemini-3-flash-preview", "gemini-3.6-flash", "gemini-2.5-flash"]
    unique_models = []
    for m in candidate_models:
        if m and m not in unique_models:
            unique_models.append(m)

    client = genai.Client(api_key=effective_key)

    for candidate in unique_models:
        try:
            logger.info("Analizando tendencias con modelo '%s'...", candidate)
            response = client.models.generate_content(
                model=candidate,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=TrendHooksAnalysis,
                    temperature=0.8,
                ),
            )

            if not response.text:
                continue

            data = json.loads(response.text)
            hooks = TrendHooksAnalysis.model_validate(data).hooks
            if hooks:
                logger.info("✓ Generados %d ganchos analíticos con Gemini", len(hooks))
                return hooks

        except Exception as exc:
            logger.warning("Fallo al analizar tendencias con '%s': %s", candidate, exc)
            continue

    if allow_fallback:
        logger.warning("Fallo en llamadas de análisis; aplicando ganchos curados de fallback.")
        return fallback_hooks

    raise RuntimeError("No se pudieron generar ganchos a partir de las tendencias.")
