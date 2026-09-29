import os
import zipfile

import img2pdf
import requests
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from config import MANGA_ID, OUTPUT_DIR
from manga_utils import fetch_chapter_list, download_image

os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_chapter_as_pdf(chapter_num, image_paths):
    pdf_path = os.path.join(OUTPUT_DIR, f"Chapter_{chapter_num}.pdf")
    with open(pdf_path, "wb") as f:
        f.write(img2pdf.convert(image_paths, rotation=img2pdf.Rotation.ifvalid))


def save_chapter_as_cbz(chapter_num, image_paths):
    cbz_path = os.path.join(OUTPUT_DIR, f"Chapter_{chapter_num}.cbz")
    with zipfile.ZipFile(cbz_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for img_path in image_paths:
            zf.write(img_path, arcname=os.path.basename(img_path))


def chapter_already_done(chap_num):
    """Check if both the PDF and CBZ already exist for this chapter."""
    pdf_path = os.path.join(OUTPUT_DIR, f"Chapter_{chap_num}.pdf")
    cbz_path = os.path.join(OUTPUT_DIR, f"Chapter_{chap_num}.cbz")
    return os.path.exists(pdf_path) and os.path.exists(cbz_path)


def make_progress():
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description:<22}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )


def main():
    chapters = fetch_chapter_list(MANGA_ID)

    with make_progress() as progress:
        chapters_task = progress.add_task("Chapters", total=len(chapters))
        pages_task = progress.add_task("Pages", total=1, visible=False)

        for chap in chapters:
            chap_id = chap["id"]
            chap_num = chap["attributes"]["chapter"] or "unknown"

            # Skip fully-completed chapters (resume support)
            if chapter_already_done(chap_num):
                progress.console.print(f"[dim]Chapter {chap_num} already done, skipping.[/dim]")
                progress.advance(chapters_task)
                continue

            progress.update(chapters_task, description=f"Chapters (Ch. {chap_num})")

            # Get image server info for the chapter
            server_resp = requests.get(f"https://api.mangadex.org/at-home/server/{chap_id}")
            server_resp.raise_for_status()
            server = server_resp.json()

            base_url = server["baseUrl"]
            chapter_hash = server["chapter"]["hash"]
            filenames = server["chapter"]["data"]

            chap_folder = os.path.join(OUTPUT_DIR, f"Chapter_{chap_num}")
            os.makedirs(chap_folder, exist_ok=True)

            # Reset the page bar for this chapter's page count
            progress.reset(
                pages_task,
                total=len(filenames),
                completed=0,
                visible=True,
                description=f"Pages (Ch. {chap_num})",
            )

            image_paths = []
            failed = 0

            for i, filename in enumerate(filenames, start=1):
                image_url = f"{base_url}/data/{chapter_hash}/{filename}"
                image_path = os.path.join(chap_folder, f"{i:03}.jpg")

                if os.path.exists(image_path) and os.path.getsize(image_path) > 0:
                    image_paths.append(image_path)
                else:
                    try:
                        download_image(image_url, image_path)
                        image_paths.append(image_path)
                    except Exception as e:
                        failed += 1
                        progress.console.print(
                            f"[red]  Ch. {chap_num} page {i} failed: {e}[/red]"
                        )

                progress.advance(pages_task)

            # Convert images to PDF and CBZ
            if image_paths:
                progress.update(pages_task, description=f"Converting (Ch. {chap_num})")
                save_chapter_as_pdf(chap_num, image_paths)
                save_chapter_as_cbz(chap_num, image_paths)
                msg = f"[green]✔ Chapter {chap_num} saved[/green]"
                if failed:
                    msg += f" [yellow]({failed} page(s) missing)[/yellow]"
                progress.console.print(msg)
            else:
                progress.console.print(f"[red]✘ No images downloaded for Chapter {chap_num}[/red]")

            progress.advance(chapters_task)

        progress.update(pages_task, visible=False)

    print("All done!")


if __name__ == "__main__":
    main()