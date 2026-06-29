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
echo   世界杯赌神 - 更新预测模型
echo ========================================
echo.
echo 将重新构建历史赛果数据集并训练模型（约一两分钟）。
echo 不会改动数据库赛程，也不会修改 .env 配置。
echo.
set /p CONFIRM=确定继续？输入 Y 后回车: 
if /i not "%CONFIRM%"=="Y" (
    echo 已取消。
    pause
    exit /b 0
)

echo.
echo [1/2] 构建历史赛果数据集 ...
"%PY%" "%ROOT%\data\historical\build_dataset.py"
if errorlevel 1 (
    echo.
    echo [错误] 构建数据集失败。
    pause
    exit /b 1
)

echo [2/2] 训练预测模型 ...
"%PY%" "%ROOT%\data\train_model.py"
if errorlevel 1 (
    echo.
    echo [错误] 模型训练失败。
    pause
    exit /b 1
)

echo.
echo 模型已更新完成。若服务正在运行，请重启「启动.bat」使新模型生效。
echo.
pause
exit /b 0
