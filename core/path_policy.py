"""DL-SEC-06-03 / W-02：用户可配置路径的本地安全策略。

规则：
- 只接受绝对本地路径；拒绝 UNC、设备命名空间、相对路径、点段穿越和空字节。
- 解析符号链接后再检查，避免链接把已检查路径重定向到其他位置。
- 记忆目录允许用户选择外部本地目录；CA Bundle 必须是已存在的普通本地文件。
- 校验失败返回错误字符串；调用方必须拒绝或回退到应用管理目录，不能静默使用原值。
"""
from __future__ import annotations

import os
import string
import sys


def _reject_components(raw: str):
    if "\x00" in raw:
        return "路径包含空字节"
    if len(raw) > 500:
        return "路径过长"
    if raw.startswith("\\\\") or raw.startswith("//"):
        return "不允许 UNC/网络路径"
    if raw.startswith("\\\\?\\") or raw.startswith("\\\\.\\"):
        return "不允许设备命名空间路径"
    parts = raw.replace("\\", "/").split("/")
    if any(part in ("..",) for part in parts):
        return "不允许路径穿越"
    drive, rest = os.path.splitdrive(raw)
    if drive and not rest:
        return "不能指向驱动器根"
    if not os.path.isabs(raw) or (drive and drive.upper() not in [d + ":" for d in string.ascii_uppercase]):
        return "必须是本地绝对路径"
    return None


def _real_unchanged(raw: str) -> bool:
    """拒绝 symlink/junction 改变路径语义；不存在的尾部允许（新建目录）。"""
    try:
        real = os.path.realpath(os.path.abspath(os.path.expanduser(raw)))
        norm = os.path.normcase(os.path.abspath(os.path.expanduser(raw)))
        # realpath 会解析已存在的链接；用 normcase 比较，避免仅大小写差异误报。
        return os.path.normcase(real) == norm
    except Exception:
        return False


def validate_local_dir(value, allow_empty=True):
    """返回 (normalized, error)。空值表示使用应用默认目录。"""
    if value is None:
        value = ""
    if not isinstance(value, str):
        return "", "目录必须是字符串"
    raw = value.strip()
    if not raw:
        if allow_empty:
            return "", None
        return "", "目录不能为空"
    problem = _reject_components(raw)
    if problem:
        return "", problem
    norm = os.path.abspath(os.path.expanduser(raw))
    if not _real_unchanged(norm):
        return "", "不允许符号链接/重定向路径"
    if getattr(sys, "frozen", False):
        install_root = os.path.dirname(os.path.abspath(sys.executable))
    else:
        install_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        if os.path.commonpath([os.path.normcase(norm), os.path.normcase(install_root)]) == os.path.normcase(install_root):
            return "", "记忆目录不能位于应用安装目录"
    except ValueError:
        pass
    return norm, None


def validate_local_file(value):
    """返回 (normalized, error)；用于 CA Bundle 等单文件输入。"""
    if not isinstance(value, str) or not value.strip():
        return "", "文件路径不能为空"
    raw = value.strip()
    problem = _reject_components(raw)
    if problem:
        return "", problem
    norm = os.path.abspath(os.path.expanduser(raw))
    if not _real_unchanged(norm):
        return "", "不允许符号链接/重定向路径"
    if not os.path.isfile(norm):
        return "", "必须是已存在的普通文件"
    try:
        if os.path.getsize(norm) > 2 * 1024 * 1024:
            return "", "文件过大"
    except Exception:
        return "", "无法读取文件属性"
    return norm, None
