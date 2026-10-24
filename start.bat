@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
rem Optional branding (written by an external tool); defaults keep the original look.
set "BRAND_NAME=Soul of Waifu"
set "BRAND_TAGLINE=— Soul Continuum"
set "BRAND_BANNER="
if exist "%~dp0app\configuration\branding_start.cmd" call "%~dp0app\configuration\branding_start.cmd"
title %BRAND_NAME% v3.0.0 BETA — AI Roleplay App

for /f %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
set "C_RESET=%ESC%[0m"
set "C_BOLD=%ESC%[1m"
set "C_DIM=%ESC%[90m"
set "C_CYAN=%ESC%[38;2;75;184;255m"
set "C_PURPLE=%ESC%[38;2;167;139;250m"
set "C_MINT=%ESC%[38;2;74;222;128m"
set "C_RED=%ESC%[38;2;248;113;113m"
set "C_GOLD=%ESC%[38;2;251;191;36m"
set "C_WHITE=%ESC%[97m"

cls
echo.
if defined BRAND_BANNER if exist "%BRAND_BANNER%" goto :BANNER_CUSTOM
echo %C_CYAN%  ███████╗ ██████╗ ██╗   ██╗██╗        ██████╗ ███████╗    ██╗    ██╗ █████╗ ██╗███████╗██╗   ██╗%C_RESET%
echo %C_CYAN%  ██╔════╝██╔═══██╗██║   ██║██║       ██╔═══██╗██╔════╝    ██║    ██║██╔══██╗██║██╔════╝██║   ██║%C_RESET%
echo %C_CYAN%  ███████╗██║   ██║██║   ██║██║       ██║   ██║█████╗      ██║ █╗ ██║███████║██║█████╗  ██║   ██║%C_RESET%
echo %C_CYAN%  ╚════██║██║   ██║██║   ██║██║       ██║   ██║██╔══╝      ██║███╗██║██╔══██║██║██╔══╝  ██║   ██║%C_RESET%
echo %C_CYAN%  ███████║╚██████╔╝╚██████╔╝███████╗  ╚██████╔╝██║         ╚███╔███╔╝██║  ██║██║██║     ╚██████╔╝%C_RESET%
echo %C_DIM%  ╚══════╝ ╚═════╝  ╚═════╝ ╚══════╝   ╚═════╝ ╚═╝          ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝╚═╝      ╚═════╝ %C_RESET%
goto :BANNER_DONE
:BANNER_CUSTOM
for /f "usebackq delims=" %%L in ("%BRAND_BANNER%") do echo %C_CYAN%  %%L%C_RESET%
:BANNER_DONE
echo.
echo %C_WHITE%   %BRAND_NAME% %C_PURPLE%v3.0.0 BETA%C_WHITE% %BRAND_TAGLINE% %C_RESET%
echo %C_DIM%  ──────────────────────────────────────────────────────────────────────────────────────────%C_RESET%
echo.

cd /d "%~dp0"
echo   %C_CYAN%[%C_WHITE%1/4%C_CYAN%]%C_RESET% %C_WHITE%Initializing workspace...%C_RESET%
echo         %C_DIM%Working Directory:%C_RESET% %C_DIM%%cd%%C_RESET%
echo         %C_MINT%✓%C_RESET% Directory confirmed.
echo.

echo   %C_CYAN%[%C_WHITE%2/4%C_CYAN%]%C_RESET% %C_WHITE%Configuring FFmpeg media pipelines...%C_RESET%
set FFMPEG_PATH=%cd%\app\ffmpeg\bin
set PATH=%FFMPEG_PATH%;%PATH%

ffmpeg -version >nul 2>&1
if errorlevel 1 goto :FFMPEG_ERROR

echo         %C_MINT%✓%C_RESET% FFmpeg core active and verified.
echo.

echo   %C_CYAN%[%C_WHITE%3/4%C_CYAN%]%C_RESET% %C_WHITE%Mounting isolated runtime environment...%C_RESET%
if not exist "app\data\Scripts\activate.bat" goto :VENV_ERROR

call app\data\Scripts\activate.bat app/data/envs/sow >nul 2>&1
echo         %C_MINT%✓%C_RESET% Environment loaded: %C_PURPLE%Python 3.11+ / PyTorch / PyQt6%C_RESET%
echo.

echo   %C_CYAN%[%C_WHITE%4/4%C_CYAN%]%C_RESET% %C_WHITE%Starting %BRAND_NAME% Core Runtime...%C_RESET%
echo         %C_DIM%Launching interface (main.py)...%C_RESET%
echo.
echo %C_DIM%  ──────────────────────────────────────────────────────────────────────────────────────────%C_RESET%
echo %C_MINT%   ⚡ App running. Logs streamed to /logs directory.%C_RESET%
echo.

python main.py
set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% EQU 0 goto :CLEAN_EXIT
if %EXIT_CODE% EQU -1073741510 goto :CLEAN_EXIT
if %EXIT_CODE% EQU 3221225786 goto :CLEAN_EXIT
goto :CRASH_EXIT


:CLEAN_EXIT
echo.
echo %C_DIM%  ──────────────────────────────────────────────────────────────────────────────────────────%C_RESET%
echo %C_MINT%   ✓ Application closed gracefully. Memory cache and sessions saved.%C_RESET%
echo %C_PURPLE%   ✨ Thank you for using %BRAND_NAME%. See you next time.%C_RESET%
echo.
echo   %C_DIM%Press any key to close this window...%C_RESET%
pause >nul
exit /b 0

:CRASH_EXIT
echo.
echo %C_RED%  ==========================================================================================%C_RESET%
echo %C_RED%   ✕ APPLICATION TERMINATED WITH CODE: %EXIT_CODE%%C_RESET%
echo %C_RED%  ==========================================================================================%C_RESET%
echo.
echo    %C_GOLD%Possible causes:%C_RESET%
echo     • Missing dependency or corrupted Python package in virtualenv.
echo     • GPU VRAM Out-of-Memory or backend driver crash.
echo     • Permission restrictions or third-party antivirus intervention.
echo.
echo    %C_CYAN%➜ Check detailed crash traceback in:%C_RESET% %C_WHITE%logs/%C_RESET%
echo.
echo   %C_DIM%Press any key to close this window...%C_RESET%
pause >nul
exit /b %EXIT_CODE%

:FFMPEG_ERROR
echo         %C_RED%✕ CRITICAL ERROR: FFmpeg binaries not detected!%C_RESET%
echo.
echo         %C_GOLD%┌─────────────────────────────────────────────────────────────┐%C_RESET%
echo         %C_GOLD%│%C_RESET%  Please ensure %C_WHITE%app\ffmpeg\bin%C_RESET% contains:                    %C_GOLD%│%C_RESET%
echo         %C_GOLD%│%C_RESET%   • %C_CYAN%ffmpeg.exe%C_RESET%    • %C_CYAN%ffprobe.exe%C_RESET%    • %C_CYAN%ffplay.exe%C_RESET%             %C_GOLD%│%C_RESET%
echo         %C_GOLD%│%C_RESET%  FFmpeg is required for voice synthesis and audio playback. %C_GOLD%│%C_RESET%
echo         %C_GOLD%└─────────────────────────────────────────────────────────────┘%C_RESET%
echo.
echo   %C_DIM%Press any key to exit...%C_RESET%
pause >nul
exit /b 1

:VENV_ERROR
echo         %C_RED%✕ Virtual environment script not found in app\data\Scripts!%C_RESET%
echo.
echo   %C_DIM%Press any key to exit...%C_RESET%
pause >nul
exit /b 1