import requests
import os

from config import OUTPUT_DIR, IMAGE_EXTS

os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_chapter_sort_key(chap_num):
    """Sort chapters numerically where possible, push 'unknown' to the end."""
    try:
        return (0, float(chap_num))
    except (ValueError, TypeError):
        return (1, chap_num)


def fetch_chapter_list(manga_id):
    """Fetch all English chapters for the manga, handling pagination."""
    chapters = []
    limit = 100
    offset = 0

    while True:
        feed_url = (
            f"https://api.mangadex.org/manga/{manga_id}/feed"
            f"?translatedLanguage[]=en&limit={limit}&offset={offset}"
            f"&order[chapter]=asc"
        )
        resp = requests.get(feed_url)
        resp.raise_for_status()
        data = resp.json()

        batch = data["data"]
        chapters.extend(batch)

        total = data.get("total", len(chapters))
        offset += limit
        if offset >= total or not batch:
            break

    return chapters


def get_chapter_map(manga_id):
    """Returns (chap_num_to_id dict, sorted list of chapter numbers)."""
    chapters = fetch_chapter_list(manga_id)
    chap_num_to_id = {}
    for chap in chapters:
        chap_num = chap["attributes"]["chapter"] or "unknown"
        if chap_num not in chap_num_to_id:
            chap_num_to_id[chap_num] = chap["id"]

    chap_numbers = sorted(chap_num_to_id.keys(), key=get_chapter_sort_key)
    return chap_num_to_id, chap_numbers


def get_chapter_folder(chap_num):
    return os.path.join(OUTPUT_DIR, f"Chapter_{chap_num}")


def check_chapter_status(chap_num):
    """
    Returns (is_empty: bool, reason: str or None)
    reason is None if the chapter is fine.
    """
    folder = get_chapter_folder(chap_num)

    if not os.path.isdir(folder):
        return True, "folder does not exist (never downloaded)"

    images = [f for f in os.listdir(folder) if f.lower().endswith(IMAGE_EXTS)]
    if len(images) == 0:
        return True, "folder exists but contains no image files"

    return False, None


def download_image(url, path):
    resp = requests.get(url)
    resp.raise_for_status()
    with open(path, "wb") as f:
        f.write(resp.content)


def download_chapter_images(chap_id, chap_num):
    """
    Downloads all pages for a given chapter id/number.
    Returns (success: bool, reason: str or None)
    """
    try:
        server_resp = requests.get(f"https://api.mangadex.org/at-home/server/{chap_id}")
        server_resp.raise_for_status()
        server = server_resp.json()
    except Exception as e:
        return False, f"failed to contact MangaDex image server ({e})"

    base_url = server["baseUrl"]
    chapter_hash = server["chapter"]["hash"]
    filenames = server["chapter"]["data"]

    if not filenames:
        return False, "MangaDex reports 0 pages for this chapter"

    folder = get_chapter_folder(chap_num)
    os.makedirs(folder, exist_ok=True)

    downloaded = 0
    for i, filename in enumerate(filenames, start=1):
        image_url = f"{base_url}/data/{chapter_hash}/{filename}"
        image_path = os.path.join(folder, f"{i:03}.jpg")
        try:
            download_image(image_url, image_path)
            downloaded += 1
        except Exception as e:
            print(f"    Failed to download page {i}: {e}")

    if downloaded == 0:
        return False, "all page downloads failed (network/server issue)"

    return True, None


def sanitize_filename(name):
    """Strip characters that are problematic in filenames."""
    invalid = '<>:"/\\|?*'
    for ch in invalid:
        name = name.replace(ch, "")
    return name.strip()