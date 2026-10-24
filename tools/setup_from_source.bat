@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
rem ---------------------------------------------------------------------------------------------
rem  Yume Companion aus dem Quelltext einrichten (fuer alle, die NICHT das fertige Setup nutzen).
rem  Legt im Projektordner an:  app\data (Miniconda) + Umgebung "sow" (Python 3.11) + app\ffmpeg
rem  laedt die zwei kleinen Modelle und startet danach installer.bat (Pakete).
rem  Nicht als Administrator ausfuehren. Der Pfad des Ordners darf keine Leerzeichen enthalten.
rem ---------------------------------------------------------------------------------------------
cd /d "%~dp0\.."
set "ROOT=%CD%"
set "PY=%ROOT%\app\data\envs\sow\python.exe"

if not "%ROOT%"=="%ROOT: =%" (
    echo FEHLER: Der Ordnerpfad enthaelt Leerzeichen: %ROOT%
    echo Verschiebe das Projekt z. B. nach C:\Yume-Companion und starte dieses Skript erneut.
    pause & exit /b 1
)

echo [1/5] Miniconda ...
if exist "app\data\Scripts\activate.bat" (
    echo       schon vorhanden.
) else (
    curl.exe -L --fail -o "%TEMP%\yume-miniconda.exe" https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe
    if errorlevel 1 ( echo FEHLER: Download von Miniconda fehlgeschlagen. & pause & exit /b 1 )
    start /wait "" "%TEMP%\yume-miniconda.exe" /InstallationType=JustMe /RegisterPython=0 /AddToPath=0 /S /D=%ROOT%\app\data
    del "%TEMP%\yume-miniconda.exe" >nul 2>&1
    if not exist "app\data\Scripts\activate.bat" ( echo FEHLER: Miniconda wurde nicht installiert. & pause & exit /b 1 )
)

echo [2/5] Python-Umgebung "sow" (Python 3.11) ...
if exist "%PY%" (
    echo       schon vorhanden.
) else (
    call "app\data\Scripts\activate.bat"
    call conda create -y -n sow -c conda-forge --override-channels python=3.11
    if errorlevel 1 ( echo FEHLER: Die Umgebung konnte nicht angelegt werden. & pause & exit /b 1 )
)

echo [3/5] FFmpeg (Audio und Video) ...
if exist "app\ffmpeg\bin\ffmpeg.exe" (
    echo       schon vorhanden.
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$ErrorActionPreference='Stop'; $z=Join-Path $env:TEMP 'yume-ffmpeg.zip'; $d=Join-Path $env:TEMP 'yume-ffmpeg';" ^
      "Invoke-WebRequest 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile $z;" ^
      "if (Test-Path $d) { Remove-Item $d -Recurse -Force }; Expand-Archive $z $d;" ^
      "$bin=(Get-ChildItem $d -Recurse -Filter ffmpeg.exe | Select-Object -First 1).Directory.FullName;" ^
      "New-Item -ItemType Directory -Force 'app\ffmpeg\bin' | Out-Null; Copy-Item (Join-Path $bin '*') 'app\ffmpeg\bin' -Force;" ^
      "Remove-Item $z,$d -Recurse -Force"
    if not exist "app\ffmpeg\bin\ffmpeg.exe" ( echo FEHLER: FFmpeg konnte nicht eingerichtet werden. & pause & exit /b 1 )
)

echo [4/5] Kleine Modelle laden (Einbettung und Gefuehle, ca. 430 MB) ...
"%PY%" -m pip install --quiet huggingface-hub==0.36.0
"%PY%" "%ROOT%\tools\fetch_models.py"
if errorlevel 1 ( echo Hinweis: Die Modelle konnten nicht geladen werden. Spaeter erneut: "%PY%" tools\fetch_models.py )

echo [5/5] Pakete installieren (dauert lange, PyTorch hat ca. 2,5 GB) ...
echo       Am Ende fragt installer.bat, ob das Programm gestartet werden soll.
call installer.bat

echo.
echo Fertig. Start mit start.bat. Beispiel-Charaktere: "%PY%" tools\demo\make_demo_content.py
pause
