# Yume Companion for Android - builds the APK. Sets up JDK, Android SDK and Gradle on demand.
# Usage: build-apk.ps1 [-Release]   (debug-signed APK; fine for installing on your own phone)
param([switch]$SkipPublish, [switch]$Release)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$CacheRoot = Join-Path $env:LOCALAPPDATA 'YumeAndroidBuild'
$SdkRoot = if ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } elseif ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
$LogPath = Join-Path $ProjectRoot 'build-apk.log'
New-Item -ItemType Directory -Force -Path $CacheRoot, $SdkRoot | Out-Null
"Yume Android APK Builder`r`nStarted: $(Get-Date -Format o)`r`nProject: $ProjectRoot`r`nSDK: $SdkRoot`r`n" | Set-Content -Encoding UTF8 $LogPath

function Say([string]$m) { Write-Host "`n==> $m" -ForegroundColor Cyan; Add-Content -Encoding UTF8 -Path $LogPath -Value "`r`n==> $m" }
function Get-File([string]$Url, [string]$Path) {
    if (-not (Test-Path $Path)) { Say "Download: $Url"; Invoke-WebRequest -Uri $Url -OutFile $Path -UseBasicParsing }
}
# Runs a program with its own stdin/stdout handling (java -version writes to stderr, sdkmanager wants "y" answers)
function Invoke-Tool([string]$File, [string[]]$Arguments, [string]$InputText = $null) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $File
    $psi.Arguments = ($Arguments | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' '
    $psi.UseShellExecute = $false; $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
    $psi.RedirectStandardInput = ($null -ne $InputText); $psi.CreateNoWindow = $true
    $p = [System.Diagnostics.Process]::Start($psi)
    $outTask = $p.StandardOutput.ReadToEndAsync(); $errTask = $p.StandardError.ReadToEndAsync()
    if ($null -ne $InputText) { $p.StandardInput.Write($InputText); $p.StandardInput.Close() }
    $p.WaitForExit()
    $text = $outTask.Result + $errTask.Result
    Add-Content -Encoding UTF8 -Path $LogPath -Value $text
    [pscustomobject]@{ ExitCode = $p.ExitCode; Output = $text }
}

# ---- JDK 17+ (the real home directory, not the Windows "javapath" shim)
$JavaHome = $null
$candidates = @($env:JAVA_HOME, 'C:\Program Files\Android\Android Studio\jbr', 'C:\Program Files\Java\jdk-21', 'C:\Program Files\Java\jdk-17') | Where-Object { $_ }
$pathJava = Get-Command java.exe -ErrorAction SilentlyContinue
if ($pathJava) {
    $r = Invoke-Tool $pathJava.Source @('-XshowSettings:properties', '-version')
    if ($r.Output -match 'java\.home = (.+)') { $candidates += $Matches[1].Trim() }
}
foreach ($c in ($candidates | Select-Object -Unique)) {
    $exe = Join-Path $c 'bin\java.exe'
    if (Test-Path $exe) {
        $v = Invoke-Tool $exe @('-version')
        if ($v.Output -match 'version "(\d+)' -and [int]$Matches[1] -ge 17) { $JavaHome = $c; break }
    }
}
if (-not $JavaHome) {
    $zip = Join-Path $CacheRoot 'temurin-jdk21.zip'
    Get-File 'https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse' $zip
    $dst = Join-Path $CacheRoot 'jdk'
    if (-not (Test-Path $dst)) { Say 'Entpacke JDK 21'; Expand-Archive -Path $zip -DestinationPath $dst -Force }
    $found = Get-ChildItem $dst -Filter java.exe -Recurse | Where-Object { $_.FullName -match '\\bin\\java\.exe$' } | Select-Object -First 1
    if (-not $found) { throw 'JDK 21 wurde entpackt, aber java.exe fehlt.' }
    $JavaHome = Split-Path (Split-Path $found.FullName -Parent) -Parent
}
$env:JAVA_HOME = $JavaHome
$env:PATH = (Join-Path $JavaHome 'bin') + ';' + $env:PATH
Say "Java: $JavaHome"

