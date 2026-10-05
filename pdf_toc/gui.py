"""Giao diện Tkinter cho PDF TOC Translator."""

import json
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from . import config as cfg_mod
from .core import read_outline, write_pdf_with_toc, pdf_page_count, TocItem
from .md_io import (export_markdown, load_markdown,
                    export_titles_json, merge_translated)
from .gemini import translate_titles, GeminiError


MODELS = ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.8-flash"]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF TOC Translator")
        self.geometry("900x640")
        self.minsize(760, 520)

        self.pdf_path = tk.StringVar()
        self.api_key_var = tk.StringVar()
        self.model_var = tk.StringVar()
        self.show_key = tk.BooleanVar(value=False)
        self.page_count = 0
        self._items = []  # list[TocItem] hiện tại

        self._build_ui()
        self._load_saved_config()

    # ================== UI ==================
    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}

        # ---------- Vùng 0: API key ----------
        f0 = ttk.LabelFrame(self, text=" Gemini API Key ", padding=10)
        f0.pack(fill="x", **pad)

        # Dòng 1: API Key + nút 👁 Lưu 🗑️
        row = ttk.Frame(f0); row.pack(fill="x")
        ttk.Label(row, text="API Key:", width=10).pack(side="left")
        self.key_entry = ttk.Entry(
            row, textvariable=self.api_key_var, show="•"
        )
        self.key_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(row, text="👁", width=4,
                   command=self.toggle_key).pack(side="left", padx=(0, 4))
        ttk.Button(row, text="💾 Lưu", width=8,
                   command=self.save_key).pack(side="left", padx=(0, 4))
        ttk.Button(row, text="🗑️", width=4,
                   command=self.delete_key).pack(side="left")

        # Dòng 2: Model (Entry + Combobox gợi ý)
        row2 = ttk.Frame(f0); row2.pack(fill="x", pady=(6, 0))
        ttk.Label(row2, text="Model:", width=10).pack(side="left")
        self.model_combo = ttk.Combobox(
            row2, textvariable=self.model_var,
            values=MODELS, width=40
        )
        self.model_combo.pack(side="left", fill="x", expand=True)
        ttk.Label(row2, text="(có thể gõ tên model khác)",
                  foreground="#888").pack(side="left", padx=(6, 0))

        # Dòng 3: Status
        self.key_status = ttk.Label(f0, text="Chưa có API key.",
                                    foreground="#a00")
        self.key_status.pack(anchor="w", pady=(6, 0))

        # ---------- Vùng 1: chọn PDF ----------
        f1 = ttk.Frame(self, padding=(12, 0))
        f1.pack(fill="x")
        ttk.Label(f1, text="File PDF:", width=10).pack(side="left")
        ttk.Entry(f1, textvariable=self.pdf_path).pack(
            side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(f1, text="📂 Chọn…",
                   command=self.choose_pdf).pack(side="left")

        # ---------- Vùng 2: tree ----------
        f2 = ttk.LabelFrame(self, text=" Mục lục trong PDF ", padding=8)
        f2.pack(fill="both", expand=True, padx=12, pady=8)

        cols = ("level", "title", "page")
        self.tree = ttk.Treeview(f2, columns=cols, show="headings")
        self.tree.heading("level", text="Cấp")
        self.tree.heading("title", text="Tiêu đề")
        self.tree.heading("page", text="Trang")
        self.tree.column("level", width=60, anchor="center")
        self.tree.column("title", width=600, anchor="w")
        self.tree.column("page", width=80, anchor="center")

        vsb = ttk.Scrollbar(f2, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # ---------- Vùng 3: nút ----------
        f3 = ttk.Frame(self, padding=(12, 0))
        f3.pack(fill="x")

        self.btn_export = ttk.Button(
            f3, text="📤 Xuất Markdown",
            width=22, command=self.do_export)
        self.btn_export.pack(side="left", padx=(0, 6))

        self.btn_gemini = ttk.Button(
            f3, text="🤖 Dịch bằng Gemini",
            width=22, command=self.do_translate)
        self.btn_gemini.pack(side="left", padx=(0, 6))

        self.btn_reload = ttk.Button(
            f3, text="🔄 Nạp lại file",
            width=22, command=self.do_reload)
        self.btn_reload.pack(side="left", padx=(0, 6))

        self.btn_write = ttk.Button(
            f3, text="📥 Ghi PDF mới",
            width=22, command=self.do_write_pdf)
        self.btn_write.pack(side="left")

        # ---------- Vùng 4: status ----------
        self.status = ttk.Label(self, text="Sẵn sàng.",
                                foreground="#555", padding=(12, 8))
        self.status.pack(fill="x")

    # ================== Config ==================
    def _load_saved_config(self):
        cfg = cfg_mod.load_config()
        key = cfg.get("gemini_api_key", "")
        model = cfg.get("model", MODELS[0]) or MODELS[0]
        self.api_key_var.set(key)
        self.model_var.set(model)
        self._refresh_key_status()

    def _refresh_key_status(self):
        key = self.api_key_var.get().strip()
        if key:
            cfg = cfg_mod.load_config()
            saved_at = cfg.get("last_saved", "")
            self.key_status.config(
                text=f"✅ Đã có API key"
                     + (f" · Lần lưu: {saved_at}" if saved_at else ""),
                foreground="#0a7")
            self.btn_gemini.state(["!disabled"])
        else:
            self.key_status.config(
                text="⚠️ Chưa có API key — nhập để dùng Gemini.",
                foreground="#a00")
            self.btn_gemini.state(["disabled"])

    def toggle_key(self):
        self.show_key.set(not self.show_key.get())
        self.key_entry.config(show="" if self.show_key.get() else "•")

    def save_key(self):
        key = self.api_key_var.get().strip()
        model = self.model_var.get().strip()

        if not key:
            messagebox.showwarning("Thiếu key", "Bạn chưa nhập API key.")
            return
        if not model:
            messagebox.showwarning("Thiếu model",
                                   "Bạn chưa nhập tên model.\n"
                                   "VD: gemini-3.5-flash")
            return

        cfg_mod.set_api_key(key, model)
        self._refresh_key_status()
        self._set_status(f"💾 Đã lưu key · Model: {model}", ok=True)

    def delete_key(self):
        """Xóa API key khỏi config."""
        if not messagebox.askyesno(
            "Xác nhận xóa",
            "Bạn có chắc muốn xóa API key?\n\n"
            "Sau khi xóa, phải nhập lại key mới để dùng Gemini."
        ):
            return

        # Xóa khỏi config
        cfg = cfg_mod.load_config()
        cfg["gemini_api_key"] = ""
        cfg["last_saved"] = ""
        cfg_mod.save_config(cfg)

        # Xóa khỏi UI
        self.api_key_var.set("")

        # Cập nhật trạng thái
        self._refresh_key_status()
        self._set_status("🗑️ Đã xóa API key.", ok=True)

    # ================== Chọn PDF ==================
    def choose_pdf(self):
        init = cfg_mod.get_last_dir() or ""
        p = filedialog.askopenfilename(
            title="Chọn PDF có mục lục",
            initialdir=init or None,
            filetypes=[("PDF files", "*.pdf")])
        if not p:
            return
        self.pdf_path.set(p)
        cfg_mod.set_last_dir(os.path.dirname(p))

        try:
            self.page_count = pdf_page_count(p)
            self._items = read_outline(p)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không đọc được PDF:\n{e}")
            return

        if not self._items:
            messagebox.showwarning(
                "Không có mục lục",
                "PDF này không có bookmark (outline).\n"
                "Hãy kiểm tra bằng Adobe Reader — panel trái phải có bookmarks.")
        self._fill_tree(self._items)
        self._set_status(
            f"📖 Đã đọc {len(self._items)} mục · PDF có {self.page_count} trang.",
            ok=True)

    # ================== Tree ==================
    def _fill_tree(self, items):
        self.tree.delete(*self.tree.get_children())
        stack = []
        for it in items:
            while stack and stack[-1][0] >= it.level:
                stack.pop()
            parent = stack[-1][1] if stack else ""
            node = self.tree.insert(
                parent, "end",
                values=(it.level, it.title, it.page))
            stack.append((it.level, node))

    # ================== Xuất Markdown ==================
    def do_export(self):
        if not self.pdf_path.get():
            messagebox.showwarning("Thiếu thông tin", "Chưa chọn PDF.")
            return
        default = os.path.splitext(os.path.basename(self.pdf_path.get()))[0] + ".md"
        init_dir = os.path.dirname(self.pdf_path.get())
        out = filedialog.asksaveasfilename(
            title="Lưu Markdown",
            initialdir=init_dir, initialfile=default,
            defaultextension=".md",
            filetypes=[("Markdown", "*.md")])
        if not out:
            return
        try:
            items = read_outline(self.pdf_path.get())
            n = export_markdown(self.pdf_path.get(), items, out, self.page_count)
            self._fill_tree(items)
            self._set_status(f"✅ Đã xuất {n} mục → {os.path.basename(out)}", ok=True)
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    # ================== Dịch bằng Gemini ==================
    def do_translate(self):
        if not self.pdf_path.get():
            messagebox.showwarning("Thiếu thông tin", "Chưa chọn PDF.")
            return
        key = self.api_key_var.get().strip()
        if not key:
            messagebox.showwarning("Thiếu key", "Chưa nhập API key.")
            return

        base = os.path.splitext(self.pdf_path.get())[0]
        md_path = base + ".md"
        titles_json = base + "_titles.json"
        translated_json = base + "_translated.json"
        vi_md = base + "_vi.md"

        # Nếu chưa có .md thì tự xuất luôn
        if not os.path.exists(md_path):
            try:
                items = read_outline(self.pdf_path.get())
                export_markdown(self.pdf_path.get(), items, md_path, self.page_count)
            except Exception as e:
                messagebox.showerror("Lỗi", str(e))
                return

        # Chuẩn bị file titles
        try:
            n = export_titles_json(md_path, titles_json)
            with open(titles_json, "r", encoding="utf-8") as f:
                titles = json.load(f)
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))
            return

        # Chạy dịch trong thread riêng để không đơ UI
        self.btn_gemini.state(["disabled"])
        self._set_status(f"⏳ Đang gọi Gemini dịch {n} mục…", ok=False)

        def worker():
            try:
                result = translate_titles(
                    api_key=key,
                    model_name=self.model_var.get(),
                    titles=titles,
                    temperature=cfg_mod.get_temperature(),
                )
                with open(translated_json, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

                merge_translated(md_path, translated_json, vi_md)

                self.after(0, lambda: self._on_translate_done(vi_md, n))
            except GeminiError as ge:
                self.after(0, lambda: self._on_translate_err(str(ge)))
            except Exception as e:
                self.after(0, lambda: self._on_translate_err(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_translate_done(self, vi_md_path, n):
        self.btn_gemini.state(["!disabled"])
        try:
            items = load_markdown(vi_md_path)
            self._fill_tree(items)
        except Exception:
            pass
        self._set_status(
            f"✅ Đã dịch {n} mục → {os.path.basename(vi_md_path)}", ok=True)
        messagebox.showinfo(
            "Xong",
            f"Đã dịch {n} mục.\nKết quả: {vi_md_path}\n\n"
            "Bấm '📥 Ghi PDF mới' để tạo PDF tiếng Việt.")

    def _on_translate_err(self, msg):
        self.btn_gemini.state(["!disabled"])
        self._set_status(f"❌ {msg}", ok=False)
        messagebox.showerror("Lỗi Gemini", msg)

    # ================== Nạp lại file ==================
    def do_reload(self):
        f = filedialog.askopenfilename(
            title="Chọn Markdown đã sửa",
            filetypes=[("Markdown", "*.md"), ("All files", "*.*")])
        if not f:
            return
        try:
            items = load_markdown(f)
            self._items = items
            self._fill_tree(items)
            self._set_status(
                f"🔄 Đã nạp {len(items)} mục từ {os.path.basename(f)}", ok=True)
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    # ================== Ghi PDF mới ==================
    def do_write_pdf(self):
        if not self.pdf_path.get():
            messagebox.showwarning("Thiếu thông tin", "Chưa chọn PDF gốc.")
            return
        items = self._items
        if not items:
            messagebox.showwarning("Trống", "Không có mục lục để ghi.")
            return

        base_dir = os.path.dirname(self.pdf_path.get())
        base_name = os.path.splitext(os.path.basename(self.pdf_path.get()))[0]
        out = filedialog.asksaveasfilename(
            title="Lưu PDF mới",
            initialdir=base_dir, initialfile=base_name + "_vi.pdf",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")])
        if not out:
            return

        try:
            toc = [TocItem(level=i.level, title=i.title, page=i.page)
                   for i in items]
            n = write_pdf_with_toc(self.pdf_path.get(), toc, out)
            self._set_status(
                f"✅ Đã ghi {n} mục → {os.path.basename(out)}", ok=True)
            if messagebox.askyesno("Xong",
                    f"Đã tạo PDF mới:\n{out}\n\nMở file ngay?"):
                try:
                    os.startfile(out)
                except Exception:
                    pass
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    # ================== Status ==================
    def _set_status(self, msg, ok=True):
        self.status.config(text=msg,
                           foreground="#0a7" if ok else "#c00")


def run():
    App().mainloop()