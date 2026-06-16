import os
import json
import tkinter as tk
from tkinter import ttk, scrolledtext

# ── colour system ──────────────────────────────────
C = {
    "bg":        "#0f1119",
    "sidebar":   "#0a0c14",
    "card":      "#161822",
    "card_hover":"#1c1f2e",
    "border":    "#222639",
    "fg":        "#c8ccd4",
    "fg_dim":    "#6b7080",
    "accent":    "#7aa2f7",
    "accent2":   "#9ece6a",
    "danger":    "#f7768e",
    "warning":   "#e0af68",
    "info":      "#7dcfff",
    "green":     "#73daca",
    "red_bar":   "#f7768e",
    "green_bar": "#73daca",
    "blue_bar":  "#7aa2f7",
    "yellow_bar":"#e0af68",
    "white":     "#1a1b26",
    "row_alt":   "#131520",
    "row_norm":  "#161822",
    "btn_text":  "#0f1119",
    "scroll_track":"#0a0c14",
    "scroll_thumb":"#2a2d3a",
    "progress_track":"#1e2130",
}
FONT = "Microsoft YaHei UI"


def _rgba(hex_color, alpha=100):
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return "#{:02x}{:02x}{:02x}".format(
        r + (255 - r) * (100 - alpha) // 100,
        g + (255 - g) * (100 - alpha) // 100,
        b + (255 - b) * (100 - alpha) // 100,
    )


def _setup_ttk_style(root):
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    style.configure("TProgressbar", background=C["accent"], troughcolor=C["progress_track"],
                    borderwidth=0, thickness=8)
    style.configure("Treeview", background=C["card"], foreground=C["fg"],
                    fieldbackground=C["card"], borderwidth=0, rowheight=30)
    style.configure("Treeview.Heading", background=C["sidebar"], foreground=C["fg_dim"],
                    font=(FONT, 9, "bold"), borderwidth=0, padding=(8, 6))
    style.map("Treeview.Heading", background=[("active", C["border"])])
    style.map("Treeview", background=[("selected", _rgba(C["accent"], 80))],
              foreground=[("selected", C["fg"])])


class _PillButton(tk.Canvas):
    def __init__(self, parent, text, command, bg=None, fg=None, font_size=10, **kw):
        self._text = text
        self._cmd = command
        self._bg = bg or C["accent"]
        self._fg = fg or C["btn_text"]
        self._fs = font_size
        self._hover = False
        w = kw.pop("width", 120)
        h = kw.pop("height", 36)
        tk.Canvas.__init__(self, parent, width=w, height=h,
                           bg=C["bg"], highlightthickness=0, cursor="hand2", **kw)
        self._draw()
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Button-1>", lambda e: self._cmd())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, e=None):
        self._hover = True
        self._draw()

    def _on_leave(self, e=None):
        self._hover = False
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 8 or h < 8:
            return
        fill = _rgba(self._bg, 80) if self._hover else self._bg
        r = h // 2
        d = r * 2
        self.create_arc(0, 0, d, d, start=90, extent=180, fill=fill, outline="")
        self.create_arc(w - d, 0, w, d, start=270, extent=180, fill=fill, outline="")
        self.create_rectangle(r, 0, w - r, h, fill=fill, outline="")
        self.create_text(w / 2, h / 2 - 1, text=self._text, fill=self._fg,
                         font=(FONT, self._fs, "bold"), anchor="center")


class _StatusDot(tk.Canvas):
    def __init__(self, parent, color, size=8):
        tk.Canvas.__init__(self, parent, width=size, height=size,
                           bg=C["sidebar"], highlightthickness=0)
        d = size - 2
        self.create_oval(1, 1, d, d, fill=color, outline="")
        self.create_oval(1, 1, d, d, fill=_rgba(color, 40), outline="")


