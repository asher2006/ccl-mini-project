#!/bin/bash
/opt/clouddrop/venv/bin/python -c 'import fitz; d = fitz.open(); p = d.new_page(); p.insert_text((72, 72), "CloudDrop AWS PDF Test"); d.save("/tmp/sample.pdf"); d.close()'
curl -s -X POST -F "files=@/tmp/sample.pdf" -F "operation=watermark" -F 'options={"text":"APPROVED"}' http://127.0.0.1:8000/api/jobs
echo ""
sleep 3
curl -s http://127.0.0.1:8000/api/jobs
echo ""
