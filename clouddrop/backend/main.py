import uuid
import json
import logging
from typing import Optional, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from pathlib import Path

from config import settings
from database import get_conn, init_db
from worker import enqueue_job, start_worker, s3, generate_presigned_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CloudDrop PDF API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    init_db()
    start_worker()
    logger.info("CloudDrop PDF API initialized")

# ── Models ────────────────────────────────────────────────────────────
class JobResponse(BaseModel):
    job_id: str
    status: str
    operation: str
    filename: Optional[str] = None
    original_size: Optional[int] = 0
    result_size: Optional[int] = 0
    download_url: Optional[str] = None
    error_msg: Optional[str] = None
    created_at: Optional[str] = None

# ── Routes ────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "CloudDrop PDF Suite", "region": settings.region}

@app.post("/api/jobs", response_model=JobResponse)
async def create_job(
    files: List[UploadFile] = File(...),
    operation: str = Form("compress"),
    options: str = Form("{}"),
    email: str = Form("")
):
    valid_ops = {"compress", "img2pdf", "pdf2img"}
    op = operation.lower().strip()
    if op not in valid_ops:
        raise HTTPException(400, f"Invalid operation. Must be one of: {', '.join(valid_ops)}")

    if not files or len(files) == 0:
        raise HTTPException(400, "Please upload at least one file.")

    try:
        opt_dict = json.loads(options) if options else {}
    except Exception:
        opt_dict = {}

    job_id = str(uuid.uuid4())
    input_keys = []
    total_size = 0
    primary_filename = files[0].filename or "document.pdf"

    # Upload files directly to S3
    for i, file in enumerate(files):
        contents = await file.read()
        file_size = len(contents)
        total_size += file_size
        safe_name = file.filename or f"file_{i}.bin"
        s3_key = f"uploads/{job_id}/{safe_name}"
        s3.put_object(
            Bucket=settings.s3_bucket,
            Key=s3_key,
            Body=contents
        )
        input_keys.append(s3_key)

    # Insert into RDS PostgreSQL
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO jobs (job_id, operation, status, filename, original_size, options, email)
        VALUES (%s, %s, 'queued', %s, %s, %s, %s)
        """,
        (job_id, op, primary_filename, total_size, json.dumps(opt_dict), email.strip()),
    )
    conn.commit()
    cur.close()
    conn.close()

    # Enqueue to SQS
    enqueue_job(
        job_id=job_id,
        operation=op,
        input_keys=input_keys,
        filename=primary_filename,
        original_size=total_size,
        options=opt_dict,
        email=email.strip()
    )

    return JobResponse(
        job_id=job_id,
        status="queued",
        operation=op,
        filename=primary_filename,
        original_size=total_size,
    )

@app.get("/api/download/{job_id}")
def download_file(job_id: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT file_key, filename, status FROM jobs WHERE job_id = %s", (job_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row or row.get("status") != "complete" or not row.get("file_key"):
        raise HTTPException(404, "File not ready or not found")
    fname = row.get("filename") or "document.pdf"
    url = generate_presigned_url(row["file_key"], expires=3600, filename=fname)
    return RedirectResponse(url=url, status_code=302)

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
        operation=row.get("operation") or "compress",
        filename=row.get("filename"),
        original_size=row.get("original_size") or 0,
        result_size=row.get("result_size") or 0,
        download_url=row.get("download_url"),
        error_msg=row.get("error_msg"),
        created_at=str(row["created_at"]) if row.get("created_at") else None,
    )

@app.get("/api/jobs")
def list_jobs(limit: int = 30):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT job_id, operation, status, filename, original_size, result_size, download_url, error_msg, created_at
        FROM jobs
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (limit,)
    )
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
