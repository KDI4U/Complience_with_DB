import os
import shutil
from pathlib import Path

ROOT_DIR = Path(r"D:\Complience_with_DB")
SOURCE_DIST = ROOT_DIR / "NEW_ESIC_AUTO_SOFTWARE" / "dist" / "esicexe"
TARGET_DIR = ROOT_DIR / "esicexe"

print(f"Assembling esicexe in: {TARGET_DIR}")

# 1. Ensure target directory exists
TARGET_DIR.mkdir(parents=True, exist_ok=True)

# 2. Copy compiled executable and _internal folder
for exe_name in ["esic_auto.exe", "esic_gui.exe"]:
    src = SOURCE_DIST / exe_name
    if src.exists():
        shutil.copy2(src, TARGET_DIR / exe_name)
        print(f"Copied {exe_name}")

if (SOURCE_DIST / "_internal").exists():
    target_internal = TARGET_DIR / "_internal"
    if target_internal.exists():
        shutil.rmtree(target_internal)
    shutil.copytree(SOURCE_DIST / "_internal", target_internal)
    print("Copied _internal folder")

# 3. Copy ms-playwright from epfoexe if not already present
source_playwright = ROOT_DIR / "epfoexe" / "ms-playwright"
target_playwright = TARGET_DIR / "ms-playwright"
if source_playwright.exists() and not target_playwright.exists():
    print("Copying bundled ms-playwright for offline browser support...")
    shutil.copytree(source_playwright, target_playwright)
    print("Copied ms-playwright")
elif target_playwright.exists():
    print("ms-playwright already exists in esicexe")

# 4. Copy esic_users.xlsx
source_users = ROOT_DIR / "NEW_ESIC_AUTO_SOFTWARE" / "ESIC_AUTO_project_structure" / "esic_users.xlsx"
if source_users.exists():
    shutil.copy2(source_users, TARGET_DIR / "esic_users.xlsx")
    print("Copied esic_users.xlsx")

# 5. Copy .env
source_env = ROOT_DIR / ".env"
if source_env.exists():
    shutil.copy2(source_env, TARGET_DIR / ".env")
    print("Copied .env")

# 6. Copy icon
source_ico = ROOT_DIR / "esic_icon.ico"
if source_ico.exists():
    shutil.copy2(source_ico, TARGET_DIR / "app_icon.ico")
    shutil.copy2(source_ico, TARGET_DIR / "esic_icon.ico")
    print("Copied icon")

# 7. Create data and log directories
subdirs = [
    TARGET_DIR / "logs",
    TARGET_DIR / "old_data",
    TARGET_DIR / "data",
    TARGET_DIR / "data" / "esic_downloads",
    TARGET_DIR / "data" / "captcha_images",
    TARGET_DIR / "data" / "compaire",
    TARGET_DIR / "data" / "dbdata",
    TARGET_DIR / "data" / "Merge_data"
]
for d in subdirs:
    d.mkdir(parents=True, exist_ok=True)
print("Created subdirectories")

# 8. Create batch files
run_esic_bat = """@echo off
title ESIC Production Automation Pipeline
cd /d "%~dp0"
echo ============================================================
echo           ESIC PRODUCTION AUTOMATION PIPELINE
echo ============================================================
echo Starting ESIC automation in AUTO mode...
echo.
esic_auto.exe --auto
echo.
pause
"""
with open(TARGET_DIR / "run_esic.bat", "w", encoding="utf-8") as f:
    f.write(run_esic_bat)

run_esic_gui_bat = """@echo off
start "" "%~dp0esic_gui.exe"
"""
with open(TARGET_DIR / "run_esic_gui.bat", "w", encoding="utf-8") as f:
    f.write(run_esic_gui_bat)

run_interactive_bat = """@echo off
title ESIC Automation (Interactive Mode)
cd /d "%~dp0"
echo ============================================================
echo       ESIC AUTOMATION (STEP-BY-STEP CONFIRMATION)
echo ============================================================
esic_auto.exe --interactive
echo.
pause
"""
with open(TARGET_DIR / "run_interactive.bat", "w", encoding="utf-8") as f:
    f.write(run_interactive_bat)

# 9. Create README.txt
readme_content = """============================================================
ESIC Automation Suite - Fully Portable Package (esicexe)
============================================================

Description:
Yeh folder ESIC Automation ka complete standalone & portable version hai.
Isko aap kisi bhi doosre Windows PC par direct copy karke chala sakte hain.
Python ya Playwright install karne ki koi zarurat nahi hai!

Folder Contents:
------------------------------------------------------------
- esic_auto.exe       : Standalone Main Executable (with ESIC icon)
- run_esic.bat        : One-click launcher script
- run_interactive.bat : Console debug launcher (agar terminal me dekhna ho)
- esic_users.xlsx     : ESIC Employer credentials & portal config
- .env                : Database & Captcha configuration
- ms-playwright/      : Pre-bundled Chromium browser for automation
- data/               : Output folder (downloads, merged files, reports)
- logs/               : Execution logs with timestamp
- _internal/          : Python runtime libraries & dependencies

Instructions for Another PC (Dusre Computer ke liye):
------------------------------------------------------------
1. Pure "esicexe" folder ko Pendrive ya Network Drive se copy karke
   dusre system me kisi bhi drive (C:, D:, etc.) par paste karein.
2. "esic_users.xlsx" me apne valid ESIC credentials check karein.
3. ".env" me agar DB/Ollama ka remote IP ya local setup ho to verify karein.
4. "run_esic.bat" par double click karein!
   -> Beautiful GUI open hoga jisme Step 1 se Step 4 aur Compare/DB Download ke
      buttons available hain.
============================================================
"""
with open(TARGET_DIR / "README.txt", "w", encoding="utf-8") as f:
    f.write(readme_content)

print("Created batch scripts and README.txt")
print("ESICEXE assembly complete!")

