import os
import subprocess
import re
import threading
from queue import Queue
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, unquote
from playwright.sync_api import sync_playwright

BASE_URL = "https://getcomics.org"
HEADERS = {"User-Agent": "Mozilla/5.0"}
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

if os.path.isfile(os.path.join(DOWNLOAD_DIR, "deleteme.txt")):
    os.remove(os.path.join(DOWNLOAD_DIR, "deleteme.txt"))

session = requests.Session()
session.headers.update(HEADERS)


def clear():
    subprocess.run("cls" if os.name == "nt" else "clear", shell=True)


def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def normalize_comic_name(text):
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def extract_year(filename):
    match = re.search(r"\((\d{4})\)", filename)
    if match:
        return match.group(1)
    return None


def extract_year_from_text(text):
    match = re.search(r"\((\d{4})\)", text)
    return match.group(1) if match else None


def parse_comic_filename(filename):
    name = re.sub(r"\.(cbz|cbr)$", "", filename, flags=re.IGNORECASE)
    year = extract_year(name)
    name = re.sub(r"\s*\(\d{4}\)\s*", "", name).strip(" -_")
    name = re.sub(r"[-_]", " ", name).strip()
    name = re.sub(r"\s+", " ", name)
    numbers = list(re.finditer(r"\b(\d+)\b", name))
    if not numbers:
        return None, None, None
    last = numbers[-1]
    issue = str(int(last.group(1)))
    title = name[: last.start()].strip()
    return title, issue, year or "Unknown"


def build_indexes():
    named_index = {}
    raw_index = {}
    for file in os.listdir(DOWNLOAD_DIR):
        if not file.lower().endswith((".cbz", ".cbr")):
            continue
        path = os.path.join(DOWNLOAD_DIR, file)
        raw_index[file.lower()] = path
        comic, issue, _ = parse_comic_filename(file)
        if comic and issue:
            named_index[(normalize_comic_name(comic), str(issue))] = path
    return named_index, raw_index


def add_file_to_indexes(indexes, path):
    named_index, raw_index = indexes
    base = os.path.basename(path)
    raw_index[base.lower()] = path
    comic, issue, _ = parse_comic_filename(base)
    if comic and issue:
        named_index[(normalize_comic_name(comic), str(issue))] = path


def remove_file_from_indexes(indexes, path):
    named_index, raw_index = indexes
    base = os.path.basename(path)
    raw_index.pop(base.lower(), None)
    comic, issue, _ = parse_comic_filename(base)
    if comic and issue:
        named_index.pop((normalize_comic_name(comic), str(issue)), None)


def find_existing(indexes, raw_filename=None, comic=None, issue=None):
    named_index, raw_index = indexes
    if raw_filename:
        raw_path = raw_index.get(raw_filename.lower())
        if raw_path and os.path.exists(raw_path):
            return raw_path
        raw_path = os.path.join(DOWNLOAD_DIR, raw_filename)
        if os.path.exists(raw_path):
            return raw_path
    if comic and issue:
        key = (normalize_comic_name(comic), str(issue))
        existing = named_index.get(key)
        if existing and os.path.exists(existing):
            return existing
    return None


def search(query, page=1):
    url = f"{BASE_URL}/page/{page}/?s={quote_plus(query)}"
    r = session.get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    for article in soup.select("article"):
        a = article.select_one("h1 a, h2 a")
        if a:
            results.append((clean(a.text), a["href"]))
    return results


def get_download_link(post):
    r = session.get(post)
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        if clean(a.text) == "DOWNLOAD NOW" and "/dlds/" in a["href"]:
            return a["href"]
    return None


