import os
import threading
import queue
from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import yt_dlp
from yt_dlp.utils import format_bytes

from download import format_duration, get_ydl_opts


def default_download_dir() -> str:
    return os.path.expanduser("~/Vidéos")


def format_kind(vcodec: str | None, acodec: str | None) -> str:
    v = vcodec or "none"
    a = acodec or "none"
    if v == "none" and a != "none":
        return "audio"
    if v != "none" and a == "none":
        return "video"
    if v != "none" and a != "none":
        return "audio+video"
    return "unknown"


@dataclass
class FormatRow:
    format_id: str
    ext: str
    size_bytes: int | None
    kind: str
    note: str


class DownloaderModel:
    def __init__(self) -> None:
        self.info: dict | None = None
        self.formats: list[FormatRow] = []
        self.is_playlist: bool = False
        self.entries: list[dict] = []

    def load_info(self, url: str) -> None:
        ydl_opts = get_ydl_opts(quiet=True)
        ydl_opts.update({
            "skip_download": True,
            "extract_flat": False,
            "noplaylist": False,
        })
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            self.info = ydl.extract_info(url, download=False)

        self.is_playlist = self.info.get("_type") == "playlist"
        self.entries = self.info.get("entries") or []
        self.formats = self._collect_formats()

    def _collect_formats(self) -> list[FormatRow]:
        if not self.info:
            return []

        # Use the first entry for playlists (format list is usually similar)
        info = self.info
        if self.is_playlist and self.entries:
            info = self.entries[0]

        rows: list[FormatRow] = []
        for f in info.get("formats") or []:
            fmt_id = f.get("format_id") or ""
            if fmt_id.startswith("sb"):
                continue
            size = f.get("filesize") or f.get("filesize_approx")
            row = FormatRow(
                format_id=fmt_id or "?",
                ext=f.get("ext") or "?",
                size_bytes=size if isinstance(size, int) else None,
                kind=format_kind(f.get("vcodec"), f.get("acodec")),
                note=f.get("format_note") or "",
            )
            rows.append(row)

        return rows

    def total_size_for_format(self, format_id: str) -> int | None:
        if not self.info:
            return None

        if not self.is_playlist:
            for f in self.info.get("formats") or []:
                if f.get("format_id") == format_id:
                    return f.get("filesize") or f.get("filesize_approx")
            return None

        total = 0
        found_any = False
        for entry in self.entries:
            for f in entry.get("formats") or []:
                if f.get("format_id") == format_id:
                    size = f.get("filesize") or f.get("filesize_approx")
                    if isinstance(size, int):
                        total += size
                        found_any = True
                    break
        return total if found_any else None


class DownloaderView(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.master = master
        self._build_ui()

    def _build_ui(self) -> None:
        self.master.title("ProDownloader")
        self.master.geometry("980x640")
        self.master.minsize(900, 600)

        style = ttk.Style(self.master)
        style.theme_use("clam")
        style.configure("TFrame", background="#f4f6f8")
        style.configure("TLabel", background="#f4f6f8", foreground="#1f2a37")
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=26, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        container = ttk.Frame(self.master, padding=16)
        container.pack(fill="both", expand=True)

        title = ttk.Label(container, text="Téléchargeur Vidéo Pro", style="Title.TLabel")
        title.pack(anchor="w")

        url_frame = ttk.Frame(container)
        url_frame.pack(fill="x", pady=(16, 8))
        ttk.Label(url_frame, text="URL :").pack(side="left")
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(url_frame, textvariable=self.url_var, width=80)
        self.url_entry.pack(side="left", padx=8, fill="x", expand=True)
        self.load_btn = ttk.Button(url_frame, text="Charger les formats")
        self.load_btn.pack(side="left", padx=8)

        out_frame = ttk.Frame(container)
        out_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(out_frame, text="Dossier :").pack(side="left")
        self.path_var = tk.StringVar(value=default_download_dir())
        self.path_entry = ttk.Entry(out_frame, textvariable=self.path_var, width=60)
        self.path_entry.pack(side="left", padx=8, fill="x", expand=True)
        self.path_btn = ttk.Button(out_frame, text="Changer")
        self.path_btn.pack(side="left")

        info_frame = ttk.Frame(container)
        info_frame.pack(fill="x", pady=(8, 8))
        self.meta_var = tk.StringVar(value="Prêt.")
        ttk.Label(info_frame, textvariable=self.meta_var).pack(side="left")

        table_frame = ttk.Frame(container)
        table_frame.pack(fill="both", expand=True, pady=(8, 8))
        columns = ("id", "format", "taille", "type", "note")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        self.tree.heading("id", text="ID")
        self.tree.heading("format", text="Format")
        self.tree.heading("taille", text="Taille")
        self.tree.heading("type", text="Type")
        self.tree.heading("note", text="Note")
        self.tree.column("id", width=80, anchor="center")
        self.tree.column("format", width=80, anchor="center")
        self.tree.column("taille", width=140, anchor="center")
        self.tree.column("type", width=120, anchor="center")
        self.tree.column("note", width=140, anchor="center")
        self.tree.pack(fill="both", expand=True, side="left")

        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scroll.set)
        scroll.pack(side="right", fill="y")

        action_frame = ttk.Frame(container)
        action_frame.pack(fill="x", pady=(8, 8))
        self.download_btn = ttk.Button(action_frame, text="Télécharger", style="Primary.TButton")
        self.download_btn.pack(side="left")

        self.total_var = tk.StringVar(value="")
        ttk.Label(action_frame, textvariable=self.total_var).pack(side="left", padx=12)

        progress_frame = ttk.Frame(container)
        progress_frame.pack(fill="x", pady=(8, 4))
        self.progress = ttk.Progressbar(progress_frame, mode="determinate")
        self.progress.pack(fill="x", expand=True)
        self.progress_text = tk.StringVar(value="")
        ttk.Label(container, textvariable=self.progress_text).pack(anchor="w")


