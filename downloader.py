import os
import re
import shutil
import sys
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, unquote
from playwright.sync_api import sync_playwright
from utils import clean

BASE_URL = "https://getcomics.org"
HEADERS = {"User-Agent": "Mozilla/5.0"}

session = requests.Session()
session.headers.update(HEADERS)


def search(query, page=1):
    url = f"{BASE_URL}/page/{page}/?s={quote_plus(query)}"
    r = session.get(url, timeout=30)
    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    for article in soup.select("article"):
        a = article.select_one("h1 a, h2 a")
        if a:
            results.append((clean(a.text), a["href"]))
    return results


def get_download_links(post):
    r = session.get(post, timeout=30)
    soup = BeautifulSoup(r.text, "html.parser")
    primary_links = []
    mirror_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = clean(a.text).upper()
        if "/dls/" in href or "/dlds/" in href:
            if any(m in text for m in ("PIXELDRAIN", "MEDIAFIRE")):
                mirror_links.append(href)
            elif text in ("DOWNLOAD NOW", "DIRECT DOWNLOAD"):
                primary_links.append(href)
    return mirror_links + primary_links


def resolve_dlds(url):
    try:
        with session.get(url, stream=True, timeout=15) as r:
            final_url = r.url
            ct = r.headers.get("content-type", "").lower()
            cd = r.headers.get("content-disposition", "").lower()
            if "pixeldrain.com/u/" in final_url:
                file_id = final_url.rstrip("/").split("/")[-1]
                return f"https://pixeldrain.com/api/file/{file_id}"
            if (
                "attachment" in cd
                or any(
                    t in ct
                    for t in (
                        "application/octet-stream",
                        "application/x-cb",
                        "application/zip",
                        "application/vnd.rar",
                    )
                )
                or final_url.lower()
                .split("?")[0]
                .endswith((".cbz", ".cbr", ".zip", ".rar"))
            ):
                return final_url
    except Exception:
        pass

    launch_args = {"headless": True}
    if sys.platform.startswith("linux"):
        for binary in [
            "chromium",
            "chromium-browser",
            "google-chrome",
            "google-chrome-stable",
            "brave-browser",
            "brave",
            "microsoft-edge",
            "microsoft-edge-stable",
            "opera",
            "vivaldi",
        ]:
            path = shutil.which(binary)
            if path:
                launch_args["executable_path"] = path
                break
    with sync_playwright() as p:
        browser = None
        last_err = None
        candidates = [launch_args]
        for ch in ("msedge", "chrome"):
            candidates.append({"headless": True, "channel": ch})
        if sys.platform == "win32":
            roots = [
                os.environ.get("PROGRAMFILES", ""),
                os.environ.get("PROGRAMFILES(X86)", ""),
                os.environ.get("LOCALAPPDATA", ""),
            ]
            rel_paths = [
                r"Google\Chrome\Application\chrome.exe",
                r"Microsoft\Edge\Application\msedge.exe",
                r"BraveSoftware\Brave-Browser\Application\brave.exe",
            ]
            for root in roots:
                for rel in rel_paths:
                    exe = os.path.join(root, rel)
                    if root and os.path.isfile(exe):
                        candidates.append({"headless": True, "executable_path": exe})
        for args in candidates:
            try:
                browser = p.chromium.launch(**args)
                break
            except Exception as e:
                last_err = e
        if not browser:
            raise RuntimeError(
                f"Playwright failed to launch Chromium browser.\n"
                f"Try running: python -m playwright install chromium\n"
                f"If you are on Arch Linux or CachyOS, make sure you have a system browser installed:\n"
                f"  sudo pacman -S chromium\n"
                f"Original error: {last_err}"
            ) from last_err
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
        except Exception:
            pass
        browser.close()
        return real


def download(url, download_dir):
    r = session.get(url, stream=True, timeout=30)
    r.raise_for_status()
    filename = None
    cd = r.headers.get("content-disposition")
    if cd:
        match = re.search(r'filename="([^"]+)"', cd)
        if match:
            filename = unquote(match.group(1))
    if not filename:
        filename = unquote(url.split("/")[-1])
    filename = os.path.basename(filename)
    filename = re.sub(r'[:*?"<>|]', "", filename)
    if not filename.endswith((".cbz", ".cbr")):
        filename += ".cbz"

    path = os.path.join(download_dir, filename)
    total = int(r.headers.get("content-length", 0))
    done = 0
    start_time = time.time()
    print(f"Downloading: {filename}")
    with open(path, "wb") as f:
        for chunk in r.iter_content(1024 * 256):
            if chunk:
                f.write(chunk)
                done += len(chunk)
                if total:
                    percent = int(done * 100 / total)
                    elapsed = time.time() - start_time
                    speed = (done / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                    speed_str = f"{int(speed)}" if speed >= 1 else f"{speed:.1f}"
                    remaining = total - done
                    eta = int(remaining / (speed * 1024 * 1024)) if speed > 0 else 0
                    print(
                        f"\r{percent}% complete - {speed_str} MB/s - {eta} seconds remaining   ",
                        end="",
                        flush=True,
                    )
    print("\nSaved ->", path, "\n")
    return path
