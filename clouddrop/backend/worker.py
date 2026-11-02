import boto3
import json
import os
import shutil
import subprocess
import threading
import time
import zipfile
import logging
from pathlib import Path
import fitz
from PIL import Image

from config import settings

logger = logging.getLogger(__name__)

s3 = boto3.client("s3", region_name=settings.region)
sqs = boto3.client("sqs", region_name=settings.region)
sns = boto3.client("sns", region_name=settings.region)

WORK_DIR = Path("/tmp/clouddrop")
WORK_DIR.mkdir(exist_ok=True, parents=True)

def enqueue_job(job_id: str, operation: str, input_keys: list, filename: str, original_size: int, options: dict, email: str = ""):
    msg = json.dumps({
        "job_id": job_id,
        "operation": operation,
        "input_keys": input_keys,
        "filename": filename,
        "original_size": original_size,
        "options": options,
        "email": email,
    })
    sqs.send_message(QueueUrl=settings.sqs_url, MessageBody=msg)

def generate_presigned_url(key: str, expires: int = 86400, filename: str = None) -> str:
    name = filename or Path(key).name or "document"
    return s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.s3_bucket,
            "Key": key,
            "ResponseContentDisposition": f'attachment; filename="{name}"',
        },
        ExpiresIn=expires,
    )

def execute_pdf_task(operation: str, in_files: list, out_path: Path, options: dict) -> tuple:
    """Returns (actual_out_path: Path, content_type: str)"""
    if operation == "compress":
        level = options.get("compress_level", "ebook")
        if level not in ("screen", "ebook", "printer", "prepress"):
            level = "ebook"
        in_file = in_files[0]
        cmd = [
            "gs",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            f"-dPDFSETTINGS=/{level}",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={str(out_path)}",
            str(in_file)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise Exception(f"Ghostscript compression failed: {res.stderr[:200]}")
        # If output is larger than input or empty, fallback to input
        if not out_path.exists() or out_path.stat().st_size == 0 or out_path.stat().st_size >= in_file.stat().st_size:
            shutil.copyfile(in_file, out_path)
        return out_path, "application/pdf"

    elif operation == "img2pdf":
        if not in_files:
            raise Exception("No image files provided.")
        doc = fitz.open()
        for img_path in in_files:
            img = Image.open(img_path)
            if img.mode != "RGB":
                img = img.convert("RGB")
            temp_jpg = img_path.with_suffix(".temp.jpg")
            img.save(temp_jpg, "JPEG", quality=95)
            
            img_doc = fitz.open(str(temp_jpg))
            rect = img_doc[0].rect
            pdf_bytes = img_doc.convert_to_pdf()
            img_pdf = fitz.open("pdf", pdf_bytes)
            page = doc.new_page(width=rect.width, height=rect.height)
            page.show_pdf_page(rect, img_pdf, 0)
            img_doc.close()
            img_pdf.close()
            temp_jpg.unlink(missing_ok=True)
            
        doc.save(str(out_path))
        doc.close()
        return out_path, "application/pdf"

    elif operation == "pdf2img":
        in_file = in_files[0]
        dpi = int(options.get("dpi", 150))
        doc = fitz.open(str(in_file))
        total_pages = len(doc)
        if total_pages == 0:
            raise Exception("PDF has no pages.")
        
        if total_pages == 1:
            pix = doc[0].get_pixmap(dpi=dpi)
            target = out_path.with_suffix(".png")
            pix.save(str(target))
            doc.close()
            return target, "image/png"
        else:
            target = out_path.with_suffix(".zip")
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
                for idx, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=dpi)
                    img_data = pix.tobytes("png")
                    zf.writestr(f"page_{idx+1:03d}.png", img_data)
            doc.close()
            return target, "application/zip"

    else:
        raise Exception(f"Unsupported operation: {operation}")

