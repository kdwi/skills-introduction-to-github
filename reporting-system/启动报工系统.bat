@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PORT=8010"
if not "%~1"=="" set "PORT=%~1"

echo ==================================================
echo              钣金车间扫码报工系统
echo ==================================================
echo.

if not exist "server.py" (
    echo [错误] 找不到 server.py
    echo        请确认本文件与 server.py 在同一个文件夹内。
    echo.
    pause
    exit /b 1
)

set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [错误] 未检测到 Python。
    echo        请先安装 Python 3.8 或更高版本，安装时务必勾选
    echo        "Add Python to PATH"，然后重新双击本文件。
    echo        下载地址: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo [1/3] 检查运行依赖...
%PY% -c "import qrcode" >nul 2>nul
if errorlevel 1 (
    echo       正在安装 qrcode，请稍候...
    %PY% -m pip install qrcode -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [警告] qrcode 安装失败，二维码生成功能将不可用。
    )
)
%PY% -c "import openpyxl" >nul 2>nul
if errorlevel 1 (
    echo       正在安装 openpyxl，请稍候...
    %PY% -m pip install openpyxl -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [警告] openpyxl 安装失败，重新提取流程卡数据时将不可用。
    )
)

set "LANIP="
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    if not defined LANIP (
        for /f "tokens=* delims= " %%b in ("%%a") do set "LANIP=%%b"
    )
)

if defined LANIP (
    if exist "tools\generate_qr.py" (
        echo [2/3] 按本机 IP %LANIP% 刷新报工二维码...
        %PY% tools\generate_qr.py http://%LANIP%:%PORT% >nul 2>nul
        if errorlevel 1 (
            echo       二维码刷新失败，可稍后手动运行 tools\generate_qr.py
        ) else (
            echo       已更新 qr 文件夹内的二维码。
        )
    ) else (
        echo       未找到 tools\generate_qr.py，跳过二维码刷新。
    )
) else (
    echo [2/3] 未获取到局域网 IP，跳过二维码刷新。
)

echo.
echo [3/3] 访问地址：
echo       本机报工页   http://127.0.0.1:%PORT%/
echo       管理看板     http://127.0.0.1:%PORT%/admin
if defined LANIP (
    echo       手机报工页   http://%LANIP%:%PORT%/
    echo       手机需与本机连接同一 WiFi / 局域网。
)
echo.
echo       若手机打不开，请在 Windows 防火墙中允许 Python 访问网络。
echo       服务运行期间请勿关闭本窗口，按 Ctrl+C 可停止。
echo ==================================================
echo.

start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:%PORT%/'"
%PY% server.py %PORT%

echo.
echo 服务已停止。
pause
