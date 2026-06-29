import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gui.aws_client as aws
import gui.config as cfg


# ── Helpers ───────────────────────────────────────────────────────────────────

def _center(win: tk.Toplevel, parent: tk.Tk | tk.Toplevel) -> None:
    win.update_idletasks()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    w, h = win.winfo_width(), win.winfo_height()
    win.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")


# ── Settings dialog ───────────────────────────────────────────────────────────

class SettingsDialog:
    def __init__(self, parent: tk.Tk, current: dict, on_save):
        self._on_save = on_save

        dlg = tk.Toplevel(parent)
        dlg.title("Settings")
        dlg.transient(parent)
        dlg.grab_set()
        dlg.resizable(False, False)
        self._dlg = dlg

        f = ttk.Frame(dlg, padding=15)
        f.pack(fill='both', expand=True)

        # ── Credentials ──
        ttk.Label(f, text="AWS Credentials", font=('', 10, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 6))

        ttk.Label(f, text="Access Key ID:").grid(row=1, column=0, sticky='e', padx=(0, 8), pady=3)
        self._ak = ttk.Entry(f, width=42)
        self._ak.insert(0, current.get('access_key', ''))
        self._ak.grid(row=1, column=1, pady=3)

        ttk.Label(f, text="Secret Access Key:").grid(row=2, column=0, sticky='e', padx=(0, 8), pady=3)
        self._sk = ttk.Entry(f, width=42, show='*')
        self._sk.insert(0, current.get('secret_key', ''))
        self._sk.grid(row=2, column=1, pady=3)

        ttk.Label(f, text="Region:").grid(row=3, column=0, sticky='e', padx=(0, 8), pady=3)
        self._region = tk.StringVar(value=current.get('region', cfg.DEFAULT_REGION))
        ttk.Combobox(f, textvariable=self._region,
                     values=[r[0] for r in cfg.REGIONS],
                     width=39, state='readonly').grid(row=3, column=1, pady=3)

        ttk.Separator(f, orient='horizontal').grid(
            row=4, column=0, columnspan=2, sticky='ew', pady=10)

        # ── SSH (optional) ──
        ttk.Label(f, text="SSH Config  (optional)", font=('', 10, 'bold')).grid(
            row=5, column=0, columnspan=2, sticky='w', pady=(0, 3))
        ttk.Label(f, text="When set, the SSH config is updated automatically on Start / Create.",
                  foreground='gray').grid(row=6, column=0, columnspan=2, sticky='w', pady=(0, 6))

        ttk.Label(f, text="SSH Alias:").grid(row=7, column=0, sticky='e', padx=(0, 8), pady=3)
        self._alias = ttk.Entry(f, width=42)
        self._alias.insert(0, current.get('ssh_alias', ''))
        self._alias.grid(row=7, column=1, pady=3)

        ttk.Label(f, text=".pem File:").grid(row=8, column=0, sticky='e', padx=(0, 8), pady=3)
        pem_row = ttk.Frame(f)
        pem_row.grid(row=8, column=1, pady=3, sticky='w')
        self._pem = ttk.Entry(pem_row, width=33)
        self._pem.insert(0, current.get('pem_path', ''))
        self._pem.pack(side='left')
        ttk.Button(pem_row, text="Browse…", command=self._browse).pack(side='left', padx=(4, 0))

        ttk.Label(f, text="SSH User:").grid(row=9, column=0, sticky='e', padx=(0, 8), pady=3)
        self._user = ttk.Entry(f, width=42)
        self._user.insert(0, current.get('ssh_user', 'ubuntu'))
        self._user.grid(row=9, column=1, pady=3)

        # ── Buttons ──
        btn_row = ttk.Frame(f)
        btn_row.grid(row=10, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(btn_row, text="Save", command=self._save).pack(side='left', padx=5)
        ttk.Button(btn_row, text="Cancel", command=dlg.destroy).pack(side='left', padx=5)

        dlg.bind('<Return>', lambda _: self._save())
        dlg.bind('<Escape>', lambda _: dlg.destroy())
        _center(dlg, parent)
        self._ak.focus()

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select .pem key file",
            filetypes=[("PEM files", "*.pem"), ("All files", "*.*")],
            initialdir=str(Path.home() / '.ssh'),
            parent=self._dlg,
        )
        if path:
            self._pem.delete(0, 'end')
            self._pem.insert(0, path)

    def _save(self):
        ak = self._ak.get().strip()
        sk = self._sk.get().strip()
        if not ak or not sk:
            messagebox.showerror("Missing credentials",
                                 "Access Key ID and Secret Access Key are required.",
                                 parent=self._dlg)
            return
        new_cfg = {
            'access_key': ak,
            'secret_key': sk,
            'region':     self._region.get(),
            'ssh_alias':  self._alias.get().strip(),
            'pem_path':   self._pem.get().strip(),
            'ssh_user':   self._user.get().strip() or 'ubuntu',
        }
        self._dlg.destroy()
        self._on_save(new_cfg)


