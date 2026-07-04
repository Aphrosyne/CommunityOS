@echo off
chcp 65001 >nul
echo CommunityOS 启动中...
call venv\Scripts\activate.bat
python main.py
pause
