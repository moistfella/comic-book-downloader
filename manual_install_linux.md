# Manual Linux Installation

If you prefer not to use the automated `install.sh` script, you can install the dependencies and set up the environment manually by running the following commands in your terminal:

### 1. Create a Virtual Environment
Initialize a local virtual environment named `env`:
```bash
python3 -m venv env
```

### 2. Activate the Virtual Environment
Activate the environment to ensure package isolation:
```bash
source env/bin/activate
```

### 3. Upgrade Pip
```bash
python3 -m pip install --upgrade pip
```

### 4. Install Project Dependencies
Install the required libraries listed in `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 5. Install Playwright Browsers
Initialize the Chromium browser binaries required for the scraper to run:
```bash
python3 -m playwright install
```

⚠️ **Arch Linux / CachyOS users:** Playwright browser binaries might be missing necessary system libraries. Please install system Chromium before running the tool: `sudo pacman -S chromium`

### 6. Running the Application
Ensure your virtual environment is active  (step 2), then launch the downloader using:
```bash
python3 main.py
```
