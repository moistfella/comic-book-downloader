import os
import subprocess
import re
import threading
from queue import Queue
from urllib.parse import unquote

import utils
import downloader
import requests

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
    os.replace(path, new_path)
    return new_path


def choose_result(query):
    page = 1
    while True:
        clear()
        print("Loading results...")
        try:
            results = downloader.search(query, page)
        except requests.RequestException:
            clear()
            print(
                "\nNetwork connection error. Please check your internet connection and try again."
            )
            input("\nPress Enter...")
            return None, None
        clear()
        if not results:
            print("No results found.")
            print(
                "\nTip: If you searched with a combined name (like 'SuperSons' or 'supersons'), try adding spaces (like 'Super Sons')."
            )
            input("\nPress Enter...")
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
        except Exception:
            pass


def download_issue(query):
    if not query:
        return
    query = utils.preprocess_search_query(query)
    indexes = build_indexes()
    selected_title, post = choose_result(query)
    if not post:
        return
    try:
        dlds_list = downloader.get_download_links(post)
    except requests.RequestException:
        print(
            "\nNetwork connection error. Please check your internet connection and try again."
        )
        input("Press Enter...")
        return
    if not dlds_list:
        print("No download link.")
        input("Press Enter...")
        return

    real_queue = Queue(maxsize=1)

    def resolver():
        real_url = None
        try:
            for dlds in dlds_list:
                try:
                    real_url = downloader.resolve_dlds(dlds)
                except Exception as e:
                    import traceback

                    err_msg = (
                        f"\n[Error] Link resolution failed: {e}\n"
                        f"If this issue persists, please submit an issue at:\n"
                        f"https://github.com/moistfella/comic-book-downloader/issues"
                    )
                    print(utils.sanitize_text(err_msg))
                    try:
                        with open("error.log", "a") as f:
                            f.write(
                                utils.sanitize_text(
                                    f"--- ERROR: {e} ---\n{traceback.format_exc()}\n"
                                )
                            )
                    except Exception:
                        pass
                if real_url:
                    break
        finally:
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
    try:
        path = downloader.download(url, DOWNLOAD_DIR)
    except requests.RequestException:
        print(
            "\n[Error] Failed to download file. Please check your network connection and try again."
        )
        input("\nPress Enter...")
        return
    add_file_to_indexes(indexes, path)

    clear()
    print(f"Downloaded {os.path.basename(path)}\n")

    rename = input("Rename downloaded file? (y/n): ").lower()
    if rename == "y":
        parsed_vol = utils.parse_volume_filename(os.path.basename(path))
        if parsed_vol:
            series, vol_num, subtitle, year = parsed_vol
            if year == "Unknown":
                year = utils.extract_year(selected_title) or "Unknown"
            new_name = utils.format_volume_name(series, vol_num, subtitle, year)
            new_path = os.path.join(DOWNLOAD_DIR, new_name)
            remove_file_from_indexes(indexes, path)
            os.replace(path, new_path)
            path = new_path
            add_file_to_indexes(indexes, path)
        else:
            comic, issue, year = utils.parse_comic_filename(os.path.basename(path))
            if year == "Unknown":
                year = utils.extract_year(selected_title) or "Unknown"
            if comic:
                remove_file_from_indexes(indexes, path)
                path = rename_file(path, comic, issue, year)
                add_file_to_indexes(indexes, path)

    input("\nDownload complete.\n\nPress Enter...")


