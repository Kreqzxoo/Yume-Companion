# Builds YumeLLMServer.exe (C# 5, no SDK needed) and, if Inno Setup 6 is installed, the installer.
param([string]$Version = '1.0.0', [switch]$NoInstaller)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location $root
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) { throw 'csc.exe (.NET Framework 4) wurde nicht gefunden.' }
New-Item -ItemType Directory -Force build | Out-Null
$icon = Join-Path $root 'build\yume.ico'
if (-not (Test-Path $icon)) { Copy-Item (Join-Path $root '..\assets\custom_branding\yume_app.ico') $icon }
$refs = 'System.Windows.Forms.dll', 'System.Drawing.dll', 'System.Management.dll', 'System.IO.Compression.dll', 'System.IO.Compression.FileSystem.dll', 'System.Core.dll'
$argsList = @('/nologo', '/target:winexe', '/optimize+', '/out:build\YumeLLMServer.exe', "/win32icon:$icon") + ($refs | ForEach-Object { "/reference:$_" }) + @('src\YumeLlmServer.cs')
& $csc @argsList
if ($LASTEXITCODE -ne 0) { throw 'Kompilieren fehlgeschlagen.' }
Write-Host 'YumeLLMServer.exe gebaut.' -ForegroundColor Green
# Code signing (optional): environment variable YUME_SIGN_CMD = signing command, "$f" stands for the file, e.g.
#   signtool.exe sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /n "Your Name" "$f"
$signCmd = $env:YUME_SIGN_CMD
if ($signCmd) {
    # through a small .cmd file: quotes inside the command survive that, but not an argument of "cmd /c" started from PowerShell
    $bat = Join-Path $env:TEMP 'yume_sign.cmd'
    Set-Content -Path $bat -Value ("@echo off`r`n" + $signCmd.Replace('$f', (Join-Path $root 'build\YumeLLMServer.exe'))) -Encoding ASCII
    & $bat
    $signCode = $LASTEXITCODE
    Remove-Item $bat -Force -ErrorAction SilentlyContinue
    if ($signCode -ne 0) { throw 'Signieren von YumeLLMServer.exe fehlgeschlagen.' }
    Write-Host 'YumeLLMServer.exe signiert.' -ForegroundColor Green
}
if ($NoInstaller) { return }
$iscc = @((Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'), (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'), (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { Write-Warning 'Inno Setup 6 nicht gefunden - nur die Exe wurde gebaut.'; return }
$out = Join-Path $root 'dist'
New-Item -ItemType Directory -Force $out | Out-Null
$isccArgs = @("/DAppVersion=$Version", '/Q')
if ($signCmd) { $isccArgs += @('/DSign=1', "/Syume=$signCmd") }
& $iscc @isccArgs 'installer\yume_llm_server.iss'
if ($LASTEXITCODE -ne 0) { throw 'ISCC fehlgeschlagen.' }
$latest = Get-ChildItem (Join-Path $out 'Yume-LLM-Server-Setup-*.exe') | Sort-Object LastWriteTime -Descending | Select-Object -First 1
# hand the installer to Yume Companion (its settings offer it as a download button for other PCs)
$main = Join-Path $root '..'
if (Test-Path $main) {
    $dest = Join-Path $main 'tools\server'
    New-Item -ItemType Directory -Force $dest | Out-Null
    Copy-Item $latest.FullName (Join-Path $dest 'Yume-LLM-Server-Setup.exe') -Force
    Write-Host ('Kopiert nach ' + $dest) -ForegroundColor Green
}
Write-Host ("Installer: {0} ({1:N1} MB)" -f $latest.FullName, ($latest.Length / 1MB)) -ForegroundColor Green
