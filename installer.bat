@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
rem Optional branding (written by an external tool); defaults keep the original name.
set "BRAND_NAME=Soul of Waifu"
if exist "%~dp0app\configuration\branding_start.cmd" call "%~dp0app\configuration\branding_start.cmd"
title %BRAND_NAME% v2.5.3 Installer
color 0A

cd /d "%~dp0"
if not exist "logs" mkdir "logs" >nul 2>&1
set "LOG=%~dp0logs\installer.log"
set "FAILED="
set "OPTIONAL_FAILED="
rem Large downloads (PyTorch is ~2.5 GB) over slow or unstable lines: wait longer for data, retry and resume more often (pip defaults: 15 s, 5 tries)
set "PIP_TIMEOUT=120"
set "PIP_RETRIES=10"
set "PIP_RESUME_RETRIES=20"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
rem Version limits (constraints.txt): the newest releases of some packages (pandas 3.1, librosa 1.0, contourpy 1.4 ...) need NumPy 2, but the
rem packages that come with the program (faiss, rvc_python, fairseq) are built for NumPy 1.26 and then fail with
rem "numpy.core.multiarray failed to import". With the limits pip picks versions that work with NumPy 1.26.4.

rem (a PIP_CONSTRAINT variable would be split at every space of the install path, so the file is passed with -c and quotes; !PIPC! also survives "(x86)" in a path)
set "PIPC="
if exist "%~dp0constraints.txt" set PIPC=-c "%~dp0constraints.txt"
>"%LOG%" echo %BRAND_NAME% v2.5.3 installer log %DATE% %TIME%

rem Unattended mode (used by the Windows setup): installer.bat /auto cuda|cpu [flash]
set "AUTO=0"
set "AUTO_TORCH="
set "AUTO_FLASH=0"
if /I "%~1"=="/auto" (
    set "AUTO=1"
    set "AUTO_TORCH=%~2"
    if /I "%~3"=="flash" set "AUTO_FLASH=1"
)
rem Test hook: SOW_INSTALLER_DRYRUN=ok|fail only reports the received arguments.
if defined SOW_INSTALLER_DRYRUN (
    echo [dry-run] auto=%AUTO% torch=%AUTO_TORCH% flash=%AUTO_FLASH%
    echo dry-run auto=%AUTO% torch=%AUTO_TORCH% flash=%AUTO_FLASH% >>"%LOG%"
    if /I "%SOW_INSTALLER_DRYRUN%"=="fail" exit /b 1
    exit /b 0
)

echo Welcome to %BRAND_NAME% v2.5.3 Installer
echo Pip output is shown here; failed steps are listed at the end and in logs\installer.log
echo.

if not exist "app\data\" (
    echo INSTALLATION ERROR: Data folder was not found.
    echo You may not have downloaded the program through the Releases section. Please download the archive from there.
    pause
    exit /b 1
)

echo [1/8] Activating Miniconda3...
call app\data\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ACTIVATING ERROR: Failed to activate Miniconda3
    pause
    exit /b 1
)

