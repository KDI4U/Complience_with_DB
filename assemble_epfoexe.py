import os
import shutil
from pathlib import Path

ROOT_DIR = Path(r"D:\Complience_with_DB")
SOURCE_DIST = ROOT_DIR / "New_EPFO_AUTO_software" / "dist" / "epfoexe"
TARGET_DIR = ROOT_DIR / "epfoexe"

print(f"Assembling epfoexe in: {TARGET_DIR}")
TARGET_DIR.mkdir(parents=True, exist_ok=True)

# Copy executables
for exe_name in ["epfo_auto.exe", "epfo_gui.exe"]:
    src = SOURCE_DIST / exe_name
    if src.exists():
        shutil.copy2(src, TARGET_DIR / exe_name)
        print(f"Copied {exe_name}")

# Copy _internal folder
if (SOURCE_DIST / "_internal").exists():
    target_internal = TARGET_DIR / "_internal"
    if target_internal.exists():
        shutil.rmtree(target_internal)
    shutil.copytree(SOURCE_DIST / "_internal", target_internal)
    print("Copied _internal folder")

# Ensure icons
for ico in ["epfo_icon.ico", "app_icon.ico"]:
    src_ico = ROOT_DIR / "epfo_icon.ico"
    if src_ico.exists():
        shutil.copy2(src_ico, TARGET_DIR / ico)
print("Copied icons")

# Create batch files
run_epfo_gui_bat = """@echo off
start "" "%~dp0epfo_gui.exe"
"""
with open(TARGET_DIR / "run_epfo_gui.bat", "w", encoding="utf-8") as f:
    f.write(run_epfo_gui_bat)

run_epfo_bat = """@echo off
title EPFO Automation Pipeline
cd /d "%~dp0"
echo ============================================================
echo           EPFO PRODUCTION AUTOMATION PIPELINE
echo ============================================================
echo Starting EPFO automation in AUTO mode...
echo.
epfo_auto.exe --auto
echo.
pause
"""
with open(TARGET_DIR / "run_epfo.bat", "w", encoding="utf-8") as f:
    f.write(run_epfo_bat)

run_interactive_bat = """@echo off
title EPFO Automation (Interactive Mode)
cd /d "%~dp0"
echo ============================================================
echo           EPFO AUTOMATION (INTERACTIVE MODE)
echo ============================================================
epfo_auto.exe --interactive
echo.
pause
"""
with open(TARGET_DIR / "run_interactive.bat", "w", encoding="utf-8") as f:
    f.write(run_interactive_bat)

print("EPFOEXE assembly complete!")