def process_job(job_id: str, operation: str, input_keys: list, filename: str, original_size: int, options: dict, email: str = ""):
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

    job_dir = WORK_DIR / job_id
    job_dir.mkdir(exist_ok=True, parents=True)

    try:
        update_status("processing")

        # 1. Download all inputs from S3
        local_inputs = []
        for i, key in enumerate(input_keys):
            ext = Path(key).suffix or ".bin"
            local_path = job_dir / f"input_{i}{ext}"
            s3.download_file(settings.s3_bucket, key, str(local_path))
            local_inputs.append(local_path)

        # 2. Determine initial output path
        stem = Path(filename).stem or "document"
        if operation == "compress":
            init_name = f"{stem}_compressed.pdf"
        elif operation == "img2pdf":
            init_name = f"{stem}_converted.pdf"
        elif operation == "pdf2img":
            init_name = f"{stem}_pages.png"
        else:
            init_name = f"{stem}_processed.pdf"

        target_path = job_dir / init_name

        # 3. Process task
        out_path, content_type = execute_pdf_task(operation, local_inputs, target_path, options)

        if not out_path.exists() or out_path.stat().st_size == 0:
            raise Exception("Processing resulted in empty file.")

        out_name = out_path.name
        result_size = out_path.stat().st_size

        # 4. Upload to S3
        s3_key = f"processed/{job_id}/{out_name}"
        s3.upload_file(
            str(out_path),
            settings.s3_bucket,
            s3_key,
            ExtraArgs={
                "ContentType": content_type,
                "ContentDisposition": f'attachment; filename="{out_name}"',
            }
        )
        dl_url = generate_presigned_url(s3_key, expires=86400, filename=out_name)

        # 5. Update DB
        update_status(
            "complete",
            filename=out_name,
            result_size=result_size,
            file_key=s3_key,
            download_url=dl_url
        )

        # 6. Notify SNS if requested
        if email:
            try:
                reduction = ""
                if original_size > 0 and operation == "compress":
                    diff = original_size - result_size
                    pct = round((diff / original_size) * 100, 1)
                    if diff > 0:
                        reduction = f" (Saved {pct}% / {round(diff/1024, 1)} KB)"
                sns.publish(
                    TopicArn=settings.sns_arn,
                    Subject=f"CloudDrop PDF — Your {operation.upper()} task is ready!",
                    Message=f"Your file '{out_name}' is ready{reduction}.\n\nDownload: {dl_url}\n\nLink expires in 24 hours.",
                )
            except Exception as se:
                logger.warning(f"SNS publish failed: {se}")

        # Cleanup
        shutil.rmtree(job_dir, ignore_errors=True)

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        update_status("failed", error_msg=str(e)[:500])
        shutil.rmtree(job_dir, ignore_errors=True)
    finally:
        cur.close()
        conn.close()

def start_worker():
    """Background SQS worker thread"""
    def _poll():
        print(f"[WORKER] SQS poller started for queue: {settings.sqs_url}", flush=True)
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
                    print(f"[WORKER] Processing message from SQS...", flush=True)
                    body = json.loads(msg["Body"])
                    print(f"[WORKER] Starting job: {body.get('job_id')} ({body.get('operation')})", flush=True)
                    process_job(
                        job_id=body["job_id"],
                        operation=body.get("operation", "compress"),
                        input_keys=body.get("input_keys", []),
                        filename=body.get("filename", "document.pdf"),
                        original_size=body.get("original_size", 0),
                        options=body.get("options", {}),
                        email=body.get("email", ""),
                    )
                    sqs.delete_message(QueueUrl=settings.sqs_url, ReceiptHandle=msg["ReceiptHandle"])
                    print(f"[WORKER] SQS message deleted for job: {body.get('job_id')}", flush=True)
            except Exception as e:
                print(f"[WORKER ERROR]: {e}", flush=True)
                time.sleep(5)
    t = threading.Thread(target=_poll, daemon=True)
    t.start()
    logger.info("CloudDrop PDF SQS worker started")
