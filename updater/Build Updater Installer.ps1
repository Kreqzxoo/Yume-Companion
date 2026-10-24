# Builds the installer of the Yume Release Tool itself: compiles the launcher exe, then runs Inno Setup.
param([string]$Version = '1.0.0')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$iscc = @((Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'), (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'), (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw 'Inno Setup 6 nicht gefunden.' }
Write-Output 'Kompiliere Launcher ...'
& $csc /nologo /target:winexe /optimize+ '/out:Yume Updater.exe' '/win32icon:installer_build\setup_icon.ico' /reference:System.Windows.Forms.dll YumeUpdaterLauncher.cs
if ($LASTEXITCODE -ne 0) { throw 'Launcher-Kompilierung fehlgeschlagen.' }
Write-Output 'Baue Installer ...'
& $iscc /Q "/DAppVersion=$Version" yume_updater_setup.iss
if ($LASTEXITCODE -ne 0) { throw 'ISCC fehlgeschlagen.' }
$exe = Get-ChildItem (Join-Path (Split-Path $PSScriptRoot -Parent) 'Yume Updater Setup') -Filter "Yume-Updater-Setup-$Version.exe" | Select-Object -First 1
Write-Output ("FERTIG: {0} ({1:N1} MB)" -f $exe.FullName, ($exe.Length / 1MB))