# ── Create Instance dialog ────────────────────────────────────────────────────

class CreateDialog:
    def __init__(self, parent: tk.Tk, session, app_config: dict, on_created):
        self._session = session
        self._app_cfg = app_config
        self._on_created = on_created
        self._snapshots: list[dict] = []

        dlg = tk.Toplevel(parent)
        dlg.title("Create EC2 Instance")
        dlg.transient(parent)
        dlg.grab_set()
        dlg.resizable(False, False)
        self._dlg = dlg

        f = ttk.Frame(dlg, padding=15)
        f.pack(fill='both', expand=True)

        pad = {'padx': (0, 8), 'pady': 4}

        ttk.Label(f, text="Key Pair Name:").grid(row=0, column=0, sticky='e', **pad)
        self._kp = ttk.Entry(f, width=36)
        self._kp.grid(row=0, column=1, pady=4)

        ttk.Label(f, text="Instance Name:").grid(row=1, column=0, sticky='e', **pad)
        self._name = ttk.Entry(f, width=36)
        self._name.insert(0, 'my-ec2')
        self._name.grid(row=1, column=1, pady=4)

        ttk.Label(f, text="Instance Type:").grid(row=2, column=0, sticky='e', **pad)
        self._itype = ttk.Combobox(f, values=cfg.INSTANCE_TYPES, width=33, state='readonly')
        self._itype.set(cfg.INSTANCE_TYPES[0])
        self._itype.grid(row=2, column=1, pady=4)

        ttk.Label(f, text="Boot Source:").grid(row=3, column=0, sticky='e', **pad)
        self._boot = tk.StringVar(value='fresh')
        boot_row = ttk.Frame(f)
        boot_row.grid(row=3, column=1, pady=4, sticky='w')
        ttk.Radiobutton(boot_row, text="Fresh instance",
                        variable=self._boot, value='fresh',
                        command=self._toggle).pack(side='left')
        ttk.Radiobutton(boot_row, text="Restore from snapshot",
                        variable=self._boot, value='snapshot',
                        command=self._toggle).pack(side='left', padx=(12, 0))

        ttk.Label(f, text="Operating System:").grid(row=4, column=0, sticky='e', **pad)
        os_names = [o[0] for o in cfg.OS_OPTIONS]
        self._os_var = tk.StringVar()
        self._os_cb = ttk.Combobox(f, textvariable=self._os_var,
                                    values=os_names, width=33, state='readonly')
        self._os_cb.set(os_names[0])
        self._os_cb.grid(row=4, column=1, pady=4)

        ttk.Label(f, text="Snapshot:").grid(row=5, column=0, sticky='e', **pad)
        self._snap_var = tk.StringVar()
        self._snap_cb = ttk.Combobox(f, textvariable=self._snap_var, width=33, state='readonly')
        self._snap_cb.grid(row=5, column=1, pady=4)

        self._status = ttk.Label(f, text="Loading snapshots…", foreground='gray')
        self._status.grid(row=6, column=0, columnspan=2, pady=(4, 0))

        self._prog = ttk.Progressbar(f, mode='indeterminate', length=320)
        self._prog.grid(row=7, column=0, columnspan=2, pady=4)
        self._prog.grid_remove()

        btn_row = ttk.Frame(f)
        btn_row.grid(row=8, column=0, columnspan=2, pady=(8, 0))
        self._create_btn = ttk.Button(btn_row, text="Create", command=self._create)
        self._create_btn.pack(side='left', padx=5)
        ttk.Button(btn_row, text="Cancel", command=dlg.destroy).pack(side='left', padx=5)

        self._toggle()
        _center(dlg, parent)
        self._kp.focus()
        self._load_snapshots()

    def _toggle(self):
        is_snap = self._boot.get() == 'snapshot'
        self._os_cb.config(state='disabled' if is_snap else 'readonly')
        self._snap_cb.config(state='readonly' if is_snap else 'disabled')

    def _load_snapshots(self):
        def fetch():
            try:
                snaps = aws.list_snapshots(self._session)
                self._dlg.after(0, lambda: self._fill_snapshots(snaps))
            except Exception as e:
                self._dlg.after(0, lambda: self._status.config(text=f"Could not load snapshots: {e}"))

        threading.Thread(target=fetch, daemon=True).start()

    def _fill_snapshots(self, snaps: list[dict]):
        self._snapshots = snaps
        labels = [f"{s['date']}  {s['id']}  {s['description'][:28]}" for s in snaps]
        self._snap_cb['values'] = labels
        if labels:
            self._snap_cb.set(labels[0])
        n = len(snaps)
        self._status.config(text=f"{n} snapshot{'s' if n != 1 else ''} available." if n else "No snapshots found.")

    def _create(self):
        kp = self._kp.get().strip()
        name = self._name.get().strip()
        itype = self._itype.get()
        boot = self._boot.get()

        if not kp:
            messagebox.showerror("Missing field", "Key pair name is required.", parent=self._dlg)
            return
        if not name:
            messagebox.showerror("Missing field", "Instance name is required.", parent=self._dlg)
            return

        os_option = None
        snapshot_id = None

        if boot == 'snapshot':
            idx = self._snap_cb.current()
            if idx < 0 or not self._snapshots:
                messagebox.showerror("No snapshot", "Please select a snapshot.", parent=self._dlg)
                return
            snapshot_id = self._snapshots[idx]['id']
        else:
            os_idx = self._os_cb.current()
            os_option = cfg.OS_OPTIONS[max(os_idx, 0)]

        self._create_btn.config(state='disabled')
        self._prog.grid()
        self._prog.start(10)

        def update_status(msg):
            self._dlg.after(0, lambda: self._status.config(text=msg))

        def run():
            try:
                result = aws.create_instance(
                    self._session, kp, name, itype,
                    os_option=os_option,
                    volume_size=cfg.DEFAULT_VOLUME_SIZE,
                    boot_source=boot,
                    snapshot_id=snapshot_id,
                    progress_cb=update_status,
                )
                self._dlg.after(0, lambda: self._done(result))
            except Exception as e:
                self._dlg.after(0, lambda: self._error(str(e)))

        threading.Thread(target=run, daemon=True).start()

    def _done(self, result):
        self._dlg.destroy()
        self._on_created(*result)

    def _error(self, msg: str):
        self._prog.stop()
        self._prog.grid_remove()
        self._create_btn.config(state='normal')
        self._status.config(text=f"Error: {msg}", foreground='red')


