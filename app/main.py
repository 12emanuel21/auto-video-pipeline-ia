"""FastAPI web server and API for Stoic Studio Dashboard."""

from pathlib import Path
import logging
from typing import Any
from pydantic import BaseModel

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import ASSETS_DIR, BASE_DIR
from app.core.pipeline import create_video_task
from app.core.scraper import extract_trending_metadata
from app.core.ai_studio import analyze_trends_and_generate_hooks
from app.database.db import (
    init_db,
    get_all_videos,
    get_video_by_id,
    update_video_status,
    save_trends,
    get_top_trends,
    save_social_token,
    get_active_token,
)
from app.core.tiktok import get_auth_url, exchange_code

logger = logging.getLogger("StoicStudioApp")

LATEST_GENERATED_HOOKS: list[str] = [
    "Estás sufriendo por cosas que jamás van a suceder, y Marco Aurelio te lo advirtió.",
    "Si no puedes dominar tus emociones hoy, alguien más las usará en tu contra mañana.",
    "La regla de oro de Marco Aurelio para destruir la ansiedad en solo 3 segundos.",
    "Deja de actuar como si tuvieras 1000 años por vivir; la muerte te observa ahora.",
    "El mayor error que cometes al despertar según el emperador Marco Aurelio."
]

app = FastAPI(
    title="Stoic Studio Engine",
    description="Local Autonomous Video Generator & Moderation Dashboard for TikTok Stoicism",
    version="1.0.0",
)

# Template and Static paths
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"

TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Mount static directories
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def to_web_video_url(raw_path: str | None) -> str | None:
    """Convert absolute filesystem video path to browser-accessible /assets/... URL."""
    if not raw_path:
        return None
    try:
        norm_path = Path(raw_path).resolve()
        # Find relative path under ASSETS_DIR
        rel = norm_path.relative_to(ASSETS_DIR.resolve())
        return f"/assets/{rel.as_posix()}"
    except Exception:
        # Fallback to output directory if file exists
        p = Path(raw_path)
        return f"/assets/output/{p.name}"


class VideoStatusUpdate(BaseModel):
    status: str


class GenerateRequest(BaseModel):
    theme: str = "disciplina"
    author: str = "Marco Aurelio"


