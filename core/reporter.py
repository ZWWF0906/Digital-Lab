from __future__ import annotations

import os
import sys
import io
import time
import base64
import datetime
import sqlite3

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def _get_plot_style():
    try:
        plt.style.use("seaborn-v0_8-darkgrid")
    except Exception:
        pass
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def _get_db_path():
    from core.config import get_config
    return get_config().monitor_db_path


def _db_exists():
    return os.path.exists(_get_db_path())


def _query_raw(seconds_ago: int) -> list:
    cutoff = (datetime.datetime.now() - datetime.timedelta(seconds=seconds_ago)).isoformat()
    db_path = _get_db_path()
    rows = []
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        cur = conn.execute(
            "SELECT timestamp, cpu, memory, disk FROM snapshots "
            "WHERE timestamp >= ? ORDER BY timestamp ASC",
            (cutoff,),
        )
        for ts, cpu, mem, disk in cur:
            try:
                dt = datetime.datetime.fromisoformat(ts)
            except (ValueError, TypeError):
                continue
            rows.append({
                "ts": dt,
                "cpu": cpu,
                "memory": mem,
                "disk": disk,
            })
        conn.close()
    except sqlite3.OperationalError:
        pass
    return rows


def _b64img(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _make_chart(rows: list, metric: str, label: str, color: str, ylabel: str = "%"):
    _get_plot_style()
    times = [r["ts"] for r in rows]
    values = [r[metric] for r in rows]

    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.plot(times, values, color=color, linewidth=1.2, marker="", alpha=0.9)
    ax.fill_between(times, values, alpha=0.08, color=color)
    ax.set_title(label, fontsize=14, fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate(rotation=30, ha="right")
    ax.grid(True, alpha=0.3)
    ax.set_ylim(bottom=0)
    if values:
        ax.axhline(y=sum(values) / len(values), color=color, linestyle="--", alpha=0.4, linewidth=0.8)
    img = _b64img(fig)
    plt.close(fig)
    return img


def _stats(rows: list, metric: str) -> dict:
    values = [r[metric] for r in rows]
    if not values:
        return {"avg": 0, "max": 0, "min": 0, "count": 0}
    return {
        "avg": round(sum(values) / len(values), 1),
        "max": round(max(values), 1),
        "min": round(min(values), 1),
        "count": len(values),
    }


def _label_for_period(seconds: int) -> str:
    if seconds >= 86400:
        days = seconds // 86400
        return "最近 {} 天".format(days)
    elif seconds >= 3600:
        hours = seconds // 3600
        return "最近 {} 小时".format(hours)
    return "最近 {} 分钟".format(seconds // 60)


def _html_report(img_cpu: str, img_mem: str, img_disk: str,
                 s_cpu: dict, s_mem: dict, s_disk: dict,
                 period_label: str) -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = []
    html.append("<!DOCTYPE html>")
    html.append('<html lang="zh-CN"><head><meta charset="utf-8">')
    html.append("<title>Digital Lab 监控报告</title>")
    html.append("<style>")
    html.append("body{font-family:'Microsoft YaHei',sans-serif;max-width:960px;margin:0 auto;padding:20px;background:#f5f5f5;color:#333}")
    html.append("h1{color:#1a73e8;border-bottom:3px solid #1a73e8;padding-bottom:8px}")
    html.append("h2{color:#444;margin-top:30px}")
    html.append(".stats{display:flex;gap:16px;flex-wrap:wrap;margin:16px 0}")
    html.append(".stat-card{flex:1;min-width:180px;background:#fff;border-radius:8px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,0.1)}")
    html.append(".stat-card h3{margin:0 0 8px;font-size:14px;color:#888}")
    html.append(".stat-card .val{font-size:28px;font-weight:700;color:#1a73e8}")
    html.append(".stat-card .sub{font-size:12px;color:#999;margin-top:4px}")
    html.append("img{max-width:100%;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1);margin:12px 0}")
    html.append("table{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)}")
    html.append("th{background:#1a73e8;color:#fff;padding:10px 12px;text-align:left}")
    html.append("td{padding:8px 12px;border-bottom:1px solid #eee}")
    html.append("tr:last-child td{border-bottom:none}")
    html.append(".footer{text-align:center;color:#999;font-size:12px;margin-top:30px}")
    html.append("</style></head><body>")
    html.append("<h1>Digital Lab 监控报告</h1>")
    html.append("<p>周期: {} | 生成时间: {}</p>".format(period_label, now))

    html.append("<h2>统计摘要</h2>")
    html.append("<div class=stats>")
    for title, s, color in [("CPU", s_cpu, "#e74c3c"), ("内存", s_mem, "#2ecc71"), ("磁盘", s_disk, "#3498db")]:
        html.append('<div class=stat-card>')
        html.append('<h3>{}</h3>'.format(title))
        html.append('<div class=val style="color:{}">{:.1f}%</div>'.format(color, s["avg"]))
        html.append('<div class=sub>峰值 {:.1f}% / 最低 {:.1f}% / {} 条数据</div>'.format(s["max"], s["min"], s["count"]))
        html.append('</div>')
    html.append("</div>")

    html.append("<h2>详细表格</h2>")
    html.append("<table><tr><th>指标</th><th>均值</th><th>峰值</th><th>最低值</th><th>数据量</th></tr>")
    for title, s in [("CPU", s_cpu), ("内存", s_mem), ("磁盘", s_disk)]:
        html.append("<tr><td>{}</td><td>{:.1f}%</td><td>{:.1f}%</td><td>{:.1f}%</td><td>{}</td></tr>".format(
            title, s["avg"], s["max"], s["min"], s["count"]
        ))
    html.append("</table>")

    if img_cpu:
        html.append("<h2>CPU 使用率</h2>")
        html.append('<img src="data:image/png;base64,{}" alt="CPU">'.format(img_cpu))
    if img_mem:
        html.append("<h2>内存使用率</h2>")
        html.append('<img src="data:image/png;base64,{}" alt="Memory">'.format(img_mem))
    if img_disk:
        html.append("<h2>磁盘使用率</h2>")
        html.append('<img src="data:image/png;base64,{}" alt="Disk">'.format(img_disk))

    html.append('<div class=footer>Digital Lab 自动生成 — {}</div>'.format(now))
    html.append("</body></html>")
    return "\n".join(html)


def generate_report(seconds_ago: int = 604800) -> dict:
    if not _db_exists():
        return {"error": "请先运行 dlab monitor 采集数据。\n    dlab monitor --daemon -n 60"}

    rows = _query_raw(seconds_ago)

    if len(rows) < 2:
        return {"error": "数据不足 ({} 条)，无法生成趋势图。\n请先运行守护模式累积数据。".format(len(rows))}

    label = _label_for_period(seconds_ago)
    s_cpu = _stats(rows, "cpu")
    s_mem = _stats(rows, "memory")
    s_disk = _stats(rows, "disk")

    img_cpu = ""
    img_mem = ""
    img_disk = ""
    if HAS_MPL:
        img_cpu = _make_chart(rows, "cpu", "CPU 使用率 ({})".format(label), "#e74c3c")
        img_mem = _make_chart(rows, "memory", "内存使用率 ({})".format(label), "#2ecc71")
        img_disk = _make_chart(rows, "disk", "磁盘使用率 ({})".format(label), "#3498db")

    html = _html_report(img_cpu, img_mem, img_disk, s_cpu, s_mem, s_disk, label)

    from core.config import get_config
    reports_dir = os.path.join(get_config().lab_root, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    filename = "report_{}.html".format(datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    path = os.path.join(reports_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    return {
        "ok": True,
        "path": path,
        "stats": {"cpu": s_cpu, "memory": s_mem, "disk": s_disk},
        "label": label,
        "html": html,
    }


def format_terminal_summary(result: dict) -> str:
    if "error" in result:
        return "[!] {}".format(result["error"])

    s = result["stats"]
    label = result["label"]

    lines = []
    lines.append("")
    lines.append("=" * 60)
    lines.append("  Digital Lab 分析报告 — {}".format(label))
    lines.append("=" * 60)
    lines.append("  {:8s}  {:8s}  {:8s}  {:8s}  {}".format("指标", "均值", "峰值", "最低值", "数据量"))
    lines.append("-" * 60)
    for title, key in [("CPU", "cpu"), ("内存", "memory"), ("磁盘", "disk")]:
        lines.append("  {:8s}  {:6.1f}%  {:6.1f}%  {:6.1f}%  {:5d} 条".format(
            title, s[key]["avg"], s[key]["max"], s[key]["min"], s[key]["count"]
        ))
    lines.append("-" * 60)
    lines.append("  HTML 报告: {}".format(result["path"]))
    lines.append("=" * 60)
    return "\n".join(lines)
