@echo off
chcp 65001 >nul
echo 正在准备打包 FolPaper 安装版应用...
echo.

echo 正在执行打包流程，请稍候...
.\.venv\Scripts\python.exe build_release.py

echo.
echo 打包完成！
echo 您可以在 dist 目录下找到 FolPaper_Setup.exe
pause
