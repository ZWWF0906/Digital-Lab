from __future__ import annotations

import os
import sys
import time
import json
import sqlite3
import datetime
import threading

try:
    from flask import Flask, jsonify, request
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

try:
    import psutil as _psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

_dashboard_thread = None

_CSS = r"""
/* ============================================================
   MyGo Minimal Design System
   ============================================================ */
:root{
/* foundation */
--bg-primary:#0d1117;
--bg-secondary:rgba(255,255,255,.03);
--bg-tertiary:rgba(255,255,255,.06);
--bg-elevated:rgba(22,27,34,.85);
/* accent */
--accent:#87CEEB;
--accent-bright:#1E90FF;
--accent-teal:#4ECDC4;
--accent-purple:#9B59B6;
--accent-pink:#E74C3C;
/* text */
--text-primary:#e6edf3;
--text-secondary:rgba(230,237,243,.6);
--text-tertiary:rgba(230,237,243,.3);
/* border */
--border:rgba(135,206,250,.08);
--border-hover:rgba(135,206,250,.3);
/* glow - single layer, hover only */
--glow-hover:rgba(135,206,250,.15);
--glow-inner-hover:rgba(135,206,250,.04);
/* layout */
--radius-sm:6px;--radius-md:16px;--radius-lg:24px;
--gap-sm:12px;--gap-md:20px;--gap-lg:24px;--padding-card:24px;
--font-sans:-apple-system,BlinkMacSystemFont,'Segoe UI','Inter',sans-serif;
--font-mono:'SF Mono','Fira Code','Cascadia Code',monospace;
--ease-smooth:cubic-bezier(.4,0,.2,1);
--ease-elastic:cubic-bezier(.33,1,.68,1);
--dur-fast:150ms;--dur-normal:200ms;--dur-slow:300ms
}
[data-theme="light"]{
--bg-primary:#f0f4f8;
--bg-secondary:rgba(255,255,255,.7);
--bg-tertiary:rgba(0,0,0,.04);
--bg-elevated:rgba(255,255,255,.85);
--accent:#1E90FF;--accent-bright:#0066CC;
--accent-teal:#2DAA9E;--accent-purple:#7D3C98;--accent-pink:#C0392B;
--text-primary:#1a2332;
--text-secondary:rgba(26,35,50,.6);
--text-tertiary:rgba(26,35,50,.3);
--border:rgba(30,144,255,.15);
--border-hover:rgba(30,144,255,.4);
--glow-hover:rgba(30,144,255,.08);
--glow-inner-hover:rgba(30,144,255,.03)
}

/* ---- Animation Keyframes ---- */
@keyframes breathe{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(.8)}}
@keyframes pulse-ring{0%{transform:scale(.6);opacity:1}100%{transform:scale(2.2);opacity:0}}
@keyframes value-update{0%{transform:translate(-50%,-50%) scale(1)}50%{transform:translate(-50%,-50%) scale(1.12)}100%{transform:translate(-50%,-50%) scale(1)}}
@keyframes value-bump{0%{stroke-width:5}50%{stroke-width:7}100%{stroke-width:5}}
@keyframes fadeInUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
@keyframes shimmer{0%{background-position:-200% 0}100%{background-position:200% 0}}

*{margin:0;padding:0;box-sizing:border-box}
body{
font-family:var(--font-sans);background:var(--bg-primary);color:var(--text-primary);
min-height:100vh;overflow-x:hidden;-webkit-font-smoothing:antialiased;
transition:background var(--dur-slow) var(--ease-smooth),color var(--dur-slow) var(--ease-smooth)
}
h2{font-size:22px;font-weight:600;letter-spacing:-.01em;margin-bottom:20px}
::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--bg-tertiary);border-radius:10px}

/* ---- nav ---- */
.nav{
position:fixed;top:0;left:0;right:0;height:56px;
background:var(--bg-elevated);
backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
border-bottom:1px solid var(--border);
z-index:100;display:flex;align-items:center;padding:0 24px;
transition:background var(--dur-slow) var(--ease-smooth),border-color var(--dur-slow) var(--ease-smooth)
}
.nav h1{font-size:17px;font-weight:600;letter-spacing:-.01em}
.nav .dot{width:8px;height:8px;border-radius:50%;background:var(--accent-teal);margin-right:8px;animation:breathe 2s ease-in-out infinite;box-shadow:0 0 8px var(--accent-teal)}
.nav .desc{font-size:12px;color:var(--text-secondary);margin-left:12px;font-feature-settings:'tnum';font-variant-numeric:tabular-nums}
.nav .nav-pills{display:flex;align-items:center;gap:8px;margin-left:20px}
.nav .nav-pill{display:flex;align-items:center;gap:5px;padding:4px 10px;border-radius:20px;background:var(--bg-tertiary);border:1px solid var(--border);font-size:11px;color:var(--text-secondary);font-feature-settings:'tnum';font-variant-numeric:tabular-nums;transition:background var(--dur-normal) var(--ease-smooth),border-color var(--dur-normal) var(--ease-smooth)}
.nav .nav-pill .pill-dot{width:5px;height:5px;border-radius:50%}
.nav .nav-pill .pill-dot.pulse{animation:pulse-ring 2s ease-out infinite}
[data-theme="dark"] .nav .nav-pill .pill-dot{box-shadow:0 0 4px var(--accent)}

/* ---- theme toggle ---- */
.theme-toggle{
position:relative;margin-left:auto;width:42px;height:42px;
border-radius:50%;border:1px solid var(--border);
background:var(--bg-secondary);color:var(--text-primary);
font-size:18px;cursor:pointer;
display:flex;align-items:center;justify-content:center;
transition:background var(--dur-slow) var(--ease-smooth),transform var(--dur-normal) var(--ease-smooth),box-shadow var(--dur-slow) var(--ease-smooth),border-color var(--dur-slow) var(--ease-smooth)
}
.theme-toggle:hover{background:var(--bg-tertiary);transform:scale(1.08);box-shadow:0 0 16px var(--glow-hover)}
.theme-toggle:active{transform:scale(.92)}
.theme-toggle .icon-sun,.theme-toggle .icon-moon{position:absolute;font-size:20px;transition:opacity var(--dur-slow) var(--ease-smooth),transform .4s var(--ease-elastic)}
.theme-toggle .icon-sun{opacity:0;transform:rotate(-90deg) scale(.5)}
.theme-toggle .icon-moon{opacity:1;transform:rotate(0) scale(1)}
[data-theme="light"] .theme-toggle .icon-sun{opacity:1;transform:rotate(0) scale(1)}
[data-theme="light"] .theme-toggle .icon-moon{opacity:0;transform:rotate(90deg) scale(.5)}

/* ---- sidebar ---- */
.side{
position:fixed;top:56px;left:0;bottom:0;width:252px;
background:var(--bg-primary);
border-right:1px solid var(--border);
overflow-y:auto;z-index:99;padding:8px 12px 24px;
transition:background var(--dur-slow) var(--ease-smooth),border-color var(--dur-slow) var(--ease-smooth)
}
.side .sg{margin-top:12px}
.side .st{font-size:10px;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.08em;padding:8px 12px 4px}
.side a{position:relative;display:flex;align-items:center;gap:10px;padding:9px 12px 9px 14px;border-radius:10px;color:var(--text-primary);font-size:14px;text-decoration:none;cursor:pointer;font-weight:450;transition:background var(--dur-fast) var(--ease-smooth),color var(--dur-fast) var(--ease-smooth),padding-left var(--dur-normal) var(--ease-smooth)}
.side a:hover{padding-left:18px;background:var(--bg-secondary)}
.side a.active{background:rgba(30,144,255,.12);color:var(--accent-bright);font-weight:500}
.side a.active::before{content:'';position:absolute;left:0;top:6px;bottom:6px;width:3px;background:var(--accent-bright);border-radius:0 4px 4px 0;box-shadow:0 0 8px var(--accent-bright)}
.side a .ico{width:24px;text-align:center;font-size:14px;opacity:.7}
.side a.active .ico{opacity:1}
.side .divider{height:1px;background:var(--border);margin:8px 12px}
.main{margin-left:252px;margin-top:56px;padding:24px 28px 60px}

/* ---- card: minimal, glow only on hover ---- */
.card{
position:relative;
background:var(--bg-secondary);
border:1px solid var(--border);
border-radius:var(--radius-lg);
padding:var(--padding-card);
overflow:hidden;
transition:transform .25s var(--ease-smooth),box-shadow .25s var(--ease-smooth),border-color var(--dur-slow) var(--ease-smooth)
}
.card:hover{
transform:translateY(-2px);
border-color:var(--border-hover);
box-shadow:0 0 30px var(--glow-hover),inset 0 0 30px var(--glow-inner-hover)
}
.card:active{transform:scale(.98)}
.card.anim,.ring-card.anim{animation:fadeInUp .5s var(--ease-elastic) both}

/* ---- ring grid ---- */
.ring-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:var(--gap-md);margin-bottom:var(--gap-lg)}
.ring-grid .ring-card.anim:nth-child(1){animation-delay:.02s}
.ring-grid .ring-card.anim:nth-child(2){animation-delay:.08s}
.ring-grid .ring-card.anim:nth-child(3){animation-delay:.14s}
/* ---- ring card: minimal, glow only on hover ---- */
.ring-card{
position:relative;
display:flex;flex-direction:column;align-items:center;justify-content:center;
padding:28px 20px 20px;cursor:default;
background:var(--bg-secondary);
border:1px solid var(--border);
border-radius:var(--radius-lg);overflow:hidden;
transition:transform .25s var(--ease-smooth),box-shadow .25s var(--ease-smooth),border-color var(--dur-slow) var(--ease-smooth)
}
.ring-card:hover{
transform:translateY(-2px);
border-color:var(--border-hover);
box-shadow:0 0 30px var(--glow-hover),inset 0 0 30px var(--glow-inner-hover)
}
.ring-card .ring-wrap{position:relative;width:130px;height:130px;display:flex;align-items:center;justify-content:center}
.ring-card .ring-wrap svg{display:block}
.ring-card .val{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);display:flex;align-items:center;justify-content:center;font-size:38px;font-weight:300;letter-spacing:-.04em;line-height:1;font-feature-settings:'tnum';font-variant-numeric:tabular-nums;transition:color var(--dur-normal) var(--ease-smooth);white-space:nowrap}
.ring-card .val-unit{font-size:20px;font-weight:400;opacity:.45;margin-left:1px}
.ring-card .lbl{margin-top:8px;font-size:13px;font-weight:500;color:var(--text-secondary);letter-spacing:.02em}
.ring-card .sub{font-size:11px;color:var(--text-tertiary);margin-top:3px;font-feature-settings:'tnum';font-variant-numeric:tabular-nums}
.ring-card .trend{margin-top:10px;font-size:12px;font-weight:500;padding:3px 10px;border-radius:20px;background:var(--bg-tertiary);border:1px solid var(--border);font-feature-settings:'tnum';font-variant-numeric:tabular-nums;transition:background var(--dur-normal) var(--ease-smooth),border-color var(--dur-normal) var(--ease-smooth)}

/* ---- segmented control ---- */
.seg{position:relative;display:inline-flex;background:var(--bg-tertiary);border-radius:10px;padding:2px}
.seg-ind{position:absolute;top:2px;left:2px;height:calc(100% - 4px);background:var(--bg-secondary);border:1px solid var(--border);border-radius:8px;transition:transform .3s var(--ease-elastic),width .3s var(--ease-elastic);pointer-events:none;z-index:0}
.seg span{position:relative;z-index:1;padding:6px 15px;border-radius:8px;font-size:13px;font-weight:500;color:var(--text-secondary);cursor:pointer;transition:color var(--dur-normal) var(--ease-smooth);user-select:none;white-space:nowrap}
.seg span.on{color:var(--text-primary);font-weight:600}
.toolbar .rt{font-size:11px;color:var(--text-tertiary);margin-left:auto;font-feature-settings:'tnum'}

/* ---- skeleton ---- */
.skeleton{background:linear-gradient(90deg,var(--bg-tertiary) 25%,rgba(128,128,128,.12) 50%,var(--bg-tertiary) 75%);background-size:200% 100%;animation:shimmer 1.5s ease-in-out infinite;border-radius:12px}

/* ---- tables ---- */
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:10px 14px;border-bottom:1px solid var(--border);font-size:11px;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.04em}
td{padding:9px 14px;border-bottom:1px solid var(--border);font-size:13px;font-weight:400}
tr:nth-child(even) td{background:rgba(255,255,255,.015)}
tr:hover td{background:var(--bg-tertiary)}
.panel{display:none}.panel.on{display:block}

/* ---- buttons ---- */
.btn{display:inline-flex;align-items:center;justify-content:center;padding:8px 18px;border-radius:20px;border:1px solid var(--border);font:500 13px var(--font-sans);cursor:pointer;transition:transform var(--dur-fast) var(--ease-smooth),opacity var(--dur-fast) var(--ease-smooth),box-shadow var(--dur-fast) var(--ease-smooth);color:var(--text-primary);background:var(--bg-tertiary)}
.btn:active{transform:scale(.94)}
.btn.blue{background:var(--accent-bright);color:#fff;border-color:transparent}
.btn.green{background:var(--accent-teal);color:#fff;border-color:transparent}
.btn.red{background:var(--accent-pink);color:#fff;border-color:transparent}
.btn+.btn{margin-left:8px}
.msg{background:var(--bg-secondary);border:1px solid var(--border);border-radius:var(--radius-md);padding:16px 20px;margin:8px 0;font:13px/1.6 var(--font-mono);white-space:pre-wrap;color:var(--text-secondary)}
.msg.good{border-left:3px solid var(--accent-teal);color:var(--text-primary)}
.empty{text-align:center;padding:48px 20px;color:var(--text-tertiary)}
.empty h3{font-size:16px;font-weight:500;color:var(--text-secondary);margin-bottom:6px}
.empty p{font-size:13px;color:var(--text-tertiary)}
.stat-row{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}
.stat-item{background:var(--bg-secondary);border:1px solid var(--border);border-radius:var(--radius-md);padding:16px 20px;min-width:120px;transition:transform var(--dur-fast) var(--ease-smooth)}
.stat-item:active{transform:scale(.97)}
.stat-item .lbl{font-size:11px;color:var(--text-tertiary);font-weight:500;margin-bottom:4px}
.stat-item .num{font-size:22px;font-weight:600;color:var(--text-primary)}
input[type=text]{padding:8px 14px;border:1px solid var(--border);border-radius:10px;background:var(--bg-primary);color:var(--text-primary);font:400 13px var(--font-sans);outline:none;transition:border var(--dur-normal) var(--ease-smooth);width:160px}
input[type=text]:focus{border-color:var(--accent-bright)}

/* ---- hardware capsules: minimal ---- */
.hw-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:var(--gap-sm);margin-bottom:var(--gap-md)}
.hw-capsule{
position:relative;
background:var(--bg-secondary);
border:1px solid var(--border);
border-radius:var(--radius-md);
padding:18px 20px;overflow:hidden;
transition:transform .2s var(--ease-smooth),box-shadow .2s var(--ease-smooth),border-color var(--dur-normal) var(--ease-smooth)
}
.hw-capsule:hover{
transform:translateY(-2px);
border-color:var(--border-hover);
box-shadow:0 0 30px var(--glow-hover),inset 0 0 30px var(--glow-inner-hover)
}
.hw-capsule .hw-head{display:flex;align-items:center;gap:10px;margin-bottom:10px;position:relative;z-index:1}
.hw-capsule .hw-icon{font-size:17px;opacity:.85;width:32px;height:32px;display:flex;align-items:center;justify-content:center;background:var(--bg-tertiary);border-radius:10px;flex-shrink:0;transition:transform var(--dur-normal) var(--ease-smooth)}
.hw-capsule:hover .hw-icon{transform:rotate(-6deg)}
.hw-capsule .hw-k{font-size:11px;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.05em}
.hw-capsule .hw-main{font-size:15px;font-weight:400;color:var(--text-primary);line-height:1.35;margin-bottom:6px;letter-spacing:-.01em;position:relative;z-index:1}
.hw-capsule .hw-sub{font-size:11px;color:var(--text-secondary);font-feature-settings:'tnum';font-variant-numeric:tabular-nums;line-height:1.4;position:relative;z-index:1}
.hw-capsule .hw-bar{margin-top:10px;height:3px;background:var(--bg-tertiary);border-radius:6px;overflow:hidden;position:relative;z-index:1}
.hw-capsule .hw-bar-fill{height:100%;border-radius:6px;transition:width .8s var(--ease-elastic);box-shadow:0 0 8px var(--accent-bright)}
.hw-tag{display:inline-block;font-size:10px;font-weight:600;padding:2px 8px;border-radius:8px;margin-top:6px;border:1px solid var(--border);position:relative;z-index:1}
.hw-tag.ok{background:rgba(78,205,196,.12);color:var(--accent-teal);border-color:rgba(78,205,196,.2)}
.hw-tag.warn{background:rgba(255,159,10,.12);color:#FF9F0A;border-color:rgba(255,159,10,.2)}
.hw-tag.bad{background:rgba(231,76,60,.12);color:var(--accent-pink);border-color:rgba(231,76,60,.2)}
.hw-summary{display:flex;gap:8px;flex-wrap:wrap;margin-top:4px;position:relative;z-index:1}
.hw-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;margin-left:auto;animation:breathe 2s ease-in-out infinite;position:relative;z-index:1}
.hw-parts{margin-top:8px;display:flex;flex-direction:column;gap:4px;position:relative;z-index:1}
.hw-part-row{display:flex;align-items:center;gap:6px;font-size:11px}
.hw-part-lbl{color:var(--text-secondary);font-weight:500;min-width:24px}
.hw-part-free{font-weight:600;font-feature-settings:'tnum';font-variant-numeric:tabular-nums}
.hw-part-total{color:var(--text-tertiary);font-feature-settings:'tnum'}

@media(max-width:900px){.side{width:200px}.main{margin-left:200px}.ring-grid{grid-template-columns:repeat(2,1fr)}.hw-grid{grid-template-columns:repeat(2,1fr)}.nav .nav-pills{display:none}}
@media(max-width:640px){.side{display:none}.main{margin-left:0;padding:16px}.ring-grid{grid-template-columns:1fr}.nav{padding:0 16px}.hw-grid{grid-template-columns:1fr}.ring-card{padding:24px 16px}.ring-card .val{font-size:32px}.ring-card .val-unit{font-size:16px}.nav h1{font-size:15px}}

/* ---- beginner tooltips ---- */
.has-tip{position:relative;cursor:help}
.has-tip::after{
content:attr(data-tip);
position:absolute;bottom:calc(100% + 8px);left:50%;transform:translateX(-50%);
background:rgba(0,0,0,.82);color:#fff;
font-size:12px;font-weight:400;line-height:1.4;
padding:8px 12px;border-radius:6px;
white-space:nowrap;pointer-events:none;
opacity:0;transition:opacity .2s var(--ease-smooth);
z-index:9999
}
.has-tip:hover::after,.has-tip:focus-visible::after{opacity:1}
.has-tip.tip-left::after{left:0;transform:none}
.has-tip.tip-right::after{left:auto;right:0;transform:none}
.has-tip.tip-bottom::after{bottom:auto;top:calc(100% + 8px)}
[data-theme="light"] .has-tip::after{background:rgba(0,0,0,.78)}

/* ---- inline hint text ---- */
.hint{font-size:13px;color:var(--text-tertiary);margin-bottom:16px;line-height:1.6}

/* ---- footer copyright ---- */
.footer-cr{text-align:center;padding:20px 0 8px;font-size:11px;color:var(--text-tertiary);letter-spacing:.02em;line-height:1.8}
.footer-cr .cr-name{color:var(--text-secondary);font-weight:500}
.footer-cr .cr-sponsor{color:var(--accent);font-style:italic}
"""

