# 🛡️ Compliance Automation with Database Integration (Complience_with_DB)

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Integrated-316192?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Selenium](https://img.shields.io/badge/Selenium-Automation-43B02A?logo=selenium&logoColor=white)](https://www.selenium.dev/)
[![PyInstaller](https://img.shields.io/badge/PyInstaller-Packaged-orange)](https://pyinstaller.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An advanced enterprise automation platform combining **ESIC** and **EPFO** compliance automation with live **database querying, automated reconciliation, and standalone executable packaging**.

---

## 🌟 Key Features

- **🗄️ Database Integration**: Direct connection to HRMS databases (`PostgreSQL`) to extract master employee and contribution rosters for reconciliation against portal data.
- **🤖 EPFO & ESIC Automation Modules**: Complete automated download, comparison, and verification workflows for both EPFO and ESIC establishments.
- **📦 Executable Packaging Pipelines**: Automated build assembly scripts (`assemble_epfoexe.py`, `assemble_esicexe.py`) that bundle the entire automation engine into standalone distribution executables with custom application icons.
- **🛠️ Path & Encoding Utilities**: Specialized scripts to resolve hardcoded paths (`fix_hardcoded_paths.py`), fix unicode/arrow characters (`fix_encoding_and_arrows.py`), and update match rules.
- **🔒 Enterprise Security**: Full credential protection via environment variables; live database passwords and client records are strictly excluded from source control.

---

## 📂 Project Architecture

```
Complience_with_DB/
├── New_EPFO_AUTO_software/         # EPFO automation source suite
│   └── EPFO_AUTO/
│       ├── main.py                 # EPFO orchestration entrypoint
│       └── modules/                # Modules: download, db query, merge, compare
│
├── NEW_ESIC_AUTO_SOFTWARE/         # ESIC automation source suite
│   ├── Main.py                     # ESIC orchestration entrypoint
│   └── ESIC_AUTO/                  # Modules: portal download, db merge, captcha
│
├── assemble_epfoexe.py             # Build script to compile EPFO standalone executable
├── assemble_esicexe.py             # Build script to compile ESIC standalone executable
├── create_icons.py                 # Icon generation utility for standalone apps
├── epfo_icon.ico                   # Application icon for EPFO tool
├── esic_icon.ico                   # Application icon for ESIC tool
│
├── fix_hardcoded_paths.py          # Utility to replace absolute paths with dynamic paths
├── fix_encoding_and_arrows.py      # Unicode and CLI character encoding fix
├── fix_unicode_escapes.py          # Unicode escape handler
├── update_match_path.py            # Path updater utility
│
├── .env.example                    # Template for database credentials
├── .gitignore                      # Security rules ignoring credentials & compiled binaries
└── README.md                       # Project documentation
```

---

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.10+
- PostgreSQL client libraries
- Google Chrome & compatible ChromeDriver

### 2. Installation
```bash
git clone https://github.com/KDI4U/Complience_with_DB.git
cd Complience_with_DB

python -m venv .venv
.venv\Scripts\activate

pip install -r New_EPFO_AUTO_software/EPFO_AUTO/requirements.txt
pip install pyinstaller psycopg2-binary
```

### 3. Database Configuration
Copy `.env.example` to `.env` and fill in your database credentials:
```bash
cp .env.example .env
```
```ini
DB_HOST=your_host
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_username
DB_PASSWORD=your_password
```

---

## 🛠️ Building Standalone Executables

To build standalone Windows `.exe` packages for deployment:

```bash
# Assemble and build EPFO Standalone Executable
python assemble_epfoexe.py

# Assemble and build ESIC Standalone Executable
python assemble_esicexe.py
```

---

## 🔒 Security & Privacy Notice
All production database credentials, user credentials (`users.xlsx`), downloaded compliance files, and compiled binary packages are strictly excluded via `.gitignore`.

---

## 📄 License
This project is licensed under the MIT License.

---

<div align="center">
  <b>Developed & Maintained by <a href="https://github.com/KDI4U">Kundan Kumar</a></b>
</div>
