from pathlib import Path

p = Path(r"D:\Complience_with_DB\epfo_downloads_txt\Pf data download codes\Match_folder.py")
content = p.read_text(encoding="utf-8")

old_text = "BASE_PATH = Path(__file__).resolve().parent"
new_text = """_curr = Path(__file__).resolve().parent
if (_curr.parent / "Return Filing History").exists() or (_curr.parent / "View-Pay Challans").exists() or (_curr.parent / "Upload").exists():
    BASE_PATH = _curr.parent
else:
    BASE_PATH = _curr"""

if old_text in content:
    content = content.replace(old_text, new_text, 1)
    p.write_text(content, encoding="utf-8")
    print("Match_folder.py updated successfully!")
else:
    print("Pattern not found in Match_folder.py")

