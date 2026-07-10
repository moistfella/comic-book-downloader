import re


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
    name_clean = re.sub(r"\s*\([^)]*\)", "", name).strip()
    hash_match = re.search(r"#\s*(\d+)", name_clean)
    if hash_match:
        issue = hash_match.group(1)
        series = name_clean[: hash_match.start()].strip(" -_–—:")
        return series, issue, year or "Unknown"
    numbers = list(re.finditer(r"\b(\d+)\b", name_clean))
    if not numbers:
        return None, None, None
    last = numbers[-1]
    issue = str(int(last.group(0)))
    if len(issue) == 4 and (issue.startswith("19") or issue.startswith("20")):
        if len(numbers) > 1:
            last = numbers[-2]
            issue = str(int(last.group(0)))
            series = name_clean[: last.start()].strip(" -_–—:")
            return series, issue, year or "Unknown"
        else:
            return None, None, None
    series = name_clean[: last.start()].strip(" -_–—:")
    return series, issue, year or "Unknown"


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
    pattern = rf"^(?:the\s+)?{escaped_comic}\b\s*(?:#|–|-|_)?\s*0*{target_issue}\b"
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


def preprocess_search_query(query):
    q = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", query)
    lower = q.lower().strip()
    words = {
        "supersons": "super sons",
        "spiderman": "spider man",
        "ironman": "iron man",
        "wonderwoman": "wonder woman",
        "xmen": "x-men",
        "spidergwen": "spider gwen",
        "spiderwoman": "spider woman",
        "greenlantern": "green lantern",
        "greenarrow": "green arrow",
        "ghostrider": "ghost rider",
        "starwars": "star wars",
        "blackpanther": "black panther",
        "blackwidow": "black widow",
        "captainamerica": "captain america",
        "moonknight": "moon knight",
        "redhood": "red hood",
        "redrobin": "red robin",
        "blackcanary": "black canary",
        "poisonivy": "poison ivy",
        "harleyquinn": "harley quinn",
        "swampthing": "swamp thing",
        "teenttians": "teen titans",
        "teentitans": "teen titans",
        "killerfrost": "killer frost",
        "beastboy": "beast boy",
        "silversurfer": "silver surfer",
        "doctorstrange": "doctor strange",
        "doctordoom": "doctor doom",
        "ironfist": "iron fist",
        "lukecage": "luke cage",
        "antman": "ant man",
        "msmarvel": "ms marvel",
        "captainmarvel": "captain marvel",
        "squirrelgirl": "squirrel girl",
        "fantasticfour": "fantastic four",
        "newmutants": "new mutants",
        "starlord": "star lord",
        "wintersolider": "winter soldier",
        "wintersoldier": "winter soldier",
        "falconandwintersoldier": "falcon and winter soldier",
        "judgedredd": "judge dredd",
        "redsonja": "red sonja",
        "tankgirl": "tank girl",
        "drstrange": "doctor strange",
        "dr strange": "doctor strange",
    }
    for k, v in words.items():
        if k in lower:
            q = re.sub(rf"\b{k}\b", v, q, flags=re.IGNORECASE)
    return q


def sanitize_text(text):
    import getpass

    try:
        username = getpass.getuser()
        if username:
            text = text.replace(username, "<USER>")
            text = text.replace(username.lower(), "<USER>")
            text = text.replace(username.upper(), "<USER>")
    except Exception:
        pass
    return text
