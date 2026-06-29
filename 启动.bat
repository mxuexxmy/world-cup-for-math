@echo off
setlocal EnableExtensions
chcp 936 >nul 2>&1
cd /d "%~dp0"
call "%~dp0_common.bat"

if not exist "%PY%" (
    echo.
    echo [提示] 尚未安装，请先双击运行「首次安装.bat」。
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   世界杯赌神 - 正在启动
echo ========================================
echo.
echo 启动后浏览器将自动打开。
echo 也可双击「关闭.bat」停止服务。
echo.

start "WorldCup-Math" /D "%ROOT%" "%PY%" "%ROOT%\run.py"

ping -n 4 127.0.0.1 >nul
start "" "http://127.0.0.1:8000"

echo 已在浏览器打开 http://127.0.0.1:8000
echo 若页面未加载，请稍等几秒后手动刷新。
echo.
pause
exit /b 0