_SIDEBAR_ITEMS = [
    ("基础", [
        ("init", "初始化", "\u2699", "一键创建项目所需的目录结构"),
        ("status", "系统状态", "\u2139", "查看 Python 版本、系统平台和目录健康状态"),
        ("config-panel", "配置管理", "\u2692", "查看和保存当前系统配置文件"),
    ]),
    ("监控", [
        ("home", "仪表盘", "\u25C9", "实时查看 CPU、内存、磁盘使用率及历史趋势图"),
        ("processes", "进程 Top 15", "\u25A3", "查看当前占用 CPU 最高的 15 个进程"),
        ("alerts", "告警记录", "\u26A0", "查看历史告警事件，包括触发时间和具体数值"),
        ("alert-test", "告警测试", "\u25B6", "手动触发一次告警检测，查看当前值是否超过阈值"),
        ("daemon", "守护进程", "\u27F3", "启动/停止后台监控采集服务，采集的数据用于图表和历史记录"),
        ("compare", "历史对比", "\u29BF", "对比当前数据与历史均值、峰值的差异"),
    ]),
    ("工具", [
        ("launcher", "快捷启动", "\u27A5", "管理常用应用的快捷启动方式，一键打开"),
        ("report", "生成报告", "\u2630", "生成并查看指定时间范围的 CPU/内存/磁盘统计报告"),
    ]),
    ("其他", [
        ("experiment", "实验管理", "\u25CB", "实验管理功能模块"),
        ("analyze", "数据分析", "\u2228", "数据分析功能模块"),
        ("ai", "AI 助手", "\u2726", "AI 智能助手功能模块"),
    ]),
]