# ---- Android command line tools + SDK 36
$SdkManager = Join-Path $SdkRoot 'cmdline-tools\latest\bin\sdkmanager.bat'
if (-not (Test-Path $SdkManager)) {
    $zip = Join-Path $CacheRoot 'commandlinetools-win.zip'
    Get-File 'https://dl.google.com/android/repository/commandlinetools-win-15859902_latest.zip' $zip
    $tmp = Join-Path $CacheRoot 'cmdline-extract'
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $latest = Join-Path $SdkRoot 'cmdline-tools\latest'
    New-Item -ItemType Directory -Force (Split-Path $latest -Parent) | Out-Null
    if (Test-Path $latest) { Remove-Item $latest -Recurse -Force }
    Move-Item (Join-Path $tmp 'cmdline-tools') $latest
}
$env:ANDROID_HOME = $SdkRoot; $env:ANDROID_SDK_ROOT = $SdkRoot
if (-not (Test-Path (Join-Path $SdkRoot 'platforms\android-36')) -or -not (Test-Path (Join-Path $SdkRoot 'build-tools\36.0.0'))) {
    Say 'Android SDK 36 wird installiert (einige hundert MB)'
    $yes = ('y' + "`n") * 80
    [void](Invoke-Tool $SdkManager @("--sdk_root=$SdkRoot", '--licenses') $yes)
    $r = Invoke-Tool $SdkManager @("--sdk_root=$SdkRoot", 'platforms;android-36', 'build-tools;36.0.0', 'platform-tools') $yes
    if ($r.ExitCode -ne 0) { throw "SDK-Installation fehlgeschlagen (Exit $($r.ExitCode)); siehe build-apk.log" }
}
# local.properties for Gradle
"sdk.dir=$($SdkRoot -replace '\\', '\\')" | Set-Content -Encoding ASCII (Join-Path $ProjectRoot 'local.properties')

# ---- Gradle 8.13
$GradleBat = Join-Path $CacheRoot 'gradle-8.13\bin\gradle.bat'
if (-not (Test-Path $GradleBat)) {
    $zip = Join-Path $CacheRoot 'gradle-8.13-bin.zip'
    Get-File 'https://services.gradle.org/distributions/gradle-8.13-bin.zip' $zip
    $tmp = Join-Path $CacheRoot 'gradle-extract'
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Say 'Entpacke Gradle 8.13'
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    Move-Item (Join-Path $tmp 'gradle-8.13') (Join-Path $CacheRoot 'gradle-8.13')
}

# ---- build
$env:YUME_BUILD_ROOT = $CacheRoot      # build output outside the (OneDrive-synced) source folder
$BuiltApk = Join-Path $CacheRoot $(if ($Release) { 'out\app\outputs\apk\release\app-release.apk' } else { 'out\app\outputs\apk\debug\app-debug.apk' })
if (Test-Path $BuiltApk) { Remove-Item $BuiltApk -Force }
Say 'Baue die APK (der erste Lauf dauert einige Minuten) ...'
Push-Location $ProjectRoot
try { $g = Invoke-Tool $GradleBat @('--no-daemon', '--console=plain', '--project-cache-dir', (Join-Path $CacheRoot 'projcache'), $(if ($Release) { 'assembleRelease' } else { 'assembleDebug' })) } finally { Pop-Location }
Write-Host $g.Output
if ($g.ExitCode -ne 0 -or -not (Test-Path $BuiltApk)) { throw 'Gradle-Build fehlgeschlagen (keine neue APK). Details: build-apk.log' }
$Final = Join-Path $CacheRoot 'Yume-Companion.apk'
Copy-Item $BuiltApk $Final -Force
Say "FERTIG: $Final ($([math]::Round((Get-Item $Final).Length / 1MB, 1)) MB)"
if (-not $SkipPublish) {
    $main = Get-ChildItem (Split-Path $ProjectRoot -Parent) -Directory -Filter 'Yume Companion*MAIN' -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
    if ($main -and (Test-Path (Join-Path $main 'main.py'))) {
        $dest = Join-Path $main 'tools\android'
        New-Item -ItemType Directory -Force $dest | Out-Null
        Copy-Item $Final (Join-Path $dest 'Yume-Companion.apk') -Force
        Say "Kopiert nach $dest (Yume Companion bietet die APK im Android Connector zum Speichern an)"
    }
}