# ══════════════════════════════════════════════════════
class DigitalLabGUI:
    def __init__(self, root):
        self.root = root
        root.title("Digital Lab")
        root.geometry("1120x720")
        root.minsize(860, 520)
        root.configure(bg=C["bg"])

        _setup_ttk_style(root)

        self._active = "home"
        self._menu = {}
        self._header_vars = {}

        self._build()

        self._switch("home")
        self._show_home()
        self._tick()

    # ── layout ──────────────────────────────────────
    def _build(self):
        # sidebar ──
        self.sbar = tk.Frame(self.root, bg=C["sidebar"], width=210)
        self.sbar.pack(side=tk.LEFT, fill=tk.Y)
        self.sbar.pack_propagate(False)

        # logo
        logo = tk.Frame(self.sbar, bg=C["sidebar"])
        logo.pack(fill=tk.X, pady=(14, 8), padx=14)
        tk.Label(logo, text="Digital", bg=C["sidebar"], fg=C["fg"],
                 font=(FONT, 15, "bold")).pack(anchor="w")
        tk.Label(logo, text="Lab Console", bg=C["sidebar"], fg=C["fg_dim"],
                 font=(FONT, 9)).pack(anchor="w")

        # divider
        tk.Frame(self.sbar, bg=C["border"], height=1).pack(fill=tk.X, padx=14, pady=(0, 6))

        # menu sections
        ICONS = {
            "init": "\u2699", "status": "\u2139", "config": "\u2692",
            "home": "\u25CB", "processes": "\u25A3", "alerts": "\u26A0",
            "alert-test": "\u25B7", "daemon": "\u27F3", "compare": "\u29BF",
            "launcher": "\u27A5", "report": "\u2630", "snapshot": "\u25CE",
            "experiment": "\u25C9", "analyze": "\u235F", "ai": "\u2726",
        }

        sections = [
            ("\u2501 基础操作", [
                ("init", "初始化系统"), ("status", "系统状态"), ("config", "配置管理"),
            ]),
            ("\u2501 系统监控", [
                ("home", "仪表盘"), ("processes", "进程 Top 15"),
                ("alerts", "告警记录"), ("alert-test", "告警测试"),
                ("daemon", "守护进程"), ("compare", "历史对比"),
            ]),
            ("\u2501 其他工具", [
                ("launcher", "快捷启动"), ("report", "生成报告"),
                ("snapshot", "快照管理"),
            ]),
            ("\u2501 AI & 实验", [
                ("experiment", "实验管理"), ("analyze", "数据分析"), ("ai", "AI 助手"),
            ]),
        ]

        callbacks = {
            "init": self._show_init, "status": self._show_status,
            "config": self._show_config, "home": self._show_home,
            "processes": self._show_processes, "alerts": self._show_alerts,
            "alert-test": self._show_alert_test, "daemon": self._show_daemon,
            "compare": self._show_compare, "launcher": self._show_launcher,
            "report": self._show_report, "snapshot": self._show_snapshot,
            "experiment": self._show_todo, "analyze": self._show_todo, "ai": self._show_todo,
        }

        for sec_title, items in sections:
            tk.Label(self.sbar, text=sec_title, bg=C["sidebar"], fg=C["fg_dim"],
                     font=(FONT, 8), anchor="w", padx=16).pack(fill=tk.X, pady=(10, 2))

            for pid, label in items:
                row = tk.Frame(self.sbar, bg=C["sidebar"], cursor="hand2")
                row.pack(fill=tk.X, padx=(8, 8))

                indicator = tk.Frame(row, bg=C["sidebar"], width=3)
                indicator.pack(side=tk.LEFT, fill=tk.Y)

                icon_str = ICONS.get(pid, "\u2022")
                icon_lbl = tk.Label(row, text=icon_str, bg=C["sidebar"], fg=C["fg_dim"],
                                    font=(FONT, 10), padx=8)
                icon_lbl.pack(side=tk.LEFT)

                lbl = tk.Label(row, text=label, bg=C["sidebar"], fg=C["fg"],
                               font=(FONT, 10), anchor="w")
                lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

                cb = callbacks[pid]
                row.bind("<Button-1>", lambda e, p=pid, c=cb: self._nav(p, c))
                lbl.bind("<Button-1>", lambda e, p=pid, c=cb: self._nav(p, c))
                icon_lbl.bind("<Button-1>", lambda e, p=pid, c=cb: self._nav(p, c))

                def _enter(e, r=row, i=indicator, il=icon_lbl, ll=lbl):
                    if r not in self._menu.values():
                        r.configure(bg=C["card"])
                        i.configure(bg=C["card"])
                        il.configure(bg=C["card"])
                        ll.configure(bg=C["card"])

                def _leave(e, r=row, i=indicator, il=icon_lbl, ll=lbl, p=pid):
                    if p == self._active:
                        return
                    r.configure(bg=C["sidebar"])
                    i.configure(bg=C["sidebar"])
                    il.configure(bg=C["sidebar"])
                    ll.configure(bg=C["sidebar"])

                for w in (row, lbl, icon_lbl):
                    w.bind("<Enter>", _enter)
                    w.bind("<Leave>", _leave)

                self._menu[pid] = (row, indicator, icon_lbl, lbl)

        # bottom status
        tk.Frame(self.sbar, bg=C["border"], height=1).pack(fill=tk.X, padx=14, pady=(12, 0))
        status_frame = tk.Frame(self.sbar, bg=C["sidebar"], padx=14, pady=8)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        _StatusDot(status_frame, C["green"], 8).pack(side=tk.LEFT, padx=(0, 6))
        self._sbar_status = tk.Label(status_frame, text="就绪", bg=C["sidebar"],
                                      fg=C["fg_dim"], font=(FONT, 8), anchor="w")
        self._sbar_status.pack(side=tk.LEFT)

        # copyright
        cr_frame = tk.Frame(self.sbar, bg=C["sidebar"], padx=14, pady=(0, 4))
        cr_frame.pack(fill=tk.X, side=tk.BOTTOM)
        cr_text = "\u00A9 2026 赵展铖 | 赞助: Ave Mujica \u2014 Oblivionis"
        tk.Label(cr_frame, text=cr_text, bg=C["sidebar"], fg=C["fg_dim"],
                 font=(FONT, 7), anchor="w").pack(fill=tk.X)

        # ── content area ──
        self.body = tk.Frame(self.root, bg=C["bg"])
        self.body.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # header bar
        hdr = tk.Frame(self.body, bg=C["bg"])
        hdr.pack(fill=tk.X, padx=22, pady=(16, 0))
        self._hdr_title = tk.Label(hdr, text="", bg=C["bg"], fg=C["fg"],
                                    font=(FONT, 20, "bold"), anchor="w")
        self._hdr_title.pack(side=tk.LEFT)
        self._hdr_sub = tk.Label(hdr, text="", bg=C["bg"], fg=C["fg_dim"],
                                  font=(FONT, 9), anchor="w")
        self._hdr_sub.pack(side=tk.LEFT, padx=(10, 0))

        # scrollable pane
        self.canvas = tk.Canvas(self.body, bg=C["bg"], highlightthickness=0)
        self.scrollbar = tk.Canvas(self.body, width=5, bg=C["bg"], highlightthickness=0)
        self.scrollbar.create_line(2, 0, 2, 1000, fill=C["scroll_track"], width=3)

        self.pane = tk.Frame(self.canvas, bg=C["bg"])
        self.pane.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.pane, anchor="nw", tags="inner")

        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig("inner", width=e.width))
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(22, 8), pady=(6, 16))
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=(6, 16))

    def _on_scroll(self, *args):
        self.canvas.yview(*args)
        self._draw_scrollbar()

    def _draw_scrollbar(self):
        y0, y1 = self.canvas.yview()
        h = self.scrollbar.winfo_height() - 10
        if h <= 0:
            return
        self.scrollbar.delete("thumb")
        self.scrollbar.create_rectangle(0, int(y0 * h), 5, int(y1 * h),
                                         fill=C["scroll_thumb"], outline="", tags="thumb")

    def _nav(self, panel_id, callback):
        self._switch(panel_id)
        callback()

    def _switch(self, panel_id):
        self._active = panel_id
        for pid, (row, ind, icn, lbl) in self._menu.items():
            if pid == panel_id:
                row.configure(bg=C["card"])
                ind.configure(bg=C["accent"], width=3)
                icn.configure(bg=C["card"], fg=C["accent"])
                lbl.configure(bg=C["card"], fg=C["fg"])
            else:
                row.configure(bg=C["sidebar"])
                ind.configure(bg=C["sidebar"])
                icn.configure(bg=C["sidebar"], fg=C["fg_dim"])
                lbl.configure(bg=C["sidebar"], fg=C["fg"])
        self._clear_pane()

    def _clear_pane(self):
        for w in self.pane.winfo_children():
            w.destroy()

    def _set_header(self, title, sub=""):
        self._hdr_title.configure(text=title)
        self._hdr_sub.configure(text=sub)

    # ── components ──────────────────────────────────
    def _stat_card(self, icon, title, val, max_val=100, color=C["accent"], sub="", bar_color=None):
        bar_color = bar_color or color
        outer = tk.Frame(self.pane, bg=C["card"], padx=0, pady=0,
                         highlightbackground=C["border"], highlightthickness=1)
        inner = tk.Frame(outer, bg=C["card"], padx=16, pady=14)
        inner.pack(fill=tk.BOTH, expand=True)

        hdr = tk.Frame(inner, bg=C["card"])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text=icon, bg=C["card"], fg=color, font=(FONT, 13)).pack(side=tk.LEFT)
        tk.Label(hdr, text=title, bg=C["card"], fg=C["fg_dim"],
                 font=(FONT, 9, "bold")).pack(side=tk.LEFT, padx=(6, 0))

        val_lbl = tk.Label(inner, text=val, bg=C["card"], fg=color,
                            font=(FONT, 30, "bold"), anchor="w")
        val_lbl.pack(anchor="w", pady=(10, 0))

        if sub:
            tk.Label(inner, text=sub, bg=C["card"], fg=C["fg_dim"],
                     font=(FONT, 8)).pack(anchor="w")

        pct = min(float(val.replace("%", "").replace("-", "0")), max_val)
        bar = ttk.Progressbar(inner, style="TProgressbar", length=180, value=pct)
        bar.pack(fill=tk.X, pady=(8, 0))
        return outer, val_lbl, bar

    def _msg(self, text, color=None):
        fg = color or C["fg"]
        frm = tk.Frame(self.pane, bg=C["card"], padx=16, pady=12,
                       highlightbackground=C["border"], highlightthickness=1)
        tk.Label(frm, text=text, bg=C["card"], fg=fg, font=("Consolas", 10),
                 anchor="w", justify=tk.LEFT).pack(anchor="w", fill=tk.X)
        frm.pack(fill=tk.X, pady=(0, 8))

    def _pill_btn(self, text, cmd, bg=None, fg=None, fs=10):
        b = _PillButton(self.pane, text, cmd, bg=bg or C["accent"],
                         fg=fg or C["btn_text"], font_size=fs, width=120, height=34)
        b.pack(side=tk.LEFT, padx=3)
        return b

    def _bytes(self, n):
        if not n:
            return "0 B"
        for u in ["B", "KB", "MB", "GB", "TB"]:
            if abs(n) < 1024:
                return "{:.1f} {}".format(n, u)
            n /= 1024
        return "{:.1f} PB".format(n)

    # ── tick ────────────────────────────────────────
    def _tick(self):
        if self._active == "home":
            self._tick_home()
        self.root.after(3000, self._tick)

    # ════════════════════════════════════════════════
    #  Dashboard
    # ════════════════════════════════════════════════
    def _show_home(self):
        self._set_header("仪表盘", "系统资源实时监控")
        self._clear_pane()

        from core.monitor import get_cpu_info, get_memory_info, get_disk_info

        cards = tk.Frame(self.pane, bg=C["bg"])
        cards.pack(fill=tk.X, pady=(8, 14))

        cpu = get_cpu_info()
        c1, self._vl_cpu, self._pb_cpu = self._stat_card(
            "\u2395", "CPU 使用率", "--", color=C["danger"], bar_color=C["red_bar"],
            sub="{} 核 / {} GHz".format(
                cpu.get("physical_cores", 0),
                cpu.get("freq_current", 0) / 1000 if cpu and cpu.get("freq_current") else 0))
        c1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        mem = get_memory_info()
        c2, self._vl_mem, self._pb_mem = self._stat_card(
            "\u2B1B", "内存使用率", "--", color=C["green"], bar_color=C["green_bar"],
            sub="{} / {}".format(self._bytes(mem.get("used", 0)),
                                 self._bytes(mem.get("total", 0))) if mem else "")
        c2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)

        disk = get_disk_info()
        c3, self._vl_disk, self._pb_disk = self._stat_card(
            "\u2B19", "磁盘 (C:)", "--", color=C["info"], bar_color=C["blue_bar"],
            sub="空闲 {} / {}".format(self._bytes(disk[0].get("free", 0)),
                                       self._bytes(disk[0].get("total", 0))) if disk else "")
        c3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        info_frm = tk.Frame(self.pane, bg=C["card"], padx=18, pady=10,
                            highlightbackground=C["border"], highlightthickness=1)
        tk.Label(info_frm, text="\u27F3  自动刷新 · 每 3 秒", bg=C["card"], fg=C["fg_dim"],
                 font=(FONT, 9)).pack(anchor="w")
        info_frm.pack(fill=tk.X)

        self._tick_home()

    def _tick_home(self):
        if self._active != "home":
            return
        try:
            import psutil
            cv = psutil.cpu_percent(interval=None)
            mv = psutil.virtual_memory().percent
            dv = psutil.disk_usage("C:").percent
            for lbl, bar, v in [
                (self._vl_cpu, self._pb_cpu, cv),
                (self._vl_mem, self._pb_mem, mv),
                (self._vl_disk, self._pb_disk, dv),
            ]:
                lbl.configure(text="{:.1f}%".format(v), fg=self._alert_color(self._active_key(lbl), v))
                bar.configure(value=v)
            self._sbar_status.configure(text="CPU {:.0f}%  |  内存 {:.0f}%  |  磁盘 {:.0f}%".format(cv, mv, dv))
        except Exception:
            pass

    def _active_key(self, lbl):
        if lbl is self._vl_cpu:
            return "cpu"
        if lbl is self._vl_mem:
            return "mem"
        return "disk"

    def _alert_color(self, key, v):
        if key == "cpu":
            return C["danger"] if v > 85 else C["warning"] if v > 60 else C["accent"]
        elif key == "mem":
            return C["danger"] if v > 90 else C["warning"] if v > 70 else C["green"]
        else:
            return C["danger"] if v > 95 else C["warning"] if v > 80 else C["info"]

    # ════════════════════════════════════════════════
    #  Processes
    # ════════════════════════════════════════════════
    def _show_processes(self):
        self._set_header("进程 Top 15", "按 CPU 使用率排序")
        self._clear_pane()
        try:
            from core.monitor import get_top_processes
            procs = get_top_processes(15, "cpu")
        except Exception:
            self._msg("psutil not installed", C["danger"])
            return
        if not procs:
            self._msg("No data", C["fg_dim"])
            return

        tree = self._make_tree(("pid", "name", "cpu", "mem", "rss"),
                                ("PID", "进程名", "CPU%", "内存%", "物理内存"),
                                (60, 260, 80, 80, 120), height=16)

        for i, p in enumerate(procs):
            tree.insert("", "end", values=(p["pid"], p.get("name", ""),
                         "{:.1f}%".format(p["cpu"]), "{:.1f}%".format(p["memory"]),
                         self._bytes(p.get("memory_bytes", 0))),
                         tags=("alt",) if i % 2 else ())

        tree.tag_configure("alt", background=C["row_alt"])
        tree.pack(fill=tk.BOTH, expand=True)

        btn_row = tk.Frame(self.pane, bg=C["bg"])
        btn_row.pack(pady=(10, 0))
        self._pill_btn("刷新", self._show_processes, bg=C["accent"])

    # ════════════════════════════════════════════════
    #  Alerts
    # ════════════════════════════════════════════════
    def _show_alerts(self):
        self._set_header("告警记录", "历史告警日志")
        self._clear_pane()
        try:
            from core.dashboard_server import _read_alerts
            alerts = _read_alerts(100)
        except Exception:
            alerts = []
        if not alerts:
            self._msg("No alert records", C["fg_dim"])
            return

        tree = self._make_tree(("time", "metric", "value", "threshold"),
                                ("时间", "指标", "当前值", "阈值"),
                                (200, 200, 100, 100), height=16)
        for i, a in enumerate(alerts):
            dt = a.get("data", {})
            tree.insert("", "end", values=(a.get("timestamp", ""), a.get("message", ""),
                         "{:.1f}%".format(dt.get("current", 0)),
                         "{}%".format(dt.get("threshold", 0))),
                         tags=("alt",) if i % 2 else ())
        tree.tag_configure("alt", background=C["row_alt"])
        tree.pack(fill=tk.BOTH, expand=True)

    # ════════════════════════════════════════════════
    #  Alert Test
    # ════════════════════════════════════════════════
    def _show_alert_test(self):
        self._set_header("告警测试", "强制触发告警验证")
        self._clear_pane()
        btn_row = tk.Frame(self.pane, bg=C["bg"])
        btn_row.pack(pady=(18, 10))
        self._pill_btn("触发告警", self._do_alert_test, bg=C["danger"], fg=C["btn_text"])
        self._alert_out = tk.Frame(self.pane, bg=C["bg"])
        self._alert_out.pack(fill=tk.BOTH, pady=10)

    def _do_alert_test(self):
        try:
            from core.monitor import collect_and_store, enable_alert_test, check_alerts
            from core.config import get_config
            cfg = get_config()
            enable_alert_test()
            cpu, mem, disk = collect_and_store()
            thresholds = cfg.get_thresholds()
            alerts = check_alerts(cpu or 0, mem or 0, disk or 0, thresholds, 0)
            lines = ["Current: CPU {:.1f}% / Memory {:.1f}% / Disk {:.1f}%".format(cpu or 0, mem or 0, disk or 0)]
            lines.append("Threshold: CPU {}% / Memory {}% / Disk {}%".format(
                thresholds["cpu"], thresholds["memory"], thresholds["disk"]))
            for a in alerts:
                lines.append("[ALERT] {}: {:.1f}% (threshold: {}%)".format(a[0], a[1], a[2]))
            for w in self._alert_out.winfo_children():
                w.destroy()
            self._msg("\n".join(lines), C["warning"])
        except Exception as e:
            self._msg(str(e), C["danger"])

    # ════════════════════════════════════════════════
    #  Daemon
    # ════════════════════════════════════════════════
    def _show_daemon(self):
        self._set_header("守护进程", "后台监控服务管理")
        self._clear_pane()
        btn_row = tk.Frame(self.pane, bg=C["bg"])
        btn_row.pack(pady=(18, 10))
        self._pill_btn("启动守护", self._do_daemon_start, bg=C["green"], fg=C["btn_text"])
        self._pill_btn("停止守护", self._do_daemon_stop, bg=C["danger"], fg=C["btn_text"])
        self._pill_btn("查看状态", self._do_daemon_status, bg=C["accent"], fg=C["btn_text"])
        self._daemon_out = tk.Frame(self.pane, bg=C["bg"])
        self._daemon_out.pack(fill=tk.BOTH, pady=10)

    def _daemon_cfg(self):
        from core.config import get_config
        cfg = get_config()
        return cfg.monitor_pid_path, str(cfg.monitor_interval), os.path.join(cfg.lab_root, "main.py")

    def _daemon_clear(self):
        for w in self._daemon_out.winfo_children():
            w.destroy()

    def _do_daemon_start(self):
        try:
            from core.daemon import start_daemon
            pid_path, interval, script = self._daemon_cfg()
            msg = start_daemon(pid_path, script, interval)
            self._daemon_clear()
            self._msg(msg, C["green"] if "[OK]" in msg else C["warning"])
        except Exception as e:
            self._msg(str(e), C["danger"])

    def _do_daemon_stop(self):
        try:
            from core.daemon import stop_daemon
            pid_path, _, _ = self._daemon_cfg()
            msg = stop_daemon(pid_path)
            self._daemon_clear()
            self._msg(msg, C["info"] if "[OK]" in msg else C["warning"])
        except Exception as e:
            self._msg(str(e), C["danger"])

    def _do_daemon_status(self):
        try:
            from core.daemon import daemon_status
            pid_path, _, _ = self._daemon_cfg()
            s = daemon_status(pid_path)
            self._daemon_clear()
            if s.get("running"):
                self._msg("Running\nPID: {} | Runtime: {} | Collections: {} | First: {} | Last: {}".format(
                    s["pid"], s.get("runtime", ""), s.get("collections", 0),
                    s.get("first_snapshot", ""), s.get("last_snapshot", "")), C["green"])
            else:
                self._msg("Stopped ({})".format(s.get("reason", "")), C["fg_dim"])
        except Exception as e:
            self._msg(str(e), C["danger"])

    # ════════════════════════════════════════════════
    #  Compare
    # ════════════════════════════════════════════════
    def _show_compare(self):
        self._set_header("历史对比", "当前值 vs 历史数据")
        self._clear_pane()
        btn_row = tk.Frame(self.pane, bg=C["bg"])
        btn_row.pack(pady=(18, 10))
        for rng, label, bg in [("1h", "1 小时", C["green"]), ("24h", "24 小时", C["accent"]), ("7d", "7 天", C["info"])]:
            self._pill_btn(label, lambda r=rng: self._do_compare(r), bg=bg, fg=C["btn_text"])
        self._cmp_out = tk.Frame(self.pane, bg=C["bg"])
        self._cmp_out.pack(fill=tk.BOTH, pady=10)

    def _do_compare(self, rng):
        from core.monitor import query_history
        seconds = {"1h": 3600, "24h": 86400, "7d": 604800}.get(rng, 86400)
        stats = query_history(seconds)
        for w in self._cmp_out.winfo_children():
            w.destroy()
        if not stats:
            self._msg("Not enough data", C["fg_dim"])
            return
        tree = self._make_tree(("metric", "avg", "max", "min", "count"),
                                ("指标", "均值", "峰值", "最低", "数据量"),
                                (100, 100, 100, 100, 100), height=5)
        for key, label in [("cpu", "CPU"), ("memory", "内存"), ("disk", "磁盘")]:
            s = stats.get(key, {})
            tree.insert("", "end", values=(label,
                     "{:.1f}%".format(s.get("avg", 0)), "{:.1f}%".format(s.get("max", 0)),
                     "{:.1f}%".format(s.get("min", 0)), "{} rows".format(s.get("count", 0))))
        tree.pack(fill=tk.X)

    # ════════════════════════════════════════════════
    #  Init
    # ════════════════════════════════════════════════
    def _show_init(self):
        self._set_header("初始化系统", "创建目录结构")
        self._clear_pane()
        self._msg("Will create:\n  tools / logs / experiments / notes / archive / interface", C["fg_dim"])
        tk.Frame(self.pane, bg=C["bg"], height=8).pack()
        self._pill_btn("执行初始化", self._do_init, bg=C["green"], fg=C["btn_text"])
        self._init_out = tk.Frame(self.pane, bg=C["bg"])
        self._init_out.pack(fill=tk.BOTH, pady=(10, 0))

    def _do_init(self):
        try:
            from core.config import get_config
            cfg = get_config()
            cfg.ensure_dirs()
            for w in self._init_out.winfo_children():
                w.destroy()
            self._msg("[OK] Directories created", C["green"])
        except Exception as e:
            self._msg(str(e), C["danger"])

    # ════════════════════════════════════════════════
    #  Status
    # ════════════════════════════════════════════════
    def _show_status(self):
        self._set_header("系统状态", "运行环境信息")
        self._clear_pane()
        from core.config import get_config
        cfg = get_config()
        lines = ["Python: {}".format(cfg.python_version),
                 "System: {}".format(cfg.platform_info), ""]
        for d in ["tools", "logs", "experiments", "notes", "archive", "interface"]:
            p = getattr(cfg, d + "_dir", "")
            ok = p and os.path.isdir(p)
            lines.append("  {}  {}".format(d, "[OK]" if ok else "[MISSING]"))
        self._msg("\n".join(lines), C["green"])

    # ════════════════════════════════════════════════
    #  Config
    # ════════════════════════════════════════════════
    def _show_config(self):
        self._set_header("配置管理", "config.json 查看/保存")
        self._clear_pane()
        from core.config import get_config
        cfg = get_config()
        data = {k: v for k, v in cfg.__dict__.items() if not k.startswith("_")}
        data.pop("config_file", None)

        txt = scrolledtext.ScrolledText(self.pane, bg=C["card"], fg=C["fg"],
                                         font=("Consolas", 10), height=18, border=0,
                                         insertbackground=C["fg"], padx=12, pady=10,
                                         highlightbackground=C["border"], highlightthickness=1)
        txt.insert("1.0", json.dumps(data, indent=2, ensure_ascii=False))
        txt.configure(state="disabled")
        txt.pack(fill=tk.BOTH, expand=True, pady=(10, 8))

        btn_row = tk.Frame(self.pane, bg=C["bg"])
        btn_row.pack(pady=(0, 6))
        self._pill_btn("保存配置", lambda: cfg.save() or self._msg("Saved", C["green"]),
                        bg=C["accent"], fg=C["btn_text"])

    # ════════════════════════════════════════════════
    #  Launcher
    # ════════════════════════════════════════════════
    def _show_launcher(self):
        self._set_header("快捷启动", "管理 & 启动常用程序")
        self._clear_pane()
        try:
            from core.launcher import list_shortcuts
            sc = list_shortcuts()
        except Exception:
            sc = []
        if not sc:
            self._msg("No shortcuts yet", C["fg_dim"])
        else:
            tree = self._make_tree(("no", "name", "path"),
                                    ("#", "名称", "路径"),
                                    (40, 140, 340), height=8)
            for i, s in enumerate(sc, 1):
                tree.insert("", "end", values=(i, s["name"], s["path"]),
                            tags=("alt",) if i % 2 else ())
            tree.tag_configure("alt", background=C["row_alt"])
            tree.pack(fill=tk.X)
            tree.bind("<Double-1>", lambda e: self._do_launch(tree))

        add_f = tk.Frame(self.pane, bg=C["bg"])
        add_f.pack(fill=tk.X, pady=(12, 0))
        self._ln_name = tk.Entry(add_f, bg=C["card"], fg=C["fg"], font=(FONT, 10),
                                  insertbackground=C["fg"], relief="flat", width=14,
                                  highlightbackground=C["border"], highlightthickness=1)
        self._ln_name.pack(side=tk.LEFT, padx=(0, 6))
        self._ln_path = tk.Entry(add_f, bg=C["card"], fg=C["fg"], font=(FONT, 10),
                                  insertbackground=C["fg"], relief="flat", width=28,
                                  highlightbackground=C["border"], highlightthickness=1)
        self._ln_path.pack(side=tk.LEFT, padx=(0, 6))
        self._pill_btn("添加", self._do_add_launch, bg=C["green"], fg=C["btn_text"])
        self._ln_out = tk.Frame(self.pane, bg=C["bg"])
        self._ln_out.pack(fill=tk.X, pady=(6, 0))

    def _do_launch(self, tree):
        sel = tree.selection()
        if not sel:
            return
        idx = int(tree.item(sel[0])["values"][0])
        try:
            from core.launcher import launch
            msg = launch(idx)
            for w in self._ln_out.winfo_children():
                w.destroy()
            self._msg(msg, C["green"] if "[OK]" in msg else C["danger"])
        except Exception as e:
            self._msg(str(e), C["danger"])

    def _do_add_launch(self):
        n = self._ln_name.get().strip()
        p = self._ln_path.get().strip()
        if not n or not p:
            return
        try:
            from core.launcher import add_shortcut
            msg = add_shortcut(n, p)
            for w in self._ln_out.winfo_children():
                w.destroy()
            self._msg(msg, C["green"] if "[OK]" in msg else C["warning"])
            self._ln_name.delete(0, tk.END)
            self._ln_path.delete(0, tk.END)
            self._show_launcher()
        except Exception as e:
            self._msg(str(e), C["danger"])

    # ════════════════════════════════════════════════
    #  Report
    # ════════════════════════════════════════════════
    def _show_report(self):
        self._set_header("生成报告", "统计汇总 & 导出")
        self._clear_pane()
        btn_row = tk.Frame(self.pane, bg=C["bg"])
        btn_row.pack(pady=(18, 10))
        for rng, label, bg in [("1h", "1 小时", C["green"]), ("6h", "6 小时", C["accent"]),
                                 ("24h", "24 小时", C["warning"]), ("7d", "7 天", C["info"])]:
            self._pill_btn(label, lambda r=rng: self._do_report(r), bg=bg, fg=C["btn_text"])
        self._rp_out = tk.Frame(self.pane, bg=C["bg"])
        self._rp_out.pack(fill=tk.BOTH, pady=10)

    def _do_report(self, rng):
        seconds = {"1h": 3600, "6h": 21600, "24h": 86400, "7d": 604800}.get(rng, 86400)
        for w in self._rp_out.winfo_children():
            w.destroy()
        self._msg("Generating...", C["fg_dim"])
        try:
            from core.reporter import generate_report
            result = generate_report(seconds)
            for w in self._rp_out.winfo_children():
                w.destroy()
            if "error" in result:
                self._msg(result["error"], C["danger"])
                return
            s = result["stats"]
            lines = ["[OK] Report: {}".format(result["path"])]
            for t, k in [("CPU", "cpu"), ("Memory", "memory"), ("Disk", "disk")]:
                lines.append("{}: avg {:.1f}% / max {:.1f}% / min {:.1f}% / {} rows".format(
                    t, s[k]["avg"], s[k]["max"], s[k]["min"], s[k]["count"]))
            self._msg("\n".join(lines), C["green"])
        except Exception as e:
            self._msg(str(e), C["danger"])

    # ════════════════════════════════════════════════
    #  Snapshot
    # ════════════════════════════════════════════════
    def _show_snapshot(self):
        self._set_header("快照管理", "创建 / 对比 / 报告")
        self._clear_pane()

        btn_row = tk.Frame(self.pane, bg=C["bg"])
        btn_row.pack(pady=(18, 10))
        self._pill_btn("创建快照", self._snap_create, bg=C["green"], fg=C["btn_text"])
        self._pill_btn("刷新列表", self._show_snapshot, bg=C["accent"], fg=C["btn_text"])

        self._snap_out = tk.Frame(self.pane, bg=C["bg"])
        self._snap_out.pack(fill=tk.BOTH, pady=10)

        try:
            from core.snapshot import list_snapshots
            snaps = list_snapshots()
        except Exception:
            snaps = []

        if not snaps:
            self._msg("暂无快照，点击「创建快照」开始", C["fg_dim"])
            return

        tree = self._make_tree(("no", "id", "time", "note", "cpu", "mem", "disk"),
                                ("#", "ID", "时间", "备注", "CPU%", "内存%", "磁盘%"),
                                (30, 160, 130, 120, 55, 55, 55), height=8)
        for i, s in enumerate(snaps[:20], 1):
            perf = s.get("performance", {})
            tree.insert("", "end", values=(
                i, s["id"], s["timestamp"][:16].replace("T", " "), s.get("note", ""),
                "{:.1f}".format(perf.get("cpu", {}).get("current", 0)),
                "{:.1f}".format(perf.get("memory", {}).get("current", 0)),
                "{:.1f}".format(perf.get("disk", {}).get("current", 0)),
            ), tags=("alt",) if i % 2 else (), iid=str(i))
        tree.tag_configure("alt", background=C["row_alt"])
        tree.pack(fill=tk.BOTH, expand=True)
        tree.bind("<Double-1>", lambda e: self._snap_report(tree))
        tree.bind("<Button-3>", lambda e: self._snap_right_click(e, tree))

        act_row = tk.Frame(self.pane, bg=C["bg"])
        act_row.pack(pady=(10, 0))
        self._pill_btn("对比选中", lambda: self._snap_compare(tree), bg=C["warning"], fg=C["btn_text"])
        self._pill_btn("查看报告", lambda: self._snap_report(tree), bg=C["info"], fg=C["btn_text"])
        self._pill_btn("删除选中", lambda: self._snap_delete(tree), bg=C["danger"], fg=C["btn_text"])

        self._snap_msg = tk.Frame(self.pane, bg=C["bg"])
        self._snap_msg.pack(fill=tk.X, pady=(8, 0))

    def _snap_selected(self, tree):
        sel = tree.selection()
        if len(sel) < 1:
            return []
        return [tree.item(i)["values"] for i in sel]

    def _snap_create(self):
        try:
            from core.snapshot import create_snapshot
            snap = create_snapshot("GUI")
            self._snap_msg_clear()
            perf = snap["performance"]
            self._msg(
                "[OK] 快照已创建: {}\nCPU {:.1f}% | 内存 {:.1f}% | 磁盘 {:.1f}% | 数据点 {}".format(
                    snap["id"],
                    perf["cpu"]["current"], perf["memory"]["current"],
                    perf["disk"]["current"], perf["cpu"].get("data_points", 0)),
                C["green"])
            self._show_snapshot()
        except Exception as e:
            self._msg(str(e), C["danger"])

    def _snap_compare(self, tree):
        rows = self._snap_selected(tree)
        if len(rows) < 2:
            self._msg("请先在表格中选中两个快照 (Ctrl+Click)", C["warning"])
            return
        try:
            from core.snapshot import compare_snapshots
            diff = compare_snapshots(rows[0][1], rows[1][1])
            if diff.get("error"):
                self._msg(diff["error"], C["danger"])
                return
            self._snap_msg_clear()
            lines = ["对比: {}  vs  {}".format(diff["id1"], diff["id2"])]
            for label in ["CPU", "内存", "磁盘"]:
                d = diff[label]
                lines.append("{}: 当前 {}%→{}% / 均值 {}%→{}%".format(
                    label, *d["current"][:2], *d["avg"][:2]))
            if diff.get("service_changes"):
                for sv in diff["service_changes"]:
                    lines.append("服务 {}: {} → {}".format(sv["name"], sv["before"], sv["after"]))
            if diff.get("config_changes"):
                for c in diff["config_changes"]:
                    lines.append("配置变更: {}".format(c))
            self._msg("\n".join(lines), C["accent"])
        except Exception as e:
            self._msg(str(e), C["danger"])

    def _snap_report(self, tree):
        rows = self._snap_selected(tree)
        if not rows:
            return
        try:
            from core.snapshot import report_snapshot
            path = report_snapshot(rows[0][1])
            import os, subprocess
            if path and os.path.exists(path):
                self._snap_msg_clear()
                self._msg("[OK] 报告已生成: {}".format(path), C["green"])
                subprocess.Popen(["cmd", "/c", "start", "", path], shell=True)
            else:
                self._msg("未找到快照", C["danger"])
        except Exception as e:
            self._msg(str(e), C["danger"])

    def _snap_delete(self, tree):
        rows = self._snap_selected(tree)
        if not rows:
            return
        try:
            from core.snapshot import delete_snapshot
            sid = rows[0][1]
            if delete_snapshot(sid):
                self._snap_msg_clear()
                self._msg("[OK] 已删除: {}".format(sid), C["green"])
                self._show_snapshot()
            else:
                self._msg("未找到快照: {}".format(sid), C["warning"])
        except Exception as e:
            self._msg(str(e), C["danger"])

    def _snap_right_click(self, event, tree):
        sel = tree.identify_row(event.y)
        if sel:
            tree.selection_set(sel)

    def _snap_msg_clear(self):
        for w in self._snap_msg.winfo_children():
            w.destroy()

    # ════════════════════════════════════════════════
    #  TODO
    # ════════════════════════════════════════════════
    def _show_todo(self):
        self._set_header("Coming Soon", "")
        self._clear_pane()
        self._msg("This feature is under development.", C["fg_dim"])

    # ── helpers ─────────────────────────────────────
    def _make_tree(self, columns, headings, widths, height=12):
        tree = ttk.Treeview(self.pane, columns=columns, show="headings", height=height)
        for col, hdr, w in zip(columns, headings, widths):
            tree.heading(col, text=hdr)
            tree.column(col, width=w, anchor="e" if col in ("pid", "no", "cpu", "mem", "rss", "avg", "max", "min", "count", "value", "threshold") else "w")
        tree.column(columns[0], width=widths[0], anchor="w")
        return tree


def launch_gui():
    root = tk.Tk()
    DigitalLabGUI(root)
    root.mainloop()
