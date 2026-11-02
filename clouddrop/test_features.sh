#!/bin/bash
# 1. Test pdf2img
echo "Testing pdf2img..."
curl -s -X POST -F "files=@/tmp/sample.pdf" -F "operation=pdf2img" -F 'options={"dpi":150}' http://127.0.0.1:8000/api/jobs
echo ""
sleep 3

# 2. Test img2pdf
echo "Creating test image..."
/opt/clouddrop/venv/bin/python -c 'from PIL import Image; img = Image.new("RGB", (300, 300), color="blue"); img.save("/tmp/test_blue.png")'
echo "Testing img2pdf..."
curl -s -X POST -F "files=@/tmp/test_blue.png" -F "operation=img2pdf" http://127.0.0.1:8000/api/jobs
echo ""
sleep 3

echo "Recent jobs:"
curl -s "http://127.0.0.1:8000/api/jobs?limit=5"
echo ""
