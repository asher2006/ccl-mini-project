import psycopg2
from psycopg2.extras import RealDictCursor
from config import settings

def get_conn():
    return psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        cursor_factory=RealDictCursor,
        connect_timeout=10,
    )

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id          SERIAL PRIMARY KEY,
            job_id      VARCHAR(64) UNIQUE NOT NULL,
            url         TEXT NOT NULL,
            format      VARCHAR(10) NOT NULL DEFAULT 'mp4',
            status      VARCHAR(20) NOT NULL DEFAULT 'queued',
            title       TEXT,
            file_key    TEXT,
            download_url TEXT,
            error_msg   TEXT,
            email       TEXT,
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            updated_at  TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_job_id ON jobs(job_id);
    """)
    conn.commit()
    cur.close()
    conn.close()
