"""
Digital Lab 启动器 - 桌面快捷方式入口
双击弹出三选一界面：Web仪表盘 / 桌面GUI / 命令行
"""
import subprocess
import sys
import os
import tkinter as tk

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LAB_ROOT = os.path.dirname(SCRIPT_DIR)
MAIN_PY = os.path.join(LAB_ROOT, "main.py")

# ── 配色 (iOS 深色风格) ──
BG   = "#1c1c1e"
CARD = "#2c2c2e"
ACCENT = "#0a84ff"
ACCENT_HOVER = "#409cff"
GREEN = "#30d158"
GREEN_HOVER = "#5ee080"
PURPLE = "#bf5af2"
PURPLE_HOVER = "#da8fff"
TEXT  = "#ffffff"
SUB   = "#8e8e93"


def _launch(mode):
    """销毁窗口, 启动对应模式"""
    root.destroy()
    args = [sys.executable, MAIN_PY]
    if mode == "web":
        args.append("dashboard")
    elif mode == "gui":
        args.append("gui")
    # CLI: 无额外参数

    # CREATE_NEW_CONSOLE 让 CLI 模式获得独立控制台
    flags = subprocess.CREATE_NEW_CONSOLE if mode == "cli" else 0
    subprocess.Popen(
        args,
        cwd=LAB_ROOT,
        creationflags=flags,
    )


# ── 窗口 ──
root = tk.Tk()
root.title("Digital Lab")
root.configure(bg=BG)
root.resizable(False, False)

# 尺寸和居中
W, H = 340, 310
root.geometry(f"{W}x{H}")
root.eval("tk::PlaceWindow . center")

# 去掉标题栏（可选, 用关闭按钮代替）
try:
    root.attributes("-toolwindow", 1)
except Exception:
    pass

# ── 布局 ──
# 顶部图标 + 标题
header = tk.Frame(root, bg=BG)
header.pack(pady=28)

title = tk.Label(
    header,
    text="Digital Lab",
    font=("Inter", 20, "bold"),
    fg=TEXT,
    bg=BG,
)
title.pack()

subtitle = tk.Label(
    header,
    text="请选择启动模式",
    font=("Inter", 11),
    fg=SUB,
    bg=BG,
)
subtitle.pack(pady=4)

# 按钮区域
btn_frame = tk.Frame(root, bg=BG)
btn_frame.pack(pady=24, padx=24, fill="x")

# ── Web 按钮 ──
btn_web = tk.Button(
    btn_frame,
    text="Web 仪表盘",
    font=("Inter", 12, "bold"),
    fg=TEXT,
    bg=ACCENT,
    activebackground=ACCENT_HOVER,
    activeforeground=TEXT,
    relief="flat",
    bd=0,
    padx=20,
    pady=12,
    cursor="hand2",
    command=lambda: _launch("web"),
)
btn_web.pack(fill="x")
btn_web.bind("<Enter>", lambda e: btn_web.configure(bg=ACCENT_HOVER))
btn_web.bind("<Leave>", lambda e: btn_web.configure(bg=ACCENT))
btn_web.configure(
    highlightthickness=0,
    borderwidth=0,
)

# ── GUI 按钮 ──
btn_gui = tk.Button(
    btn_frame,
    text="桌面控制台",
    font=("Inter", 12, "bold"),
    fg=TEXT,
    bg=GREEN,
    activebackground=GREEN_HOVER,
    activeforeground=TEXT,
    relief="flat",
    bd=0,
    padx=20,
    pady=12,
    cursor="hand2",
    command=lambda: _launch("gui"),
)
btn_gui.pack(fill="x", pady=12)
btn_gui.bind("<Enter>", lambda e: btn_gui.configure(bg=GREEN_HOVER))
btn_gui.bind("<Leave>", lambda e: btn_gui.configure(bg=GREEN))
btn_gui.configure(
    highlightthickness=0,
    borderwidth=0,
)

# ── CLI 按钮 ──
btn_cli = tk.Button(
    btn_frame,
    text="命令行",
    font=("Inter", 12, "bold"),
    fg=TEXT,
    bg=PURPLE,
    activebackground=PURPLE_HOVER,
    activeforeground=TEXT,
    relief="flat",
    bd=0,
    padx=20,
    pady=12,
    cursor="hand2",
    command=lambda: _launch("cli"),
)
btn_cli.pack(fill="x", pady=12)
btn_cli.bind("<Enter>", lambda e: btn_cli.configure(bg=PURPLE_HOVER))
btn_cli.bind("<Leave>", lambda e: btn_cli.configure(bg=PURPLE))
btn_cli.configure(
    highlightthickness=0,
    borderwidth=0,
)

root.mainloop()