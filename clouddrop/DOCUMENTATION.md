# CloudDrop Architecture & Operations Manual

This document details every infrastructure component, security setting, server-level optimization, database schema, and operational command implemented across the **CloudDrop PDF Platform** deployed on Amazon Web Services (AWS).

---

## 1. System Architecture Overview

CloudDrop is an event-driven, decoupled cloud-native document processing pipeline. HTTP upload ingestion is strictly decoupled from heavy document conversion tasks (Ghostscript, PyMuPDF, Pillow) using AWS SQS.

```
                              ┌──────────────────────────────────────────────┐
                              │                 VPC 10.0.0.0/16              │
                              │                                              │
                              │   Public Subnet (10.0.1.0/24)                │
                              │   ┌───────────────────────────────────────┐  │
[Client Browser]              │   │ EC2 (t3.micro / Amazon Linux 2023)    │  │
       │                      │   │  ├── Nginx (Port 80)                  │  │
       │ HTTP/REST            │   │  │    └── Reverse Proxy -> 127.0.0.1  │  │
       ▼                      │   │  └── FastAPI + Uvicorn (Port 8000)    │  │
 [Internet Gateway] ─────────▶│   │       ├── /api/jobs (Ingest)          │  │
                              │   │       ├── /api/jobs (Poll status)     │  │
                              │   │       └── Worker Engine (Threaded)    │  │
                              │   └──────┬──────────────────────┬─────────┘  │
                              │          │                      │            │
                              │          │ Private 5432         │            │
                              │          ▼                      │            │
                              │   Private Subnet (10.0.10.0/24) │            │
                              │   ┌──────────────────────────┐  │            │
                              │   │ RDS PostgreSQL 15        │  │            │
                              │   │ (db.t3.micro - metadata) │  │            │
                              │   └──────────────────────────┘  │            │
                              └─────────────────────────────────┼────────────┘
                                                                │
                     ┌─────────────────── IAM Instance Role ────┴────────┐
                     ▼                                                   ▼
       ┌───────────────────────────┐                       ┌───────────────────────────┐
       │     Amazon S3 Bucket      │                       │      Amazon SQS Queue     │
       │  (clouddrop-media-23871)  │                       │      (clouddrop-jobs)     │
       │  - uploads/{job_id}/...   │◀── [Worker Polls] ────│  - Buffers job payloads   │
       │  - processed/{job_id}/... │                       │  - Decouples CPU spikes   │
       │  - 24hr auto-delete rule  │                       └───────────────────────────┘
       └───────────────────────────┘
```

### Core Flow:
1. **Upload:** Client selects files and submits to `POST /api/jobs`.
2. **Ingest:** FastAPI buffers the raw files directly into Amazon S3 under `uploads/{job_id}/...`.
3. **Queue:** FastAPI inserts a pending job entry into PostgreSQL on RDS, then enqueues an event message into Amazon SQS containing the job configuration.
4. **Process:** Background worker daemon long-polls SQS (`WaitTimeSeconds=10`), claims the job, fetches input objects from S3 into an isolated `/tmp/clouddrop/{job_id}/` sandbox, and executes the target binary engine:
   - **`compress`**: Ghostscript optimization (`gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/ebook ...`).
   - **`img2pdf`**: Pillow RGB conversion and multi-frame compilation into standard PDF.
   - **`pdf2img`**: PyMuPDF (`fitz`) rasterization to PNG at 72/150/300 DPI, auto-archived into a ZIP archive if multi-page.
5. **Store:** Worker uploads the result to `processed/{job_id}/` in S3.
6. **Download:** Worker updates PostgreSQL with `status = 'completed'` and generates a pre-signed S3 URL containing `ResponseContentDisposition="attachment; filename=..."` so clicking Download initiates an immediate file download rather than viewing inside browser tabs.

---

## 2. AWS Infrastructure & Network Configuration

### 2.1 Virtual Private Cloud (VPC)
- **VPC ID:** `vpc-06e4f0ecc87b1ac52`
- **IPv4 CIDR Block:** `10.0.0.0/16`
- **Internet Gateway:** `igw-0d0bb31d662fdfd23` attached to `vpc-06e4f0ecc87b1ac52`
- **Route Table:** `rtb-0a7f5bd4309ac9b1a`
  - `10.0.0.0/16` -> Local
  - `0.0.0.0/0` -> `igw-0d0bb31d662fdfd23`

