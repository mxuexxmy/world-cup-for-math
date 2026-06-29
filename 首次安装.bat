@echo off
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
