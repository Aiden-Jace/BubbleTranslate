import os
import sys


def resource_path(*parts):
    """返回开发环境或 PyInstaller 环境中的资源绝对路径。"""
    if hasattr(sys, "_MEIPASS"):
        root = sys._MEIPASS
    else:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, *parts)
