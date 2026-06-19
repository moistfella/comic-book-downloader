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


def get_download_links(post):
    r = session.get(post)
    soup = BeautifulSoup(r.text, "html.parser")
    primary_links = []
    mirror_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = clean(a.text).upper()
        if "/dls/" in href or "/dlds/" in href:
            if any(m in text for m in ("PIXELDRAIN", "MEDIAFIRE", "ZIPPYSHARE")):
                mirror_links.append(href)
            elif text in ("DOWNLOAD NOW", "DIRECT DOWNLOAD"):
                primary_links.append(href)
    return mirror_links + primary_links


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
            for _ in range(12):
                if real:
                    break
                if "pixeldrain.com/u/" in page.url:
                    file_id = page.url.split("/")[-1]
                    real = f"https://pixeldrain.com/api/file/{file_id}"
                    break
                page.wait_for_timeout(500)
            else:
                page.wait_for_timeout(1000)
        except:
            pass
        browser.close()
        return real


def download(url):
    r = session.get(url, stream=True)

    filename = None
    cd = r.headers.get("content-disposition")
    if cd:
        match = re.search(r'filename="([^"]+)"', cd)
        if match:
            filename = unquote(match.group(1))

    if not filename:
        filename = unquote(url.split("/")[-1])

    filename = re.sub(r'[:*?"<>|]', "", filename)
    if not filename.endswith((".cbz", ".cbr")):
        filename += ".cbz"

    path = os.path.join(DOWNLOAD_DIR, filename)
    total = int(r.headers.get("content-length", 0))
    done = 0
    last_percent = -1
    print(f"Downloading: {filename}")

    with open(path, "wb") as f:
        for chunk in r.iter_content(1024 * 256):
            if chunk:
                f.write(chunk)
                done += len(chunk)
                if total:
                    percent = int(done * 100 / total)
                    if percent != last_percent:
                        print(f"\r{percent}% ", end="")
                        last_percent = percent

    print("\nSaved ->", path, "\n")
    return path


def rename_file(path, comic, issue, year):
    new_name = f"{comic} #{issue} ({year}).cbz"
    new_path = os.path.join(DOWNLOAD_DIR, new_name)
    os.rename(path, new_path)
    return new_path


def parse_volume_filename(filename):
    name = re.sub(r"\.(cbz|cbr)$", "", filename, flags=re.IGNORECASE)
    year = extract_year(name) or "Unknown"
    vol_match = re.search(r"\b(vol|v|volume)\.?\s*0*(\d+)\b", name, re.IGNORECASE)
    if not vol_match:
        return None
    vol_num = str(int(vol_match.group(2)))
    series_raw = name[: vol_match.start()].strip()
    series = re.sub(r"\s+", " ", series_raw).strip(" -_:")
    post_raw = name[vol_match.end() :].strip()
    post_clean = re.sub(r"\s*\([^)]*\)\s*", " ", post_raw).strip()
    subtitle = re.sub(r"^[^\w]+", "", post_clean).strip()
    subtitle = re.sub(r"\b(tpb)\b", "", subtitle, flags=re.IGNORECASE).strip(" -_:")
    return series, vol_num, re.sub(r"\s+", " ", subtitle), year


def format_volume_name(series, vol_num, subtitle, year):
    if subtitle:
        return f"{series} Vol. {vol_num} - {subtitle} ({year}).cbz"
    return f"{series} Vol. {vol_num} ({year}).cbz"


def match_title_to_issue(title, comic, issue):
    clean_comic = re.sub(r"^the\s+", "", comic.lower().strip())
    escaped_comic = re.escape(clean_comic)
    target_issue = str(int(issue))
    pattern = rf"\b(?:the\s+)?{escaped_comic}\b\s*(?:#|–|-|_)?\s*0*{target_issue}\b"

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

    t = title.lower()
    if any(b in t for b in banned):
        return False
    if re.search(pattern, t):
        return True
    return False


def find_exact_issue(results, comic, issue):
    for title, url in results:
        if match_title_to_issue(title, comic, issue):
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
    dlds_list = get_download_links(post)
    if not dlds_list:
        print("No download link.")
        input("Press Enter...")
        return

    real_queue = Queue(maxsize=1)

    def resolver():
        real_url = None
        for dlds in dlds_list:
            real_url = resolve_dlds(dlds)
            if real_url:
                break
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
        parsed_vol = parse_volume_filename(os.path.basename(path))
        if parsed_vol:
            series, vol_num, subtitle, year = parsed_vol
            if year == "Unknown":
                year = extract_year_from_text(selected_title) or "Unknown"
            new_name = format_volume_name(series, vol_num, subtitle, year)
            new_path = os.path.join(DOWNLOAD_DIR, new_name)
            remove_file_from_indexes(indexes, path)
            os.rename(path, new_path)
            path = new_path
            add_file_to_indexes(indexes, path)
        else:
            comic, issue, year = parse_comic_filename(os.path.basename(path))
            if year == "Unknown":
                year = extract_year_from_text(selected_title) or "Unknown"
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
        needed_issues = []
        for issue in range(start, end + 1):
            existing = find_existing(indexes, comic=comic, issue=issue)
            if not existing:
                needed_issues.append(issue)

        resolved_posts = {}
        if needed_issues:
            max_pages = 15
            for page in range(1, max_pages + 1):
                unresolved = [i for i in needed_issues if i not in resolved_posts]
                if not unresolved:
                    break
                results = search(comic, page)
                if not results:
                    break
                for title, url in results:
                    for issue in list(unresolved):
                        if match_title_to_issue(title, comic, issue):
                            resolved_posts[issue] = url
                            unresolved.remove(issue)
                            break

        for issue in range(start, end + 1):
            existing = find_existing(indexes, comic=comic, issue=issue)
            if existing:
                existing_files.append((issue, existing))
                next_issue_queue.put(("EXISTS", issue, existing))
                continue
            post = resolved_posts.get(issue)
            if not post:
                next_issue_queue.put((None, issue, None))
                continue
            dlds_list = get_download_links(post)
            real = None
            for dlds in dlds_list:
                real = resolve_dlds(dlds)
                if real:
                    break
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
            parsed_vol = parse_volume_filename(os.path.basename(path))
            if parsed_vol:
                series, vol_num, subtitle, year = parsed_vol
                if year == "Unknown":
                    year = (
                        extract_year_from_text(os.path.basename(path))
                        or last_year
                        or "Unknown"
                    )
                new_name = format_volume_name(series, vol_num, subtitle, year)
                new_path = os.path.join(DOWNLOAD_DIR, new_name)
                remove_file_from_indexes(indexes, path)
                os.rename(path, new_path)
                downloaded_files[i] = new_path
                add_file_to_indexes(indexes, new_path)
            else:
                comic_name, issue_num, year = parse_comic_filename(
                    os.path.basename(path)
                )
                if year == "Unknown":
                    year = (
                        extract_year_from_text(os.path.basename(path))
                        or last_year
                        or "Unknown"
                    )
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