### 2.2 Subnet Topology
| Subnet ID | Type | CIDR | Availability Zone | Purpose |
|---|---|---|---|---|
| `subnet-02b0a4e2fc3985d03` | Public | `10.0.1.0/24` | `us-east-1a` | EC2 Compute (`184.195.164.225`) |
| `subnet-08e77798b5fe9cac3` | Public | `10.0.2.0/24` | `us-east-1b` | Secondary public redundancy |
| `subnet-0ef5466a76941ae76` | Private | `10.0.10.0/24` | `us-east-1a` | RDS PostgreSQL Primary |
| `subnet-00bafaed83b83bee5` | Private | `10.0.20.0/24` | `us-east-1b` | RDS PostgreSQL Secondary (Subnet Group) |

- **RDS Subnet Group:** `clouddrop-db-subnet-group` containing `subnet-0ef5466a76941ae76` and `subnet-00bafaed83b83bee5`. Ensures database is physically isolated from direct public Internet access.

---

## 3. Security Groups & Least-Privilege Access Controls

### 3.1 EC2 Security Group (`clouddrop-ec2-sg` / `sg-09942c6b9fc5a0169`)
| Type | Protocol | Port Range | Source | Description |
|---|---|---|---|---|
| Inbound | TCP | 22 | `0.0.0.0/0` | SSH Administration (Key-pair authenticated) |
| Inbound | TCP | 80 | `0.0.0.0/0` | Public HTTP Web Traffic (Nginx) |
| Inbound | TCP | 443 | `0.0.0.0/0` | HTTPS Web Traffic |
| Inbound | TCP | 8000 | `0.0.0.0/0` | Direct FastAPI API testing |
| Outbound | ALL | ALL | `0.0.0.0/0` | Outbound Internet for AWS SDK, package updates |

### 3.2 RDS Security Group (`clouddrop-rds-sg` / `sg-09023a551558cb1d3`)
| Type | Protocol | Port Range | Source | Description |
|---|---|---|---|---|
| Inbound | TCP | 5432 | `sg-09942c6b9fc5a0169` | Only accepts connections originating from EC2 SG |
| Outbound | ALL | ALL | `0.0.0.0/0` | Internal VPC routing |

*No direct public ingress is allowed to RDS PostgreSQL.*

---

## 4. Managed AWS Services Specifications

### 4.1 Compute (Amazon EC2)
- **Instance ID:** `i-041d9c437d77036dc`
- **Instance Type:** `t3.micro` (2 vCPU, 1 GB RAM, Burstable compute)
- **Operating System:** Amazon Linux 2023 (Kernel 6.1)
- **Public IPv4:** `184.195.164.225`
- **IAM Instance Profile:** `clouddrop-ec2-role`
  - `AmazonS3FullAccess` (Object upload, download, presigned URL generation)
  - `AmazonSQSFullAccess` (Message polling, message deletion)
  - `AmazonSSMReadOnlyAccess` (Parameter retrieval on boot)
  - `AmazonSNSFullAccess` (Job completion status alerts)

### 4.2 Storage (Amazon S3)
- **Bucket Name:** `clouddrop-media-23871`
- **Region:** `us-east-1`
- **Default Encryption:** Server-Side Encryption with Amazon S3 managed keys (`SSE-S3`, AES-256)
- **Public Access:** Block All Public Access enabled (`true`). Files are strictly fetched via IAM or pre-signed URLs.
- **Lifecycle Expiration Configuration:**
  - Prefix `uploads/`: Auto-delete objects after 1 day (24 hours).
  - Prefix `processed/`: Auto-delete objects after 1 day (24 hours).
  - Prevents unbounded disk accumulation and minimizes storage costs.

### 4.3 Queue (Amazon SQS)
- **Queue Name:** `clouddrop-jobs`
- **Queue URL:** `https://sqs.us-east-1.amazonaws.com/205839628513/clouddrop-jobs`
- **Type:** Standard Queue
- **Default Visibility Timeout:** 300 seconds (matches worker timeout)
- **Message Retention Period:** 1 day (86,400 seconds)
- **Receive Message Wait Time:** 10 seconds (enables SQS Long Polling to eliminate empty read costs)

### 4.4 Relational Database (Amazon RDS PostgreSQL)
- **DB Identifier:** `clouddrop-db`
- **Engine:** PostgreSQL 15.7
- **Instance Class:** `db.t3.micro`
- **Storage:** 20 GB gp3 SSD
- **Endpoint:** `clouddrop-db.cb8g8iywyk62.us-east-1.rds.amazonaws.com:5432`
- **Database Name:** `clouddrop`
- **Master Username:** `clouddrop_admin`
- **Publicly Accessible:** Disabled (`No`)

