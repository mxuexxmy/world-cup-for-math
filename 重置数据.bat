@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"

if not exist "%PY%" (
    echo.
    echo [提示] 尚未安装，请先双击运行「首次安装.bat」。
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   世界杯赌神 — 重置赛程数据
echo ========================================
echo.
echo 将重新从种子文件导入球队、赛程等数据。
echo 不会删除已训练好的 model.pkl，也不会改动 .env 配置。
echo.
set /p CONFIRM=确定继续？输入 Y 后回车: 
if /i not "%CONFIRM%"=="Y" (
    echo 已取消。
    pause
    exit /b 0
)

echo.
echo 正在导入数据 ...
"%PY%" data\seed\seed_database.py
if errorlevel 1 (
    echo.
    echo [错误] 导入失败。
    pause
    exit /b 1
)

echo.
echo 数据已重新导入完成。
echo.
pause
