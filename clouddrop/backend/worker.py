import boto3
import uuid
import json
import os
import subprocess
import threading
import time
import logging
from pathlib import Path
from config import settings

logger = logging.getLogger(__name__)

s3 = boto3.client("s3", region_name=settings.region)
sqs = boto3.client("sqs", region_name=settings.region)
sns = boto3.client("sns", region_name=settings.region)

DOWNLOAD_DIR = Path("/tmp/clouddrop")
DOWNLOAD_DIR.mkdir(exist_ok=True)
COOKIE_FILE = Path("/etc/clouddrop/cookies.txt")

def enqueue_job(job_id: str, url: str, fmt: str, email: str = ""):
    msg = json.dumps({"job_id": job_id, "url": url, "format": fmt, "email": email})
    sqs.send_message(QueueUrl=settings.sqs_url, MessageBody=msg)

def generate_presigned_url(key: str, expires: int = 3600) -> str:
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires,
    )

def upload_to_s3(file_path: Path, key: str) -> str:
    s3.upload_file(str(file_path), settings.s3_bucket, key)
    return key

def clean_error_message(raw_err: str) -> str:
    err_lower = raw_err.lower()
    if "sign in to confirm you’re not a bot" in err_lower or "bot verification" in err_lower:
        return "YouTube anti-bot verification triggered by AWS IP. YouTube blocks data-center servers without cookies."
    if "login required" in err_lower or "rate-limit reached" in err_lower:
        return "Instagram/YouTube rate-limit barrier reached on server IP."
    if "cookies" in err_lower and ("twitter" in err_lower or "x.com" in err_lower or "tiktok" in err_lower or "instagram" in err_lower):
        return f"This platform requires login cookies for server-side downloads. ({raw_err[:200]})"
    if "is not a valid url" in err_lower or "unsupported url" in err_lower:
        return "This link isn't a direct video/post URL. Open it and paste the direct media link."
    if "private video" in err_lower or "this video is private" in err_lower or "login required to view" in err_lower:
        return "This media is private or restricted."
    if "age" in err_lower and "confirm" in err_lower:
        return "Age-restricted media requires login cookies on the server."
    if "geo" in err_lower and ("restricted" in err_lower or "blocked" in err_lower):
        return "This media is geo-blocked in the AWS region (us-east-1)."
    if "removed" in err_lower or "taken down" in err_lower or "not available" in err_lower:
        return "This media has been removed or is not available."
    lines = [line.strip() for line in raw_err.split("\n") if line.strip() and not line.startswith("Deprecated Feature")]
    error_lines = [l for l in lines if l.startswith("ERROR:")]
    if error_lines:
        return error_lines[0].replace("ERROR: ", "").strip()
    return lines[-1] if lines else "Download failed. Please check the URL and try again."

def process_job(job_id: str, url: str, fmt: str, email: str = ""):
    from database import get_conn
    conn = get_conn()
    cur = conn.cursor()

    def update_status(status, **kwargs):
        fields = ", ".join(f"{k} = %s" for k in kwargs)
        vals = list(kwargs.values()) + [job_id]
        if fields:
            cur.execute(f"UPDATE jobs SET status=%s, {fields}, updated_at=NOW() WHERE job_id=%s",
                        [status] + vals)
        else:
            cur.execute("UPDATE jobs SET status=%s, updated_at=NOW() WHERE job_id=%s", [status, job_id])
        conn.commit()

    try:
        update_status("processing")
        out_dir = DOWNLOAD_DIR / job_id
        out_dir.mkdir(exist_ok=True)

        is_youtube = "youtube.com" in url.lower() or "youtu.be" in url.lower()

        base_args = [
            "--no-playlist",
            "--no-overwrites",
            "--impersonate", "chrome",
        ]
        if is_youtube:
            base_args += ["--extractor-args", "youtube:player_client=android_vr,ios"]
        base_args += [
            "--max-filesize", "200m",
            "--retries", "3",
            "--fragment-retries", "3",
            "--output", str(out_dir / "%(title).120B.%(ext)s"),
        ]

        if COOKIE_FILE.exists() and COOKIE_FILE.stat().st_size > 0:
            base_args.extend(["--cookies", str(COOKIE_FILE)])

        if settings.proxy_url:
            base_args.extend(["--proxy", settings.proxy_url])

        if fmt == "mp3":
            ydl_args = ["yt-dlp"] + base_args + [
                "-x", "--audio-format", "mp3",
                "-f", "bestaudio/best",
                url
            ]
        else:
            ydl_args = ["yt-dlp"] + base_args + [
                "-f", "best[ext=mp4][vcodec!=none]/best[vcodec!=none]/bestvideo+bestaudio/best",
                "--merge-output-format", "mp4",
                url
            ]

        result = subprocess.run(ydl_args, capture_output=True, text=True, timeout=420)
        if result.returncode != 0:
            clean_err = clean_error_message(result.stderr)
            raise Exception(clean_err)

        # Find downloaded file (pick largest if multiple artifacts)
        files = [f for f in out_dir.iterdir() if f.is_file()]
        if not files:
            raise Exception("No file downloaded by conversion worker.")
        file_path = max(files, key=lambda f: f.stat().st_size)
        title = file_path.stem

        # Upload to S3
        s3_key = f"downloads/{job_id}/{file_path.name}"
        upload_to_s3(file_path, s3_key)
        dl_url = generate_presigned_url(s3_key, expires=86400)

        update_status("complete", title=title, file_key=s3_key, download_url=dl_url)

        # Notify via SNS if email provided
        if email:
            try:
                sns.publish(
                    TopicArn=settings.sns_arn,
                    Subject="CloudDrop — Your download is ready!",
                    Message=f"Your file '{title}' is ready.\nDownload: {dl_url}\n\nLink expires in 24 hours.",
                )
            except Exception as se:
                logger.warning(f"SNS publish failed: {se}")

        # Cleanup local
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        update_status("failed", error_msg=str(e)[:500])
    finally:
        cur.close()
        conn.close()

def start_worker():
    """Background SQS worker thread"""
    def _poll():
        while True:
            try:
                resp = sqs.receive_message(
                    QueueUrl=settings.sqs_url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=10,
                    VisibilityTimeout=300,
                )
                msgs = resp.get("Messages", [])
                for msg in msgs:
                    body = json.loads(msg["Body"])
                    process_job(
                        body["job_id"],
                        body["url"],
                        body["format"],
                        body.get("email", ""),
                    )
                    sqs.delete_message(QueueUrl=settings.sqs_url, ReceiptHandle=msg["ReceiptHandle"])
            except Exception as e:
                logger.error(f"Worker error: {e}")
                time.sleep(5)
    t = threading.Thread(target=_poll, daemon=True)
    t.start()
    logger.info("SQS worker started")