### 4.5 AWS Systems Manager (SSM) Parameter Store
Configuration parameters injected dynamically into runtime memory:
| Parameter Path | Type | Value / Purpose |
|---|---|---|
| `/clouddrop/db_host` | String | `clouddrop-db.cb8g8iywyk62.us-east-1.rds.amazonaws.com` |
| `/clouddrop/db_name` | String | `clouddrop` |
| `/clouddrop/db_user` | String | `clouddrop_admin` |
| `/clouddrop/db_password` | SecureString | Stored encrypted; decrypted at runtime via KMS |
| `/clouddrop/s3_bucket` | String | `clouddrop-media-23871` |
| `/clouddrop/sqs_url` | String | SQS queue endpoint |
| `/clouddrop/sns_arn` | String | SNS topic ARN for status notifications |

---

## 5. Server-Level Optimizations & OS Tuning

### 5.1 Critical Memory Tuning: 2GB Swap Space
Because `t3.micro` instances have only 1 GB physical RAM, heavy rendering tasks (Ghostscript PDF re-sampling and PyMuPDF 300 DPI pixmap matrices) can trigger the Linux kernel Out-Of-Memory (OOM) killer.

To prevent process termination, a 2 GB virtual swap file was created:
```bash
sudo dd if=/dev/zero of=/swapfile bs=128M count=16
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo "/swapfile swap swap defaults 0 0" | sudo tee -a /etc/fstab
```
Verification:
```bash
free -h
# Output:
#               total        used        free      shared  buff/cache   available
# Mem:           946M        420M        180M         12M        346M        480M
# Swap:          2.0G        110M        1.8G
```

### 5.2 Nginx Reverse Proxy Configuration
Located at `/etc/nginx/conf.d/clouddrop.conf`:
```nginx
server {
    listen 80;
    server_name _;
    client_max_body_size 50m;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
        proxy_connect_timeout 10s;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }
}
```
**Key Tweaks:**
- `client_max_body_size 50m;`: Overrides Nginx's default 1 MB limit to allow large PDF/image batch uploads.
- `proxy_read_timeout 300s;`: Accommodates long conversion jobs without 504 Gateway Timeouts.
- `Cache-Control "no-cache, no-store, must-revalidate"`: Prevents browsers from aggressively caching stale Single-Page Application assets during updates.

### 5.3 Systemd Service (`clouddrop.service`)
Located at `/etc/systemd/system/clouddrop.service`:
```ini
[Unit]
Description=CloudDrop PDF Suite API and Background Worker
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/clouddrop/backend
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```
Commands to manage the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable clouddrop.service
sudo systemctl restart clouddrop.service
sudo journalctl -u clouddrop -f
```

---

## 6. Database Schema & State Machine

### 6.1 PostgreSQL Table DDL
```sql
CREATE TABLE IF NOT EXISTS jobs (
    job_id VARCHAR(64) PRIMARY KEY,
    operation VARCHAR(32) NOT NULL DEFAULT 'compress',
    status VARCHAR(32) NOT NULL DEFAULT 'queued',
    filename VARCHAR(512),
    original_size BIGINT DEFAULT 0,
    result_size BIGINT DEFAULT 0,
    download_url TEXT,
    error_msg TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);
```

### 6.2 Job State Lifecycle
```
[queued] ──▶ [processing] ──┬──▶ [completed] (with presigned S3 URL)
                            └──▶ [failed]    (with error trace)
```

---

## 7. Engine Implementations

### 7.1 PDF Compression (`compress`)
Compresses documents using the native Ghostscript engine (`gs`).
```bash
gs -sDEVICE=pdfwrite \
   -dCompatibilityLevel=1.4 \
   -dPDFSETTINGS=/ebook \
   -dNOPAUSE -dQUIET -dBATCH \
   -sOutputFile=output.pdf input.pdf