def _build_sidebar():
    parts = ['<nav class="nav">',
             '<span class="dot"></span>',
             '<h1>Digital Lab</h1>',
             '<span class="desc" id="nav-desc">System Monitor</span>',
             '<span class="nav-pills" id="nav-pills">',
             '<span class="nav-pill has-tip" id="pill-cpu" data-tip="CPU 实时负载"><span class="pill-dot pulse" style="background:var(--accent-teal)"></span>CPU</span>',
             '<span class="nav-pill has-tip" id="pill-memory" data-tip="内存 实时负载"><span class="pill-dot pulse" style="background:var(--accent-bright)"></span>MEM</span>',
             '<span class="nav-pill has-tip" id="pill-disk" data-tip="磁盘 实时负载"><span class="pill-dot pulse" style="background:var(--accent-bright)"></span>DISK</span>',
             '</span>',
             '<button class="theme-toggle has-tip tip-bottom" id="theme-btn" onclick="toggleTheme()" data-tip="切换到浅色模式">',
             '<span class="icon-moon">\u263E</span>',
             '<span class="icon-sun">\u2600</span>',
             '</button>',
             '</nav>',
             '<div class="side">']
    for title, items in _SIDEBAR_ITEMS:
        parts.append('<div class="sg">')
        parts.append('<div class="st">{}</div>'.format(title))
        for panel_id, label, icon, tip in items:
            cls_str = 'active has-tip' if panel_id == "home" else 'has-tip'
            parts.append(
                '<a href="#" onclick="loadPanel(\'{0}\');return false" data-panel="{0}" class="{1}" data-tip="{4}">'
                '<span class="ico">{2}</span>{3}</a>'.format(
                    panel_id, cls_str, icon, label, tip
                )
            )
        parts.append('</div>')
    parts.append('</div>')
    return "\n".join(parts)

