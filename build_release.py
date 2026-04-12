import os
import shutil
import sqlite3
import subprocess
import zipfile

from PIL import Image

from database import DatabaseManager


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(ROOT_DIR, 'dist')
BUILD_DIR = os.path.join(ROOT_DIR, 'build')
ICON_PNG = os.path.join(ROOT_DIR, 'ico', 'favicon (1).png')
ICON_ICO = os.path.join(ROOT_DIR, 'ico', 'folpaper.ico')
SOURCE_DB = os.path.join(ROOT_DIR, 'articles.db')
SEED_DB = os.path.join(BUILD_DIR, 'folpaper_seed.db')
PAYLOAD_ZIP = os.path.join(BUILD_DIR, 'FolPaper_package.zip')
APP_NAME = 'FolPaper'
APP_DIST_DIR = os.path.join(DIST_DIR, APP_NAME)
APP_EXE = os.path.join(APP_DIST_DIR, 'FolPaper.exe')
UNINSTALLER_EXE = os.path.join(DIST_DIR, 'FolPaper_Uninstall.exe')
SETUP_EXE = os.path.join(DIST_DIR, 'FolPaper_Setup.exe')
PYTHON_EXE = os.path.join(ROOT_DIR, 'venv_new', 'Scripts', 'python.exe')


def ensure_python():
    if not os.path.exists(PYTHON_EXE):
        raise RuntimeError('未找到 venv_new 的 Python 解释器')


def run_command(args):
    print('执行命令:', ' '.join(args))
    subprocess.run(args, cwd=ROOT_DIR, check=True)


def ensure_clean_path(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)


def clean_old_artifacts():
    os.makedirs(BUILD_DIR, exist_ok=True)
    for path in [
        APP_DIST_DIR,
        UNINSTALLER_EXE,
        SETUP_EXE,
        PAYLOAD_ZIP,
        SEED_DB,
        os.path.join(BUILD_DIR, 'FolPaper'),
        os.path.join(BUILD_DIR, 'FolPaper_Uninstall'),
        os.path.join(BUILD_DIR, 'FolPaper_Setup'),
    ]:
        ensure_clean_path(path)


def build_icon():
    if not os.path.exists(ICON_PNG):
        raise RuntimeError('未找到图标 PNG 文件')
    image = Image.open(ICON_PNG).convert('RGBA')
    image.save(
        ICON_ICO,
        format='ICO',
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    return ICON_ICO


def read_current_config():
    config = {}
    if not os.path.exists(SOURCE_DB):
        return config
    conn = sqlite3.connect(SOURCE_DB)
    try:
        rows = conn.execute('SELECT key, value FROM config').fetchall()
        for key, value in rows:
            config[key] = value or ''
    finally:
        conn.close()
    return config


def build_seed_db():
    ensure_clean_path(SEED_DB)
    db = DatabaseManager(SEED_DB)
    current_config = read_current_config()
    for key, value in current_config.items():
        if 'key' in (key or '').lower():
            db.set_config(key, '')
        else:
            db.set_config(key, value)
    if not current_config.get('base_url'):
        db.set_config('base_url', 'https://api.openai.com/v1')
    if not current_config.get('model'):
        db.set_config('model', 'gpt-3.5-turbo')
    db.set_config('api_key', '')


def build_app(icon_path):
    command = [
        PYTHON_EXE,
        '-m',
        'PyInstaller',
        '--noconfirm',
        '--clean',
        '--onedir',
        '--name',
        APP_NAME,
        '--icon',
        icon_path,
        '--add-data',
        'templates;templates',
        'app.py',
    ]
    run_command(command)
    shutil.copy2(SEED_DB, os.path.join(APP_DIST_DIR, 'articles.db'))
    shutil.copy2(icon_path, os.path.join(APP_DIST_DIR, 'folpaper.ico'))


def make_payload_zip():
    ensure_clean_path(PAYLOAD_ZIP)
    with zipfile.ZipFile(PAYLOAD_ZIP, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(APP_DIST_DIR):
            dirs.sort()
            files.sort()
            for name in files:
                abs_path = os.path.join(root, name)
                rel_path = os.path.relpath(abs_path, DIST_DIR)
                zf.write(abs_path, rel_path)


def build_uninstaller(icon_path):
    command = [
        PYTHON_EXE,
        '-m',
        'PyInstaller',
        '--noconfirm',
        '--clean',
        '--onefile',
        '--windowed',
        '--name',
        'FolPaper_Uninstall',
        '--icon',
        icon_path,
        'uninstaller.py',
    ]
    run_command(command)


def build_setup(icon_path):
    command = [
        PYTHON_EXE,
        '-m',
        'PyInstaller',
        '--noconfirm',
        '--clean',
        '--onefile',
        '--windowed',
        '--name',
        'FolPaper_Setup',
        '--icon',
        icon_path,
        '--add-data',
        PAYLOAD_ZIP + ';.',
        '--add-data',
        UNINSTALLER_EXE + ';.',
        'installer.py',
    ]
    run_command(command)


def verify_outputs():
    required_files = [
        APP_EXE,
        os.path.join(APP_DIST_DIR, 'articles.db'),
        os.path.join(APP_DIST_DIR, 'folpaper.ico'),
        UNINSTALLER_EXE,
        SETUP_EXE,
    ]
    missing = [path for path in required_files if not os.path.exists(path)]
    if missing:
        raise RuntimeError('缺少打包产物: ' + ' | '.join(missing))


def main():
    ensure_python()
    clean_old_artifacts()
    icon_path = build_icon()
    build_seed_db()
    build_app(icon_path)
    make_payload_zip()
    build_uninstaller(icon_path)
    build_setup(icon_path)
    verify_outputs()
    print('打包完成')
    print('应用目录:', APP_DIST_DIR)
    print('安装包:', SETUP_EXE)


if __name__ == '__main__':
    main()
