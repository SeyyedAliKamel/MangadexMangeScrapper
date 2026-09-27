import os
import zipfile

import img2pdf
import requests

from config import MANGA_ID, OUTPUT_DIR
from manga_utils import fetch_chapter_list, download_image

os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_chapter_as_pdf(chapter_num, image_paths):
    pdf_path = os.path.join(OUTPUT_DIR, f"Chapter_{chapter_num}.pdf")
    with open(pdf_path, "wb") as f:
        f.write(img2pdf.convert(image_paths, rotation=img2pdf.Rotation.ifvalid))
    print(f"Saved PDF: {pdf_path}")


def save_chapter_as_cbz(chapter_num, image_paths):
    cbz_path = os.path.join(OUTPUT_DIR, f"Chapter_{chapter_num}.cbz")
    with zipfile.ZipFile(cbz_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for img_path in image_paths:
            zf.write(img_path, arcname=os.path.basename(img_path))
    print(f"Saved CBZ: {cbz_path}")


def chapter_already_done(chap_num):
    """Check if both the PDF and CBZ already exist for this chapter."""
    pdf_path = os.path.join(OUTPUT_DIR, f"Chapter_{chap_num}.pdf")
    cbz_path = os.path.join(OUTPUT_DIR, f"Chapter_{chap_num}.cbz")
    return os.path.exists(pdf_path) and os.path.exists(cbz_path)


def main():
    # 1. Fetch chapter list (English only)
    chapters = fetch_chapter_list(MANGA_ID)

    for chap in chapters:
        chap_id = chap["id"]
        chap_num = chap["attributes"]["chapter"] or "unknown"

        # Skip fully-completed chapters (resume support)
        if chapter_already_done(chap_num):
            print(f"Chapter {chap_num} already done, skipping.")
            continue

        print(f"Downloading Chapter {chap_num} ...")

        # 2. Get image server info for the chapter
        server_resp = requests.get(f"https://api.mangadex.org/at-home/server/{chap_id}")
        server_resp.raise_for_status()
        server = server_resp.json()

        base_url = server["baseUrl"]
        chapter_hash = server["chapter"]["hash"]
        filenames = server["chapter"]["data"]

        # Prepare folder for this chapter's images
        chap_folder = os.path.join(OUTPUT_DIR, f"Chapter_{chap_num}")
        os.makedirs(chap_folder, exist_ok=True)

        image_paths = []

        # 3. Download each image page (skip pages already on disk)
        for i, filename in enumerate(filenames, start=1):
            image_url = f"{base_url}/data/{chapter_hash}/{filename}"
            image_path = os.path.join(chap_folder, f"{i:03}.jpg")

            if os.path.exists(image_path) and os.path.getsize(image_path) > 0:
                image_paths.append(image_path)
                print(f"  Page {i} already downloaded, skipping.")
                continue

            try:
                download_image(image_url, image_path)
                image_paths.append(image_path)
                print(f"  Downloaded page {i}")
            except Exception as e:
                print(f"  Failed to download page {i}: {e}")

        # 4. Convert images to PDF and CBZ
        if image_paths:
            save_chapter_as_pdf(chap_num, image_paths)
            save_chapter_as_cbz(chap_num, image_paths)
        else:
            print(f"No images downloaded for Chapter {chap_num}")

    print("All done!")


if __name__ == "__main__":
    main()