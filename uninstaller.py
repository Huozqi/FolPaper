import ctypes
import os
import subprocess
import sys
import tempfile
import tkinter as tk
import traceback
from tkinter import messagebox


APP_NAME = 'FolPaper'
APP_EXE_NAME = 'FolPaper.exe'
UNINSTALLER_NAME = 'FolPaper_Uninstall.exe'
REGISTRY_KEY = r'HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\FolPaper'


def install_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def desktop_shortcut_path():
    return os.path.join(os.path.expanduser('~'), 'Desktop', APP_NAME + '.lnk')


def start_menu_dir():
    appdata = os.environ.get('APPDATA')
    if not appdata:
        appdata = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming')
    return os.path.join(appdata, 'Microsoft', 'Windows', 'Start Menu', 'Programs', APP_NAME)


def start_menu_shortcut_path():
    return os.path.join(start_menu_dir(), APP_NAME + '.lnk')


def remove_registry():
    subprocess.run(['reg', 'delete', REGISTRY_KEY, '/f'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def run_cleanup_batch(silent=False):
    target_dir = install_dir()
    desktop_link = desktop_shortcut_path()
    start_link = start_menu_shortcut_path()
    menu_dir = start_menu_dir()
    script_path = os.path.join(tempfile.gettempdir(), 'folpaper_uninstall_cleanup.ps1')
    lines = [
        "$ErrorActionPreference = 'SilentlyContinue'",
        'Start-Sleep -Seconds 2',
        "Stop-Process -Name 'FolPaper' -Force",
        "Stop-Process -Name 'FolPaper_Uninstall' -Force",
        "Remove-Item -LiteralPath '" + desktop_link.replace("'", "''") + "' -Force",
        "Remove-Item -LiteralPath '" + start_link.replace("'", "''") + "' -Force",
        "Remove-Item -LiteralPath '" + menu_dir.replace("'", "''") + "' -Recurse -Force",
        "$target = '" + target_dir.replace("'", "''") + "'",
        'for ($i = 0; $i -lt 20; $i++) {',
        '    if (-not (Test-Path -LiteralPath $target)) { break }',
        '    Remove-Item -LiteralPath $target -Recurse -Force',
        '    Start-Sleep -Seconds 1',
        '}',
        'Remove-Item -LiteralPath $MyInvocation.MyCommand.Path -Force',
    ]
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    subprocess.Popen(
        ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        startupinfo=startup,
    )
    if not silent:
        messagebox.showinfo('卸载完成', '卸载程序已经开始执行，关闭此窗口后将清理安装目录。')


def perform_uninstall(silent=False):
    remove_registry()
    run_cleanup_batch(silent=silent)


def cli_uninstall():
    if '--silent' not in sys.argv:
        return False
    perform_uninstall(silent=True)
    return True


def show_ui():
    root = tk.Tk()
    root.withdraw()
    if messagebox.askyesno(APP_NAME + ' 卸载程序', '确定要卸载 FolPaper 吗？\n\n安装目录中的程序文件与数据库将一并删除。'):
        perform_uninstall(silent=False)
    root.destroy()


if __name__ == '__main__':
    try:
        if not cli_uninstall():
            show_ui()
    except Exception as exc:
        if '--silent' in sys.argv:
            log_path = os.path.join(tempfile.gettempdir(), 'folpaper_uninstall_error.log')
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(traceback.format_exc())
            raise
        ctypes.windll.user32.MessageBoxW(0, str(exc), APP_NAME + ' 卸载失败', 0x10)