# ── Main application window ───────────────────────────────────────────────────

class App:
    _STATE_COLORS = {
        'running':  '#28a745',
        'stopped':  '#dc3545',
        'pending':  '#e6a817',
        'stopping': '#e6a817',
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("EC2 Manager")
        self.root.minsize(800, 480)
        self.root.geometry("960x540")

        self._config = cfg.load()
        self._session = None
        self._busy = False

        self._build_ui()

        if cfg.is_configured(self._config):
            self._connect()
        else:
            self._show_settings()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Toolbar
        toolbar = ttk.Frame(self.root, padding=(8, 5))
        toolbar.pack(fill='x', side='top')

        ttk.Label(toolbar, text="EC2 Manager", font=('', 13, 'bold')).pack(side='left')
        ttk.Button(toolbar, text="Settings", command=self._show_settings).pack(side='right', padx=3)
        ttk.Button(toolbar, text="Refresh", command=self._refresh).pack(side='right', padx=3)
        self._region_lbl = ttk.Label(toolbar, text="", foreground='gray')
        self._region_lbl.pack(side='right', padx=12)

        ttk.Separator(self.root, orient='horizontal').pack(fill='x')

        # Instance table
        table_frame = ttk.Frame(self.root, padding=(8, 6))
        table_frame.pack(fill='both', expand=True)

        cols = ('name', 'id', 'type', 'state', 'ip')
        self._tree = ttk.Treeview(table_frame, columns=cols, show='headings', selectmode='browse')
        headers = {'name': ('Name', 160), 'id': ('Instance ID', 200),
                   'type': ('Type', 110), 'state': ('State', 90), 'ip': ('Public IP', 140)}
        for col, (label, width) in headers.items():
            self._tree.heading(col, text=label)
            self._tree.column(col, width=width, minwidth=60)

        for state, color in self._STATE_COLORS.items():
            self._tree.tag_configure(state, foreground=color)

        vsb = ttk.Scrollbar(table_frame, orient='vertical', command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        self._tree.bind('<<TreeviewSelect>>', lambda _: self._sync_buttons())

        # Action buttons
        btn_frame = ttk.Frame(self.root, padding=(8, 5))
        btn_frame.pack(fill='x', side='bottom')

        self._btn_start    = ttk.Button(btn_frame, text="Start",      command=self._start)
        self._btn_stop     = ttk.Button(btn_frame, text="Stop",       command=self._stop)
        self._btn_snapshot = ttk.Button(btn_frame, text="Snapshot",   command=self._snapshot)
        self._btn_add_ip   = ttk.Button(btn_frame, text="Add My IP",  command=self._add_ip)
        self._btn_delete   = ttk.Button(btn_frame, text="Delete",     command=self._delete)
        self._btn_create   = ttk.Button(btn_frame, text="Create New Instance", command=self._create)

        for btn in (self._btn_start, self._btn_stop, self._btn_snapshot,
                    self._btn_add_ip, self._btn_delete):
            btn.pack(side='left', padx=3)
        self._btn_create.pack(side='right', padx=3)

        # Bottom bar (progress + status)
        bottom = ttk.Frame(self.root)
        bottom.pack(fill='x', side='bottom')
        bottom.grid_columnconfigure(0, weight=1)

        self._prog = ttk.Progressbar(bottom, mode='indeterminate')
        self._prog.grid(row=0, column=0, sticky='ew')
        self._prog.grid_remove()

        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(bottom, textvariable=self._status_var,
                  relief='sunken', anchor='w', padding=(6, 2)).grid(row=1, column=0, sticky='ew')

        self._sync_buttons()

    # ── State helpers ─────────────────────────────────────────────────────────

    def _set_status(self, msg: str):
        self._status_var.set(msg)
        self.root.update_idletasks()

    def _start_busy(self, msg: str = "Working…"):
        self._busy = True
        self._set_status(msg)
        self._prog.grid()
        self._prog.start(10)
        self._sync_buttons()

    def _end_busy(self, msg: str = "Ready"):
        self._busy = False
        self._prog.stop()
        self._prog.grid_remove()
        self._set_status(msg)
        self._sync_buttons()

    def _sync_buttons(self):
        inst = self._selected()
        state = inst['state'] if inst else None

        def s(enabled: bool):
            return 'normal' if enabled and not self._busy else 'disabled'

        self._btn_start.config(state=s(state == 'stopped'))
        self._btn_stop.config(state=s(state == 'running'))
        self._btn_snapshot.config(state=s(state in ('running', 'stopped')))
        self._btn_add_ip.config(state=s(state == 'running'))
        self._btn_delete.config(state=s(state in ('running', 'stopped')))
        self._btn_create.config(state='normal' if not self._busy else 'disabled')

    def _selected(self) -> dict | None:
        sel = self._tree.selection()
        if not sel:
            return None
        v = self._tree.item(sel[0])['values']
        return {'name': v[0], 'id': v[1], 'type': v[2], 'state': v[3], 'ip': v[4]}

    # ── Async helper ──────────────────────────────────────────────────────────

    def _run(self, fn, on_done, on_error=None):
        def _thread():
            try:
                result = fn()
                self.root.after(0, lambda: on_done(result))
            except Exception as e:
                def _handle_err():
                    self._end_busy()
                    messagebox.showerror("Error", str(e), parent=self.root)
                self.root.after(0, on_error or _handle_err)
        threading.Thread(target=_thread, daemon=True).start()

    # ── Networking ────────────────────────────────────────────────────────────

    def _connect(self):
        self._session = aws.get_session(
            self._config['access_key'],
            self._config['secret_key'],
            self._config.get('region', cfg.DEFAULT_REGION),
        )
        self._region_lbl.config(text=self._config.get('region', cfg.DEFAULT_REGION))
        self._refresh()

    def _refresh(self):
        if not self._session or self._busy:
            return
        self._set_status("Fetching instances…")
        self._sync_buttons()

        def fetch():
            return aws.list_instances(self._session)

        def done(instances):
            for item in self._tree.get_children():
                self._tree.delete(item)
            for inst in instances:
                tag = inst['state'] if inst['state'] in self._STATE_COLORS else ''
                self._tree.insert('', 'end',
                                  values=(inst['name'], inst['id'],
                                          inst['type'], inst['state'], inst['ip']),
                                  tags=(tag,))
            n = len(instances)
            self._set_status(f"{n} instance{'s' if n != 1 else ''} found  —  click an action button to manage")
            self._sync_buttons()

        def error():
            messagebox.showerror("Connection error",
                                 "Could not fetch instances. Check your credentials and region.",
                                 parent=self.root)
            self._set_status("Error fetching instances")
            self._sync_buttons()

        self._run(fetch, done, error)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _start(self):
        inst = self._selected()
        if not inst:
            return
        self._start_busy(f"Starting '{inst['name']}'…")

        def fn():
            return aws.start_instance(
                self._session, inst['id'],
                progress_cb=lambda m: self.root.after(0, lambda: self._set_status(m)),
            )

        def done(ip):
            self._end_busy(f"'{inst['name']}' is running  —  IP: {ip}")
            self._maybe_update_ssh(ip, self._config.get('ssh_user', 'ubuntu'))
            self._refresh()

        self._run(fn, done)

    def _stop(self):
        inst = self._selected()
        if not inst:
            return
        if not messagebox.askyesno("Stop instance",
                                   f"Stop '{inst['name']}'?\n\n"
                                   "The public IP will change when you restart it.",
                                   parent=self.root):
            return
        self._start_busy(f"Stopping '{inst['name']}'…")

        def fn():
            aws.stop_instance(
                self._session, inst['id'],
                progress_cb=lambda m: self.root.after(0, lambda: self._set_status(m)),
            )

        def done(_):
            self._end_busy(f"'{inst['name']}' stopped.")
            self._refresh()

        self._run(fn, done)

    def _snapshot(self):
        inst = self._selected()
        if not inst:
            return
        default_desc = f"snapshot of {inst['name']} ({inst['id']})"
        desc = self._ask_string("Create Snapshot",
                                f"Description for the snapshot of '{inst['name']}':",
                                default_desc)
        if desc is None:
            return
        self._start_busy(f"Creating snapshot of '{inst['name']}'…")

        def fn():
            return aws.snapshot_instance(
                self._session, inst['id'], desc,
                progress_cb=lambda m: self.root.after(0, lambda: self._set_status(m)),
            )

        def done(snap_id):
            self._end_busy(f"Snapshot {snap_id} created.")
            messagebox.showinfo("Snapshot complete",
                                f"Snapshot created successfully.\n\nSnapshot ID: {snap_id}",
                                parent=self.root)

        self._run(fn, done)

    def _add_ip(self):
        inst = self._selected()
        if not inst:
            return
        self._start_busy("Adding your IP to the security group…")

        def fn():
            return aws.add_my_ip(
                self._session, inst['id'],
                progress_cb=lambda m: self.root.after(0, lambda: self._set_status(m)),
            )

        def done(my_ip):
            self._end_busy(f"SSH access granted for {my_ip}.")

        self._run(fn, done)

    def _delete(self):
        inst = self._selected()
        if not inst:
            return
        if not messagebox.askyesno(
                "WARNING — Terminate instance",
                f"Terminate '{inst['name']}'?\n\n"
                "This is IRREVERSIBLE. All data will be lost unless you snapshot first.",
                icon='warning', parent=self.root):
            return
        do_snap = messagebox.askyesno(
            "Create snapshot first?",
            "Create a snapshot before terminating?\n(Recommended)",
            parent=self.root,
        )
        self._start_busy(f"Deleting '{inst['name']}'…")

        def fn():
            return aws.delete_instance(
                self._session, inst['id'],
                snapshot_first=do_snap,
                snapshot_desc=f"{inst['name']} backup",
                progress_cb=lambda m: self.root.after(0, lambda: self._set_status(m)),
            )

        def done(snap_id):
            msg = f"'{inst['name']}' terminated."
            if snap_id:
                msg += f"  Snapshot {snap_id} saved."
            self._end_busy(msg)
            self._refresh()

        self._run(fn, done)

    def _create(self):
        if not self._session:
            messagebox.showwarning("Not configured",
                                   "Please configure your AWS credentials in Settings first.",
                                   parent=self.root)
            self._show_settings()
            return
        CreateDialog(self.root, self._session, self._config, self._on_created)

    def _on_created(self, instance_id: str, public_ip: str, ssh_user: str):
        self._maybe_update_ssh(public_ip, ssh_user)
        self._refresh()
        msg = f"Instance created!\n\nPublic IP: {public_ip}"
        if self._config.get('ssh_alias'):
            msg += f"\nSSH: ssh {self._config['ssh_alias']}"
        messagebox.showinfo("Instance created", msg, parent=self.root)

    # ── Settings ──────────────────────────────────────────────────────────────

    def _show_settings(self):
        SettingsDialog(self.root, self._config, self._on_settings_saved)

    def _on_settings_saved(self, new_cfg: dict):
        self._config = new_cfg
        cfg.save(new_cfg)
        self._connect()

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _maybe_update_ssh(self, ip: str, ssh_user: str):
        alias = self._config.get('ssh_alias')
        pem = self._config.get('pem_path')
        if alias and pem and ip and ip != 'N/A':
            try:
                aws.update_ssh_config(alias, ip, pem, ssh_user)
            except Exception:
                pass

    def _ask_string(self, title: str, prompt: str, default: str = '') -> str | None:
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.resizable(False, False)

        ttk.Label(dlg, text=prompt, padding=(12, 10, 12, 4)).pack()
        var = tk.StringVar(value=default)
        entry = ttk.Entry(dlg, textvariable=var, width=52)
        entry.pack(padx=12, pady=4)
        entry.select_range(0, 'end')
        entry.focus()

        result: list[str | None] = [None]

        def ok():
            result[0] = var.get()
            dlg.destroy()

        btn_row = ttk.Frame(dlg, padding=(0, 6, 0, 10))
        btn_row.pack()
        ttk.Button(btn_row, text="OK", command=ok).pack(side='left', padx=5)
        ttk.Button(btn_row, text="Cancel", command=dlg.destroy).pack(side='left', padx=5)

        entry.bind('<Return>', lambda _: ok())
        entry.bind('<Escape>', lambda _: dlg.destroy())
        _center(dlg, self.root)
        dlg.wait_window()
        return result[0]


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