echo [2/8] Activating virtual environment...
call app\data\Scripts\activate.bat sow
if %errorlevel% neq 0 (
    echo ACTIVATING ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

echo [3/8] Upgrading pip and installing PyTorch...
python -m pip install --upgrade pip setuptools wheel

if "%AUTO%"=="1" (
    if /I "%AUTO_TORCH%"=="cuda" (set "choice=1") else (set "choice=2")
) else (
    echo.
    echo ==============================================================
    echo Please select PyTorch installation:
    echo [1] CUDA ^(cu128^) - Recommended for NVIDIA GPU
    echo [2] CPU only
    echo ==============================================================
    set /p choice="Enter choice (1 or 2): "
)
set "TORCH_TRIES=0"
:torch_retry
set /a TORCH_TRIES+=1
if "%choice%"=="1" (
    echo Installing PyTorch with CUDA support... ^(attempt !TORCH_TRIES! of 4^)
    python -m pip install --no-cache-dir !PIPC! torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0 --index-url https://download.pytorch.org/whl/cu128
) else if "%choice%"=="2" (
    echo Installing PyTorch CPU... ^(attempt !TORCH_TRIES! of 4^)
    python -m pip install --no-cache-dir !PIPC! torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0
) else (
    echo Invalid choice.
    pause
    exit /b 1
)
if errorlevel 1 (
    if !TORCH_TRIES! LSS 4 (
        echo PyTorch download failed - trying again in 20 seconds...
        echo PyTorch attempt !TORCH_TRIES! failed, retrying>>"%LOG%"
        ping -n 21 127.0.0.1 >nul
        goto :torch_retry
    )
    echo.
    echo PyTorch could not be installed ^(see messages above^). Everything else depends on it - stopping.
    echo PyTorch install failed after 4 attempts - see logs\installer_console.log>>"%LOG%"
    pause
    exit /b 1
)

echo [4/8] Installing core dependencies (with version pins)...

call :pipi --force-reinstall numpy==1.26.4

call :pipi PyQt6==6.9.0 PyQt6-WebEngine==6.9.0 qasync==0.27.1
call :pipi beautifulsoup4 mss
call :pipi ddgs pypdf python-docx
call :pipi discord.py PyNaCl davey
call :pipi pypresence
call :pipi pyautogui playwright
python -m playwright install chromium
if errorlevel 1 (
    set "FAILED=!FAILED! [playwright-chromium]"
    echo playwright chromium failed>>"%LOG%"
)
call :pipi sentence-transformers==5.1.0
call :pipi openai==1.70.0 mistralai==1.5.0
call :pipi edge-tts==7.2.7 elevenlabs==1.52.0 kokoro==0.9.4
call :pipi qwen-tts
call :pipi faster-whisper
call :pipi curl_cffi
call :pipi translators==6.0.1 psutil==7.0.0 GPUtil==1.4.0
call :pipi sounddevice==0.5.1 soundfile==0.13.1 pydub==0.25.1
call :pipi PyOpenGL==3.1.9 live2d-py==0.5.4
call :pipi scikit-learn==1.4.2 aiohttp==3.11.13 requests==2.32.3
call :pipi tiktoken==0.11.0 PyYAML==6.0.2 pillow==11.3.0 ipython==9.4.0

call :pipi huggingface-hub==0.36.0 hf_transfer==0.1.9
call :pipi transformers==4.57.3

call :pipi av praat-parselmouth scipy==1.13.1
call :pipi python-multipart PyAudio tensorboardX qrcode
call :pipi antlr4-python3-runtime==4.9.3 portalocker==3.2.0

echo [5/8] Installing Coqui TTS / XTTSv2 and RVC support...
call :pipi coqui-tts[codec]
call :pipi pyworld torchcrepe uvicorn omegaconf==2.3.0
call :pipi --force-reinstall torchcodec==0.10.0

echo [6/8] Installing WebRTC AEC3 (echo cancellation, optional)...
python -m pip install --no-cache-dir !PIPC! pywebrtc-audio==0.2.0
if errorlevel 1 (
    set "OPTIONAL_FAILED=!OPTIONAL_FAILED! [WebRTC-AEC3: SoW falls back to half-duplex echo protection]"
    echo pywebrtc-audio failed>>"%LOG%"
)

echo [7/8] Optional: FlashAttention-2 for faster Qwen3-TTS...
if not "%choice%"=="1" (
    echo Skipped ^(needs the CUDA PyTorch build^).
) else if "%AUTO%"=="1" (
    if "%AUTO_FLASH%"=="1" ( call :install_flash ) else ( echo Skipped ^(not selected in the setup^). )
) else (
    echo FlashAttention-2 is a prebuilt community wheel ^(Windows, Python 3.11, PyTorch 2.10, CUDA 12.8^).
    echo SoW works without it; it may speed up Qwen3-TTS by roughly 15-25 percent.
    rem Confirmed automatically after 10 seconds; press N to skip.
    choice /C YN /T 10 /D Y /M "Install FlashAttention-2 now? Downloads about 250 MB"
    if not errorlevel 2 call :install_flash
)

echo [8/8] Final checks...
rem Safety net: if any package still replaced NumPy by version 2, put 1.26.4 back (faiss / RVC would not start otherwise)
python -c "import numpy,sys; sys.exit(0 if numpy.__version__.startswith('1.26') else 1)" || python -m pip install --no-cache-dir --force-reinstall --no-deps numpy==1.26.4
python -c "import numpy, faiss; print('NumPy', numpy.__version__, '+ faiss OK')" || set "FAILED=!FAILED! [numpy-faiss-import-test]"
python -m pip check
python -c "import torch, numpy, transformers, PyQt6; print('Core imports OK')"
if errorlevel 1 set "FAILED=!FAILED! [core-import-test]"
python -c "from TTS.api import TTS; print('Coqui TTS import OK')" || echo WARNING: Coqui TTS import failed - possible version conflict!
python -c "import requests, PIL, psutil, aiohttp; print('Vision plugin requirements OK')" || set "FAILED=!FAILED! [vision-requirements]"

echo.
echo =====================================================
if defined FAILED (
    echo Installation finished WITH PROBLEMS in:
    echo   !FAILED!
    echo Run installer.bat again, or check logs\installer.log
) else (
    echo Installation completed successfully!
)
if defined OPTIONAL_FAILED (
    echo Optional components that were not installed:
    echo   !OPTIONAL_FAILED!
)
echo If there are warnings from pip check - RVC and Coqui may have minor conflicts.
echo =====================================================
if "%AUTO%"=="1" (
    rem Unattended: the Windows setup decides what happens next; report the result via the exit code.
    if defined FAILED ( exit /b 1 ) else ( exit /b 0 )
)
echo [1] Start the program
echo [2] Exit
set /p post_install_choice="Enter your choice: "
if "%post_install_choice%"=="1" (
    call start.bat
) else (
    echo Exiting.
    pause
)
exit /b 0


:pipi
rem Installs the given pip arguments; records failures instead of silently continuing.
python -m pip install --no-cache-dir !PIPC! %*
if errorlevel 1 (
    set "FAILED=!FAILED! [%*]"
    echo pip failed: %* >>"%LOG%"
)
exit /b 0


:install_flash
rem Pinned community build, verified by SHA-256 before it is installed.
set "FA_NAME=flash_attn-2.8.3+cu128torch2.10-cp311-cp311-win_amd64.whl"
set "FA_URL=https://huggingface.co/Pakaho-q1/window-wheel_store/resolve/main/flash_attn-2.8.3/flash_attn-2.8.3%%2Bcu128torch2.10-cp311-cp311-win_amd64.whl"
set "FA_SHA256=ae6b7d34c79afbf84d9b63a0b48d384fae1961e04d69153d49b198a4afff9c98"
set "FA_FILE=%~dp0logs\%FA_NAME%"

python -c "import sys, torch; sys.exit(0 if torch.__version__.startswith('2.10') and (torch.version.cuda or '').startswith('12.8') else 1)"
if errorlevel 1 (
    echo FlashAttention-2 skipped: installed PyTorch is not 2.10 with CUDA 12.8.
    set "OPTIONAL_FAILED=!OPTIONAL_FAILED! [FlashAttention-2: PyTorch version mismatch]"
    exit /b 0
)
echo Downloading %FA_NAME% ...
curl.exe -L --fail -o "%FA_FILE%" "%FA_URL%"
if errorlevel 1 (
    echo Download failed ^(a DNS filter or firewall may block huggingface.co / *.hf.co^).
    set "OPTIONAL_FAILED=!OPTIONAL_FAILED! [FlashAttention-2: download failed]"
    del "%FA_FILE%" >nul 2>&1
    exit /b 0
)
set "FA_HASH="
for /f "skip=1 tokens=*" %%H in ('certutil -hashfile "%FA_FILE%" SHA256') do if not defined FA_HASH set "FA_HASH=%%H"
set "FA_HASH=!FA_HASH: =!"
if /I not "!FA_HASH!"=="%FA_SHA256%" (
    echo Checksum mismatch - the file is NOT installed.
    echo Expected %FA_SHA256%
    echo Got      !FA_HASH!
    set "OPTIONAL_FAILED=!OPTIONAL_FAILED! [FlashAttention-2: checksum mismatch]"
    del "%FA_FILE%" >nul 2>&1
    exit /b 0
)
python -m pip install --no-deps "%FA_FILE%"
if errorlevel 1 (
    set "OPTIONAL_FAILED=!OPTIONAL_FAILED! [FlashAttention-2: pip install failed]"
    del "%FA_FILE%" >nul 2>&1
    exit /b 0
)
python -c "import flash_attn; print('FlashAttention-2', flash_attn.__version__, 'OK')"
if errorlevel 1 (
    echo flash_attn does not import with this setup - removing it again.
    python -m pip uninstall -y flash-attn
    set "OPTIONAL_FAILED=!OPTIONAL_FAILED! [FlashAttention-2: import failed]"
)
del "%FA_FILE%" >nul 2>&1
exit /b 0