class DownloaderController:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.model = DownloaderModel()
        self.view = DownloaderView(root)
        self.view.pack(fill="both", expand=True)

        self.events: queue.Queue[dict] = queue.Queue()
        self._download_total = None
        self._downloaded_overall = 0
        self._last_file_bytes: dict[str, int] = {}

        self._bind_events()
        self._poll_events()

    def _bind_events(self) -> None:
        self.view.load_btn.configure(command=self.load_formats)
        self.view.download_btn.configure(command=self.download_selected)
        self.view.path_btn.configure(command=self.change_folder)

    def _poll_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _handle_event(self, event: dict) -> None:
        etype = event.get("type")
        if etype == "progress":
            downloaded = event.get("downloaded")
            total = event.get("total")
            if total:
                self.view.progress.configure(mode="determinate", maximum=total, value=downloaded)
                self.view.progress_text.set(f"{format_bytes(downloaded)} / {format_bytes(total)}")
            elif isinstance(downloaded, int):
                self.view.progress.configure(mode="indeterminate")
                self.view.progress.start(100)
                self.view.progress_text.set(f"{format_bytes(downloaded)} téléchargés...")
        elif etype == "status":
            self.view.meta_var.set(event.get("text", ""))
        elif etype == "done":
            self.view.progress.stop()
            self.view.progress_text.set("Téléchargement terminé.")

    def change_folder(self) -> None:
        path = filedialog.askdirectory(initialdir=self.view.path_var.get())
        if path:
            self.view.path_var.set(path)

    def load_formats(self) -> None:
        url = self.view.url_var.get().strip()
        if not url:
            messagebox.showwarning("URL manquante", "Veuillez entrer une URL.")
            return

        self.view.meta_var.set("Chargement des formats...")
        self.view.tree.delete(*self.view.tree.get_children())
        self.view.total_var.set("")

        def task() -> None:
            try:
                self.model.load_info(url)
                info = self.model.info or {}
                title = info.get("title") or "Sans titre"
                if self.model.is_playlist:
                    count = len(self.model.entries)
                    self.events.put({"type": "status", "text": f"Playlist: {title} ({count} vidéos)"})
                else:
                    duration = info.get("duration")
                    dtext = format_duration(int(duration)) if isinstance(duration, int) else "?"
                    self.events.put({"type": "status", "text": f"Vidéo: {title} ({dtext})"})

                for row in self.model.formats:
                    size = format_bytes(row.size_bytes) if row.size_bytes else "inconnue"
                    self.view.tree.insert(
                        "",
                        "end",
                        values=(row.format_id, row.ext, size, row.kind, row.note),
                    )
            except Exception as e:
                self.events.put({"type": "status", "text": "Erreur lors du chargement."})
                messagebox.showerror("Erreur", str(e))

        threading.Thread(target=task, daemon=True).start()

    def _selected_format_id(self) -> str | None:
        selection = self.view.tree.selection()
        if not selection:
            return None
        values = self.view.tree.item(selection[0], "values")
        return values[0] if values else None

    def download_selected(self) -> None:
        url = self.view.url_var.get().strip()
        if not url:
            messagebox.showwarning("URL manquante", "Veuillez entrer une URL.")
            return

        fmt_id = self._selected_format_id()
        if not fmt_id:
            messagebox.showwarning("Format manquant", "Veuillez sélectionner un format.")
            return

        out_dir = self.view.path_var.get().strip()
        if not out_dir:
            messagebox.showwarning("Dossier manquant", "Veuillez choisir un dossier de sortie.")
            return

        total = self.model.total_size_for_format(fmt_id)
        self._download_total = total
        self._downloaded_overall = 0
        self._last_file_bytes.clear()
        if total:
            self.view.total_var.set(f"Taille totale: {format_bytes(total)}")
        else:
            self.view.total_var.set("Taille totale: inconnue")

        self.view.progress.configure(value=0, maximum=total or 100)
        self.view.progress_text.set("")

        def hook(d: dict) -> None:
            if d.get("status") != "downloading":
                return
            downloaded = d.get("downloaded_bytes") or 0
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
            filename = d.get("filename") or "?"
            last = self._last_file_bytes.get(filename, 0)
            delta = max(0, downloaded - last)
            self._last_file_bytes[filename] = downloaded
            if total:
                self._downloaded_overall += delta
                self.events.put({
                    "type": "progress",
                    "downloaded": self._downloaded_overall,
                    "total": total,
                })
            elif isinstance(total_bytes, int):
                self.events.put({
                    "type": "progress",
                    "downloaded": downloaded,
                    "total": total_bytes,
                })
            else:
                self.events.put({
                    "type": "progress",
                    "downloaded": downloaded,
                    "total": None,
                })

        def task() -> None:
            try:
                self.events.put({"type": "status", "text": "Téléchargement en cours..."})
                ydl_opts = get_ydl_opts(quiet=True)
                ydl_opts.update({
                    "format": fmt_id,
                    "outtmpl": os.path.join(out_dir, "%(title)s.%(ext)s"),
                    "progress_hooks": [hook],
                    "noplaylist": False,
                })
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                self.events.put({"type": "done"})
                self.events.put({"type": "status", "text": "Téléchargement terminé."})
            except Exception as e:
                self.events.put({"type": "status", "text": "Erreur de téléchargement."})
                messagebox.showerror("Erreur", str(e))

        threading.Thread(target=task, daemon=True).start()


def main() -> None:
    root = tk.Tk()
    DownloaderController(root)
    root.mainloop()


if __name__ == "__main__":
    main()
