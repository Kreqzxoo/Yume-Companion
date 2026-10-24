@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0\.."
title Soul of Waifu Studio - Stimme, GPUs, Branding und Deutsch

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import PyQt6, yaml" >nul 2>&1
  if not errorlevel 1 (
    ".venv\Scripts\python.exe" "tools\sow_studio.py"
    goto :end
  )
)
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" -c "import PyQt6, yaml" >nul 2>&1
  if not errorlevel 1 (
    "venv\Scripts\python.exe" "tools\sow_studio.py"
    goto :end
  )
)

py -3 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3 wurde nicht gefunden. Installiere Python 3.11 oder 3.12 fuer Windows.
  echo https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
if not exist ".sow-studio-venv\Scripts\python.exe" py -3 -m venv ".sow-studio-venv"
if errorlevel 1 goto :error
".sow-studio-venv\Scripts\python.exe" -c "import PyQt6, yaml" >nul 2>&1
if errorlevel 1 (
  echo Installiere PyQt6 und PyYAML in einer separaten SOW-Studio-Umgebung...
  ".sow-studio-venv\Scripts\python.exe" -m pip install --upgrade pip || goto :error
  ".sow-studio-venv\Scripts\python.exe" -m pip install PyQt6 PyYAML || goto :error
)
".sow-studio-venv\Scripts\python.exe" "tools\sow_studio.py"
goto :end

:error
echo Studio konnte nicht eingerichtet werden. Pruefe Python, Internetverbindung und Rechte.
pause
exit /b 1
:end
endlocal