def download_series(query):
    if not query:
        return
    query = utils.preprocess_search_query(query)
    indexes = build_indexes()
    clear()
    print("Searching and grouping series...")

    series_groups = {}
    for page in range(1, 7):
        try:
            results = downloader.search(query, page)
        except requests.RequestException:
            print(
                "\nNetwork connection error. Please check your internet connection and try again."
            )
            input("Press Enter...")
            return
        if not results:
            break
        for title, url in results:
            parsed_vol = utils.parse_volume_filename(title)
            if parsed_vol:
                series, vol_num, subtitle, year = parsed_vol
                norm = utils.normalize_comic_name(series)
                if norm not in series_groups:
                    series_groups[norm] = {
                        "name": series,
                        "issues": {},
                        "vols": {},
                        "urls": {},
                    }
                series_groups[norm]["vols"][
                    int(vol_num) if vol_num.isdigit() else vol_num
                ] = year
                series_groups[norm]["urls"][f"V{vol_num}"] = url
            else:
                comic, issue, year = utils.parse_comic_filename(title)
                if comic and issue:
                    norm = utils.normalize_comic_name(comic)
                    if norm not in series_groups:
                        series_groups[norm] = {
                            "name": comic,
                            "issues": {},
                            "vols": {},
                            "urls": {},
                        }
                    series_groups[norm]["issues"][
                        int(issue) if issue.isdigit() else issue
                    ] = year
                    series_groups[norm]["urls"][
                        int(issue) if issue.isdigit() else issue
                    ] = url
                else:
                    series = re.sub(r"\s*\([^)]*\)", "", title).strip()
                    series = re.sub(r"\.(cbz|cbr)$", "", series, flags=re.IGNORECASE)
                    norm = utils.normalize_comic_name(series)
                    if norm not in series_groups:
                        series_groups[norm] = {
                            "name": series,
                            "issues": {},
                            "vols": {},
                            "urls": {},
                        }
                    series_groups[norm]["issues"]["Other"] = "Unknown"
                    series_groups[norm]["urls"]["Other"] = url

    if not series_groups:
        print("No series found.")
        print(
            "\nTip: If you searched with a combined name (like 'SuperSons' or 'supersons'), try adding spaces (like 'Super Sons')."
        )
        input("Press Enter...")
        return

    active_series = {}
    for norm, data in series_groups.items():
        issues = [iss for iss in data["issues"].keys() if isinstance(iss, int)]
        if issues:
            active_series[norm] = data

    if not active_series:
        print("No series with downloadable issues found.")
        input("Press Enter...")
        return

    clear()
    print("Select a series to download:\n")
    query_norm = utils.normalize_comic_name(query)

    def get_sort_score(data):
        name_norm = utils.normalize_comic_name(data["name"])
        if name_norm == query_norm:
            return (0, len(name_norm), data["name"])
        elif name_norm.startswith(query_norm):
            return (1, len(name_norm), data["name"])
        return (2, len(name_norm), data["name"])

    group_list = sorted(list(active_series.values()), key=get_sort_score)
    for i, data in enumerate(group_list, 1):
        name = data["name"]
        issues = sorted([iss for iss in data["issues"].keys() if isinstance(iss, int)])
        print(f"{i}. {name} ({len(issues)} issues (#{issues[0]}-{issues[-1]}))")

    print("\nB = back")
    choice = input("\nSelect: ").lower().strip()
    if choice == "b":
        return

    try:
        selected_series = group_list[int(choice) - 1]
    except Exception:
        print("Invalid selection.")
        input("Press Enter...")
        return

    comic = selected_series["name"]
    rng = input(f"\nIssue range for '{comic}' (example 1-10): ").strip()
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
        items_sent = 0
        try:
            for issue in range(start, end + 1):
                existing = find_existing(indexes, comic=comic, issue=issue)
                if existing:
                    existing_files.append((issue, existing))
                    next_issue_queue.put(("EXISTS", issue, existing))
                    items_sent += 1
                    continue
                post = selected_series["urls"].get(issue)
                if not post:
                    for page in range(1, 6):
                        try:
                            results = downloader.search(f"{comic} #{issue}", page)
                        except requests.RequestException:
                            results = []
                        post = utils.find_exact_issue(results, comic, issue)
                        if post:
                            break
                if not post:
                    next_issue_queue.put((None, issue, None))
                    items_sent += 1
                    continue
                try:
                    dlds_list = downloader.get_download_links(post)
                except requests.RequestException:
                    dlds_list = []
                real = None
                for dlds in dlds_list:
                    try:
                        real = downloader.resolve_dlds(dlds)
                    except Exception as e:
                        import traceback

                        err_msg = (
                            f"\n[Error] Link resolution failed: {e}\n"
                            f"If this issue persists, please submit an issue at:\n"
                            f"https://github.com/moistfella/comic-book-downloader/issues"
                        )
                        print(utils.sanitize_text(err_msg))
                        try:
                            with open("error.log", "a") as f:
                                f.write(
                                    utils.sanitize_text(
                                        f"--- ERROR: {e} ---\n{traceback.format_exc()}\n"
                                    )
                                )
                        except Exception:
                            pass
                    if real:
                        break
                if not real:
                    next_issue_queue.put((None, issue, None))
                    items_sent += 1
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
                    items_sent += 1
                    continue
                next_issue_queue.put((real, issue, None))
                items_sent += 1
        finally:
            expected = end - start + 1
            while items_sent < expected:
                try:
                    next_issue_queue.put((None, start + items_sent, None))
                except Exception:
                    pass
                items_sent += 1

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
        try:
            path = downloader.download(url, DOWNLOAD_DIR)
        except requests.RequestException:
            print(
                f"\n[Error] Failed to download issue #{issue}. Please check your network connection and try again."
            )
            continue
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
                    year = (
                        utils.extract_year(os.path.basename(path))
                        or last_year
                        or "Unknown"
                    )
                new_name = utils.format_volume_name(series, vol_num, subtitle, year)
                new_path = os.path.join(DOWNLOAD_DIR, new_name)
                remove_file_from_indexes(indexes, path)
                os.replace(path, new_path)
                downloaded_files[i] = new_path
                add_file_to_indexes(indexes, new_path)
            else:
                comic_name, issue_num, year = utils.parse_comic_filename(
                    os.path.basename(path)
                )
                if year == "Unknown":
                    year = (
                        utils.extract_year(os.path.basename(path))
                        or last_year
                        or "Unknown"
                    )
                if comic_name:
                    remove_file_from_indexes(indexes, path)
                    new_path = rename_file(path, comic_name, issue_num, year)
                    downloaded_files[i] = new_path
                    add_file_to_indexes(indexes, new_path)

    input("\nSeries complete.\n\nPress Enter...")


