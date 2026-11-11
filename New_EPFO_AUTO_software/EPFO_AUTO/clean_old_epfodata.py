import sys
import shutil
import logging
from pathlib import Path
from datetime import datetime

# FULL ABSOLUTE PATHS
if getattr(sys, "frozen", False):
    PROJECT_FOLDER = Path(sys.executable).resolve().parent
else:
    PROJECT_FOLDER = Path(__file__).resolve().parent

DATA_FOLDER = PROJECT_FOLDER / "data"
PF_DOWNLOADS_FOLDER = DATA_FOLDER / "pf_downloads"
CAPTCHA_FOLDER = DATA_FOLDER / "captcha_images"
MERGE_FOLDER = PROJECT_FOLDER / "Merge_data"
DB_FOLDER = DATA_FOLDER / "db"
ARCHIVE_FOLDER = PROJECT_FOLDER / "old_data"

logger = logging.getLogger("clean_data")
if not logger.hasHandlers():
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)


def delete_captcha_folders():
    deleted_count = 0
    captcha_candidates = [
        CAPTCHA_FOLDER,
        DATA_FOLDER / "captcha",
    ]

    for c_dir in captcha_candidates:
        if c_dir.exists():
            try:
                shutil.rmtree(c_dir)
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete CAPTCHA folder ({c_dir}): {e}")

    # Check date subfolders for captcha
    if DATA_FOLDER.exists():
        for sub_dir in DATA_FOLDER.iterdir():
            if not sub_dir.is_dir():
                continue
            sub_captcha = sub_dir / "captcha_images"
            if sub_captcha.exists():
                try:
                    shutil.rmtree(sub_captcha)
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete CAPTCHA folder ({sub_captcha}): {e}")

    logger.info(f"CAPTCHA folders deleted: {deleted_count}")


def move_folder_to_archive(source_folder, archive_root):
    if not source_folder.exists():
        return

    try:
        has_content = any(source_folder.iterdir())
    except Exception:
        has_content = True

    if not has_content:
        return

    destination = archive_root / source_folder.name
    if destination.exists():
        timestamp = datetime.now().strftime("%H%M%S")
        destination = archive_root / f"{source_folder.name}_{timestamp}"

    try:
        shutil.move(str(source_folder), str(destination))
        logger.info(f"Archived {source_folder.name} -> {destination}")
    except Exception as e:
        logger.error(f"Archive error for {source_folder.name}: {e}")


def clean_old_data():
    logger.info("Starting EPFO Old Data Cleanup...")

    if not PROJECT_FOLDER.exists():
        raise FileNotFoundError(f"Project folder not found: {PROJECT_FOLDER}")

    timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
    archive_root = ARCHIVE_FOLDER / timestamp
    archive_root.mkdir(parents=True, exist_ok=True)

    delete_captcha_folders()

    folders_to_archive = [
        PF_DOWNLOADS_FOLDER,
        MERGE_FOLDER,
        DB_FOLDER,
    ]

    for folder in folders_to_archive:
        move_folder_to_archive(folder, archive_root)

    # Recreate fresh empty directories
    DATA_FOLDER.mkdir(parents=True, exist_ok=True)
    PF_DOWNLOADS_FOLDER.mkdir(parents=True, exist_ok=True)
    CAPTCHA_FOLDER.mkdir(parents=True, exist_ok=True)
    MERGE_FOLDER.mkdir(parents=True, exist_ok=True)
    DB_FOLDER.mkdir(parents=True, exist_ok=True)

    logger.info("Fresh directories ready: data/pf_downloads, Merge_data, data/db, captcha_images")
    logger.info("Cleanup completed successfully.")
    return True


if __name__ == "__main__":
    try:
        clean_old_data()
    except Exception as exc:
        logger.error(f"Cleanup failed: {exc}")
        sys.exit(1)

