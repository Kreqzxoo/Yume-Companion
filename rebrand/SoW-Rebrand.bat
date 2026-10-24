@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title SoW Rebrand

rem Python lookup: python_path.txt (one line, path to python.exe), else the SoW folder
rem one level up, else system Python.
set "PY="
if exist "python_path.txt" set /p PY=<python_path.txt
if not defined PY set "PY=..\app\data\envs\sow\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
  echo PyQt6 wurde nicht gefunden. Starte dieses Programm mit dem Python eines SoW-Ordners
  echo oder trage in python_path.txt den Pfad zu einer python.exe mit PyQt6 ein.
  pause
  exit /b 1
)
"%PY%" sow_rebrand.py %*
if errorlevel 1 pause
