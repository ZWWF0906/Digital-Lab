import os
import sys
import subprocess
import traceback
from datetime import datetime

LAB_ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(LAB_ROOT, "startup.log")

def log(msg):
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except OSError:
        pass

def run_mode(args_str):
    main_py = os.path.join(LAB_ROOT, "main.py")
    args = [sys.executable, main_py]
    if args_str:
        args.append(args_str)
    log(f"launching: {' '.join(args)}")
    subprocess.Popen(args, cwd=LAB_ROOT, creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0)
    try:
        root.quit()
    except Exception:
        sys.exit(0)

log("launcher.py started")
log(f"python: {sys.executable}")
log(f"lab_root: {LAB_ROOT}")
log(f"sys.path[0]: {sys.path[0]}")

try:
    import tkinter as tk
    from tkinter import font as tkfont
    _has_tk = True
    log("tkinter loaded")
except ImportError:
    _has_tk = False
    log("tkinter not available, using console menu")

if not _has_tk:
    print("Digital Lab - 启动选项")
    print("=" * 40)
    print("  [1] Web 仪表盘 — 在浏览器中打开实时监控")
    print("  [2] 桌面控制台 — 打开桌面 GUI")
    print("  [3] 命令行菜单 — 打开交互式命令行界面")
    print("  [0] 退出")
    print("=" * 40)
    try:
        choice = input("请选择 (1-3): ").strip()
    except (EOFError, KeyboardInterrupt):
        sys.exit(0)

    mode_map = {"1": "dashboard", "2": "gui", "3": ""}
    if choice in mode_map:
        run_mode(mode_map[choice])
    sys.exit(0)

root = tk.Tk()
root.title("Digital Lab — 启动选项")
root.geometry("380x460")
root.resizable(False, False)
root.configure(bg="#f5f5f5")

try:
    root.eval("tk::PlaceWindow . center")
except tk.TclError:
    root.update_idletasks()
    w, h = 380, 460
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

title_font = tkfont.Font(family="Microsoft YaHei UI", size=18, weight="bold")
sub_font = tkfont.Font(family="Microsoft YaHei UI", size=9)
btn_font = tkfont.Font(family="Microsoft YaHei UI", size=12, weight="bold")
desc_font = tkfont.Font(family="Microsoft YaHei UI", size=8)

tk.Label(root, text="Digital Lab", font=title_font, fg="#1e1e1e", bg="#f5f5f5").pack(pady=28)
tk.Label(root, text="个人数字实验室 · 请选择启动模式", font=sub_font, fg="#8c8c8c", bg="#f5f5f5").pack()

tk.Frame(root, height=1, bg="#e0e0e0").pack(fill="x", padx=30, pady=16)

def make_btn(text, desc, color, hover_color, args_str):
    c = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
    hc = f"#{hover_color[0]:02x}{hover_color[1]:02x}{hover_color[2]:02x}"

    f = tk.Frame(root, bg="#f5f5f5")
    f.pack(fill="x", padx=20, pady=2)

    btn = tk.Button(
        f, text=text, font=btn_font, bg=c, fg="white",
        activebackground=hc, activeforeground="white",
        relief="flat", borderwidth=0, cursor="hand2",
        padx=20, pady=14,
        command=lambda a=args_str: run_mode(a),
    )
    btn.pack(fill="x")
    btn.bind("<Enter>", lambda e, b=btn, hc=hc: b.configure(bg=hc))
    btn.bind("<Leave>", lambda e, b=btn, c=c: b.configure(bg=c))

    tk.Label(root, text=desc, font=desc_font, fg="#999", bg="#f5f5f5").pack(pady=14)

make_btn("Web 仪表盘", "在浏览器中打开实时监控面板", (30, 144, 255), (0, 110, 220), "dashboard")
make_btn("桌面控制台", "打开桌面 GUI 程序", (78, 205, 196), (50, 170, 160), "gui")
make_btn("命令行菜单", "打开交互式命令行选择界面", (155, 89, 182), (120, 60, 150), "")

try:
    root.mainloop()
except Exception:
    log(f"tkinter crash: {traceback.format_exc()}")
    sys.exit(0)

log("launcher.py exiting normally")
