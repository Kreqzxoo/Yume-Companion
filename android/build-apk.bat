@echo off
setlocal
cd /d "%~dp0"
echo ==============================================
echo Yume Companion fuer Android - APK erstellen
echo ==============================================
echo Das Skript richtet bei Bedarf JDK, Android SDK und Gradle ein.
echo Dafuer werden Internetzugriff und mehrere GB freier Speicher benoetigt.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-apk.ps1"
if errorlevel 1 (
  echo.
  echo APK-Build fehlgeschlagen. Details stehen in build-apk.log.
  pause
  exit /b 1
)
echo.
echo Fertig: Yume-Companion.apk
pause
