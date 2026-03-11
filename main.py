import os
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

session = requests.Session()
session.headers.update(HEADERS)

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def clean(text):
    return re.sub(r"\s+", " ", text).strip()

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

def extract_year(filename):
    match = re.search(r"\((\d{4})\)", filename)
    if match:
        return match.group(1)
    return None

def rename_file(path, comic, issue, year):
    new_name = f"{comic} #{issue} ({year}).cbz"
    new_path = os.path.join(DOWNLOAD_DIR, new_name)
    os.rename(path, new_path)
    return new_path

def find_exact_issue(results, comic, issue):
    target = f"{comic} #{issue}".lower()
    banned = ["vol","collection","omnibus","tpb","incursion","special","annual","w.i.p"]
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
        results = search(query, page)
        if not results:
            print("No results found.")
            return None
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
            return None
        try:
            index = int(choice) - 1
            return results[index][1]
        except:
            pass

def download_issue(query):
    post = choose_result(query)
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
    print("Downloaded Issues:\n")
    print("<No issues downloaded yet>\n")
    print(f"Downloading: {query}...\n")

    url = real_queue.get()
    if not url:
        print("Failed resolving download link.")
        input("Press Enter...")
        return
    path = download(url)

    clear()
    print("Downloaded Issues:\n")
    print(f"1. {os.path.basename(path)}\n")

    rename = input("Rename downloaded file? (y/n): ").lower()
    if rename == "y":
        issue_match = re.search(r"#(\d+)", query)
        issue = issue_match.group(1) if issue_match else "1"
        comic = query.split("#")[0].strip()
        year = extract_year(os.path.basename(path)) or "Unknown"
        path = rename_file(path, comic, issue, year)

    input("Download complete. Press Enter...")

def download_series(comic):
    rng = input("Issue range (example 1-10): ").strip()
    if "-" not in rng:
        print("Invalid range.")
        input("Press Enter...")
        return
    start, end = map(int, rng.split("-"))

    next_issue_queue = Queue(maxsize=1)
    downloaded_files = []
    last_year = None

    def resolver():
        for issue in range(start, end + 1):
            post = search_issue_pages(comic, issue)
            if not post:
                next_issue_queue.put((None, issue))
                continue
            dlds = get_download_link(post)
            if not dlds:
                next_issue_queue.put((None, issue))
                continue
            real = resolve_dlds(dlds)
            next_issue_queue.put((real, issue))

    threading.Thread(target=resolver, daemon=True).start()

    for _ in range(start, end + 1):
        url, issue = next_issue_queue.get()
        clear()
        print("Downloaded Issues:")
        for i, path in enumerate(downloaded_files, start=1):
            print(f"{i}. {os.path.basename(path)}")
        print()
        if not url:
            print(f"Issue #{issue} not found or failed to resolve.\n")
            continue
        print(f"Downloading issue #{issue}...")
        path = download(url)
        downloaded_files.append(path)
        year = extract_year(os.path.basename(path))
        if year:
            last_year = year

    clear()
    print("All downloaded issues:")
    for i, path in enumerate(downloaded_files, start=1):
        print(f"{i}. {os.path.basename(path)}")
    print()

    rename = input("Rename all downloaded files? (y/n): ").lower()
    if rename == "y":
        issue_number = start
        for path in downloaded_files:
            year = extract_year(os.path.basename(path)) or last_year or "Unknown"
            new_path = rename_file(path, comic, issue_number, year)
            downloaded_files[issue_number - start] = new_path
            issue_number += 1

    input("Series complete. Press Enter...")

def main():
    while True:
        clear()
        cmd = input("Search comic (or /series <name>, exit): ").strip()
        if cmd.lower() == "exit":
            break
        if cmd.startswith("/series"):
            comic = cmd.replace("/series", "").strip()
            if not comic:
                print("Usage: /series <comic name>")
                input("Press Enter...")
                continue
            download_series(comic)
            continue
        download_issue(cmd)

if __name__ == "__main__":
    main()
