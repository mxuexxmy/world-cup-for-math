@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 936 >nul 2>&1
cd /d "%~dp0"
call "%~dp0_common.bat"

set "PORT=8000"
if exist "%ROOT%\.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%ROOT%\.env") do (
        if /i "%%a"=="PORT" set "PORT=%%b"
    )
)

echo.
echo ========================================
echo   世界杯赌神 - 关闭服务
echo ========================================
echo.

set "STOPPED=0"

taskkill /FI "WINDOWTITLE eq WorldCup-Math*" /F >nul 2>&1
if not errorlevel 1 (
    echo 已关闭 WorldCup-Math 服务窗口。
    set "STOPPED=1"
)

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
    wmic process where "ProcessId=%%p" get CommandLine 2>nul | findstr /i "run.py" >nul
    if not errorlevel 1 (
        taskkill /PID %%p /F >nul 2>&1
        if not errorlevel 1 (
            echo 已结束占用端口 %PORT% 的服务进程（PID %%p）。
            set "STOPPED=1"
        )
    )
)

if "!STOPPED!"=="0" (
    echo 未发现正在运行的服务（端口 %PORT% 无 run.py 进程）。
) else (
    echo.
    echo 服务已停止。需要使用时请双击「启动.bat」。
)

echo.
pause
exit /b 0