def resolve_dlds(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        real = None

        def handler(download):
            nonlocal real
            real = download.url

        page.on("download", handler)
        try:
            page.goto(url)
            page.wait_for_timeout(4000)
        except:
            pass
        browser.close()
        return real


def download(url):
    filename = unquote(url.split("/")[-1])
    filename = re.sub(r'[:*?"<>|]', "", filename)
    if not filename.endswith((".cbz", ".cbr")):
        filename += ".cbz"
    path = os.path.join(DOWNLOAD_DIR, filename)
    r = session.get(url, stream=True)
    total = int(r.headers.get("content-length", 0))
    done = 0
    print(f"Downloading: {filename}")
    with open(path, "wb") as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)
                done += len(chunk)
                if total:
                    percent = int(done * 100 / total)
                    print(f"\r{percent}% ", end="")
    print("\nSaved ->", path, "\n")
    return path


def rename_file(path, comic, issue, year):
    new_name = f"{comic} #{issue} ({year}).cbz"
    new_path = os.path.join(DOWNLOAD_DIR, new_name)
    os.rename(path, new_path)
    return new_path


def find_exact_issue(results, comic, issue):
    target = f"{comic} #{issue}".lower()
    banned = [
        "vol",
        "collection",
        "omnibus",
        "tpb",
        "incursion",
        "special",
        "annual",
        "w.i.p",
    ]
    for title, url in results:
        t = title.lower()
        if any(b in t for b in banned):
            continue
        if not t.startswith(comic.lower()):
            continue
        if target in t:
            return url
    return None


def search_issue_pages(comic, issue, max_pages=5):
    for page in range(1, max_pages + 1):
        results = search(f"{comic} #{issue}", page)
        post = find_exact_issue(results, comic, issue)
        if post:
            return post
    return None


def choose_result(query):
    page = 1
    while True:
        clear()
        print("Loading results...")
        results = search(query, page)
        clear()
        if not results:
            print("No results found.")
            return None, None
        print(f"Results for '{query}' (page {page})\n")
        for i, (title, _) in enumerate(results[:10], 1):
            print(f"{i}. {title}")
        print("\nN = next page | P = previous page | B = back")
        choice = input("\nSelect: ").lower().strip()
        if choice == "n":
            page += 1
            continue
        if choice == "p" and page > 1:
            page -= 1
            continue
        if choice == "b":
            return None, None
        try:
            index = int(choice) - 1
            return results[index][0], results[index][1]
        except:
            pass


def download_issue(query):
    indexes = build_indexes()
    selected_title, post = choose_result(query)
    if not post:
        return
    dlds = get_download_link(post)
    if not dlds:
        print("No download link.")
        input("Press Enter...")
        return

    real_queue = Queue(maxsize=1)

    def resolver():
        real_url = resolve_dlds(dlds)
        real_queue.put(real_url)

    threading.Thread(target=resolver, daemon=True).start()

    clear()
    print(f"Downloading: {selected_title}...\n")

    url = real_queue.get()
    if not url:
        print("Failed resolving download link.")
        input("Press Enter...")
        return

    raw_filename = re.sub(r'[:*?"<>|]', "", unquote(url.split("/")[-1]))
    if not raw_filename.endswith((".cbz", ".cbr")):
        raw_filename += ".cbz"
    parsed_comic, parsed_issue, _ = parse_comic_filename(raw_filename)

    print("Checking existing files...\n")
    existing = find_existing(
        indexes, raw_filename=raw_filename, comic=parsed_comic, issue=parsed_issue
    )
    if existing:
        print(f"Found: {os.path.basename(existing)}")
        input("\nPress Enter...")
        clear()
        return

    clear()
    path = download(url)
    add_file_to_indexes(indexes, path)

    clear()
    print(f"Downloaded {os.path.basename(path)}\n")

    rename = input("Rename downloaded file? (y/n): ").lower()
    if rename == "y":
        comic, issue, year = parse_comic_filename(os.path.basename(path))
        if year == "Unknown":
            title_year = extract_year_from_text(selected_title)
            if title_year:
                year = title_year
        if comic:
            remove_file_from_indexes(indexes, path)
            path = rename_file(path, comic, issue, year)
            add_file_to_indexes(indexes, path)

    input("\nDownload complete.\n\nPress Enter...")


