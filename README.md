# Comic Book Downloader

A terminal-based Python tool to search, download, and rename comics from [GetComics.org](https://getcomics.org). 

Supports single-issue downloads and full comic runs.

Has not been tested on any other operating systems except Windows 11.

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

## Usage

- **Single issue download:**  
  Launch the program and type the comic name. Select the issue from the search results to download.

- **Series download:**  
  Use the command `/series <comic name>` and enter the issue range (e.g., `1-10`) to download multiple issues automatically.

- **Renaming:**  
  After each download (or series), the program prompts to rename files to a consistent format like:  
  ```
  Ultimate Spider-Man #1 (2024).cbz
  ```

- **Exit:**  
  Type `exit` at the prompt to close the program.

## License

This project is licensed under the [MIT License](LICENSE).
