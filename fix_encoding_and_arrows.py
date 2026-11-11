import os
from pathlib import Path

folder = Path(r"D:\Complience_with_DB\epfo_downloads_txt\Pf data download codes")

utf8_header = """import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
"""

for py_file in folder.glob("*.py"):
    content = py_file.read_text(encoding="utf-8")
    
    # Replace unicode arrow
    content = content.replace("→", "->")
    content = content.replace("\\u2192", "->")
    
    # Add UTF-8 reconfiguration if not present
    if "sys.stdout.reconfigure" not in content:
        content = utf8_header + "\n" + content

    py_file.write_text(content, encoding="utf-8")
    print(f"Fixed: {py_file.name}")

print("All scripts updated!")

