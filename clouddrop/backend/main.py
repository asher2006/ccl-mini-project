import uuid
import logging
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path

from config import settings
from database import get_conn, init_db
from worker import enqueue_job, start_worker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CloudDrop API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_HOSTS = [
    "youtube.com", "youtu.be", "m.youtube.com", "music.youtube.com",
    "instagram.com", "instagr.am", "ig.me",
    "twitter.com", "x.com", "t.co",
    "tiktok.com", "vm.tiktok.com", "vt.tiktok.com",
    "reddit.com", "v.redd.it", "redd.it",
    "facebook.com", "fb.watch", "fb.com",
    "vimeo.com", "dailymotion.com", "dai.ly",
    "soundcloud.com", "twitch.tv", "clips.twitch.tv",
    "snapchat.com", "bilibili.com", "vk.com", "vkvideo.ru",
    "archive.org", "bandcamp.com",
]

def is_allowed_url(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    host = host.lower().removeprefix("www.")
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)

@app.on_event("startup")
async def startup():
    init_db()
    start_worker()
    logger.info("CloudDrop API started")

# ── Models ────────────────────────────────────────────────
class JobRequest(BaseModel):
    url: str
    format: str = "mp4"   # mp4 | mp3
    email: str = ""

class JobResponse(BaseModel):
    job_id: str
    status: str
    title: Optional[str] = None
    download_url: Optional[str] = None
    error_msg: Optional[str] = None
    format: str = "mp4"
    created_at: Optional[str] = None

# ── Routes ────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "region": settings.region}

@app.post("/api/jobs", response_model=JobResponse)
def create_job(req: JobRequest):
    clean_url = req.url.strip()
    if req.format not in ("mp4", "mp3"):
        raise HTTPException(400, "Format must be mp4 or mp3")
    if not clean_url:
        raise HTTPException(400, "URL is required")

    url_lower = clean_url.lower()
    if not (url_lower.startswith("http://") or url_lower.startswith("https://")):
        raise HTTPException(400, "URL must start with http:// or https://")
    if not is_allowed_url(clean_url):
        raise HTTPException(400, "Unsupported or unrecognized URL. Paste a direct video/post link (YouTube, Instagram, X/Twitter, TikTok, Reddit, Facebook, etc.).")

    job_id = str(uuid.uuid4())
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO jobs (job_id, url, format, status, email) VALUES (%s, %s, %s, 'queued', %s)",
        (job_id, clean_url, req.format, req.email.strip()),
    )
    conn.commit()
    cur.close()
    conn.close()

    enqueue_job(job_id, clean_url, req.format, req.email.strip())
    return JobResponse(job_id=job_id, status="queued", format=req.format)

@app.get("/api/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE job_id = %s", (job_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise HTTPException(404, "Job not found")
    return JobResponse(
        job_id=row["job_id"],
        status=row["status"],
        title=row["title"],
        download_url=row["download_url"],
        error_msg=row["error_msg"],
        format=row["format"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )

@app.get("/api/jobs")
def list_jobs(limit: int = 20):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT job_id, url, format, status, title, error_msg, created_at FROM jobs ORDER BY created_at DESC LIMIT %s", (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]

# Serve React frontend
frontend_dir = Path(__file__).parent.parent / "frontend" / "dist"
assets_dir = frontend_dir / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/favicon.svg")
    def serve_favicon():
        fav = frontend_dir / "favicon.svg"
        if fav.exists():
            return FileResponse(str(fav), media_type="image/svg+xml")
        raise HTTPException(404)

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        return FileResponse(str(frontend_dir / "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