SUGGESTED_THEMES = [
    {"id": "control_emocional", "name": "Control de las Emociones", "author": "Marco Aurelio"},
    {"id": "disciplina_hierro", "name": "Disciplina de Hierro", "author": "Marco Aurelio"},
    {"id": "superar_ira", "name": "Cómo Superar la Ira", "author": "Séneca"},
    {"id": "memento_mori", "name": "Memento Mori (Propósito de Vida)", "author": "Marco Aurelio"},
    {"id": "lo_que_no_controlas", "name": "Lo que no puedes controlar", "author": "Epicteto"},
    {"id": "resiliencia_adversidad", "name": "Fuerza ante la Adversidad", "author": "Séneca"},
]


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize database on server launch."""
    init_db()
    logger.info("Stoic Studio Engine started. Dashboard available at http://localhost:8855")


@app.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request) -> HTMLResponse:
    """Render main Stoic Studio control dashboard."""
    videos = get_all_videos()

    # Format videos with web-accessible URLs and safe rendering fields
    formatted_videos = []
    for v in videos:
        v_dict = dict(v)
        v_dict["web_video_url"] = to_web_video_url(v_dict.get("video_path"))
        formatted_videos.append(v_dict)

    # Compute metrics
    total_count = len(formatted_videos)
    pending_count = sum(1 for v in formatted_videos if v.get("status") == "READY_FOR_REVIEW")
    approved_count = sum(1 for v in formatted_videos if v.get("status") == "APPROVED")
    rejected_count = sum(1 for v in formatted_videos if v.get("status") == "REJECTED")
    draft_count = sum(1 for v in formatted_videos if v.get("status") == "DRAFT")

    metrics = {
        "total": total_count,
        "pending": pending_count,
        "approved": approved_count,
        "rejected": rejected_count,
        "draft": draft_count,
    }

    top_trends = get_top_trends(limit=5)
    
    active_tiktok = get_active_token(platform="tiktok")
    tiktok_connected = active_tiktok is not None

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "videos": formatted_videos,
            "metrics": metrics,
            "suggested_themes": SUGGESTED_THEMES,
            "top_trends": top_trends,
            "trending_hooks": LATEST_GENERATED_HOOKS,
            "tiktok_connected": tiktok_connected,
        },
    )


@app.post("/api/generate")
async def api_generate_video(
    background_tasks: BackgroundTasks,
    request: Request,
) -> dict[str, Any]:
    """Trigger an autonomous video creation task in the background."""
    # Support both JSON payload and multipart/form-data
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        theme = body.get("theme", "disciplina").strip()
        author = body.get("author", "Marco Aurelio").strip()
    else:
        form = await request.form()
        theme = str(form.get("theme", "disciplina")).strip()
        author = str(form.get("author", "Marco Aurelio")).strip()

    if not theme:
        raise HTTPException(status_code=400, detail="El tema no puede estar vacío.")

    # Run in FastAPI background task so request responds immediately
    background_tasks.add_task(create_video_task, theme=theme, author=author)

    logger.info("Enqueued video generation task: theme='%s', author='%s'", theme, author)
    return {
        "status": "processing",
        "message": "Generando video en segundo plano...",
        "theme": theme,
        "author": author,
    }


@app.post("/api/videos/{video_id}/status")
async def api_update_status(
    video_id: int,
    payload: VideoStatusUpdate,
) -> dict[str, Any]:
    """Update review status for a specific video."""
    allowed = {"APPROVED", "REJECTED", "READY_FOR_REVIEW", "PUBLISHED"}
    new_status = payload.status.upper().strip()

    if new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Estado inválido. Debe ser uno de: {list(allowed)}",
        )

    existing = get_video_by_id(video_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Video con ID {video_id} no encontrado.")

    success = update_video_status(video_id=video_id, status=new_status)
    if not success:
        raise HTTPException(status_code=500, detail="Error al actualizar la base de datos.")

    logger.info("Video ID %d actualizado a estado '%s'", video_id, new_status)
    return {
        "success": True,
        "video_id": video_id,
        "status": new_status,
    }


@app.get("/api/videos/status-counts")
async def api_status_counts() -> dict[str, int]:
    """Return live status counts for frontend polling and telemetry."""
    videos = get_all_videos()
    return {
        "total": len(videos),
        "pending": sum(1 for v in videos if v.get("status") == "READY_FOR_REVIEW"),
        "approved": sum(1 for v in videos if v.get("status") == "APPROVED"),
        "rejected": sum(1 for v in videos if v.get("status") == "REJECTED"),
        "draft": sum(1 for v in videos if v.get("status") == "DRAFT"),
    }


@app.get("/api/videos")
async def api_list_videos() -> list[dict[str, Any]]:
    """Return all videos with web URLs for dynamic client refresh."""
    videos = get_all_videos()
    results = []
    for v in videos:
        d = dict(v)
        d["web_video_url"] = to_web_video_url(d.get("video_path"))
        results.append(d)
    return results


@app.post("/api/trends/scrape")
async def api_scrape_trends(request: Request) -> dict[str, Any]:
    """Scrape trending videos for a tag, calculate engagement, save to SQLite and analyze hooks."""
    global LATEST_GENERATED_HOOKS
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        tag = body.get("tag", "estoicismo").strip()
    else:
        form = await request.form()
        tag = str(form.get("tag", "estoicismo")).strip()

    clean_tag = tag.lstrip("#") or "estoicismo"
    logger.info("Triggered trend scraping for tag: #%s", clean_tag)

    extracted = extract_trending_metadata(tag=clean_tag, max_results=8)
    saved_count = save_trends(tag=clean_tag, trends=extracted)

    new_hooks = []
    if extracted:
        try:
            new_hooks = analyze_trends_and_generate_hooks(top_trends=extracted[:5])
            LATEST_GENERATED_HOOKS = new_hooks
        except Exception as exc:
            logger.warning("Could not generate hooks from trends: %s", exc)

    return {
        "status": "success",
        "tag": clean_tag,
        "count": saved_count,
        "trends": extracted[:5],
        "hooks": new_hooks or LATEST_GENERATED_HOOKS,
    }


@app.get("/api/trends")
async def api_get_trends(limit: int = 5, tag: str | None = None) -> dict[str, Any]:
    """Retrieve top trending stoic videos and the latest analyzed viral hooks."""
    trends = get_top_trends(limit=limit, tag=tag)
    return {
        "tag": tag or "all",
        "count": len(trends),
        "trends": trends,
        "hooks": LATEST_GENERATED_HOOKS,
    }


@app.get("/auth/tiktok/login")
async def auth_tiktok_login():
    """Redirect to TikTok authorization URL."""
    auth_url = get_auth_url()
    return RedirectResponse(url=auth_url)


@app.get("/callback")
async def auth_tiktok_callback(code: str):
    """Handle TikTok OAuth callback."""
    try:
        token_data = exchange_code(code)
        access_token = token_data.get("access_token", "")
        refresh_token = token_data.get("refresh_token", "")
        open_id = token_data.get("open_id", "")
        
        if access_token and open_id:
            save_social_token(
                platform="tiktok",
                account_name="Autobots Default",
                open_id=open_id,
                access_token=access_token,
                refresh_token=refresh_token
            )
            return {"status": "success", "message": "Autenticación de TikTok exitosa"}
        else:
            return {"status": "error", "message": "No se recibieron tokens de la API"}
    except Exception as e:
        logger.error("Error exchanging code: %s", e)
        return {"status": "error", "detail": str(e)}

