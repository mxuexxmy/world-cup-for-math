"""Generate GBK-encoded Windows .bat launchers (cmd.exe on zh-CN Windows)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COMMON = r"""@echo off
REM Shared paths for Windows launcher scripts.
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "PY=%ROOT%\.venv\Scripts\python.exe"
set "PIP=%ROOT%\.venv\Scripts\pip.exe"
exit /b 0
"""

INSTALL = r"""@echo off
setlocal EnableExtensions
chcp 936 >nul 2>&1
cd /d "%~dp0"
call "%~dp0_common.bat"

echo.
echo ========================================
echo   世界杯赌神 - 首次安装
echo ========================================
echo.
echo 将创建虚拟环境、安装依赖、初始化数据库、
echo 构建历史数据集、训练模型、导入赛程数据。
echo 全程约需数分钟，请保持网络畅通。
echo.

set "PY_BOOT="

where py >nul 2>&1
if not errorlevel 1 goto try_py_launcher

where python >nul 2>&1
if not errorlevel 1 goto try_python

goto python_missing

:try_py_launcher
py -3 "%ROOT%\scripts\check_python.py" >nul 2>&1
if not errorlevel 1 set "PY_BOOT=py -3"
if defined PY_BOOT goto python_found
goto try_python

:try_python
python "%ROOT%\scripts\check_python.py" >nul 2>&1
if not errorlevel 1 set "PY_BOOT=python"
if defined PY_BOOT goto python_found
goto python_missing

:python_missing
echo [错误] 未找到 Python 3.10 或更高版本。
echo.
echo 请从 https://www.python.org/downloads/ 下载安装，
echo 安装时务必勾选 Add python.exe to PATH。
echo.
pause
exit /b 1

:python_found
echo [1/7] 创建虚拟环境 .venv ...
if exist "%PY%" (
    echo       虚拟环境已存在，跳过创建。
    goto step_install_deps
)

%PY_BOOT% -m venv "%ROOT%\.venv"
if errorlevel 1 (
    echo [错误] 创建虚拟环境失败。
    pause
    exit /b 1
)

:step_install_deps
echo [2/7] 安装 Python 依赖（可能需要几分钟）...
REM 清除失效代理（VPN/抓包软件残留会导致 pip ProxyError 10061）
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "http_proxy="
set "https_proxy="
set "ALL_PROXY="
set "all_proxy="

"%PIP%" install --proxy="" -r "%ROOT%\requirements.txt"
if errorlevel 1 (
    echo       官方源失败，尝试清华镜像 ...
    "%PIP%" install --proxy="" -r "%ROOT%\requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
)
if errorlevel 1 (
    echo       清华源失败，尝试阿里云镜像 ...
    "%PIP%" install --proxy="" -r "%ROOT%\requirements.txt" -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
)
if errorlevel 1 (
    echo [错误] 依赖安装失败。
    echo       若日志含 ProxyError，请关闭 VPN/系统代理后重试，
    echo       或在「设置 - 网络和 Internet - 代理」中关闭手动代理。
    pause
    exit /b 1
)

echo [3/7] 准备配置文件 .env ...
if not exist "%ROOT%\.env" (
    copy /Y "%ROOT%\.env.example" "%ROOT%\.env" >nul
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
"%PY%" "%ROOT%\data\historical\build_dataset.py"
if errorlevel 1 (
    echo [错误] 构建数据集失败。
    pause
    exit /b 1
)

echo [6/7] 训练预测模型（可能需要一两分钟）...
"%PY%" "%ROOT%\data\train_model.py"
if errorlevel 1 (
    echo [错误] 模型训练失败。
    pause
    exit /b 1
)

echo [7/7] 导入球队与赛程数据 ...
"%PY%" "%ROOT%\data\seed\seed_database.py"
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
exit /b 0
"""

START = r"""@echo off
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
"""

RESET = r"""@echo off
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
echo   世界杯赌神 - 重置赛程数据
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
"%PY%" "%ROOT%\data\seed\seed_database.py"
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
exit /b 0
"""

UPDATE = r"""@echo off
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
"""

STOP = r"""@echo off
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
"""

FILES = {
    "_common.bat": COMMON,
    "首次安装.bat": INSTALL,
    "启动.bat": START,
    "关闭.bat": STOP,
    "重置数据.bat": RESET,
    "更新模型.bat": UPDATE,
}


def write_gbk(path: Path, content: str) -> None:
    text = content.replace("\n", "\r\n")
    if not text.endswith("\r\n"):
        text += "\r\n"
    path.write_bytes(text.encode("gbk"))


def main() -> None:
    for name, content in FILES.items():
        path = ROOT / name
        write_gbk(path, content)
        print(f"wrote {name}")


if __name__ == "__main__":
    main()
