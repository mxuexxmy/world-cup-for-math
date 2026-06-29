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
echo   世界杯赌神 — 正在启动
echo ========================================
echo.
echo 启动后浏览器将自动打开；关闭「世界杯赌神-服务」窗口即可停止。
echo.

start "世界杯赌神-服务" /D "%~dp0" "%PY%" run.py

:: 等待服务就绪
timeout /t 3 /nobreak >nul

start "" "http://127.0.0.1:8000"

echo 已在浏览器打开 http://127.0.0.1:8000
echo 若页面未加载，请稍等几秒后手动刷新。
echo.
pause
