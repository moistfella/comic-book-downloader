@echo off
echo Installing Python dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install
echo Installation complete!
pause
