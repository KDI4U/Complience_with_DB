from pathlib import Path

targets = [
    Path(r"D:\Complience_with_DB\epfo_downloads_txt\Pf data download codes\View-Pay Challans.py"),
    Path(r"D:\Complience_with_DB\epfo_downloads_txt\Pf data download codes\tran_challan.py"),
    Path(r"D:\Complience_with_DB\epfo_downloads_txt\Pf data download codes\Return Filing History.py"),
]

for p in targets:
    if p.exists():
        content = p.read_text(encoding="utf-8")
        content = content.replace(r'View-Pay Challans_users\users.xlsx', 'View-Pay Challans_users/users.xlsx')
        content = content.replace(r'Return Filing History users\users.xlsx', 'Return Filing History users/users.xlsx')
        p.write_text(content, encoding="utf-8")
        print(f"Fixed: {p.name}")

print("All unicode escape bugs fixed!")

