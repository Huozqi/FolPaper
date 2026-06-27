import ctypes
import os
import shutil
import subprocess
import sys
import tkinter as tk
import traceback
import zipfile
from tkinter import filedialog, messagebox


APP_NAME = 'FolPaper'
APP_EXE_NAME = 'FolPaper.exe'
UNINSTALLER_NAME = 'FolPaper_Uninstall.exe'
ARCHIVE_NAME = 'FolPaper_package.zip'
REGISTRY_KEY = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\FolPaper'


def resource_path(name):
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    direct_path = os.path.join(base_dir, name)
    if os.path.exists(direct_path):
        return direct_path
    for root, dirs, files in os.walk(base_dir):
        dirs.sort()
        files.sort()
        if name in files:
            return os.path.join(root, name)
    fallback_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build', name),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist', name),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), name),
    ]
    for path in fallback_paths:
        if os.path.exists(path):
            return path
    return direct_path


def default_install_dir():
    local_appdata = os.environ.get('LOCALAPPDATA')
    if not local_appdata:
        local_appdata = os.path.join(os.path.expanduser('~'), 'AppData', 'Local')
    return os.path.join(local_appdata, APP_NAME)


def desktop_shortcut_path():
    return os.path.join(os.path.expanduser('~'), 'Desktop', APP_NAME + '.lnk')


def start_menu_dir():
    appdata = os.environ.get('APPDATA')
    if not appdata:
        appdata = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming')
    return os.path.join(appdata, 'Microsoft', 'Windows', 'Start Menu', 'Programs', APP_NAME)


def start_menu_shortcut_path():
    return os.path.join(start_menu_dir(), APP_NAME + '.lnk')


def powershell_command(script):
    startup = None
    if os.name == 'nt':
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    subprocess.run(
        ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
        check=True,
        startupinfo=startup,
        timeout=15,
    )


def create_shortcut(shortcut_path, target_path, icon_path, working_dir):
    os.makedirs(os.path.dirname(shortcut_path), exist_ok=True)
    script = (
        "$shell = New-Object -ComObject WScript.Shell;"
        "$shortcut = $shell.CreateShortcut('" + shortcut_path.replace("'", "''") + "');"
        "$shortcut.TargetPath = '" + target_path.replace("'", "''") + "';"
        "$shortcut.WorkingDirectory = '" + working_dir.replace("'", "''") + "';"
        "$shortcut.IconLocation = '" + icon_path.replace("'", "''") + ",0';"
        "$shortcut.Save();"
    )
    powershell_command(script)


def register_uninstall_info(install_dir):
    import winreg

    exe_path = os.path.join(install_dir, APP_EXE_NAME)
    uninstaller_path = os.path.join(install_dir, UNINSTALLER_NAME)
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY)
    winreg.SetValueEx(key, 'DisplayName', 0, winreg.REG_SZ, APP_NAME)
    winreg.SetValueEx(key, 'InstallLocation', 0, winreg.REG_SZ, install_dir)
    winreg.SetValueEx(key, 'DisplayIcon', 0, winreg.REG_SZ, exe_path)
    winreg.SetValueEx(key, 'UninstallString', 0, winreg.REG_SZ, '"' + uninstaller_path + '"')
    winreg.SetValueEx(key, 'Publisher', 0, winreg.REG_SZ, APP_NAME)
    winreg.CloseKey(key)


def copy_tree_preserve_db(src_dir, dst_dir):
    os.makedirs(dst_dir, exist_ok=True)
    for root, dirs, files in os.walk(src_dir):
        dirs.sort()
        files.sort()
        rel_root = os.path.relpath(root, src_dir)
        current_dst = dst_dir if rel_root == '.' else os.path.join(dst_dir, rel_root)
        os.makedirs(current_dst, exist_ok=True)
        for name in files:
            src_file = os.path.join(root, name)
            dst_file = os.path.join(current_dst, name)
            if name.lower() == 'articles.db' and os.path.exists(dst_file):
                continue
            shutil.copy2(src_file, dst_file)


