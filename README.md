# Comic Book Downloader

A terminal-based Python tool to search, download, and rename comics from [GetComics.org](https://getcomics.org).

Supports single-issue downloads and full comic runs.

## Features

- Search for comics by name.
- Download single issues or an entire series.
- Automatically resolves GetComics download links.
- Supports `.cbz` and `.cbr` files.
- Option to rename downloaded files with consistent formatting.
- Clean terminal output with download progress.

## Requirements

- Python 3.10+
- Internet

## Installation

<details>
<summary>Windows Installation</summary>
1. Clone this repository:

```bash
git clone https://github.com/moistfella/comic-book-downloader.git
```

2. Run the install file to install dependencies:

```
install.bat
```

3. To launch the program, run:

```
run.bat
```

> `install.bat` installs required Python packages (`requests`, `beautifulsoup4`, `playwright`) and runs `python -m playwright install`.  
> `run.bat` simply starts the main script (`main.py`) in the terminal.

</details>

<details>
<summary>Linux instructions</summary>
In a new terminal window:

1. Clone this repository:

```bash
git clone https://github.com/moistfella/comic-book-downloader.git
```

2. Open the directory

```bash
cd comic-book-downloader
```

3. Start a virtual environment to avoid system conflicts

```bash
python -m venv env
```

4. Activate the virtual environment

```bash
source env/bin/activate
```

5. Install requirements

```bash
pip install -r requirements.txt
```

6. Install playwright

```bash
python -m playwright install
```

7. Run the program

```bash
python main.py
```

</details>

## Usage

- **Single issue download:**  
  Launch the program and enter 1 then type the comic name when prompted. Select the issue from the search results to download.

- **Series download:**  
  Launch the program and enter 2 then type the comic series name when prompted. Then enter the issue range (e.g., `1-10`) to download multiple issues automatically.

- **Renaming:**  
  After each download (or series), the program prompts to rename files to a consistent format like:

  ```
  Ultimate Spider-Man #1 (2024).cbz
  ```

- **Exit:**  
  Click Ctrl+C at any time to exit the program.

## License

This project is licensed under the [MIT License](LICENSE).
