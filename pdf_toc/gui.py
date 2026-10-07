"""Giao diện Tkinter cho PDF TOC Translator."""

import json
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from . import config as cfg_mod
from .core import read_outline, write_pdf_with_toc, pdf_page_count, TocItem
from .filter import get_all_levels
from .md_io import (export_markdown, load_markdown,
                    export_titles_json, merge_translated_list)
from .gemini import (translate_filtered, GeminiError,
                     get_model_limits, auto_batch_size,
                     DEFAULT_BATCH_SIZE, MIN_BATCH_SIZE, MAX_BATCH_SIZE)


MODELS = ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.8-flash"]
BATCH_SUGGESTIONS = ["50", "100", "150", "200", "300", "500", "1000"]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF TOC Translator")
        self.geometry("980x680")
        self.minsize(800, 560)

        self.pdf_path = tk.StringVar()
        self.api_key_var = tk.StringVar()
        self.model_var = tk.StringVar()
        self.batch_var = tk.StringVar(value=str(DEFAULT_BATCH_SIZE))
        self.show_key = tk.BooleanVar(value=False)
        self.page_count = 0
        self._items = []            # list[TocItem] hiện tại
        self.level_vars = {}        # {level: tk.BooleanVar}

        self._build_ui()
        self._load_saved_config()

    # ================== UI ==================
    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}

        # ---------- Vùng 0: API key ----------
        f0 = ttk.LabelFrame(self, text=" Gemini API Key ", padding=10)
        f0.pack(fill="x", **pad)

        # Dòng 1: API Key
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

        # Dòng 2: Model + Batch
        row2 = ttk.Frame(f0); row2.pack(fill="x", pady=(6, 0))
        ttk.Label(row2, text="Model:", width=10).pack(side="left")
        self.model_combo = ttk.Combobox(
            row2, textvariable=self.model_var,
            values=MODELS, width=32
        )
        self.model_combo.pack(side="left", padx=(0, 6))

        ttk.Label(row2, text="Batch:").pack(side="left")
        self.batch_combo = ttk.Combobox(
            row2, textvariable=self.batch_var,
            values=BATCH_SUGGESTIONS, width=8
        )
        self.batch_combo.pack(side="left", padx=(4, 4))
        ttk.Label(row2, text="mục/lần",
                  foreground="#888").pack(side="left", padx=(0, 6))
        ttk.Button(row2, text="⚙️ Tự động", width=12,
                   command=self.auto_fill_batch).pack(side="left")

        # Dòng 3: chọn level
        row3 = ttk.Frame(f0); row3.pack(fill="x", pady=(6, 0))
        ttk.Label(row3, text="Dịch level:", width=10).pack(side="left")
        self.level_frame = ttk.Frame(row3)
        self.level_frame.pack(side="left", fill="x", expand=True)
        ttk.Label(row3,
                  text="(bỏ tick level nào để giữ nguyên tiếng Anh)",
                  foreground="#888").pack(side="left", padx=(6, 0))

        # Dòng 4: status
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

        # Batch size
        bs = cfg.get("batch_size", DEFAULT_BATCH_SIZE)
        self.batch_var.set(str(bs))

        self._refresh_key_status()
        # Level checkbox sẽ được tạo khi mở PDF

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

        # Clamp batch size
        try:
            bs = int(self.batch_var.get())
        except ValueError:
            bs = DEFAULT_BATCH_SIZE
        bs = max(MIN_BATCH_SIZE, min(bs, MAX_BATCH_SIZE))
        self.batch_var.set(str(bs))

        # Level được chọn
        selected_levels = sorted(
            lv for lv, var in self.level_vars.items() if var.get()
        )

        # Lưu config
        cfg = cfg_mod.load_config()
        cfg["gemini_api_key"] = key
        cfg["model"] = model
        cfg["batch_size"] = bs
        if selected_levels:
            cfg["selected_levels"] = selected_levels

        from datetime import datetime
        cfg["last_saved"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cfg_mod.save_config(cfg)

        self._refresh_key_status()
        self._set_status(
            f"💾 Đã lưu · Model: {model} · Batch: {bs} · "
            f"Dịch level: {selected_levels or 'tất cả'}",
            ok=True
        )

    def delete_key(self):
        """Xóa API key khỏi config."""
        if not messagebox.askyesno(
            "Xác nhận xóa",
            "Bạn có chắc muốn xóa API key?\n\n"
            "Sau khi xóa, phải nhập lại key mới để dùng Gemini."
        ):
            return

        cfg = cfg_mod.load_config()
        cfg["gemini_api_key"] = ""
        cfg["last_saved"] = ""
        cfg_mod.save_config(cfg)

        self.api_key_var.set("")
        self._refresh_key_status()
        self._set_status("🗑️ Đã xóa API key.", ok=True)

    # ================== Batch tự động ==================
    def auto_fill_batch(self):
        """Gọi API để lấy output limit → tự tính batch size."""
        key = self.api_key_var.get().strip()
        model = self.model_var.get().strip()

        if not key:
            messagebox.showwarning("Thiếu key",
                                   "Cần nhập API key trước.")
            return
        if not model:
            messagebox.showwarning("Thiếu model",
                                   "Cần nhập model trước.")
            return

        self._set_status("⏳ Đang kiểm tra giới hạn model...", ok=False)

        def worker():
            try:
                limits = get_model_limits(key, model)
                output_limit = limits.get("output_token_limit")
                batch = auto_batch_size(output_limit)

                if output_limit:
                    msg = (f"✅ Model '{model}' có output limit "
                           f"{output_limit:,} token → Batch đề xuất: {batch}")
                else:
                    msg = (f"⚠️ Không lấy được giới hạn model. "
                           f"Dùng mặc định: {batch}")

                self.after(0, lambda b=batch, m=msg: self._on_auto_batch(b, m))
            except Exception as e:
                err = str(e)
                self.after(0, lambda m=err: self._on_auto_batch_err(m))

        threading.Thread(target=worker, daemon=True).start()

    def _on_auto_batch(self, batch, msg):
        self.batch_var.set(str(batch))
        self._set_status(msg, ok=True)

    def _on_auto_batch_err(self, msg):
        self._set_status(f"❌ {msg}", ok=False)

    # ================== Checkbox level ==================
    def _rebuild_level_checkboxes(self):
        """Tạo lại checkbox level dựa trên self._items."""
        for w in self.level_frame.winfo_children():
            w.destroy()
        self.level_vars.clear()

        if not self._items:
            ttk.Label(self.level_frame,
                      text="(chưa có mục lục)",
                      foreground="#888").pack(side="left")
            return

        levels = get_all_levels(self._items)
        saved = cfg_mod.load_config().get("selected_levels", None)

        for lv in levels:
            # Nếu có config lưu → dùng; ngược lại mặc định tick
            if saved is None:
                initial = True
            else:
                initial = lv in saved

            var = tk.BooleanVar(value=initial)
            self.level_vars[lv] = var
            ttk.Checkbutton(
                self.level_frame,
                text=str(lv),
                variable=var
            ).pack(side="left", padx=(4, 0))

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
        self._rebuild_level_checkboxes()
        self._set_status(
            f"📖 Đã đọc {len(self._items)} mục · "
            f"PDF có {self.page_count} trang.",
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
            self._set_status(
                f"✅ Đã xuất {n} mục → {os.path.basename(out)}", ok=True)
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

        # Lấy level được chọn
        selected_levels = set(
            lv for lv, var in self.level_vars.items() if var.get()
        )
        if not selected_levels:
            messagebox.showwarning(
                "Chưa chọn level",
                "Bạn cần tick ít nhất 1 level để dịch.\n"
                "Nếu muốn dịch tất cả, tick hết các level.")
            return

        # Lấy batch size (clamp)
        try:
            bs = int(self.batch_var.get())
        except ValueError:
            bs = DEFAULT_BATCH_SIZE
        bs = max(MIN_BATCH_SIZE, min(bs, MAX_BATCH_SIZE))

        # Chuẩn bị file .md gốc
        base = os.path.splitext(self.pdf_path.get())[0]
        md_path = base + ".md"
        vi_md = base + "_vi.md"

        if not os.path.exists(md_path):
            try:
                items = read_outline(self.pdf_path.get())
                export_markdown(self.pdf_path.get(), items, md_path, self.page_count)
            except Exception as e:
                messagebox.showerror("Lỗi", str(e))
                return

        current_items = self._items
        if not current_items:
            messagebox.showwarning("Trống", "Chưa có mục lục để dịch.")
            return

        # Đếm số mục cần dịch
        n_to_translate = sum(
            1 for it in current_items if it.level in selected_levels
        )
        n_batches_est = (n_to_translate + bs - 1) // bs

        # Chạy dịch trong thread riêng
        self.btn_gemini.state(["disabled"])
        self._set_status(
            f"⏳ Đang dịch {n_to_translate} mục "
            f"(~{n_batches_est} batch, batch size {bs})…",
            ok=False
        )

        def on_progress(batch_num, n_batches, start, count, total):
            self.after(0, lambda: self._set_status(
                f"⏳ Batch {batch_num}/{n_batches} "
                f"({start + 1}–{start + count}/{total} mục)…",
                ok=False))

        def worker():
            try:
                result = translate_filtered(
                    api_key=key,
                    model_name=self.model_var.get(),
                    items=current_items,
                    selected_levels=selected_levels,
                    temperature=cfg_mod.get_temperature(),
                    batch_size=bs,
                    progress_callback=on_progress,
                )

                # Ghi kết quả vào file _vi.md
                merge_translated_list(md_path, result, vi_md)

                self.after(0, lambda: self._on_translate_done(
                    vi_md, len(current_items)))

            except GeminiError as ge:
                msg = str(ge)
                self.after(0, lambda m=msg: self._on_translate_err(m))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda m=msg: self._on_translate_err(m))

        threading.Thread(target=worker, daemon=True).start()

    def _on_translate_done(self, vi_md_path, n):
        self.btn_gemini.state(["!disabled"])
        try:
            items = load_markdown(vi_md_path)
            self._fill_tree(items)
            self._items = items
            self._rebuild_level_checkboxes()
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
            self._rebuild_level_checkboxes()
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