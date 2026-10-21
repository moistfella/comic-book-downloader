#!/bin/bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=120000 python3 -m playwright install chromium
