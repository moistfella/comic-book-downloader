# Manual Windows Installation

If you prefer not to use the automated `install.bat` script, you can install the dependencies and set up the environment manually by running the following commands in your terminal (Command Prompt or PowerShell):

### 1. Upgrade Pip (Optional but Recommended)
```cmd
python -m pip install --upgrade pip
```

### 2. Install Project Dependencies
Install the required libraries listed in `requirements.txt`:
```cmd
pip install -r requirements.txt
```

### 3. Install Playwright Browsers
Initialize the Chromium browser binaries required for the scraper to run:
```cmd
python -m playwright install
```

### 4. Running the Application
Once installation is complete, you can launch the downloader using:
```cmd
python main.py
```
