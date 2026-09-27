import os
import shutil
import time
import zipfile

from config import MANGA_ID, OUTPUT_DIR, IMAGE_EXTS
from manga_utils import (
    get_chapter_map,
    get_chapter_folder,
    get_chapter_sort_key,
    check_chapter_status,
    download_chapter_images,
    sanitize_filename,
)


def combine_all_chapters(manga_name, chapters_with_images):
    """
    Combine all non-empty chapters (in order) into one CBZ, named after the
    manga and its chapter range, e.g. "One Piece_Chapter_1-65.cbz".
    Returns the path to the combined CBZ.
    """
    chap_nums = [c for c, _ in chapters_with_images]
    first, last = chap_nums[0], chap_nums[-1]

    safe_name = sanitize_filename(manga_name) or "Manga"
    combined_filename = f"{safe_name}_Chapter_{first}-{last}.cbz"
    combined_path = os.path.join(OUTPUT_DIR, combined_filename)

    with zipfile.ZipFile(combined_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for chap_num, folder in chapters_with_images:
            images = sorted(
                f for f in os.listdir(folder) if f.lower().endswith(IMAGE_EXTS)
            )
            for img in images:
                img_path = os.path.join(folder, img)
                # Each chapter goes in its own subfolder inside the zip so that
                # update_cbz.py can later tell which chapters are already included.
                arcname = f"Chapter_{chap_num}/{img}"
                zf.write(img_path, arcname=arcname)

    print(f"\nCombined CBZ saved: {combined_path}")
    return combined_path


def delete_chapter_folders(chapters_with_images):
    for _, folder in chapters_with_images:
        try:
            shutil.rmtree(folder)
        except Exception as e:
            print(f"  Warning: couldn't delete {folder}: {e}")


def print_empty_report(empty_dict):
    if not empty_dict:
        print("All chapters are present and downloaded.")
        return
    print("The following chapters have issues:")
    for c, reason in empty_dict.items():
        print(f"  - Chapter {c}: {reason}")


def main():
    print("Fetching chapter list from MangaDex...")
    chap_num_to_id, chap_numbers = get_chapter_map(MANGA_ID)

    if not chap_numbers:
        print("No English chapters found for this manga.")
        return

    latest = [c for c in chap_numbers if c != "unknown"]
    if latest:
        print(f"Latest chapter available on MangaDex: {latest[-1]}")
    print(f"Total chapters found: {len(chap_numbers)}\n")

    # --- Initial check ---
    empty_chapters = {}   # chap_num -> reason
    chapters_with_images = []

    for chap_num in chap_numbers:
        is_empty, reason = check_chapter_status(chap_num)
        if is_empty:
            empty_chapters[chap_num] = reason
        else:
            chapters_with_images.append((chap_num, get_chapter_folder(chap_num)))

    print_empty_report(empty_chapters)
    print(f"\n{len(chapters_with_images)} chapter(s) have images and can be combined.")

    # --- Retry option ---
    if empty_chapters:
        retry_answer = input(
            "\nRetry downloading the missing/empty chapters listed above? (y/n): "
        ).strip().lower()

        if retry_answer == "y":
            print("\nRetrying missing/empty chapters...")
            still_empty = {}

            for chap_num in list(empty_chapters.keys()):
                if chap_num == "unknown":
                    still_empty[chap_num] = "no chapter number, skipped retry"
                    continue

                chap_id = chap_num_to_id[chap_num]
                print(f"  Retrying Chapter {chap_num} ...")
                success, reason = download_chapter_images(chap_id, chap_num)
                time.sleep(0.2)  # be nice to the API

                if success:
                    print(f"    Success.")
                    chapters_with_images.append((chap_num, get_chapter_folder(chap_num)))
                else:
                    print(f"    Still failed: {reason}")
                    still_empty[chap_num] = reason

            print("\nRetry finished. Updated status:")
            print_empty_report(still_empty)
            print(f"\n{len(chapters_with_images)} chapter(s) now have images and can be combined.")
            empty_chapters = still_empty

    if not chapters_with_images:
        print("\nNothing to combine. Exiting.")
        return

    # --- Combine confirmation ---
    combine_answer = input(
        "\nCombine all downloaded chapters into a single CBZ for the whole manga? (y/n): "
    ).strip().lower()

    if combine_answer == "y":
        manga_name = input("Enter the manga's name (used for the CBZ filename): ").strip()
        while not manga_name:
            manga_name = input("Please enter a non-empty name: ").strip()

        # Sort by proper chapter order before combining/naming
        chapters_with_images.sort(key=lambda pair: get_chapter_sort_key(pair[0]))

        combine_all_chapters(manga_name, chapters_with_images)

        print("Deleting per-chapter folders (their images now live in the CBZ)...")
        delete_chapter_folders(chapters_with_images)
        print("Done.")
    else:
        print("Skipped combining. Done.")


if __name__ == "__main__":
    main()