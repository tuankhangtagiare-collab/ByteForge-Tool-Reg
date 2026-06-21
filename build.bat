@echo off
chcp 65001 >nul
title ByteForg Tool - Build EXE

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║        ByteForg Tool Reg Acc Discord - Build EXE        ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

:: Kiểm tra Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [LỖI] Python chưa được cài đặt!
    pause
    exit /b 1
)

:: Cài đặt PyInstaller nếu chưa có
echo [1/4] Kiểm tra PyInstaller...
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/4] Đang cài PyInstaller...
    pip install pyinstaller
) else (
    echo [1/4] PyInstaller đã có sẵn.
)

:: Cài dependencies
echo.
echo [2/4] Cài đặt thư viện từ requirements.txt...
pip install -r requirements.txt

:: Tạo thư mục models nếu chưa có
echo.
echo [3/4] Kiểm tra thư mục models...
if not exist "models" (
    mkdir models
    echo [THÔNG BÁO] Đã tạo thư mục models.
    echo [THÔNG BÁO] Hãy đặt file hcaptcha_classifier.onnx vào thư mục models.
)

:: Build EXE
echo.
echo [4/4] Đang build file EXE...
pyinstaller --onefile --console --name ByteForgDiscordReg ^
    --add-data "models;models" ^
    --add-data "config.json;." ^
    --add-data "proxy.txt;." ^
    --hidden-import colorama ^
    --hidden-import pydantic ^
    --hidden-import tls_client ^
    --hidden-import cv2 ^
    --hidden-import numpy ^
    --hidden-import onnxruntime ^
    main.py

if %errorlevel% equ 0 (
    echo.
    echo ╔══════════════════════════════════════════════════════════╗
    echo ║  BUILD THÀNH CÔNG!                                     ║
    echo ║  File EXE: dist\ByteForgDiscordReg.exe                 ║
    echo ╚══════════════════════════════════════════════════════════╝
    echo.
    echo LƯU Ý: Khi chạy EXE, cần có các file sau cùng thư mục:
    echo   - config.json
    echo   - proxy.txt
    echo   - models\hcaptcha_classifier.onnx (tùy chọn)
) else (
    echo.
    echo [LỖI] Build thất bại! Kiểm tra lỗi ở trên.
)

pause