def perform_install(install_dir, launch_after=False):
    archive_path = resource_path(ARCHIVE_NAME)
    uninstaller_payload = resource_path(UNINSTALLER_NAME)
    if not os.path.exists(archive_path):
        raise RuntimeError('未找到安装载荷文件')
    if not os.path.exists(uninstaller_payload):
        raise RuntimeError('未找到卸载程序载荷')

    temp_dir = os.path.join(os.environ.get('TEMP', install_dir), APP_NAME + '_setup_extract')
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)
    os.makedirs(temp_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(archive_path, 'r') as zf:
            zf.extractall(temp_dir)

        payload_root = os.path.join(temp_dir, APP_NAME)
        if not os.path.exists(payload_root):
            raise RuntimeError('安装包结构异常')

        copy_tree_preserve_db(payload_root, install_dir)
        shutil.copy2(uninstaller_payload, os.path.join(install_dir, UNINSTALLER_NAME))

        exe_path = os.path.join(install_dir, APP_EXE_NAME)
        icon_path = os.path.join(install_dir, 'folpaper.ico')
        create_shortcut(desktop_shortcut_path(), exe_path, icon_path, install_dir)
        create_shortcut(start_menu_shortcut_path(), exe_path, icon_path, install_dir)
        register_uninstall_info(install_dir)

        if launch_after:
            os.startfile(exe_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


class InstallerWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_NAME + ' 安装程序')
        # Remove hardcoded geometry to allow auto-sizing to fit all widgets perfectly
        # self.root.geometry('560x240')
        self.root.resizable(False, False)
        self.root.configure(bg='#f8fafc')
        self.path_var = tk.StringVar(value=default_install_dir())
        self.build_ui()
        
        # Center the window after it computes its required size
        self.root.update_idletasks()
        width = self.root.winfo_reqwidth()
        height = self.root.winfo_reqheight()
        
        # Ensure minimum sane dimensions
        width = max(width, 560)
        height = max(height, 280)
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def build_ui(self):
        wrapper = tk.Frame(self.root, bg='#f8fafc', padx=24, pady=24)
        wrapper.pack(fill='both', expand=True)

        title = tk.Label(wrapper, text=APP_NAME + ' 安装向导', font=('Microsoft YaHei UI', 18, 'bold'), bg='#f8fafc', fg='#1e293b')
        title.pack(anchor='w')

        desc = tk.Label(wrapper, text='安装后数据库将保存在安装目录下，卸载程序也会一并写入该目录。', font=('Microsoft YaHei UI', 10), bg='#f8fafc', fg='#475569')
        desc.pack(anchor='w', pady=(8, 20))

        row = tk.Frame(wrapper, bg='#f8fafc')
        row.pack(fill='x')

        entry = tk.Entry(row, textvariable=self.path_var, font=('Microsoft YaHei UI', 10), relief='solid', bd=1)
        entry.pack(side='left', fill='x', expand=True, ipady=7)

        browse_btn = tk.Button(row, text='浏览', command=self.choose_dir, bg='#e2e8f0', fg='#0f172a', relief='flat', padx=18, pady=8)
        browse_btn.pack(side='left', padx=(12, 0))

        tips = tk.Label(wrapper, text='建议安装到当前用户可写目录，例如默认路径。', font=('Microsoft YaHei UI', 9), bg='#f8fafc', fg='#64748b')
        tips.pack(anchor='w', pady=(12, 24))

        action_row = tk.Frame(wrapper, bg='#f8fafc')
        action_row.pack(fill='x', side='bottom')

        self.cancel_btn = tk.Button(action_row, text='取消', command=self.root.destroy, bg='#e2e8f0', fg='#0f172a', relief='flat', padx=18, pady=8)
        self.cancel_btn.pack(side='right')

        self.install_btn = tk.Button(action_row, text='安装', command=self.install, bg='#2563eb', fg='white', relief='flat', padx=22, pady=8)
        self.install_btn.pack(side='right', padx=(0, 12))

    def choose_dir(self):
        current_path = self.path_var.get().strip()
        initial_dir = os.path.dirname(current_path) if current_path else default_install_dir()
        selected = filedialog.askdirectory(initialdir=initial_dir)
        if selected:
            selected = os.path.normpath(selected)
            if os.path.basename(selected).lower() != APP_NAME.lower():
                selected = os.path.join(selected, APP_NAME)
            self.path_var.set(selected)

    def install(self):
        install_dir = self.path_var.get().strip()
        if not install_dir:
            messagebox.showerror('安装失败', '请选择安装目录')
            return

        install_dir = os.path.normpath(install_dir)
        if os.path.basename(install_dir).lower() != APP_NAME.lower():
            msg = f"您当前的安装路径为:\n{install_dir}\n\n建议将程序安装在独立的 {APP_NAME} 文件夹中，以防止文件分散。\n\n是否自动为您追加文件夹？\n\n点击“是”安装到: {os.path.join(install_dir, APP_NAME)}\n点击“否”继续安装到当前路径。"
            if messagebox.askyesno('安装路径确认', msg):
                install_dir = os.path.join(install_dir, APP_NAME)
                self.path_var.set(install_dir)

        self.install_btn.config(state='disabled', text='安装中...', bg='#94a3b8')
        self.cancel_btn.config(state='disabled')
        
        import threading
        
        def run_install():
            try:
                os.makedirs(install_dir, exist_ok=True)
                perform_install(install_dir, launch_after=False)
                self.root.after(0, self.on_install_success, install_dir)
            except Exception as exc:
                err_msg = f"{type(exc).__name__}: {str(exc)}\n\n(详细日志已保存至系统临时目录)"
                try:
                    import traceback
                    log_path = os.path.join(os.environ.get('TEMP', ''), 'folpaper_setup_error.log')
                    with open(log_path, 'w', encoding='utf-8') as f:
                        f.write(traceback.format_exc())
                except:
                    pass
                self.root.after(0, self.on_install_error, err_msg)

        threading.Thread(target=run_install, daemon=True).start()

    def on_install_success(self, install_dir):
        if messagebox.askyesno('安装成功', 'FolPaper 安装完成，是否立即启动程序？'):
            os.startfile(os.path.join(install_dir, APP_EXE_NAME))
        self.root.destroy()

    def on_install_error(self, err_msg):
        messagebox.showerror('安装失败', err_msg)
        self.install_btn.config(state='normal', text='安装', bg='#2563eb')
        self.cancel_btn.config(state='normal')

    def run(self):
        self.root.mainloop()


def cli_install():
    if '--silent-install' not in sys.argv:
        return False
    index = sys.argv.index('--silent-install')
    if index + 1 >= len(sys.argv):
        raise RuntimeError('缺少安装目录参数')
    install_dir = sys.argv[index + 1]
    perform_install(install_dir, launch_after='--launch' in sys.argv)
    return True


if __name__ == '__main__':
    try:
        if not cli_install():
            InstallerWindow().run()
    except Exception as exc:
        if '--silent-install' in sys.argv:
            log_path = os.path.join(os.environ.get('TEMP', os.getcwd()), 'folpaper_setup_error.log')
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(traceback.format_exc())
            raise
        ctypes.windll.user32.MessageBoxW(0, str(exc), APP_NAME + ' 安装失败', 0x10)
