@echo off
chcp 65001 >nul
title CAD Bridge - Muse
cd /d %~dp0
py --version >nul 2>&1
if errorlevel 1 (
  echo Khong thay Python.
  echo Cai Python tu https://www.python.org/downloads/ roi chay lai file nay.
  echo Khi cai nho tick "Add python.exe to PATH".
  pause
  exit /b 1
)
py -m pip install --quiet --disable-pip-version-check pyautocad comtypes
if errorlevel 1 (
  echo Cai pyautocad that bai. Kiem tra mang roi chay lai.
  pause
  exit /b 1
)
echo.
echo Dang chay cau noi AutoCAD...
echo Giu cua so nay mo trong luc dung. Bam Ctrl+C de dung.
py bridge.py
pause
