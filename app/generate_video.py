import asyncio
import json
import random
from pathlib import Path
import edge_tts
from moviepy import (
    AudioFileClip,
    VideoFileClip,
    concatenate_videoclips,
)

# ---------------------------------------------------------
# CONFIGURACIÓN DE RUTAS DINÁMICAS
# ---------------------------------------------------------
# Detecta si el script se ejecuta dentro de 'app' o desde la raíz
CURRENT_DIR = Path(__file__).resolve().parent
BASE_DIR = CURRENT_DIR.parent if CURRENT_DIR.name == "app" else CURRENT_DIR

BROLL_DIR = BASE_DIR / "assets" / "video" / "broll"
OUTPUT_DIR = BASE_DIR / "assets" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VOICE = "es-ES-AlvaroNeural"  # Voz sobria, profunda y reflexiva

# Mapeo de términos narrativos a las carpetas base
TAG_MAP = {
    "caos": "caos",
    "control": "control",
    "foco": "foco",
    "tiempo": "tiempo",
    "esclavo digital": "caos",
    "pausa reflexiva": "control",
    "caminar firme": "foco",
    "reloj acelerado": "tiempo",
    "notificaciones invasivas": "caos",
    "pantalla apagada": "control",
    "ruido mental": "caos",
    "manos trabajando": "control",
    "rostro sereno": "foco",
    "rueda de hámster": "caos",
    "brújula en mano": "tiempo",
    "paso decidido": "foco",
    "multitud aplaudiendo": "caos",
    "espejo solitario": "control",
    "mirada introspectiva": "foco",
    "estática mental": "caos",
    "filtro depurador": "control",
    "claridad absoluta": "foco",
    "scroll compulsivo": "caos",
    "bloqueo de pantalla": "control",
    "respiración profunda": "foco",
    "tráfico colapsado": "caos",
    "respiración en calma": "control",
    "enfoque interno": "foco",
    "huracán urbano": "caos",
    "eje inmóvil": "control",
    "mirada inquebrantable": "foco",
}

AVAILABLE_CATEGORIES = ["caos", "control", "foco", "tiempo"]


async def synthesize_voice(text: str, output_path: str):
    """Sintetiza el guion a audio con entonación pausada y reflexiva."""
    communicate = edge_tts.Communicate(text, VOICE, rate="-4%", pitch="-2Hz")
    await communicate.save(output_path)


def resolve_clip(tag: str) -> Path:
    """Busca un clip correspondiente a la categoría o toma uno aleatorio si no existe."""
    category = TAG_MAP.get(tag.lower().strip())
    if not category or not (BROLL_DIR / category).exists():
        category = random.choice(AVAILABLE_CATEGORIES)

    available = list((BROLL_DIR / category).glob("*.mp4"))
    if not available:
        all_clips = list(BROLL_DIR.rglob("*.mp4"))
        if not all_clips:
            raise FileNotFoundError(
                f"No se encontraron videos .mp4 en '{BROLL_DIR}'. "
                "Verifica que los clips estén dentro de assets/video/broll/[caos|control|foco|tiempo]/"
            )
        return random.choice(all_clips)
    return random.choice(available)


def assemble_video(script_data: dict, output_filename: str):
    """Ensambla audio sintetizado y b-roll en un video vertical final (1080x1920)."""
    full_text = f"{script_data['hook']} {script_data['body']} {script_data['punchline']}"
    audio_path = str(OUTPUT_DIR / "temp_audio.mp3")

    print(f"\n[1/3] Sintetizando voz para: Día {script_data.get('day_number', 1)} - {script_data.get('theme', '')}")
    asyncio.run(synthesize_voice(full_text, audio_path))
    
    audio_clip = AudioFileClip(audio_path)
    total_duration = audio_clip.duration
    print(f"      Duración total de audio: {total_duration:.2f} segundos")

    print("[2/3] Ensamblando segmentos visuales...")
    sequence = script_data.get("visual_sequence", ["caos", "control", "foco"])
    sub_duration = total_duration / len(sequence)
    video_segments = []

    for tag in sequence:
        clip_path = resolve_clip(tag)
        print(f"      Usando: {clip_path.parent.name}/{clip_path.name} para '{tag}'")
        clip = VideoFileClip(str(clip_path))

        # Si el clip de Flow dura menos que el tercio del audio, repetir en bucle suave
        if clip.duration < sub_duration:
            loops = int(sub_duration // clip.duration) + 1
            clip = concatenate_videoclips([clip] * loops)

        # Recortar al tiempo exacto del segmento y asegurar resolución vertical 1080x1920
        clip = clip.subclipped(0, sub_duration).resized((1080, 1920))
        video_segments.append(clip)

    final_visual = concatenate_videoclips(video_segments, method="compose")
    final_video = final_visual.with_audio(audio_clip)

    print(f"[3/3] Exportando video final en: {output_filename}...")
    final_output = str(OUTPUT_DIR / output_filename)
    final_video.write_videofile(
        final_output,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        threads=4
    )

    # Liberar recursos y descriptores de archivo
    audio_clip.close()
    final_video.close()
    for seg in video_segments:
        seg.close()

    print(f"\n[+] Video generado exitosamente en: {final_output}\n")


if __name__ == "__main__":
    # Buscar el JSON en la raíz o en la carpeta app
    json_path = BASE_DIR / "scripts_batch.json"
    if not json_path.exists():
        json_path = CURRENT_DIR / "scripts_batch.json"

    if not json_path.exists():
        print(f"[ERROR] No se encontró 'scripts_batch.json' en {BASE_DIR} ni en {CURRENT_DIR}")
        exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        scripts = json.load(f)

    # Generar el Día 1 de prueba
    assemble_video(scripts[0], "dia_01_control_y_eleccion.mp4")