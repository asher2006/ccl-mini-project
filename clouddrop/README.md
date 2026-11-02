# CloudDrop PDF Platform

Why are you reading this? Don't you have your own code to write? Stop snooping around my repository.

It's a retro Windows 95-styled cloud PDF processing suite running on AWS (EC2, S3, SQS, RDS PostgreSQL). It does three things and only three things:
1. **Images to PDF** (`img2pdf`) - Combines JPG/PNG/WEBP images into a clean PDF.
2. **PDF to Images** (`pdf2img`) - Renders PDF pages to high-res PNGs (auto-zipped if multi-page).
3. **Compress PDF** (`compress`) - Crushes PDF file size using Ghostscript optimization.

If you're looking for how every single tiny knob was turned or why your setup is broken, go read [DOCUMENTATION.md](DOCUMENTATION.md) and leave me alone.

Now close this tab.
