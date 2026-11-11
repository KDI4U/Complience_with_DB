import os
import sys
import subprocess
import threading
import queue
import logging
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

if getattr(sys, "frozen", False):
    PROJECT_FOLDER = Path(sys.executable).resolve().parent
else:
    PROJECT_FOLDER = Path(__file__).resolve().parent

if str(PROJECT_FOLDER) not in sys.path:
    sys.path.insert(0, str(PROJECT_FOLDER))

import user_manager

# Color Theme
BG_COLOR = "#F4F6F9"
HEADER_BG = "#1A365D"
HEADER_FG = "#FFFFFF"
CARD_BG = "#FFFFFF"
ACCENT_GREEN = "#2B6CB0"
TEXT_COLOR = "#2D3748"


class TextHandler(logging.Handler):
    """Custom logging handler to route logs to GUI text widget safely via thread queue."""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)


class EpfoControlPanel(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EPFO Portal Automation - Control Panel")
        self.geometry("960x680")
        self.minsize(800, 580)
        self.configure(bg=BG_COLOR)

        # Set Window Icon if exists
        icon_path = PROJECT_FOLDER / "app_icon.ico"
        if not icon_path.exists():
            icon_path = Path(__file__).resolve().parent.parent / "app_icon.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass

        self.log_queue = queue.Queue()
        self.is_running = False

        self._setup_logging()
        self._build_ui()
        self._check_db_status_async()
        self.after(100, self._process_log_queue)

    def _setup_logging(self):
        self.gui_handler = TextHandler(self.log_queue)
        self.gui_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"))
        root_logger = logging.getLogger()
        root_logger.addHandler(self.gui_handler)

    def _build_ui(self):
        # 1. HEADER
        header_frame = tk.Frame(self, bg=HEADER_BG, height=75)
        header_frame.pack(fill=tk.X, side=tk.TOP)
        header_frame.pack_propagate(False)

        title_label = tk.Label(
            header_frame,
            text="EPFO PORTAL AUTOMATION - CONTROL PANEL",
            font=("Segoe UI", 16, "bold"),
            bg=HEADER_BG,
            fg=HEADER_FG
        )
        title_label.pack(anchor="w", padx=20, pady=(12, 2))

        sub_label = tk.Label(
            header_frame,
            text="Urmila International Services Pvt. Ltd. | Production Pipeline",
            font=("Segoe UI", 9),
            bg=HEADER_BG,
            fg="#CBD5E0"
        )
        sub_label.pack(anchor="w", padx=20)

        # DB Status Indicator on right side of header
        self.status_label = tk.Label(
            header_frame,
            text="Checking DB...",
            font=("Segoe UI", 9, "bold"),
            bg="#4A5568",
            fg="#FFFFFF",
            padx=10,
            pady=4
        )
        self.status_label.place(relx=1.0, rely=0.5, anchor="e", x=-20)

        # 2. MAIN CONTAINER (Left: Menu Buttons, Right: Real-time Execution Logs)
        main_container = tk.Frame(self, bg=BG_COLOR)
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # Left Menu Panel
        left_panel = tk.Frame(main_container, bg=CARD_BG, width=320, relief=tk.RIDGE, bd=1)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)

        menu_title = tk.Label(
            left_panel,
            text="ACTIONS & OPTIONS",
            font=("Segoe UI", 11, "bold"),
            bg=CARD_BG,
            fg="#4A5568"
        )
        menu_title.pack(anchor="w", padx=15, pady=(15, 10))

        # Big Button: Run Full Process
        self.btn_full_run = tk.Button(
            left_panel,
            text="▶  Run Full Process (4 Steps)",
            font=("Segoe UI", 11, "bold"),
            bg="#2B6CB0",
            fg="white",
            activebackground="#2C5282",
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            pady=10,
            command=self.run_full_process
        )
        self.btn_full_run.pack(fill=tk.X, padx=15, pady=5)

        # User Management Section
        tk.Label(left_panel, text="USER MANAGEMENT", font=("Segoe UI", 9, "bold"), bg=CARD_BG, fg="#718096").pack(anchor="w", padx=15, pady=(15, 5))

        btn_add_user = tk.Button(
            left_panel,
            text="➕  Add New User",
            font=("Segoe UI", 10),
            bg="#EDF2F7",
            fg="#2D3748",
            relief=tk.GROOVE,
            cursor="hand2",
            pady=6,
            command=self.open_add_user_dialog
        )
        btn_add_user.pack(fill=tk.X, padx=15, pady=3)

        btn_edit_users = tk.Button(
            left_panel,
            text="👥  View / Edit Users",
            font=("Segoe UI", 10),
            bg="#EDF2F7",
            fg="#2D3748",
            relief=tk.GROOVE,
            cursor="hand2",
            pady=6,
            command=self.open_manage_users_window
        )
        btn_edit_users.pack(fill=tk.X, padx=15, pady=3)

        # Step by Step Execution
        tk.Label(left_panel, text="RUN INDIVIDUAL STEPS", font=("Segoe UI", 9, "bold"), bg=CARD_BG, fg="#718096").pack(anchor="w", padx=15, pady=(15, 5))

        steps = [
            (1, "Step 1: Clean Old Data"),
            (2, "Step 2: EPFO Portal Download"),
            (3, "Step 3: Merge Downloaded Files"),
            (4, "Step 4: Insert Data to DB")
        ]
        for step_no, label_text in steps:
            btn = tk.Button(
                left_panel,
                text=label_text,
                font=("Segoe UI", 9),
                bg="#F7FAFC",
                fg="#4A5568",
                relief=tk.GROOVE,
                cursor="hand2",
                pady=4,
                command=lambda s=step_no: self.run_single_step(s)
            )
            btn.pack(fill=tk.X, padx=15, pady=2)

        # Quick Links / Tools
        tk.Label(left_panel, text="TOOLS & FOLDERS", font=("Segoe UI", 9, "bold"), bg=CARD_BG, fg="#718096").pack(anchor="w", padx=15, pady=(15, 5))

        tool_frame = tk.Frame(left_panel, bg=CARD_BG)
        tool_frame.pack(fill=tk.X, padx=15, pady=2)

        btn_downloads = tk.Button(tool_frame, text="📁 Downloads", font=("Segoe UI", 8), bg="#EDF2F7", command=self.open_downloads_folder)
        btn_downloads.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)

        btn_merged = tk.Button(tool_frame, text="📁 Merged", font=("Segoe UI", 8), bg="#EDF2F7", command=self.open_merged_folder)
        btn_merged.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)

        btn_logs = tk.Button(tool_frame, text="📁 Logs", font=("Segoe UI", 8), bg="#EDF2F7", command=self.open_logs_folder)
        btn_logs.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)

        btn_env = tk.Button(
            left_panel,
            text="⚙  Edit Configuration (.env)",
            font=("Segoe UI", 9),
            bg="#EDF2F7",
            fg="#2D3748",
            relief=tk.GROOVE,
            cursor="hand2",
            pady=4,
            command=self.open_env_file
        )
        btn_env.pack(fill=tk.X, padx=15, pady=(6, 2))

        # Right Panel (Execution Console & Logs)
        right_panel = tk.Frame(main_container, bg=CARD_BG, relief=tk.RIDGE, bd=1)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        log_header = tk.Frame(right_panel, bg="#EDF2F7", height=38)
        log_header.pack(fill=tk.X, side=tk.TOP)
        log_header.pack_propagate(False)

        tk.Label(
            log_header,
            text="EXECUTION LOGS & LIVE OUTPUT",
            font=("Segoe UI", 10, "bold"),
            bg="#EDF2F7",
            fg="#4A5568"
        ).pack(side=tk.LEFT, padx=12, pady=8)

        btn_clear = tk.Button(
            log_header,
            text="Clear Logs",
            font=("Segoe UI", 8),
            bg="#FFFFFF",
            relief=tk.GROOVE,
            command=self.clear_logs
        )
        btn_clear.pack(side=tk.RIGHT, padx=10, pady=6)

        # Scrolled Text for Logs
        self.log_text = tk.Text(
            right_panel,
            bg="#1A202C",
            fg="#E2E8F0",
            font=("Consolas", 10),
            wrap=tk.WORD,
            relief=tk.FLAT
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        scrollbar = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text["yscrollcommand"] = scrollbar.set

        # Initial greeting in log text
        self.log_text.insert(tk.END, "============================================================\n")
        self.log_text.insert(tk.END, "  EPFO Portal Automation System Ready\n")
        self.log_text.insert(tk.END, "  Click 'Run Full Process' or select an option to start.\n")
        self.log_text.insert(tk.END, "============================================================\n\n")

    def _check_db_status_async(self):
        def _check():
            ok, msg = user_manager.test_db_connection()
            if ok:
                self.status_label.config(text="● DB Connected", bg="#22543D", fg="#C6F6D5")
            else:
                self.status_label.config(text="● DB Offline (Excel Fallback)", bg="#742A2A", fg="#FED7D7")
        threading.Thread(target=_check, daemon=True).start()

    def _process_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, msg + "\n")
                self.log_text.see(tk.END)
        except queue.Empty:
            pass
        self.after(100, self._process_log_queue)

    def clear_logs(self):
        self.log_text.delete("1.0", tk.END)

    def _run_action_in_thread(self, target_func, label):
        if self.is_running:
            messagebox.showwarning("Busy", "A task is already running. Please wait for it to complete.")
            return

        self.is_running = True
        self.btn_full_run.config(state=tk.DISABLED, text="⏳ Running...")

        def _worker():
            try:
                target_func()
            except Exception as e:
                logging.getLogger("gui").error(f"Execution Error: {e}", exc_info=True)
            finally:
                self.is_running = False
                self.btn_full_run.config(state=tk.NORMAL, text="▶  Run Full Process (4 Steps)")

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def run_full_process(self):
        from main import run_step_module, setup_logger
        def _execute():
            logger, _ = setup_logger(verbose=False)
            logger.info("Starting Full 4-Step Pipeline from Control Panel...")
            from clean_old_epfodata import clean_old_data
            from epfo_portal_download import run_portal_download
            from merge import merge_epfo_files
            from insert_epfo_data import insert_merged_data_to_db

            steps = [
                (1, 4, "Clean Old Data", clean_old_data),
                (2, 4, "EPFO Portal Download", lambda: run_portal_download(headless=False, auto_mode=True, concurrency=1)),
                (3, 4, "Merge Downloaded Files", merge_epfo_files),
                (4, 4, "Insert into DB", insert_merged_data_to_db)
            ]
            for s_no, total, name, func in steps:
                ok, _ = run_step_module(s_no, total, name, func, logger)
                if not ok:
                    logger.error(f"Pipeline terminated prematurely at Step {s_no}.")
                    return
            logger.info("Full Pipeline Execution Finished Successfully!")

        self._run_action_in_thread(_execute, "Full Process")

    def run_single_step(self, step_number):
        from main import run_step_module, setup_logger
        def _execute():
            logger, _ = setup_logger(verbose=False)
            if step_number == 1:
                from clean_old_epfodata import clean_old_data
                run_step_module(1, 1, "Clean Old Data", clean_old_data, logger)
            elif step_number == 2:
                from epfo_portal_download import run_portal_download
                run_step_module(2, 1, "EPFO Portal Download", lambda: run_portal_download(headless=False, auto_mode=True, concurrency=1), logger)
            elif step_number == 3:
                from merge import merge_epfo_files
                run_step_module(3, 1, "Merge Downloaded Files", merge_epfo_files, logger)
            elif step_number == 4:
                from insert_epfo_data import insert_merged_data_to_db
                run_step_module(4, 1, "Insert into DB", insert_merged_data_to_db, logger)

        self._run_action_in_thread(_execute, f"Step {step_number}")

    # ============================================================
    # ADD NEW USER DIALOG
    # ============================================================
    def open_add_user_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Add New EPFO User")
        dialog.geometry("400x260")
        dialog.resizable(False, False)
        dialog.configure(bg=CARD_BG)
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text="Add New Portal Credential", font=("Segoe UI", 12, "bold"), bg=CARD_BG, fg=HEADER_BG).pack(pady=(15, 10))

        form_frame = tk.Frame(dialog, bg=CARD_BG)
        form_frame.pack(fill=tk.X, padx=30, pady=5)

        tk.Label(form_frame, text="Login ID (Establishment ID):", font=("Segoe UI", 9, "bold"), bg=CARD_BG).grid(row=0, column=0, sticky="w", pady=4)
        entry_user = ttk.Entry(form_frame, width=28)
        entry_user.grid(row=0, column=1, pady=4)
        entry_user.focus_set()

        tk.Label(form_frame, text="Portal Password:", font=("Segoe UI", 9, "bold"), bg=CARD_BG).grid(row=1, column=0, sticky="w", pady=4)
        entry_pass = ttk.Entry(form_frame, width=28, show="*")
        entry_pass.grid(row=1, column=1, pady=4)

        tk.Label(form_frame, text="Status / Type:", font=("Segoe UI", 9, "bold"), bg=CARD_BG).grid(row=2, column=0, sticky="w", pady=4)
        combo_status = ttk.Combobox(form_frame, values=["PF", "EPFO"], width=25, state="readonly")
        combo_status.set("PF")
        combo_status.grid(row=2, column=1, pady=4)

        def _save():
            uid = entry_user.get().strip()
            pwd = entry_pass.get().strip()
            st = combo_status.get().strip()
            if not uid or not pwd:
                messagebox.showerror("Error", "Login ID and Password are required!", parent=dialog)
                return

            ok, msg = user_manager.add_user(uid, pwd, st)
            if ok:
                messagebox.showinfo("Success", f"User '{uid}' added successfully!\n({msg})", parent=dialog)
                dialog.destroy()
            else:
                messagebox.showerror("Error", msg, parent=dialog)

        btn_frame = tk.Frame(dialog, bg=CARD_BG)
        btn_frame.pack(fill=tk.X, pady=18, padx=30)

        btn_submit = tk.Button(btn_frame, text="Save User", font=("Segoe UI", 10, "bold"), bg="#2B6CB0", fg="white", padx=15, pady=4, command=_save)
        btn_submit.pack(side=tk.RIGHT, padx=5)

        btn_cancel = tk.Button(btn_frame, text="Cancel", font=("Segoe UI", 10), bg="#EDF2F7", padx=10, pady=4, command=dialog.destroy)
        btn_cancel.pack(side=tk.RIGHT)

    # ============================================================
    # VIEW / EDIT USERS WINDOW
    # ============================================================
    def open_manage_users_window(self):
        win = tk.Toplevel(self)
        win.title("Manage EPFO Users")
        win.geometry("720x480")
        win.configure(bg=CARD_BG)
        win.transient(self)

        top_frame = tk.Frame(win, bg="#EDF2F7", height=50)
        top_frame.pack(fill=tk.X, side=tk.TOP)
        top_frame.pack_propagate(False)

        tk.Label(top_frame, text="EPFO Registered Users", font=("Segoe UI", 12, "bold"), bg="#EDF2F7", fg=HEADER_BG).pack(side=tk.LEFT, padx=15, pady=12)

        # Search Box
        tk.Label(top_frame, text="Search:", font=("Segoe UI", 9), bg="#EDF2F7").pack(side=tk.LEFT, padx=(20, 5))
        search_var = tk.StringVar()
        entry_search = ttk.Entry(top_frame, textvariable=search_var, width=20)
        entry_search.pack(side=tk.LEFT, padx=2)

        # Treeview Table
        tree_frame = tk.Frame(win, bg=CARD_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        columns = ("id", "loginid", "password", "status", "source")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        tree.heading("id", text="ID")
        tree.heading("loginid", text="Login ID / Establishment")
        tree.heading("password", text="Password")
        tree.heading("status", text="Status")
        tree.heading("source", text="Source")

        tree.column("id", width=50, anchor="center")
        tree.column("loginid", width=220)
        tree.column("password", width=160)
        tree.column("status", width=80, anchor="center")
        tree.column("source", width=100, anchor="center")

        tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscroll=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        all_users = []

        def _refresh_table():
            nonlocal all_users
            for item in tree.get_children():
                tree.delete(item)
            all_users = user_manager.load_all_users()
            query = search_var.get().strip().lower()
            for u in all_users:
                if query and (query not in u["loginid"].lower() and query not in u["status"].lower()):
                    continue
                tree.insert("", tk.END, values=(u["id"], u["loginid"], u["password"], u["status"], u["source"]))

        search_var.trace_add("write", lambda *args: _refresh_table())

        # Buttons on bottom
        bottom_frame = tk.Frame(win, bg=CARD_BG, height=50)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=15, pady=10)

        def _edit_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select User", "Please select a user to edit.", parent=win)
                return
            vals = tree.item(sel[0], "values")
            loginid = vals[1]
            old_pass = vals[2]

            new_pass = simpledialog.askstring("Change Password", f"Enter new password for {loginid}:", initialvalue=old_pass, parent=win)
            if new_pass:
                ok, msg = user_manager.update_user_password(loginid, new_pass)
                if ok:
                    messagebox.showinfo("Updated", f"Password for {loginid} updated!\n({msg})", parent=win)
                    _refresh_table()
                else:
                    messagebox.showerror("Error", msg, parent=win)

        def _delete_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select User", "Please select a user to delete.", parent=win)
                return
            vals = tree.item(sel[0], "values")
            loginid = vals[1]

            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to remove user '{loginid}'?", parent=win):
                ok, msg = user_manager.delete_user(loginid)
                if ok:
                    messagebox.showinfo("Removed", msg, parent=win)
                    _refresh_table()
                else:
                    messagebox.showerror("Error", msg, parent=win)

        btn_edit = tk.Button(bottom_frame, text="✏  Edit Password", font=("Segoe UI", 9, "bold"), bg="#EDF2F7", padx=10, pady=4, command=_edit_selected)
        btn_edit.pack(side=tk.LEFT, padx=5)

        btn_del = tk.Button(bottom_frame, text="🗑  Delete User", font=("Segoe UI", 9), bg="#FFF5F5", fg="#C53030", padx=10, pady=4, command=_delete_selected)
        btn_del.pack(side=tk.LEFT, padx=5)

        btn_add = tk.Button(bottom_frame, text="➕  Add User", font=("Segoe UI", 9, "bold"), bg="#2B6CB0", fg="white", padx=12, pady=4, command=lambda: [self.open_add_user_dialog(), _refresh_table()])
        btn_add.pack(side=tk.RIGHT, padx=5)

        btn_reload = tk.Button(bottom_frame, text="🔄  Refresh", font=("Segoe UI", 9), bg="#EDF2F7", padx=10, pady=4, command=_refresh_table)
        btn_reload.pack(side=tk.RIGHT, padx=5)

        _refresh_table()

    # ============================================================
    # FOLDERS & TOOLS
    # ============================================================
    def open_downloads_folder(self):
        f = PROJECT_FOLDER / "data" / "pf_downloads"
        f.mkdir(parents=True, exist_ok=True)
        os.startfile(str(f))

    def open_merged_folder(self):
        f = PROJECT_FOLDER / "Merge_data"
        f.mkdir(parents=True, exist_ok=True)
        os.startfile(str(f))

    def open_logs_folder(self):
        f = PROJECT_FOLDER / "logs"
        f.mkdir(parents=True, exist_ok=True)
        os.startfile(str(f))

    def open_env_file(self):
        env_f = PROJECT_FOLDER / ".env"
        if not env_f.exists():
            env_f.write_text("DB_HOST=\nDB_PORT=5432\nDB_NAME=\nDB_USER=\nDB_PASSWORD=\n", encoding="utf-8")
        os.startfile(str(env_f))


def launch_gui():
    app = EpfoControlPanel()
    app.mainloop()


if __name__ == "__main__":
    launch_gui()

