import sys
import os
import platform

def set_autostart(enable=True):
    """
    设置开机自启动
    Windows: 写入注册表 Run 键
    macOS: 写入 LaunchAgents
    """
    system = platform.system()
    app_path = os.path.abspath(sys.argv[0])
    # 如果是 python 脚本运行，我们需要指向 python 解释器
    if app_path.endswith('.py'):
        app_command = f'"{sys.executable}" "{app_path}"'
    else:
        app_command = f'"{app_path}"'

    if system == "Windows":
        _set_windows_autostart(enable, app_command)
    elif system == "Darwin":
        _set_macos_autostart(enable, app_command)

def _set_windows_autostart(enable, app_command):
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "BubbleTranslate"
        legacy_app_name = "Fast" + "TranslateApp"
        
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, legacy_app_name)
            except FileNotFoundError:
                pass
            if enable:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, app_command)
                print(f"[AutoStart] Windows 自启动已开启: {app_command}")
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                    print("[AutoStart] Windows 自启动已关闭")
                except FileNotFoundError:
                    pass
    except Exception as e:
        print(f"[AutoStart] Windows 设置失败: {e}")

def _set_macos_autostart(enable, app_command):
    try:
        label = "com.bubbletranslate.app"
        plist_path = os.path.expanduser(f"~/Library/LaunchAgents/{label}.plist")
        legacy_label = "com." + "fast" + "translate.app"
        legacy_plist_path = os.path.expanduser(
            f"~/Library/LaunchAgents/{legacy_label}.plist"
        )
        if os.path.exists(legacy_plist_path):
            os.remove(legacy_plist_path)
        
        if enable:
            # 这里的 app_command 在 Mac 上如果是 python 运行，可能需要拆分数组
            import shlex
            cmd_parts = shlex.split(app_command)
            
            args_str = "\n".join([f"        <string>{arg}</string>" for arg in cmd_parts])
            
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
{args_str}
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
            os.makedirs(os.path.dirname(plist_path), exist_ok=True)
            with open(plist_path, "w", encoding="utf-8") as f:
                f.write(plist_content)
            print(f"[AutoStart] macOS 自启动已开启: {plist_path}")
        else:
            if os.path.exists(plist_path):
                os.remove(plist_path)
                print("[AutoStart] macOS 自启动已关闭")
    except Exception as e:
        print(f"[AutoStart] macOS 设置失败: {e}")