def show_settings():
    while True:
        clear()
        config = utils.load_config()
        status = "Enabled" if config.get("check_updates", True) else "Disabled"
        print("Settings\n")
        print(f"1. Check for updates on startup: {status}")
        print("\nB = Back to main menu")
        choice = input("\nChoice: ").strip().lower()
        if choice == "1":
            config["check_updates"] = not config.get("check_updates", True)
            utils.save_config(config)
        elif choice == "b":
            break


update_available = False


def check_updates_worker():
    global update_available
    config = utils.load_config()
    if not config.get("check_updates", True):
        return
    if utils.check_for_updates():
        update_available = True


def main():
    try:
        while True:
            clear()
            print("Welcome\nPress Ctrl+C at any time to exit")
            if update_available:
                if os.name == "nt":
                    print(
                        "\n* A new update is available! Run update-windows.bat to update."
                    )
                else:
                    print("\n* A new update is available! Run git pull to update.")
            option = input(
                "\nWhat are you looking for?\n1. Search comic\n2. Search Series\n\nChoice (1/2): "
            ).strip()
            if not option or option not in ("1", "2", "0"):
                print("Invalid choice. Must be either option 1 or 2.")
                input("Press Enter to continue...")
                continue
            if option == "1":
                comic = input(
                    "\nWhat is the name of the comic you want to download?: "
                ).strip()
                if not comic:
                    continue
                download_issue(comic)
            elif option == "2":
                comic = input(
                    "\nWhat is the name of the comic series you want to download?: "
                ).strip()
                if not comic:
                    continue
                download_series(comic)
            elif option == "0":
                show_settings()
    except KeyboardInterrupt:
        print("\n\nExiting...")


if __name__ == "__main__":
    updater_thread = threading.Thread(target=check_updates_worker, daemon=True)
    updater_thread.start()
    updater_thread.join(timeout=1.0)
    main()
