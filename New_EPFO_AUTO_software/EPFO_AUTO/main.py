import os
import sys
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Configure Windows console encoding safely
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ============================================================
# EPFO PRODUCTION AUTOMATION PIPELINE - MAIN (4 STEPS)
# ============================================================

if getattr(sys, "frozen", False):
    PROJECT_FOLDER = Path(sys.executable).resolve().parent
else:
    PROJECT_FOLDER = Path(__file__).resolve().parent

if str(PROJECT_FOLDER) not in sys.path:
    sys.path.insert(0, str(PROJECT_FOLDER))

# Set Playwright bundled browser path if present
if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
    bundled_browser = PROJECT_FOLDER / "ms-playwright"
    if bundled_browser.exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(bundled_browser)

LOGS_FOLDER = PROJECT_FOLDER / "logs"
LOGS_FOLDER.mkdir(parents=True, exist_ok=True)

# Required Script Files for 4-Step Pipeline
CLEAN_FILE = PROJECT_FOLDER / "clean_old_epfodata.py"
PORTAL_FILE = PROJECT_FOLDER / "epfo_portal_download.py"
MERGE_FILE = PROJECT_FOLDER / "merge.py"
INSERT_DB_FILE = PROJECT_FOLDER / "insert_epfo_data.py"


def setup_logger(verbose=False):
    log_filename = LOGS_FOLDER / f"epfo_auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    root_logger.handlers.clear()

    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    ch.setFormatter(formatter)
    root_logger.addHandler(ch)

    # File Handler
    fh = logging.FileHandler(log_filename, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d]: %(message)s"))
    root_logger.addHandler(fh)

    logger = logging.getLogger("epfo_auto_main")
    return logger, log_filename


def check_prerequisites(logger):
    if getattr(sys, "frozen", False):
        logger.debug("Running in compiled binary mode (modules bundled).")
        return True

    required_files = [
        ("Cleanup Script", CLEAN_FILE),
        ("EPFO Portal Download Script (DB Credentials)", PORTAL_FILE),
        ("Merge Script", MERGE_FILE),
        ("DB Insert Script", INSERT_DB_FILE),
    ]

    missing = False
    for name, path in required_files:
        if path.exists():
            logger.debug(f"Found required file: {name} -> {path.name}")
        else:
            logger.error(f"Missing required file: {name} ({path})")
            missing = True

    return not missing


def run_step_module(step_no, total_steps, step_name, action_func, logger):
    logger.info("=" * 70)
    logger.info(f"STEP {step_no}/{total_steps} : {step_name}")
    logger.info("=" * 70)

    start_time = time.time()
    try:
        success = action_func()
        elapsed = time.time() - start_time
        if success is False:
            logger.error(f"Step {step_no} ({step_name}) FAILED after {elapsed:.2f}s")
            return False, elapsed
        logger.info(f"Step {step_no} ({step_name}) SUCCESS ({elapsed:.2f}s)")
        return True, elapsed
    except Exception as exc:
        elapsed = time.time() - start_time
        logger.error(f"Step {step_no} ({step_name}) EXCEPTION: {exc}", exc_info=True)
        return False, elapsed


def hide_console():
    """Hides the Windows CMD console window when running in GUI mode."""
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def main():
    if len(sys.argv) == 1 or "--gui" in sys.argv or "-g" in sys.argv:
        # Launched in GUI mode -> Hide console and launch Control Panel
        hide_console()
        try:
            from gui_launcher import launch_gui
            launch_gui()
            return
        except Exception as e:
            print(f"Failed to launch GUI ({e}), falling back to console pipeline...")

    parser = argparse.ArgumentParser(
        description="Production Automation Pipeline - EPFO AUTO (4 Steps)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--gui", "-g", action="store_true", help="Launch Graphical Control Panel")
    parser.add_argument("--auto", "-a", action="store_true", default=True, help="Run full pipeline automatically without blocking prompts")
    parser.add_argument("--interactive", "-i", action="store_true", help="Prompt for confirmation between steps")
    parser.add_argument("--headless", "-H", action="store_true", help="Run Playwright browser automation in headless mode")
    parser.add_argument("--step", "-s", type=int, choices=range(1, 5), help="Run a specific single step (1-4)")
    parser.add_argument("--concurrency", "-c", type=int, default=1, help="Number of concurrent workers (default: 1)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging")

    args = parser.parse_args()
    auto_mode = not args.interactive

    logger, log_file = setup_logger(verbose=args.verbose)

    logger.info("=" * 70)
    logger.info("          PRODUCTION AUTOMATION PIPELINE - EPFO AUTO")
    logger.info("=" * 70)
    logger.info(f"Project Folder : {PROJECT_FOLDER}")
    logger.info(f"Execution Log  : {log_file.name}")
    logger.info(f"Execution Mode : {'AUTO (Unattended)' if auto_mode else 'INTERACTIVE'}")
    logger.info(f"Browser Mode   : {'HEADLESS' if args.headless else 'VISIBLE'}")
    logger.info("=" * 70)

    if not check_prerequisites(logger):
        logger.error("Prerequisite check failed. Aborting pipeline.")
        sys.exit(1)

    # 4 Dynamic Step Definitions
    def step1_action():
        from clean_old_epfodata import clean_old_data
        return clean_old_data()

    def step2_action():
        from epfo_portal_download import run_portal_download
        return run_portal_download(
            headless=args.headless,
            auto_mode=auto_mode,
            concurrency=args.concurrency,
        )

    def step3_action():
        from merge import merge_epfo_files
        return merge_epfo_files()

    def step4_action():
        from insert_epfo_data import insert_merged_data_to_db
        return insert_merged_data_to_db()

    steps = [
        (1, "Clean Old Data", step1_action),
        (2, "EPFO Portal Download (DB Credentials)", step2_action),
        (3, "Merge Downloaded Files", step3_action),
        (4, "Insert into EPFOEmployeeDetails DB", step4_action),
    ]

    if args.step:
        steps = [s for s in steps if s[0] == args.step]

    results = []
    total_start_time = time.time()
    total_steps = len(steps) if args.step else 4

    for step_no, step_name, step_func in steps:
        success, elapsed = run_step_module(step_no, total_steps, step_name, step_func, logger)
        results.append((step_no, step_name, "SUCCESS" if success else "FAILED", elapsed))

        if not success:
            logger.error(f"Pipeline stopped at Step {step_no}: {step_name}")
            break

        if not auto_mode and step_no < len(steps):
            input("\nPress Enter to proceed to next step...")

    total_elapsed = time.time() - total_start_time
    all_passed = all(status == "SUCCESS" for _, _, status, _ in results)

    # Final Summary Report
    print("\n")
    logger.info("=" * 70)
    logger.info("                    PIPELINE EXECUTION SUMMARY")
    logger.info("=" * 70)
    for s_no, s_name, status, s_time in results:
        status_tag = "[ OK ]" if status == "SUCCESS" else "[ FAIL ]"
        logger.info(f"Step {s_no}: {s_name:<42} {status_tag:<8} ({s_time:.2f}s)")

    logger.info("-" * 70)
    logger.info(f"Overall Status  : {'SUCCESS' if all_passed else 'FAILED'}")
    logger.info(f"Total Time      : {total_elapsed:.2f} seconds")
    logger.info(f"Log File Saved  : {log_file}")
    logger.info("=" * 70)

    if getattr(sys, "frozen", False) or not auto_mode:
        try:
            input("\nExecution completed. Press Enter to exit...")
        except Exception:
            pass

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
