@echo off
chcp 65001 >nul
echo ==================================
echo   CommunityOS 一键安装
echo ==================================
echo.

:: 创建虚拟环境
if not exist venv (
    echo [1/4] 创建 Python 虚拟环境...
    python -m venv venv
) else (
    echo [1/4] 虚拟环境已存在，跳过
)

:: 安装依赖
echo [2/4] 安装 Python 依赖...
call venv\Scripts\activate.bat
pip install -r requirements.txt -q

:: 复制配置文件
echo [3/4] 复制配置文件...
if not exist .env (
    copy .env.example .env >nul
    echo   .env 已创建，请编辑填写必要配置
) else (
    echo   .env 已存在，跳过
)
if not exist config\shortcuts.json (
    copy config\shortcuts.example.json config\shortcuts.json >nul
    echo   shortcuts.json 已创建
) else (
    echo   shortcuts.json 已存在，跳过
)
if not exist config\keywords.json (
    copy config\keywords.example.json config\keywords.json >nul
    echo   keywords.json 已创建
) else (
    echo   keywords.json 已存在，跳过
)
if not exist config\runtime.json (
    copy config\runtime.example.json config\runtime.json >nul
    echo   runtime.json 已创建
) else (
    echo   runtime.json 已存在，跳过
)

echo [4/4] 完成！
echo.
echo 请编辑 .env 文件填写必要配置（OWNER、ADMINS、MANAGED_GROUPS 等）
echo 然后编辑 config\runtime.json 填写运营配置（GREETING_REPLY 等）
echo 然后运行 start.bat 启动机器人
pause
