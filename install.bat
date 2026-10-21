@echo off
echo Installing Python dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
set PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=120000
python -m playwright install chromium
echo Installation complete!
pause