def download_series(comic):
    indexes = build_indexes()
    rng = input("Issue range (example 1-10): ").strip()
    if not re.fullmatch(r"[0-9]+-[0-9]+", rng):
        print("Invalid range.")
        input("Press Enter...")
        return
    start, end = map(int, rng.split("-"))
    if start > end:
        print("Start issue cannot be greater than end issue.")
        input("Press Enter...")
        return

    next_issue_queue = Queue(maxsize=1)
    downloaded_files = []
    last_year = None
    existing_files = []

    def resolver():
        for issue in range(start, end + 1):
            existing = find_existing(indexes, comic=comic, issue=issue)
            if existing:
                existing_files.append((issue, existing))
                next_issue_queue.put(("EXISTS", issue, existing))
                continue
            post = search_issue_pages(comic, issue)
            if not post:
                next_issue_queue.put((None, issue, None))
                continue
            dlds = get_download_link(post)
            if not dlds:
                next_issue_queue.put((None, issue, None))
                continue
            real = resolve_dlds(dlds)
            if not real:
                next_issue_queue.put((None, issue, None))
                continue
            raw_filename = re.sub(r'[:*?"<>|]', "", unquote(real.split("/")[-1]))
            if not raw_filename.endswith((".cbz", ".cbr")):
                raw_filename += ".cbz"
            parsed_comic, parsed_issue, _ = parse_comic_filename(raw_filename)
            existing = find_existing(
                indexes,
                raw_filename=raw_filename,
                comic=parsed_comic,
                issue=parsed_issue,
            )
            if existing:
                existing_files.append((issue, existing))
                next_issue_queue.put(("EXISTS", issue, existing))
                continue
            next_issue_queue.put((real, issue, None))

    threading.Thread(target=resolver, daemon=True).start()

    for _ in range(start, end + 1):
        url, issue, extra = next_issue_queue.get()

        if url == "EXISTS":
            clear()
            print("Already downloaded:\n")
            for i, (iss, path) in enumerate(existing_files, 1):
                print(f"{i}. Issue #{iss} - {os.path.basename(path)}")
            continue

        clear()
        print("Downloaded Issues:")
        for i, path in enumerate(downloaded_files, start=1):
            print(f"{i}. {os.path.basename(path)}")

        if not url:
            print(f"\nIssue #{issue} not found or failed to resolve.\n")
            continue

        print(f"\nDownloading issue #{issue}...")
        path = download(url)
        downloaded_files.append(path)
        add_file_to_indexes(indexes, path)

        year = extract_year(os.path.basename(path))
        if year:
            last_year = year

    clear()
    if len(downloaded_files) == 0:
        print("No issues downloaded.")
        input("Press Enter...")
        return

    print("All downloaded issues:")
    for i, path in enumerate(downloaded_files, start=1):
        print(f"{i}. {os.path.basename(path)}")

    rename = input("\nRename all downloaded files? (y/n): ").lower()
    if rename == "y":
        for i, path in enumerate(downloaded_files):
            comic_name, issue_num, year = parse_comic_filename(os.path.basename(path))
            if year == "Unknown":
                title_year = extract_year_from_text(os.path.basename(path))
                year = title_year or last_year or "Unknown"
            if comic_name:
                remove_file_from_indexes(indexes, path)
                new_path = rename_file(path, comic_name, issue_num, year)
                downloaded_files[i] = new_path
                add_file_to_indexes(indexes, new_path)

    input("\nSeries complete.\n\nPress Enter...")


def main():
    try:
        while True:
            clear()
            print("Welcome\nPress Ctrl+C at any time to exit")
            option = input(
                "\nWhat are you looking for?\n1. Search comic\n2. Search Series\n\nChoice (1/2): "
            ).strip()
            if not option or option not in ("1", "2"):
                print("Invalid choice. Must be either option 1 or 2.")
                input("Press Enter to continue...")
                continue
            if option == "1":
                comic = input("\nWhat is the name of the comic you want to download?: ")
                download_issue(comic)
            elif option == "2":
                comic = input(
                    "\nWhat is the name of the comic series you want to download?: "
                )
                download_series(comic)
    except KeyboardInterrupt:
        print("\n\nExiting...")


if __name__ == "__main__":
    main()
