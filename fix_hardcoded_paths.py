"""
fix_hardcoded_paths.py
Replaces all hardcoded E:\\ paths with dynamic Path(__file__).resolve().parent paths.
Ensures the software can run portably on ANY drive/computer (C:, D:, Desktop, etc.).
"""

import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def fix_supplementary():
    supp_dir = BASE_DIR / "Supplementary Monthly Contributio"
    for py_file in supp_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        orig = content

        # Replace hardcoded paths in Supplementary
        content = re.sub(
            r'Path\(r"E:\\Supplementary Monthly Contributio\\suplimentry_esic_users\.xlsx"\)',
            'BASE_DIR / "suplimentry_esic_users.xlsx"',
            content
        )
        content = re.sub(
            r'Path\(r"E:\\Supplementary Monthly Contributio\\esic_users\.xlsx"\)',
            'BASE_DIR / "esic_users.xlsx"',
            content
        )
        content = re.sub(
            r'Path\(\s*r"E:\\Supplementary Monthly Contributio\\ESIC_AUTO\\data"\s*\)',
            'BASE_DIR / "ESIC_AUTO" / "data"',
            content
        )
        content = re.sub(
            r'r"E:\\Supplementary Monthly Contributio\\ESIC_AUTO\\data"',
            'str(BASE_DIR / "ESIC_AUTO" / "data")',
            content
        )
        content = re.sub(
            r'r"E:\\Supplementary Monthly Contributio"',
            'str(BASE_DIR)',
            content
        )
        content = re.sub(
            r'r"E:\\Supplementary Monthly Contribution"',
            'str(BASE_DIR)',
            content
        )

        # Ensure BASE_DIR is defined
        if "BASE_DIR = Path(__file__).resolve().parent" not in content:
            # Add BASE_DIR after imports
            content = "from pathlib import Path\nBASE_DIR = Path(__file__).resolve().parent\n" + content

        if content != orig:
            py_file.write_text(content, encoding="utf-8")
            print(f"[OK] Fixed paths in: {py_file.name}")

def fix_pf_codes():
    pf_dir = BASE_DIR / "epfo_downloads_txt" / "Pf data download codes"
    if pf_dir.exists():
        for py_file in pf_dir.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            orig = content

            content = re.sub(
                r'Path\(r"E:\\epfo_downloads_txt\\([^\"]+)"\)',
                r'BASE_DIR / "\1"',
                content
            )
            if "BASE_DIR = Path(__file__).resolve().parent" not in content:
                content = "from pathlib import Path\nBASE_DIR = Path(__file__).resolve().parent.parent\n" + content

            if content != orig:
                py_file.write_text(content, encoding="utf-8")
                print(f"[OK] Fixed paths in: {py_file.name}")

def fix_new_epfo_auto():
    run_txt = BASE_DIR / "New_EPFO_AUTO_software" / "EPFO_AUTO" / "run_epfo_txt_download.py"
    if run_txt.exists():
        content = run_txt.read_text(encoding="utf-8")
        orig = content
        content = re.sub(
            r'Path\(r"E:\\New_EPFO_AUTO_software\\EPFO_AUTO\\data\\users\.xlsx"\)',
            'BASE_DIR / "data" / "users.xlsx"',
            content
        )
        content = re.sub(
            r'Path\(r"E:\\New_EPFO_AUTO_software\\EPFO_AUTO\\data\\captcha_images"\)',
            'BASE_DIR / "data" / "captcha_images"',
            content
        )
        content = re.sub(
            r'Path\(r"E:\\epfo_downloads_txt"\)',
            'BASE_DIR.parent.parent / "epfo_downloads_txt"',
            content
        )
        if "BASE_DIR = Path(__file__).resolve().parent" not in content:
            content = "from pathlib import Path\nBASE_DIR = Path(__file__).resolve().parent\n" + content
        if content != orig:
            run_txt.write_text(content, encoding="utf-8")
            print(f"[OK] Fixed paths in: {run_txt.name}")

if __name__ == "__main__":
    fix_supplementary()
    fix_pf_codes()
    fix_new_epfo_auto()
    print("[FINISHED] All hardcoded paths converted to dynamic base paths!")

