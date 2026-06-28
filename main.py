import os
import subprocess
import re
import threading
from queue import Queue
from urllib.parse import unquote

import utils
import downloader

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

if os.path.isfile(os.path.join(DOWNLOAD_DIR, "deleteme.txt")):
    os.remove(os.path.join(DOWNLOAD_DIR, "deleteme.txt"))

def clear():
    subprocess.run("cls" if os.name == "nt" else "clear", shell=True)

def build_indexes():
    named_index = {}
    raw_index = {}
    for file in os.listdir(DOWNLOAD_DIR):
        if not file.lower().endswith((".cbz", ".cbr")):
            continue
        path = os.path.join(DOWNLOAD_DIR, file)
        raw_index[file.lower()] = path
        comic, issue, _ = utils.parse_comic_filename(file)
        if comic and issue:
            named_index[(utils.normalize_comic_name(comic), str(issue))] = path
    return named_index, raw_index

def add_file_to_indexes(indexes, path):
    named_index, raw_index = indexes
    base = os.path.basename(path)
    raw_index[base.lower()] = path
    comic, issue, _ = utils.parse_comic_filename(base)
    if comic and issue:
        named_index[(utils.normalize_comic_name(comic), str(issue))] = path

def remove_file_from_indexes(indexes, path):
    named_index, raw_index = indexes
    base = os.path.basename(path)
    raw_index.pop(base.lower(), None)
    comic, issue, _ = utils.parse_comic_filename(base)
    if comic and issue:
        named_index.pop((utils.normalize_comic_name(comic), str(issue)), None)

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
        key = (utils.normalize_comic_name(comic), str(issue))
        existing = named_index.get(key)
        if existing and os.path.exists(existing):
            return existing
    return None

def rename_file(path, comic, issue, year):
    new_name = f"{comic} #{issue} ({year}).cbz"
    new_path = os.path.join(DOWNLOAD_DIR, new_name)
    os.rename(path, new_path)
    return new_path

def choose_result(query):
    page = 1
    while True:
        clear()
        print("Loading results...")
        results = downloader.search(query, page)
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
    dlds_list = downloader.get_download_links(post)
    if not dlds_list:
        print("No download link.")
        input("Press Enter...")
        return

    real_queue = Queue(maxsize=1)

    def resolver():
        real_url = None
        for dlds in dlds_list:
            real_url = downloader.resolve_dlds(dlds)
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
    parsed_comic, parsed_issue, _ = utils.parse_comic_filename(raw_filename)

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
    path = downloader.download(url, DOWNLOAD_DIR)
    add_file_to_indexes(indexes, path)

    clear()
    print(f"Downloaded {os.path.basename(path)}\n")

    rename = input("Rename downloaded file? (y/n): ").lower()
    if rename == "y":
        parsed_vol = utils.parse_volume_filename(os.path.basename(path))
        if parsed_vol:
            series, vol_num, subtitle, year = parsed_vol
            if year == "Unknown":
                year = utils.extract_year_from_text(selected_title) or "Unknown"
            new_name = utils.format_volume_name(series, vol_num, subtitle, year)
            new_path = os.path.join(DOWNLOAD_DIR, new_name)
            remove_file_from_indexes(indexes, path)
            os.rename(path, new_path)
            path = new_path
            add_file_to_indexes(indexes, path)
        else:
            comic, issue, year = utils.parse_comic_filename(os.path.basename(path))
            if year == "Unknown":
                year = utils.extract_year_from_text(selected_title) or "Unknown"
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
                results = downloader.search(comic, page)
                if not results:
                    break
                for title, url in results:
                    for issue in list(unresolved):
                        if utils.match_title_to_issue(title, comic, issue):
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
            dlds_list = downloader.get_download_links(post)
            real = None
            for dlds in dlds_list:
                real = downloader.resolve_dlds(dlds)
                if real:
                    break
            if not real:
                next_issue_queue.put((None, issue, None))
                continue
            raw_filename = re.sub(r'[:*?"<>|]', "", unquote(real.split("/")[-1]))
            if not raw_filename.endswith((".cbz", ".cbr")):
                raw_filename += ".cbz"
            parsed_comic, parsed_issue, _ = utils.parse_comic_filename(raw_filename)
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
        path = downloader.download(url, DOWNLOAD_DIR)
        downloaded_files.append(path)
        add_file_to_indexes(indexes, path)

        year = utils.extract_year(os.path.basename(path))
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
            parsed_vol = utils.parse_volume_filename(os.path.basename(path))
            if parsed_vol:
                series, vol_num, subtitle, year = parsed_vol
                if year == "Unknown":
                    year = utils.extract_year_from_text(os.path.basename(path)) or last_year or "Unknown"
                new_name = utils.format_volume_name(series, vol_num, subtitle, year)
                new_path = os.path.join(DOWNLOAD_DIR, new_name)
                remove_file_from_indexes(indexes, path)
                os.rename(path, new_path)
                downloaded_files[i] = new_path
                add_file_to_indexes(indexes, new_path)
            else:
                comic_name, issue_num, year = utils.parse_comic_filename(os.path.basename(path))
                if year == "Unknown":
                    year = utils.extract_year_from_text(os.path.basename(path)) or last_year or "Unknown"
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