_SCRIPTS = """\
<script>
var API='/api';
var CP='home';
var RING_KEYS=['cpu','memory','disk'];
var RING_LABELS=['CPU','内存','磁盘'];
var RING_COLORS=['var(--accent)','var(--accent)','var(--accent)'];
var _prev={cpu:0,memory:0,disk:0};
var _na={};

/* ---- helpers ---- */
function $(id){return document.getElementById(id)}
function cssVar(name){
    var v=getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v||name
}
function api(url,method,data){
    var o={};
    if(method){o.method=method;o.headers={'Content-Type':'application/json'};if(data)o.body=JSON.stringify(data)}
    return fetch(API+url,o).then(function(r){return r.json()})
}
function fmt(n){if(!n)return'0 B';var u=['B','KB','MB','GB','TB'];for(var i=0;i<u.length;i++){if(Math.abs(n)<1024)return n.toFixed(1)+' '+u[i];n/=1024}return n.toFixed(1)+' PB'}
function showEmpty(id,msg){msg=msg||'No data';var el=$('p-'+id);if(el)el.innerHTML='<div class="empty"><h3>'+msg+'</h3></div>'}

/* ---- number scroll animation ---- */
function numAnim(el,from,to,dur,fmt){
    dur=dur||600;fmt=fmt||function(v){return v.toFixed(1)+'%'};
    var id=el.id||Math.random().toString(36);
    if(_na[id])cancelAnimationFrame(_na[id]);
    var start=performance.now();
    function step(now){
        var p=Math.min((now-start)/dur,1);
        var e=1-Math.pow(1-p,3);
        el.textContent=fmt(from+(to-from)*e);
        if(p<1)_na[id]=requestAnimationFrame(step)
    }
    _na[id]=requestAnimationFrame(step)
}

/* ---- panel switcher ---- */
function panel(id){
    var ps=document.querySelectorAll('.panel');
    for(var i=0;i<ps.length;i++)ps[i].classList.remove('on');
    var el=$('p-'+id);if(el)el.classList.add('on');
    var as=document.querySelectorAll('.side a');
    for(var i=0;i<as.length;i++)as[i].classList.remove('active');
    var lnk=document.querySelector('[data-panel="'+id+'"]');
    if(lnk)lnk.classList.add('active')
}
function loadPanel(id){
    panel(id);CP=id;
    var m={'home':H,'processes':P,'alerts':AL,'init':I,'status':ST,'config-panel':CF,'daemon':D,'alert-test':AT,'compare':CMP,'launcher':LA,'report':RP};
    if(m[id])m[id]()
}

/* ---- SVG ring builder ---- */
function ringSVG(key,color,size){
    size=size||120;var cx=size/2,cy=size/2;
    var sw=5;var r=(size-sw)/2;var circ=2*Math.PI*r;
    var resolved=cssVar(color);
    if(resolved.indexOf('(')>0)resolved='#87CEEB';
    var svg='<svg width="'+size+'" height="'+size+'" viewBox="0 0 '+size+' '+size+'">';
    svg+='<circle cx="'+cx+'" cy="'+cy+'" r="'+r+'" fill="none" stroke="var(--border)" stroke-width="'+sw+'" stroke-linecap="round"/>';
    svg+='<circle id="ring-'+key+'" cx="'+cx+'" cy="'+cy+'" r="'+r+'" fill="none" stroke="'+resolved+'" stroke-width="'+sw+'" stroke-linecap="round" stroke-dasharray="'+circ+'" stroke-dashoffset="'+circ+'" transform="rotate(-90 '+cx+' '+cy+')" style="transition:stroke-dashoffset .8s cubic-bezier(.33,1,.68,1)"/>';
    svg+='</svg>';
    return {html:svg,circ:circ}
}

/* ---- animate ring ---- */
function animateRing(key,toPct){
    var el=document.getElementById('ring-'+key);
    if(!el)return;
    var circ=2*Math.PI*((120-5)/2);
    el.setAttribute('stroke-dashoffset',circ*(1-toPct/100))
}

/* ---- ring color: blue brightness by load ---- */
function ringClr(key,val){
    if(val>=80)return'var(--accent-bright)';
    if(val>=50)return'var(--accent-bright)';
    return'var(--accent)'
}

/* ---- trend calc ---- */
function trend(key,val){
    var p=_prev[key];_prev[key]=val;
    if(p===0)return'<span style="color:rgba(255,255,255,.4)">\u2192 \u6301\u5E73</span>';
    var d=val-p;
    if(Math.abs(d)<0.5)return'<span style="color:rgba(255,255,255,.4)">\u2192 \u6301\u5E73</span>';
    var arrow=d>0?'\u2191':'\u2193';
    var clr=d>0?cssVar('--accent-teal'):cssVar('--accent-pink');
    return'<span style="color:'+clr+'">'+arrow+' '+Math.abs(d).toFixed(0)+'%</span>'
}

/* ---- hardware capsules ---- */
function HW(){
    api('/hardware').then(function(d){
        if(!d||d.error)return;
        var c=d.cpu,m=d.memory,g=d.gpu,di=d.disk,sys=d.system;
        var dp=d._display;
        var xcpu=d.cpu||{},xmem=d.memory||{},xgpu=d.gpu||{},xdisk=d.disk||{},xsys=d.system||{},
            xdisp=d.display||{},xnet=d.network||{};
        function s(v){return v!=null&&v!==''&&v!==undefined}
        function join(arr){return arr.filter(s).join(' · ')}

        var caps;
        if(dp){
            caps=[
                {icon:'\u2699',key:'cpu',title:'PROCESSOR',main:dp.cpu.title||'',subs:dp.cpu.subtitle?[dp.cpu.subtitle]:[],tags:dp.cpu.tags||[],tagColor:dp.cpu.tag_color||''},
                {icon:'\u2248',key:'memory',title:'MEMORY',main:dp.memory.title||'',subs:dp.memory.subtitle?[dp.memory.subtitle]:[],tags:dp.memory.tags||[],bar:dp.memory.bar||0},
                {icon:'\u25A8',key:'gpu',title:'GRAPHICS',main:dp.gpu.title||'',subs:dp.gpu.subtitle?[dp.gpu.subtitle]:[],tags:dp.gpu.tags||[],glow:dp.gpu.glow||''},
                {icon:'\u25A5',key:'disk',title:'STORAGE',main:dp.disk.title||'',subs:dp.disk.subtitle?[dp.disk.subtitle]:[],tags:dp.disk.tags||[],parts:dp.disk.parts||[]},
                {icon:'\u29C9',key:'system',title:'SYSTEM',main:dp.system.title||'',subs:dp.system.subtitle?[dp.system.subtitle]:[],tags:dp.system.tags||[]}
            ];
        }else{
            caps=[
                {icon:'\u2699',key:'cpu',title:'PROCESSOR',main:'',subs:[],tags:[]},
                {icon:'\u2248',key:'memory',title:'MEMORY',main:'',subs:[],tags:[],bar:0},
                {icon:'\u25A8',key:'gpu',title:'GRAPHICS',main:'',subs:[],tags:[],glow:''},
                {icon:'\u25A5',key:'disk',title:'STORAGE',main:'',subs:[],tags:[],parts:[]},
                {icon:'\u29C9',key:'system',title:'SYSTEM',main:'',subs:[],tags:[]}
            ];

            if(c){
                caps[0].main=s(c.short_model)?c.short_model:(s(c.model)?c.model:'处理器');
                var ca=[];
                if(c.cores&&c.threads)ca.push(c.cores+'核'+c.threads+'线程');
                if(s(c.freq_current))ca.push(c.freq_current+'GHz');
                else if(s(c.freq_base))ca.push(c.freq_base+'GHz');
                caps[0].subs=ca;
                if(c.cores&&c.cores>=14)caps[0].tags.push('HX系列');
                if(c.short_model&&c.short_model.indexOf('HX')>0)caps[0].tags.push('游戏本标压');
            }

            if(m){
                caps[1].main=s(m.total_gb)?m.total_gb+' GB':'';
                var sa=[];
                if(s(m.type)&&s(m.frequency))sa.push(m.type+'-'+m.frequency);
                else if(s(m.type))sa.push(m.type);
                if(s(m.available_gb))sa.push(m.available_gb+'GB 可用');
                if(s(m.slots_used)&&s(m.slots_total))sa.push(m.slots_used+'/'+m.slots_total+' 插槽');
                caps[1].subs=sa;
                if(s(m.total_gb)&&s(m.available_gb))caps[1].bar=Math.round((m.total_gb-m.available_gb)/m.total_gb*100);
            }

            if(g){
                caps[2].main=s(g.short_name)?g.short_name:(s(g.name)?g.name:'GPU');
                var ga=[];
                if(s(g.vram_gb)&&s(g.vram_type))ga.push(g.vram_gb+'GB '+g.vram_type);
                else if(s(g.vram_gb))ga.push(g.vram_gb+'GB 显存');
                if(s(g.temperature))ga.push(g.temperature+'°C');
                if(g.utilization!=null)ga.push(g.utilization+'%');
                caps[2].subs=ga;
                if(g.dedicated){
                    caps[2].tags.push('独显模式');
                    caps[2].glow='ok';
                }
                if(s(g.driver))caps[2].tags.push('驱动 '+g.driver);
                if(g.mode==='laptop')caps[2].tags.push('Laptop');
            }else{
                caps[2].main='集成显卡';
                caps[2].subs=(c&&c.short_model)?[c.short_model+' 核显']:['无独立显卡'];
            }

            if(di){
                caps[3].main=s(di.capacity_gb)?di.capacity_gb+' GB':'';
                if(s(di.model))caps[3].subs.push(di.model.slice(0,28));
                if(s(di.type))caps[3].subs.push(di.type);
                if(s(di.interface))caps[3].subs.push(di.interface);
                if(di.partitions&&di.partitions.length){
                    var pl=[];
                    for(var i=0;i<di.partitions.length;i++){
                        var p=di.partitions[i];
                        var pct=p.total_gb?Math.round(p.free_gb/p.total_gb*100):0;
                        var cls=pct<10?'bad':pct<20?'warn':'ok';
                        pl.push({letter:p.letter,free:p.free_gb,total:p.total_gb,pct:pct,cls:cls});
                    }
                    caps[3].parts=pl;
                }
            }

            if(sys){
                var osName='';
                if(s(sys.edition))osName='Win11 '+sys.edition;
                else osName=(sys.os||'').replace('Windows 11 build','Win11').replace('Windows 10 build','Win10');
                if(!osName)osName=sys.os||'';
                caps[4].main=osName;
                var sya=[];
                if(s(sys.uptime_seconds))sya.push('运行 '+uptimeStr(sys.uptime_seconds));
                if(s(sys.python_version))sya.push('Python '+sys.python_version);
                caps[4].subs=sya;
                if(s(sys.boot_time))caps[4].tags.push(sys.boot_time.slice(0,10));
            }
        }

        var hwhtml='<div class="hw-grid">';
        for(var i=0;i<caps.length;i++){
            var cp=caps[i];
            if(!s(cp.main)&&(!cp.parts||!cp.parts.length))continue;
            hwhtml+='<div class="hw-capsule anim" style="animation-delay:'+(i*.05).toFixed(2)+'s">';
            hwhtml+='<div class="hw-head">';
            if(cp.glow)hwhtml+='<span class="hw-icon" style="background:rgba(78,205,196,.12);color:var(--accent-teal)">'+cp.icon+'</span>';
            else hwhtml+='<span class="hw-icon">'+cp.icon+'</span>';
            var hwTips={cpu:'处理器型号、核心/线程数、当前频率',memory:'内存容量、类型、频率和插槽使用情况',gpu:'显卡型号、显存、温度和驱动信息',disk:'磁盘容量、分区及剩余空间',system:'操作系统版本、开机时长和 Python 版本'};
            hwhtml+='<span class="hw-k has-tip" data-tip="'+hwTips[cp.key]+'">'+cp.title+'</span>';
            if(cp.glow)hwhtml+='<span class="hw-dot" style="background:var(--accent-teal);box-shadow:0 0 8px var(--accent-teal)"></span>';
            hwhtml+='</div>';
            if(s(cp.main))hwhtml+='<div class="hw-main">'+cp.main+'</div>';
            if(cp.subs.length)hwhtml+='<div class="hw-sub">'+join(cp.subs)+'</div>';
            if(cp.key==='cpu'&&xcpu.temperature)hwhtml+='<div class="hw-parts"><span class="hw-part-row"><span class="hw-part-lbl">Temp</span><span class="hw-part-free">'+xcpu.temperature+'\u00B0C</span></span></div>'
            if(s(cp.bar))hwhtml+='<div class="hw-bar"><div class="hw-bar-fill" style="width:'+cp.bar+'%;background:var(--accent-bright)"></div></div>';
            if(cp.tags.length){
                hwhtml+='<div class="hw-summary">';
                for(var j=0;j<cp.tags.length;j++){
                    var tagCls='';
                    if(cp.tags[j]==='独显模式')tagCls='ok';
                    else if(cp.tags[j]==='⚠ 高温')tagCls='bad';
                    else if(cp.tags[j]==='🌡 温热')tagCls='warn';
                    hwhtml+='<span class="hw-tag'+(tagCls?' '+tagCls:'')+'"'+(cp.tagColor&&cp.key==='cpu'?' style="background:rgba(255,107,107,.15);color:'+cp.tagColor+';border:1px solid rgba(255,107,107,.3)"':'')+'>'+cp.tags[j]+'</span>';
                }
                hwhtml+='</div>';
            }
            if(cp.key==='disk'&&xdisk.temperature)hwhtml+='<div class="hw-parts"><span class="hw-part-row"><span class="hw-part-lbl">Temp</span><span class="hw-part-free">'+xdisk.temperature+'\u00B0C</span></span></div>'
            if(cp.parts&&cp.parts.length){
                hwhtml+='<div class="hw-parts">';
                for(var k=0;k<cp.parts.length;k++){
                    var pt=cp.parts[k];
                    hwhtml+='<div class="hw-part-row">';
                    hwhtml+='<span class="hw-part-lbl">'+pt.letter+'盘</span>';
                    hwhtml+='<span class="hw-part-free" style="color:var(--'+(pt.cls==='bad'?'accent-pink':pt.cls==='warn'?'accent-teal':'text-secondary')+')">剩'+pt.free+'GB</span>';
                    hwhtml+='<span class="hw-part-total">/ '+pt.total+'GB</span>';
                    hwhtml+='</div>';
                }
                hwhtml+='</div>';
            }
            hwhtml+='</div>';
        }

        if(dp&&dp.warnings&&dp.warnings.length){
            hwhtml+='<div class="hw-warn" style="grid-column:1/-1;background:rgba(255,159,10,.08);border:1px solid rgba(255,159,10,.18);border-radius:12px;padding:10px 16px;font-size:11px;color:#FF9F0A;margin-top:4px">';
            hwhtml+='<span style="font-weight:600">⚠ 兼容性提示</span>';
            for(var w=0;w<dp.warnings.length;w++)hwhtml+='<div style="margin-top:4px">'+dp.warnings[w]+'</div>';
            hwhtml+='</div>';
        }

        var an=0;
        var disp_data,net_data;
        if(dp&&dp.display){
            var dd=dp.display.split('@');
            disp_data={main:dd[0]||dp.display,sub:dd[1]?dd[1].trim():''};
        }else if(xdisp&&xdisp.displays&&xdisp.displays.length){
            var dm=xdisp.displays[0];
            var panelName=dm.name||'';
            disp_data={main:xdisp.total_resolution||'',sub:dm.refresh_rate?dm.refresh_rate+'Hz':''};
            if(panelName)disp_data.sub2=panelName;
        }
        cp={key:'display',title:'DISPLAY',icon:'\u25A1',main:disp_data?disp_data.main:'',sub:disp_data?(disp_data.sub?(disp_data.sub2?disp_data.sub+' · '+disp_data.sub2:disp_data.sub):(disp_data.sub2||'')):''};
        if(!cp.main)cp.main='--';
        hwhtml+='<div class="hw-capsule anim hw-'+cp.key+'" style="animation-delay:'+(0.12+an*0.04)+'s">';
        hwhtml+='<div class="hw-head">';
        hwhtml+='<span class="hw-icon">'+cp.icon+'</span>';
        hwhtml+='<span class="hw-k has-tip" data-tip="显示器面板型号、分辨率和刷新率">'+cp.title+'</span>';
        hwhtml+='</div>';
        hwhtml+='<div class="hw-main">'+cp.main+'</div>';
        if(cp.sub)hwhtml+='<div class="hw-sub">'+cp.sub+'</div>';
        hwhtml+='</div>';
        an++;
        if(xnet&&xnet.adapters&&xnet.adapters.length){
            var na=xnet.adapters[0];
            var naSub=[];
            if(na.speed_mbps)naSub.push(na.speed_mbps+' Mbps');
            if(na.type)naSub.push(na.type);
            if(xnet.adapters.length>1)naSub.push('+ '+(xnet.adapters.length-1)+' adapters');
            cp={key:'network',title:'NETWORK',icon:'\u2601',main:na.name||'Network Adapter',sub:naSub.join(' · ')};
        }else{
            cp={key:'network',title:'NETWORK',icon:'\u2601',main:'--',sub:''};
        }
        hwhtml+='<div class="hw-capsule anim hw-'+cp.key+'" style="animation-delay:'+(0.12+an*0.04)+'s">';
        hwhtml+='<div class="hw-head">';
        hwhtml+='<span class="hw-icon">'+cp.icon+'</span>';
        hwhtml+='<span class="hw-k has-tip" data-tip="网络适配器型号、连接速率信息">'+cp.title+'</span>';
        hwhtml+='</div>';
        hwhtml+='<div class="hw-main">'+cp.main+'</div>';
        if(cp.sub)hwhtml+='<div class="hw-sub">'+cp.sub+'</div>';
        hwhtml+='</div>';
        hwhtml+='</div>';
        $('hw-panel').innerHTML=hwhtml;

        var hwSubs=[
            {k:'cpu',v:c?s(c.short_model)?c.short_model:(c.cores?c.cores+'C/'+c.threads+'T':null):null},
            {k:'memory',v:m?s(m.total_gb)?m.total_gb+'GB':null:null},
            {k:'disk',v:di?s(di.model)?di.model.slice(0,18):(s(di.capacity_gb)?di.capacity_gb+'GB':null):null}
        ];
        for(var i=0;i<hwSubs.length;i++){
            var el=$('hwl-'+hwSubs[i].k);
            if(el&&s(hwSubs[i].v))el.textContent=hwSubs[i].v
        }
    })
}
function uptimeStr(s){
    var d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60);
    if(d>0)return d+'d '+h+'h';
    if(h>0)return h+'h '+m+'m';
    return m+'m'
}

/* ---- segmented control (sliding indicator) ---- */
function segClick(containerId,val,btn,callback){
    var container=$(containerId);
    if(!container)return;
    var spans=container.querySelectorAll('span');
    var ind=container.querySelector('.seg-ind');
    for(var i=0;i<spans.length;i++)spans[i].classList.remove('on');
    btn.classList.add('on');
    if(ind){
        var cr=container.getBoundingClientRect();
        var br=btn.getBoundingClientRect();
        ind.style.width=br.width+'px';
        ind.style.transform='translateX('+(br.left-cr.left-2)+'px)'
    }
    if(callback)callback(val)
}
function initSegIndicators(){
    var segs=document.querySelectorAll('.seg');
    for(var i=0;i<segs.length;i++){
        var ind=segs[i].querySelector('.seg-ind');
        if(!ind)continue;
        var on=segs[i].querySelector('span.on');
        if(!on){ind.style.display='none';continue}
        var cr=segs[i].getBoundingClientRect();
        var br=on.getBoundingClientRect();
        ind.style.width=br.width+'px';
        ind.style.transform='translateX('+(br.left-cr.left-2)+'px'
    }
}

/* ---- refresh loop ---- */
var _tick=0;
function RF(){
    _tick++;
    if(CP==='home'){X()}
    else if(CP==='processes'){
        var t=$('p-processes');
        if(t&&t.querySelector('table')){if(_tick%2===0)updateProcesses()}else P()
    }
    else if(CP==='alerts')AL()
}

/* ---- current metrics (update rings + glow + number anim) ---- */
function X(){
    api('/current').then(function(d){
        if(!d||d.error)return;
        for(var i=0;i<3;i++){
            var key=RING_KEYS[i],val=Math.min(d[key]||0,100),clrVar=ringClr(key,val),clr=cssVar(clrVar);
            var el=$('rv-'+key);
            if(el){
                var numSpan=el.querySelector('.val-num');
                if(numSpan){
                    var cur=parseFloat(numSpan.textContent)||0;
                    el.style.color=clr;
                    numAnim(numSpan,cur,val,200,function(v){return Math.round(v)})
                }
                var diff=Math.abs(val-(parseFloat(el.getAttribute('data-prev'))||0));
                if(diff>=3){
                    el.style.animation='none';
                    el.offsetHeight;
                    el.style.animation='value-update .4s var(--ease-elastic)';
                    var ringEl=document.getElementById('ring-'+key);
                    if(ringEl){
                        ringEl.style.animation='none';
                        ringEl.offsetHeight;
                        ringEl.style.animation='value-bump .4s var(--ease-elastic)'
                    }
                }
                el.setAttribute('data-prev',val)
            }
            el=$('rt-'+key);if(el)el.innerHTML=trend(key,val);
            animateRing(key,val);
            var rc=$('rc-'+key);
            if(rc){
                var tip;
                if(val>=80)tip='负载较高，建议关闭不必要的程序';
                else if(val>=50)tip='负载中等，正在进行计算任务';
                else tip='负载正常，系统运行流畅';
                rc.setAttribute('data-tip',RING_LABELS[i]+' '+val.toFixed(0)+'% - '+tip)
            }
        }
        var nav=$('nav-desc');if(nav)nav.textContent='CPU '+d.cpu.toFixed(0)+'%  \u00b7  Mem '+d.memory.toFixed(0)+'%  \u00b7  Disk '+d.disk.toFixed(0)+'%';
        updateNavPills(d)
    })
}

function updateNavPills(d){
    var pills=$('nav-pills');
    if(!pills)return;
    var keys=['cpu','memory','disk'];
    var sp=pills.querySelectorAll('.pill-dot');
    var labels=['CPU','内存','磁盘'];
    for(var i=0;i<3&&i<sp.length;i++){
        var pct=(d[keys[i]]||0).toFixed(0);
        sp[i].style.background=cssVar(ringClr(keys[i],d[keys[i]]||0));
        var el=$('pill-'+keys[i]);
        if(el)el.setAttribute('data-tip',labels[i]+' 当前 '+pct+'%')
    }
}

/* ---- dashboard ---- */
function H(){
    panel('home');
    var s='<div id="hw-panel"><div class="hw-grid">';
    for(var i=0;i<5;i++)s+='<div class="hw-capsule anim" style="animation-delay:'+(i*.04).toFixed(2)+'s"><div class="skeleton" style="width:100%;height:82px;border-radius:12px"></div></div>';
    s+='</div></div>';
    s+='<div class="ring-grid">';
    for(var i=0;i<3;i++){
        var key=RING_KEYS[i],lbl=RING_LABELS[i],clr=RING_COLORS[i];
        var r=ringSVG(key,clr,120);
        var lbls=['CPU','内存','磁盘'];
        s+='<div class="ring-card anim has-tip" id="rc-'+key+'" data-tip="'+lbls[i]+' 使用率">';
        s+='<div class="ring-wrap">'+r.html;
        s+='<div class="val" id="rv-'+key+'" style="color:var(--text-primary)"><span class="val-num">--</span><span class="val-unit">%</span></div>';
        s+='</div>';
        s+='<div class="lbl">'+lbl+'</div>';
        s+='<div class="sub" id="hwl-'+key+'"></div>';
        s+='<div class="trend" id="rt-'+key+'"></div>';
        s+='</div>'
    }
    s+='</div>';
    $('p-home').innerHTML=s;
    initSegIndicators();
    X();HW()
}

/* ---- processes ---- */
function P(){api('/processes').then(function(d){if(!d||!Array.isArray(d)||!d.length){showEmpty('processes');return}var h='<table><tr><th>PID</th><th>Name</th><th>CPU</th><th>Mem</th><th>RSS</th></tr>';for(var i=0;i<d.length;i++){var p=d[i];h+='<tr><td>'+p.pid+'</td><td>'+(p.name||'')+'</td><td>'+p.cpu.toFixed(1)+'%</td><td>'+p.memory.toFixed(1)+'%</td><td>'+fmt(p.rss)+'</td></tr>'}h+='</table>';$('p-processes').innerHTML=h}).catch(function(){showEmpty('processes')})}
function updateProcesses(){var t=$('p-processes');if(!t)return;var rows=t.querySelectorAll('table tr');if(rows.length<=1)return;api('/processes').then(function(d){if(!d||!Array.isArray(d))return;for(var i=0;i<Math.min(d.length,rows.length-1);i++){var p=d[i],cells=rows[i+1].children;if(cells.length>=5){cells[0].textContent=p.pid;cells[1].textContent=p.name||'';cells[2].textContent=p.cpu.toFixed(1)+'%';cells[3].textContent=p.memory.toFixed(1)+'%';cells[4].textContent=fmt(p.rss)}}})}

/* ---- alerts ---- */
function AL(){api('/alerts').then(function(d){if(!d||!Array.isArray(d)||!d.length){showEmpty('alerts','No alerts');return}var h='<table><tr><th>Time</th><th>Metric</th><th>Value</th><th>Threshold</th></tr>';for(var i=0;i<d.length;i++){var a=d[i],dt=a.data||{};h+='<tr><td>'+a.timestamp+'</td><td>'+a.message+'</td><td>'+(dt.current||0).toFixed(1)+'%</td><td>'+dt.threshold+'%</td></tr>'}h+='</table>';$('p-alerts').innerHTML=h}).catch(function(){showEmpty('alerts')})}

/* ---- init ---- */
function I(){var h='<div class="empty"><p>Create directory structure: tools/logs/experiments/notes/archive/interface</p><br><button class="btn green" onclick="doInit()">Initialize</button><div id="init-msg"></div></div>';$('p-init').innerHTML=h}
function doInit(){api('/init','POST').then(function(d){$('init-msg').innerHTML='<div class="msg'+(d.ok?' good':'')+'">'+(d.msg||'')+'</div>'})}

/* ---- status ---- */
function ST(){api('/status').then(function(d){if(!d)return;var h='<h2>System Status</h2><p class="hint">查看 Python 运行环境、操作系统信息及各子目录的健康状态。[OK] 表示目录存在，[MISSING] 表示尚未初始化。</p><div class="stat-row">';h+='<div class="stat-item"><div class="lbl">Python</div><div class="num" style="font-size:16px">'+(d.python||'')+'</div></div>';h+='<div class="stat-item"><div class="lbl">System</div><div class="num" style="font-size:16px">'+(d.platform||'')+'</div></div>';h+='</div>';h+='<div style="font-size:13px;line-height:1.8;color:var(--text-secondary)">'+(d.dirs||[]).join('<br>')+'</div>';h+='<div class="msg">'+(d.config||'')+'</div>';$('p-status').innerHTML=h}).catch(function(){showEmpty('status')})}

/* ---- config ---- */
function CF(){api('/config').then(function(d){if(!d)return;var h='<h2>Configuration</h2><p class="hint">当前加载的系统配置内容（JSON 格式）。点击 Save Config 可将当前内存配置写入配置文件。</p><button class="btn blue" onclick="doConfigSave()">Save Config</button><div id="cfg-msg"></div>';h+='<div class="msg" style="max-height:500px;overflow-y:auto;margin-top:12px">'+JSON.stringify(d,null,2)+'</div>';$('p-config-panel').innerHTML=h}).catch(function(){showEmpty('config-panel')})}
function doConfigSave(){api('/config','POST',{}).then(function(d){$('cfg-msg').innerHTML='<div class="msg">'+(d.msg||'')+'</div>'})}

/* ---- daemon ---- */
function D(){var h='<h2>Daemon</h2><p class="hint">守护进程在后台定时采集 CPU/内存/磁盘数据并存入数据库。图表、历史对比和告警功能均依赖该服务运行。点击 Start 启动采集。</p>';h+='<button class="btn green" onclick="doDaemon(&quot;start&quot;)">Start</button>';h+='<button class="btn red" onclick="doDaemon(&quot;stop&quot;)">Stop</button>';h+='<button class="btn blue" onclick="doDaemon(&quot;status&quot;)">Status</button>';h+='<div id="daemon-msg"></div>';$('p-daemon').innerHTML=h}
function doDaemon(a){api('/daemon/'+a,'POST').then(function(d){$('daemon-msg').innerHTML='<div class="msg">'+(d.msg||'')+'</div>'})}

/* ---- alert test ---- */
function AT(){var h='<h2>Alert Test</h2><p class="hint">手动触发一次告警检测。系统将采集当前 CPU/内存/磁盘值，与配置文件中的阈值对比，并在下方展示检测结果。</p><button class="btn red" onclick="doAlertTest()">Trigger Alert</button><div id="alert-msg"></div>';$('p-alert-test').innerHTML=h}
function doAlertTest(){api('/alert/test','POST').then(function(d){$('alert-msg').innerHTML='<div class="msg">'+(d.msg||'')+'</div>'})}

/* ---- compare ---- */
function CMP(){var h='<h2>Compare</h2><p class="hint">将当前实时数据与选定历史时间段的均值、峰值进行对比。选择一个时间范围后自动加载对比表格。</p><div class="toolbar"><div class="seg" id="seg-cmp"><div class="seg-ind"></div>';h+='<span class="on" onclick="segClick(&quot;seg-cmp&quot;,&quot;1h&quot;,this,function(v){doCMP(v)})">1h</span>';h+='<span onclick="segClick(&quot;seg-cmp&quot;,&quot;24h&quot;,this,function(v){doCMP(v)})">24h</span>';h+='<span onclick="segClick(&quot;seg-cmp&quot;,&quot;7d&quot;,this,function(v){doCMP(v)})">7d</span>';h+='</div></div><div id="cmp-r"></div>';$('p-compare').innerHTML=h;initSegIndicators()}
function doCMP(range){api('/current').then(function(cur){if(!cur)return;api('/data?range='+range).then(function(d){var c=$('cmp-r');if(!d||!d.times||!d.times.length){c.innerHTML='<div class="empty"><h3>Not enough data</h3></div>';return}var n=d.times.length;var avg=function(a){var s=0;for(var i=0;i<a.length;i++)s+=a[i];return s/a.length};var mx=function(a){return Math.max.apply(null,a)};var h='<table><tr><th>Metric</th><th>Current</th><th>Avg</th><th>Peak</th><th>Samples</th></tr>';var ks=['cpu','memory','disk'],ns=['CPU','Memory','Disk'];for(var i=0;i<ks.length;i++){var cv=cur[ks[i]]||0,av=avg(d[ks[i]]),mv=mx(d[ks[i]]);h+='<tr><td>'+ns[i]+'</td><td>'+cv.toFixed(1)+'%</td><td>'+av.toFixed(1)+'%</td><td>'+mv.toFixed(1)+'%</td><td>'+n+'</td></tr>'}h+='</table>';c.innerHTML=h})})}

/* ---- launcher ---- */
function LA(){api('/launcher/list').then(function(d){var h='<h2>Launcher</h2><p class="hint">管理常用应用的快捷启动方式。已添加的应用可直接点击 Launch 打开。在下方输入名称和路径可添加新的快捷方式。</p>';if(!d||!Array.isArray(d)||!d.length){h+='<div class="empty"><h3>No shortcuts</h3></div>'}else{h+='<table><tr><th>#</th><th>Name</th><th>Path</th><th></th></tr>';for(var i=0;i<d.length;i++){h+='<tr><td>'+(i+1)+'</td><td>'+d[i].name+'</td><td style="font-size:12px;color:var(--text-tertiary)">'+d[i].path+'</td><td><button class="btn blue" onclick="doLaunch('+i+')">Launch</button></td></tr>'}h+='</table>'}h+='<div class="msg" style="margin-top:16px"><input id="ln-name" placeholder="Name"><input id="ln-path" placeholder="Path"><button class="btn green" onclick="doAddLaunch()">Add</button></div><div id="ln-msg"></div>';$('p-launcher').innerHTML=h}).catch(function(){showEmpty('launcher')})}
function doLaunch(i){api('/launcher/launch','POST',{index:i}).then(function(d){$('ln-msg').innerHTML='<div class="msg">'+(d.msg||'')+'</div>'})}
function doAddLaunch(){var n=$('ln-name').value.trim(),p=$('ln-path').value.trim();if(!n||!p)return;api('/launcher/add','POST',{name:n,path:p}).then(function(d){$('ln-msg').innerHTML='<div class="msg">'+(d.msg||'')+'</div>';LA()})}

/* ---- report ---- */
function RP(){var h='<h2>Report</h2><p class="hint">选择一个时间范围，系统将自动统计该时段内 CPU/内存/磁盘的均值、峰值和最低值，并生成报告文件保存至项目目录。</p><div class="toolbar"><div class="seg" id="seg-rp"><div class="seg-ind"></div>';h+='<span class="on" onclick="segClick(&quot;seg-rp&quot;,&quot;1h&quot;,this,function(v){doRP(v)})">1h</span>';h+='<span onclick="segClick(&quot;seg-rp&quot;,&quot;6h&quot;,this,function(v){doRP(v)})">6h</span>';h+='<span onclick="segClick(&quot;seg-rp&quot;,&quot;24h&quot;,this,function(v){doRP(v)})">24h</span>';h+='<span onclick="segClick(&quot;seg-rp&quot;,&quot;7d&quot;,this,function(v){doRP(v)})">7d</span>';h+='</div></div><div id="rp-msg"></div>';$('p-report').innerHTML=h;initSegIndicators()}
function doRP(range){$('rp-msg').innerHTML='<div class="empty"><p style="color:var(--text-secondary)">Generating...</p></div>';api('/report/generate?range='+range).then(function(d){if(!d)return;$('rp-msg').innerHTML='<div class="msg">'+(d.msg||'')+'</div><div class="msg" style="margin-top:8px;max-height:500px;overflow-y:auto">'+(d.stats||'')+'</div>'})}

/* ---- theme toggle ---- */
 function toggleTheme(){
     var h=document.documentElement;
     var isLight=h.getAttribute('data-theme')==='light';
     var next=isLight?'dark':'light';
     h.setAttribute('data-theme',next);
     try{localStorage.setItem('dlab-theme',next)}catch(e){}
     var btn=$('theme-btn');
     if(btn)btn.setAttribute('data-tip',next==='light'?'切换到深色模式':'切换到浅色模式')
 }
 
 /* ---- boot ---- */
 document.addEventListener('DOMContentLoaded',function(){
     try{
         var saved=localStorage.getItem('dlab-theme')||'dark';
         document.documentElement.setAttribute('data-theme',saved);
         var btn=$('theme-btn');
         if(btn)btn.setAttribute('data-tip',saved==='dark'?'切换到浅色模式':'切换到深色模式')
     }catch(e){}
     H();
    setInterval(function(){try{RF()}catch(e){}},500);
    var as=document.querySelectorAll('.side a[data-panel]');
    for(var i=0;i<as.length;i++)as[i].addEventListener('click',function(e){e.preventDefault();loadPanel(this.getAttribute('data-panel'))})
});

/* ---- plotly async ---- */
/* plotly removed */
</script>
"""

