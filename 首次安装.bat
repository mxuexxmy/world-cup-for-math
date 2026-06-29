@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ========================================
echo   世界杯赌神 — 首次安装
echo ========================================
echo.
echo 本脚本将：创建虚拟环境、安装依赖、初始化数据库、
echo 构建历史数据集、训练模型、导入赛程数据。
echo 全程约需数分钟，请保持网络畅通。
echo.

:: 检测 Python（优先 Windows 启动器 py -3）
set "PY_CMD="
where py >nul 2>&1
if %errorlevel%==0 (
    py -3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if !errorlevel!==0 set "PY_CMD=py -3"
)
if not defined PY_CMD (
    where python >nul 2>&1
    if %errorlevel%==0 (
        python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
        if !errorlevel!==0 set "PY_CMD=python"
    )
)
if not defined PY_CMD (
    echo [错误] 未找到 Python 3.10 或更高版本。
    echo.
    echo 请从 https://www.python.org/downloads/ 下载安装，
    echo 安装时务必勾选「Add python.exe to PATH」。
    echo.
    pause
    exit /b 1
)

echo [1/7] 创建虚拟环境 .venv ...
if not exist ".venv\Scripts\python.exe" (
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败。
        pause
        exit /b 1
    )
) else (
    echo       虚拟环境已存在，跳过创建。
)

set "PY=%~dp0.venv\Scripts\python.exe"
set "PIP=%~dp0.venv\Scripts\pip.exe"

echo [2/7] 安装 Python 依赖（可能需要几分钟）...
"%PIP%" install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败。
    pause
    exit /b 1
)

echo [3/7] 准备配置文件 .env ...
if not exist ".env" (
    copy /Y ".env.example" ".env" >nul
    echo       已从 .env.example 复制生成 .env
) else (
    echo       .env 已存在，跳过。
)

echo [4/7] 数据库迁移 ...
"%PY%" -m alembic upgrade head
if errorlevel 1 (
    echo [错误] 数据库迁移失败。
    pause
    exit /b 1
)

echo [5/7] 构建历史赛果数据集 ...
"%PY%" data\historical\build_dataset.py
if errorlevel 1 (
    echo [错误] 构建数据集失败。
    pause
    exit /b 1
)

echo [6/7] 训练预测模型（可能需要一两分钟）...
"%PY%" data\train_model.py
if errorlevel 1 (
    echo [错误] 模型训练失败。
    pause
    exit /b 1
)

echo [7/7] 导入球队与赛程数据 ...
"%PY%" data\seed\seed_database.py
if errorlevel 1 (
    echo [错误] 导入种子数据失败。
    pause
    exit /b 1
)

echo.
echo ========================================
echo   安装完成！
echo ========================================
echo.
echo 以后请双击「启动.bat」打开应用。
echo.
pause
