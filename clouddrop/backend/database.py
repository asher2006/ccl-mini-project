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
            id            SERIAL PRIMARY KEY,
            job_id        VARCHAR(64) UNIQUE NOT NULL,
            operation     VARCHAR(30) NOT NULL DEFAULT 'compress',
            status        VARCHAR(20) NOT NULL DEFAULT 'queued',
            filename      TEXT,
            original_size BIGINT DEFAULT 0,
            result_size   BIGINT DEFAULT 0,
            options       TEXT DEFAULT '{}',
            file_key      TEXT,
            download_url  TEXT,
            error_msg     TEXT,
            email         TEXT,
            created_at    TIMESTAMPTZ DEFAULT NOW(),
            updated_at    TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_job_id ON jobs(job_id);

        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='jobs' AND column_name='operation') THEN
                ALTER TABLE jobs ADD COLUMN operation VARCHAR(30) DEFAULT 'compress';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='jobs' AND column_name='filename') THEN
                ALTER TABLE jobs ADD COLUMN filename TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='jobs' AND column_name='original_size') THEN
                ALTER TABLE jobs ADD COLUMN original_size BIGINT DEFAULT 0;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='jobs' AND column_name='result_size') THEN
                ALTER TABLE jobs ADD COLUMN result_size BIGINT DEFAULT 0;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='jobs' AND column_name='options') THEN
                ALTER TABLE jobs ADD COLUMN options TEXT DEFAULT '{}';
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='jobs' AND column_name='url') THEN
                ALTER TABLE jobs ALTER COLUMN url DROP NOT NULL;
            END IF;
        END $$;
    """)
    conn.commit()
    cur.close()
    conn.close()