```
- Available optimization levels:
  - `screen`: 72 DPI (Lowest size, ideal for email attachments)
  - `ebook`: 150 DPI (Balanced readability and compression - Default)
  - `printer`: 300 DPI (High fidelity)
  - `prepress`: 300 DPI with full color-accuracy preservation

### 7.2 Images to PDF (`img2pdf`)
Combines multiple heterogeneous images (`.jpg`, `.jpeg`, `.png`, `.webp`) into a standardized PDF:
- Converts color profiles cleanly using `PIL.Image.convert('RGB')`.
- Compiles sequentially into a single PDF document.

### 7.3 PDF to Images (`pdf2img`)
Renders PDF vector pages into raster PNG images via PyMuPDF (`fitz`):
- Scales zoom factors using `fitz.Matrix(dpi / 72.0, dpi / 72.0)`.
- If single-page PDF: exports directly as a standalone `.png`.
- If multi-page PDF: renders each page sequentially (`page_001.png`, `page_002.png`, ...), bundles them into a compressed `.zip` archive, and provides a single direct-download archive.

### 7.4 Download Content-Disposition Configuration
In `worker.py`, when generating the pre-signed URL:
```python
s3.generate_presigned_url(
    "get_object",
    Params={
        "Bucket": settings.s3_bucket,
        "Key": key,
        "ResponseContentDisposition": f'attachment; filename="{filename}"',
    },
    ExpiresIn=86400,
)
```
This forces browser user-agents to trigger the native file save prompt instead of displaying inside browser PDF plugins.

---

## 8. CLI Testing & Verification Commands

### 8.1 API Health Check
```bash
curl -s http://184.195.164.225/api/health
# Response: {"status":"ok","service":"CloudDrop PDF Suite","region":"us-east-1"}
```

### 8.2 Testing Image to PDF
```bash
curl -X POST http://184.195.164.225/api/jobs \
  -F "operation=img2pdf" \
  -F "files=@test_image1.png" \
  -F "files=@test_image2.jpg"
```

### 8.3 Testing PDF Compression
```bash
curl -X POST http://184.195.164.225/api/jobs \
  -F "operation=compress" \
  -F 'options={"compress_level":"ebook"}' \
  -F "files=@document.pdf"
```

### 8.4 Testing PDF to Image
```bash
curl -X POST http://184.195.164.225/api/jobs \
  -F "operation=pdf2img" \
  -F 'options={"dpi":150}' \
  -F "files=@document.pdf"
```

### 8.5 Polling Job Status
```bash
curl -s http://184.195.164.225/api/jobs/<job_id>
```

---

## 9. Security & Production Checklist
- [x] RDS database contained strictly within private subnets with zero public IP routing.
- [x] Inbound PostgreSQL port 5432 limited specifically to the EC2 Security Group ID.
- [x] S3 bucket blocks all public ACLs; objects accessible only via short-lived pre-signed tokens.
- [x] Auto-expiration lifecycle rule configured on S3 (24h TTL) to prevent storage bloat.
- [x] 2GB Swap file active to protect EC2 instance against memory starvation.
- [x] Nginx reverse-proxy configured with `client_max_body_size 50m` and cache-busting headers.
- [x] SQS Long Polling enabled (`WaitTimeSeconds=10`) for minimal AWS billing overhead.


---

## 10. Load Balancing, Auto Scaling, CORS & Observability

### 10.1 Application Load Balancer (ALB) & Auto Scaling Group (ASG)
- **ALB Security Group (`clouddrop-alb-sg`):** Inbound Port 80 from `0.0.0.0/0`.
- **Target Group (`clouddrop-tg`):** HTTP Port 80 forward to EC2 with health checks on `/api/health` returning 200 OK.
- **Launch Template (`clouddrop-lt`):** Amazon Linux 2023 with instance profile `clouddrop-ec2-role` and security group `clouddrop-ec2-sg`.
- **Auto Scaling Group (`clouddrop-asg`):** Min: 1, Desired: 1, Max: 3, spanning public subnets (`subnet-02b0a4e2fc3985d03`, `subnet-08e77798b5fe9cac3`).
- **SQS Backlog Scaling Policy:** Target tracking metric scaling on `AWS/SQS ApproximateNumberOfMessagesVisible` (target value = 10.0). When work accumulates in the queue, ASG automatically scales out EC2 worker nodes.

### 10.2 S3 Bucket Policy (TLS Strict Enforcement + Least-Privilege IAM)
Defined in `s3-policy.json`:
- Denies all insecure HTTP (`aws:SecureTransport: false`) calls.
- Permits read/write/list explicitly to `arn:aws:iam::205839628513:role/clouddrop-ec2-role`.

### 10.3 Cross-Origin Resource Sharing (CORS)
Defined in `s3-cors.json`:
- Origins: `*`
- Methods: `GET`, `PUT`, `POST`, `HEAD`, `DELETE`
- Allowed Headers: `*`
- Expose Headers: `ETag`, `Content-Disposition`, `Content-Length`
- MaxAgeSeconds: `3600`

### 10.4 CloudWatch Operations Dashboard (`CloudDrop-Platform-Monitor`)
Defined in `cloudwatch-dashboard.json`:
- **EC2 CPU Utilization:** Line chart tracking compute load.
- **SQS Queue Backlog & In-Flight:** Real-time visibility into `ApproximateNumberOfMessagesVisible` and `ApproximateNumberOfMessagesNotVisible`.
- **RDS Health:** CPU utilization and active PostgreSQL connections.
- **Job Throughput:** Aggregated `NumberOfMessagesSent` vs `NumberOfMessagesDeleted`.
