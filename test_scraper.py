"""Test script for Market Intelligence Scraper and Trend Analysis (Phase 4)."""

import sys
import time

# Reconfigure console output encoding for Windows compatibility with emojis
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app.core.scraper import extract_trending_metadata
from app.core.ai_studio import analyze_trends_and_generate_hooks
from app.database.db import save_trends, get_top_trends, init_db


def print_banner(title: str) -> None:
    """Print a styled section header."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def main() -> None:
    """Run Phase 4 verification test."""
    init_db()
    tag = "estoicismo"
    max_results = 5

    print_banner(f"FASE 4: EXTRACCIÓN DE TENDENCIAS EN VIVO (#{tag.upper()})")
    print(f"Consultando los {max_results} videos de mayor engagement con yt-dlp...\n")

    t0 = time.time()
    trends = extract_trending_metadata(tag=tag, max_results=max_results)
    elapsed = time.time() - t0

    if not trends:
        print("❌ No se pudieron extraer videos para el tag solicitado.")
        sys.exit(1)

    print(f"✓ Extracción completada en {elapsed:.2f} segundos ({len(trends)} videos encontrados)\n")

    # Display results table
    header = f"{'#':<3} | {'TÍTULO':<42} | {'VIEWS':<9} | {'LIKES':<7} | {'ENGAGEMENT':<10}"
    divider = "-" * len(header)
    print(divider)
    print(header)
    print(divider)

    for i, t in enumerate(trends, 1):
        title = (t['title'][:39] + '...') if len(t['title']) > 42 else t['title']
        views = f"{t['view_count']:,}"
        likes = f"{t['like_count']:,}"
        eng = f"{t['engagement_rate']:.2f}%"
        print(f"{i:<3} | {title:<42} | {views:<9} | {likes:<7} | {eng:<10}")

    print(divider + "\n")

    # 2. Persistencia en SQLite
    print_banner("PASO 2: GUARDADO EN BASE DE DATOS SQLITE (TABLA 'trends')")
    saved_count = save_trends(tag=tag, trends=trends)
    print(f"✓ {saved_count} registros almacenados exitosamente en la tabla 'trends'.")

    top_db = get_top_trends(limit=3, tag=tag)
    print(f"✓ Consulta de comprobación: {len(top_db)} registros recuperados de SQLite.")
    for r in top_db:
        print(f"  • [Score: {r['engagement_score']:.2f}%] {r['title'][:55]}")

    # 3. Análisis Psicológico y Generación de Ganchos con Gemini
    print_banner("PASO 3: ANÁLISIS PSICOLÓGICO DE GANCHOS CON GEMINI")
    print("Enviando los patrones virales a Gemini para generar ganchos de Marco Aurelio...\n")

    try:
        hooks = analyze_trends_and_generate_hooks(top_trends=trends[:5])
        print("✓ Ganchos virales generados para Marco Aurelio (Meditaciones):")
        for idx, hook in enumerate(hooks, 1):
            print(f"  {idx}. \"{hook}\"")
    except Exception as exc:
        print(f"⚠️ Nota sobre análisis con Gemini: {exc}")

    print_banner("FASE 4 COMPLETADA EXITOSAMENTE")
    print(f"Tiempo total: {time.time() - t0:.2f}s | Datos listos en http://localhost:8855\n")


if __name__ == "__main__":
    main()