_PANEL_WRAPPER = '<div class="panel" id="p-{id}"></div>'

_NO_DATA = '<div class="empty"><h3>暂无数据</h3><p>请先运行 <code>dlab monitor --daemon -n 60</code> 采集数据</p></div>'


def _get_db_path():
    from core.config import get_config
    return get_config().monitor_db_path


def _current_snapshot() -> dict:
    if HAS_PSUTIL:
        cpu = _psutil.cpu_percent(interval=0.05)
        mem = _psutil.virtual_memory().percent
        disk = _psutil.disk_usage("/").percent
        return {"cpu": round(cpu, 1), "memory": round(mem, 1), "disk": round(disk, 1)}

    try:
        conn = sqlite3.connect(_get_db_path(), timeout=5)
        cur = conn.execute("SELECT cpu, memory, disk FROM snapshots ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        if row:
            return {"cpu": round(row[0], 1), "memory": round(row[1], 1), "disk": round(row[2], 1)}
    except sqlite3.OperationalError:
        pass
    return {"error": "no data"}


def _top_processes():
    from core.monitor import get_top_processes, HAS_PSUTIL
    if not HAS_PSUTIL:
        return []
    return get_top_processes(15, "cpu")


def _read_alerts(limit=50) -> list:
    log_path = None
    try:
        from core.config import get_config
        log_path = get_config().monitor_log_path
    except Exception:
        pass
    if not log_path or not os.path.exists(log_path):
        return []
    alerts = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("level") == "ALERT":
                        alerts.append(entry)
                except (json.JSONDecodeError, KeyError):
                    continue
    except OSError:
        pass
    alerts.reverse()
    return alerts[:limit]


def create_app() -> Flask:
    app = Flask(__name__)

    @app.after_request
    def add_header(response):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    panels = ["home", "processes", "alerts", "init", "status", "config-panel",
              "daemon", "alert-test", "compare", "launcher", "report",
              "experiment", "analyze", "ai"]
    panels_html = "\n".join(
        _PANEL_WRAPPER.format(id=pid)
        for pid in panels
    )

    @app.route("/")
    def index():
        html = '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
        html += '<meta charset="UTF-8">\n'
        html += '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        html += '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        html += '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        html += '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&amp;display=swap" rel="stylesheet">\n'
        html += '<title>Digital Lab</title>\n'
        html += '<style>\n' + _CSS + '\n</style>\n'
        html += '</head>\n<body>\n'
        html += _build_sidebar()
        html += '\n<div class="main">\n' + panels_html
        html += '\n<div class="footer-cr"><span class="cr-name">Digital Lab</span> \u00A9 2026 \u8D75\u5C55\u94D6 | \u8D5E\u52A9\u8005: <span class="cr-sponsor">Ave Mujica \u2014 Oblivionis</span></div>'
        html += '\n</div>\n'
        html += _SCRIPTS
        html += '\n</body>\n</html>'
        return html

    @app.route("/api/current")
    def api_current():
        return jsonify(_current_snapshot())

    @app.route("/api/hardware")
    def api_hardware():
        try:
            from core.hardware import collect_all
            data = collect_all()
            keep_display = data.pop("_display", None)
            for key in list(data.keys()):
                if key.startswith("_"):
                    del data[key]
            for k in ("cpu", "memory", "gpu", "disk", "system"):
                if data.get(k):
                    data[k].pop("_confidence", None)
            if keep_display:
                data["_display"] = keep_display
            return jsonify(data)
        except Exception:
            return jsonify({"error": "hardware collection failed"})

    @app.route("/api/processes")
    def api_processes():
        procs = _top_processes()
        result = []
        for p in procs:
            result.append({
                "pid": p["pid"],
                "name": p["name"],
                "cpu": round(p["cpu"], 1),
                "memory": round(p["memory"], 1),
                "rss": p.get("memory_bytes", 0),
            })
        return jsonify(result)

    @app.route("/api/alerts")
    def api_alerts():
        return jsonify(_read_alerts(100))

    @app.route("/api/init", methods=["POST"])
    def api_init():
        try:
            from core.config import get_config
            cfg = get_config()
            cfg.ensure_dirs()
            return jsonify({"ok": True, "msg": "[OK] 目录结构已创建\n  tools / logs / experiments / notes / archive / interface"})
        except Exception as e:
            return jsonify({"ok": False, "msg": "[ERROR] {}".format(e)})

    @app.route("/api/status")
    def api_status():
        try:
            from core.config import get_config
            cfg = get_config()
            dirs = ["tools", "logs", "experiments", "notes", "archive", "interface"]
            dir_list = []
            for d in dirs:
                p = getattr(cfg, d + "_dir", "")
                exists = os.path.isdir(p) if p else False
                dir_list.append("{}  {}".format(d, "[OK]" if exists else "[MISSING]"))
            return jsonify({
                "python": cfg.python_version,
                "platform": cfg.platform_info,
                "dirs": dir_list,
                "config": "配置文件: {}".format(cfg.config_file),
            })
        except Exception as e:
            return jsonify({"error": str(e)})

    @app.route("/api/config")
    def api_config():
        try:
            from core.config import get_config
            cfg = get_config()
            data = {k: v for k, v in cfg.__dict__.items() if not k.startswith("_")}
            data.pop("config_file", None)
            return jsonify(data)
        except Exception as e:
            return jsonify({"error": str(e)})

    @app.route("/api/config", methods=["POST"])
    def api_config_save():
        try:
            from core.config import get_config
            cfg = get_config()
            cfg.save()
            return jsonify({"ok": True, "msg": "[OK] 配置文件已刷新: {}".format(cfg.config_file)})
        except Exception as e:
            return jsonify({"ok": False, "msg": "[ERROR] {}".format(e)})

    @app.route("/api/daemon/<action>", methods=["POST"])
    def api_daemon(action):
        from core.daemon import daemon_status, start_daemon, stop_daemon
        from core.config import get_config
        cfg = get_config()
        pid_path = cfg.monitor_pid_path
        interval = str(cfg.monitor_interval)
        lab_root = cfg.lab_root
        script_path = os.path.join(lab_root, "main.py")

        if action == "status":
            s = daemon_status(pid_path)
            if s.get("running"):
                msg = "运行中  PID: {}\n运行时长: {}\n采集次数: {}\n首次: {}\n最近: {}".format(
                    s["pid"], s.get("runtime", ""), s.get("collections", 0),
                    s.get("first_snapshot", ""), s.get("last_snapshot", "")
                )
            else:
                msg = "未运行  ({})".format(s.get("reason", ""))
            return jsonify({"ok": True, "msg": msg})
        elif action == "start":
            return jsonify({"ok": True, "msg": start_daemon(pid_path, script_path, interval)})
        elif action == "stop":
            return jsonify({"ok": True, "msg": stop_daemon(pid_path)})
        return jsonify({"ok": False, "msg": "[!] 未知操作: {}".format(action)})

    @app.route("/api/alert/test", methods=["POST"])
    def api_alert_test():
        try:
            from core.monitor import collect_and_store, enable_alert_test
            from core.config import get_config
            cfg = get_config()
            enable_alert_test()
            cpu, mem, disk = collect_and_store()
            thresholds = cfg.get_thresholds()
            from core.monitor import check_alerts
            alerts = check_alerts(cpu or 0, mem or 0, disk or 0, thresholds, 0)
            lines = ["当前值: CPU {:.1f}% / 内存 {:.1f}% / 磁盘 {:.1f}%".format(cpu or 0, mem or 0, disk or 0)]
            lines.append("阈值: CPU {}% / 内存 {}% / 磁盘 {}%".format(thresholds["cpu"], thresholds["memory"], thresholds["disk"]))
            for a in alerts:
                lines.append("[警告] {}: {:.1f}% (阈值: {}%)".format(a[0], a[1], a[2]))
            return jsonify({"ok": True, "msg": "\n".join(lines)})
        except Exception as e:
            return jsonify({"ok": False, "msg": "[ERROR] {}".format(e)})

    @app.route("/api/launcher/list")
    def api_launcher_list():
        from core.launcher import list_shortcuts
        return jsonify(list_shortcuts())

    @app.route("/api/launcher/launch", methods=["POST"])
    def api_launcher_launch():
        from core.launcher import launch
        data = request.get_json() or {}
        idx = data.get("index", -1) + 1
        msg = launch(idx)
        return jsonify({"ok": "[OK]" in msg, "msg": msg})

    @app.route("/api/launcher/add", methods=["POST"])
    def api_launcher_add():
        from core.launcher import add_shortcut
        data = request.get_json() or {}
        msg = add_shortcut(data.get("name", ""), data.get("path", ""))
        return jsonify({"ok": "[OK]" in msg, "msg": msg})

    @app.route("/api/report/generate")
    def api_report_generate():
        rng = request.args.get("range", "24h")
        seconds = {"1h": 3600, "6h": 21600, "24h": 86400, "7d": 604800}.get(rng, 86400)
        try:
            from core.reporter import generate_report
            result = generate_report(seconds)
            if "error" in result:
                return jsonify({"ok": False, "msg": result["error"], "stats": ""})
            s = result["stats"]
            rows = []
            for title, key in [("CPU", "cpu"), ("内存", "memory"), ("磁盘", "disk")]:
                rows.append("{}: 均值 {:.1f}% / 峰值 {:.1f}% / 最低 {:.1f}% / {} 条".format(
                    title, s[key]["avg"], s[key]["max"], s[key]["min"], s[key]["count"]
                ))
            return jsonify({
                "ok": True,
                "msg": "[OK] 报告已生成: {}".format(result["path"]),
                "stats": "\n".join(rows),
            })
        except Exception as e:
            return jsonify({"ok": False, "msg": "[ERROR] {}".format(e), "stats": ""})

    return app


def _find_port(start, host):
    import socket
    port = start
    for _ in range(10):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind((host, port))
            s.close()
            return port
        except OSError:
            port += 1
            s.close()
    return 0


def start_dashboard(host="127.0.0.1", port=8080, daemon_thread=True):
    global _dashboard_thread

    if _dashboard_thread and _dashboard_thread.is_alive():
        return "[!] Dashboard 已在 http://{}:{} 运行".format(host, port)

    if not HAS_FLASK:
        return "[ERROR] 需要 flask 库，请运行: pip install flask"

    actual_port = _find_port(port, host)
    if actual_port == 0:
        return "[!] 端口 {}-{} 均被占用，请指定其他端口".format(port, port + 9)
    if actual_port != port:
        port = actual_port

    app = create_app()

    def _run():
        app.config["SERVER_NAME"] = None
        try:
            app.run(host=host, port=port, debug=False, use_reloader=False)
        except OSError:
            pass

    _dashboard_thread = threading.Thread(target=_run, daemon=daemon_thread)
    _dashboard_thread.start()
    time.sleep(0.5)

    return "[OK] Dashboard 已启动: http://{}:{}".format(host, port)
