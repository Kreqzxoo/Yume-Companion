# Yume Build - scans the working folder (MAIN), strips everything that installer.bat or the app creates
# (installed Python packages, caches, logs, user data), stages a clean copy and builds the setup exe.
# Called by "Yume Release Tool.ps1"; can also be run by hand:
#   powershell -File "Yume Build.ps1" -Version 2.5.4-beta1 -Mode Update|Full [-OutDir <folder>] [-Launcher] [-NoPatch] [-KeepStage]
#
# The original folder is only READ. Everything (version change, clean-up, tests) happens in a copy.
param(
    [Parameter(Mandatory = $true)][string]$Version,
    [ValidateSet('Update', 'Full')][string]$Mode = 'Update',
    [string]$Source = 'C:\Pfad\zu\Yume-Companion',
    [string]$Stage = (Join-Path $env:USERPROFILE 'YumeStage'),
    [string]$OutDir = 'C:\Pfad\zu\Ausgabe',
    [switch]$Launcher,
    [switch]$NoPatch,
    [switch]$KeepStage,       # keep the temporary copy after the build (default: it is deleted)
    [switch]$Verify,          # before the build: reset check, syntax, imports (abort on failure)
    [switch]$VerifyInstall,   # after the build: silent test installation of the exe (own AppId, deleted afterwards)
    [switch]$VerifySmoke,     # after the build: start the program headless, render every page
    [switch]$VerifyAI,        # after the build: tiny model through the shipped llama.cpp backend + provider
    [switch]$VerifyDeps       # Full only: REAL installation incl. installer.bat (CPU torch, several GB), then import + start test with the installed environment
)
$ErrorActionPreference = 'Stop'
# installer_build (Inno script, wizard images, templates, launcher source) lives next to this script
$BuildDir = Join-Path $PSScriptRoot 'installer_build'
if (-not (Test-Path (Join-Path $BuildDir 'yume_setup.iss'))) { Write-Output "FEHLER: installer_build fehlt neben dem Updater: $BuildDir"; exit 1 }
$ModelDir = Join-Path $env:LOCALAPPDATA 'Yume Updater\testmodel'
$Iscc = @((Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'), (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'), (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')) | Where-Object { Test-Path $_ } | Select-Object -First 1
$Csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$Templates = Join-Path $BuildDir 'templates'

function Say($m) { Write-Output $m }
# The wizard picture has "Version x.y.z" painted into it. For every build a copy with the real version number is made (the originals stay untouched):
# the old text is wiped with the (purely vertical) background gradient, the new one is drawn at the same place.
function New-WizardImages($Version, $OutDir) {
    Add-Type -AssemblyName System.Drawing
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
    foreach ($spec in @(@{ File = 'wizard_large.bmp'; Y0 = 224; Y1 = 258; Px = 12 }, @{ File = 'wizard_large_2x.bmp'; Y0 = 448; Y1 = 516; Px = 24 })) {
        $src = Join-Path $BuildDir $spec.File
        $img = [System.Drawing.Bitmap]::FromFile($src)
        try {
            $bmp = New-Object System.Drawing.Bitmap $img.Width, $img.Height, ([System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
            $g = [System.Drawing.Graphics]::FromImage($bmp)
            $g.DrawImage($img, 0, 0, $img.Width, $img.Height)
            # colour of the old text = the brightest pixel in its rows
            $best = $null; $bestL = -1
            for ($y = $spec.Y0; $y -lt $spec.Y1; $y++) { for ($x = 8; $x -lt $img.Width - 8; $x += 1) { $c = $img.GetPixel($x, $y); $l = $c.R + $c.G + $c.B; if ($l -gt $bestL) { $bestL = $l; $best = $c } } }
            for ($y = $spec.Y0; $y -lt $spec.Y1; $y++) {
                $bg = $img.GetPixel(3, $y)
                $pen = New-Object System.Drawing.SolidBrush $bg
                $g.FillRectangle($pen, 0, $y, $img.Width, 1)
                $pen.Dispose()
            }
            $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
            $font = New-Object System.Drawing.Font('Segoe UI', [single]$spec.Px, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
            $brush = New-Object System.Drawing.SolidBrush $best
            $fmt = New-Object System.Drawing.StringFormat
            $fmt.Alignment = [System.Drawing.StringAlignment]::Center; $fmt.LineAlignment = [System.Drawing.StringAlignment]::Center
            $rect = New-Object System.Drawing.RectangleF 0, $spec.Y0, $img.Width, ($spec.Y1 - $spec.Y0)
            $g.DrawString("Version $Version", $font, $brush, $rect, $fmt)
            $g.Dispose()
            $bmp.Save((Join-Path $OutDir $spec.File), [System.Drawing.Imaging.ImageFormat]::Bmp)
            $bmp.Dispose()
        } finally { $img.Dispose() }
    }
    foreach ($f in 'wizard_small.bmp', 'wizard_small_2x.bmp') { Copy-Item (Join-Path $BuildDir $f) (Join-Path $OutDir $f) -Force }
}

function SizeMB($path) {
    if (-not (Test-Path $path)) { return 0 }
    $s = (Get-ChildItem $path -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    return [math]::Round($s / 1MB)
}
function Fail($m) { Say "FEHLER: $m"; exit 1 }

# only one build at a time: the temporary copy and the test folders are shared
$script:buildLock = New-Object System.Threading.Mutex($false, 'Global\YumeReleaseToolBuild')
try { $gotLock = $script:buildLock.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $gotLock = $true }
if (-not $gotLock) { Fail 'Ein anderer Build laeuft bereits (gemeinsame Arbeitskopie). Bitte warten, bis er fertig ist, und dann neu starten.' }
if (-not (Test-Path (Join-Path $Source 'main.py'))) { Fail "main.py nicht gefunden in $Source" }
if (-not $Iscc) { Fail "Inno Setup nicht gefunden (weder pro Benutzer noch in Programme)" }

# fingerprint of the original folder (without the big Python environment and run data) - proves it stays untouched
function Get-Fingerprint($root) {
    $skip = @('app\data\', '\logs\', 'app\cache\', '\Backups\', '\backups\', '\.soul', '__pycache__', '\.git\')
    $files = Get-ChildItem $root -Recurse -File -Force -ErrorAction SilentlyContinue | Where-Object {
        $p = $_.FullName.Substring($root.Length)
        -not ($skip | Where-Object { $p.Contains($_) }) }
    $sum = ($files | Measure-Object Length -Sum).Sum
    $newest = ($files | Measure-Object LastWriteTimeUtc -Maximum).Maximum.Ticks
    return "{0}|{1}|{2}" -f $files.Count, $sum, $newest
}
$fingerprintBefore = Get-Fingerprint $Source

# ------------------------------------------------------------------ 1. version strings (applied to the COPY, see below)
$Targets = @(
    @('VERSION.txt',                      '^{OLD}',                             '{NEW}'),
    @('installer.bat',                    'v{OLD}',                             'v{NEW}'),
    @('start.bat',                        'v{OLD}',                             'v{NEW}'),
    @('main.py',                          '(\{_brand_name\} v){OLD}',           '${1}{NEW}'),
    @('main.py',                          '(current_version = "v){OLD}',        '${1}{NEW}'),
    @('app\gui\custom_widgets.py',        '(QLabel\("v){OLD}("\))',             '${1}{NEW}${2}'),
    @('app\utils\backup_manager.py',      '(APP_VERSION = "){OLD}"',            '${1}{NEW}"'),
    @('app\utils\integrations\home_assistant.py', '(SoulOfWaifu/){OLD}',        '${1}{NEW}')
)
function Read-Text($path) {
    $bytes = [IO.File]::ReadAllBytes($path)
    $bom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    $enc = New-Object System.Text.UTF8Encoding($bom)
    $skip = if ($bom) { 3 } else { 0 }
    return @{ Text = $enc.GetString($bytes, $skip, $bytes.Length - $skip); Enc = $enc }
}
function Set-Version($root, $oldVersion, $newVersion) {
    $oldRx = [regex]::Escape($oldVersion)
    foreach ($tg in $Targets) {
        $path = Join-Path $root $tg[0]
        if (-not (Test-Path $path)) { Say "  uebersprungen (fehlt): $($tg[0])"; continue }
        $r = Read-Text $path
        $rx = New-Object System.Text.RegularExpressions.Regex($tg[1].Replace('{OLD}', $oldRx), 'Multiline')
        if ($rx.IsMatch($r.Text)) {
            [IO.File]::WriteAllText($path, $rx.Replace($r.Text, $tg[2].Replace('{NEW}', $newVersion)), $r.Enc)
            Say "  angepasst: $($tg[0])"
        } else { Say "  nichts gefunden in $($tg[0])" }
    }
}
Say '=== 1/5 Version'
$vf = Join-Path $Source 'VERSION.txt'
$old = if (Test-Path $vf) { (Get-Content $vf -Raw).Trim() } else { '' }
if ($NoPatch -or -not $old -or $old -eq $Version) { Say "Version bleibt: $old" }
else { Say "Version $old -> $Version wird nur in der Arbeitskopie gesetzt (Originalordner bleibt unveraendert)." }

# ------------------------------------------------------------------ 2. scan / analysis
Say '=== 2/5 Analyse des Arbeitsordners'
$envSow = Join-Path $Source 'app\data\envs\sow'
$remove = @(
    @{ Name = 'Installierte Python-Pakete (installer.bat: torch, TTS, ...)'; Path = "$envSow\Lib\site-packages" },
    @{ Name = 'Pip-Startdateien der Umgebung (Scripts\*.exe)';               Path = "$envSow\Scripts" },
    @{ Name = 'Conda-Paketcache';                                            Path = (Join-Path $Source 'app\data\pkgs') },
    @{ Name = 'Programm-Cache (Avatare, Icon-Cache, Boot-Datei)';            Path = (Join-Path $Source 'app\cache') },
    @{ Name = 'Heruntergeladene Modelle / HF-Cache';                         Path = (Join-Path $Source 'app\models') },
    @{ Name = 'Heruntergeladene Vision-Modelle (assets\vision_models)';      Path = (Join-Path $Source 'assets\vision_models') },
    @{ Name = 'Lokale LLM-Modelle (assets\local_llm)';                       Path = (Join-Path $Source 'assets\local_llm') },
    @{ Name = 'Logdateien';                                                  Path = (Join-Path $Source 'logs') },
    @{ Name = 'Eigene Charaktere';                                           Path = (Join-Path $Source 'app\configuration\characters') },
    @{ Name = 'Spielstand-/Memory-Daten (.soul_stage, .soul)';               Path = (Join-Path $Source '.soul_stage') },
    @{ Name = 'Backups';                                                     Path = (Join-Path $Source 'backups') }
)
$total = 0
foreach ($r in $remove) {
    $mb = SizeMB $r.Path
    if ($mb -gt 0 -or (Test-Path $r.Path)) { Say ("  entfernt: {0,7:N0} MB  {1}" -f $mb, $r.Name); $total += $mb }
}
Say ("  zusaetzlich entfernt: unins000.*, __pycache__, *.pyc, *.log, persoenliche settings/api/characters (durch saubere Vorlagen ersetzt)")
Say ("  Summe entfernt (ohne Kleinteile): {0:N0} MB" -f $total)

# ------------------------------------------------------------------ 3. templates
Say '=== 3/5 Saubere Vorlagen'
$pyExe = Join-Path $envSow 'python.exe'
if (Test-Path $pyExe) {
    & $pyExe -I -B (Join-Path $Templates 'make_templates.py') $Source | ForEach-Object { Say "  $_" }
    if ($LASTEXITCODE -ne 0) { Say '  Vorlagen konnten nicht neu erzeugt werden - benutze vorhandene.' }
} else { Say '  keine Python-Umgebung im Arbeitsordner - benutze vorhandene Vorlagen.' }
foreach ($f in 'settings.json', 'settings_de.json', 'api.json', 'characters.json') {
    if (-not (Test-Path (Join-Path $Templates $f))) { Fail "Vorlage fehlt: $f" }
}

# ------------------------------------------------------------------ 4. stage a clean copy
Say '=== 4/5 Saubere Kopie erstellen (Staging)'
if ($Stage.Length -lt 12 -or $Stage -notlike 'C:\Users\*') { Fail "Stage-Pfad unplausibel: $Stage" }
if (Test-Path $Stage) {
    Say '  alte Kopie wird geloescht...'
    & cmd.exe /c rd /s /q "`"$Stage`"" | Out-Null
    if (Test-Path $Stage) { Fail "Staging-Ordner konnte nicht geloescht werden: $Stage" }
}
New-Item -ItemType Directory -Path $Stage | Out-Null
$xd = @("$envSow\Lib\site-packages", "$envSow\Scripts", (Join-Path $Source 'app\data\pkgs'), (Join-Path $Source 'app\cache'),
        (Join-Path $Source 'app\models'), (Join-Path $Source 'assets\vision_models'), (Join-Path $Source 'assets\local_llm'), (Join-Path $Source 'logs'), (Join-Path $Source 'app\configuration\characters'),
        (Join-Path $Source '.soul_stage'), (Join-Path $Source '.soul'), (Join-Path $Source 'app\data\.soul'), (Join-Path $Source 'backups'), '__pycache__', '.git')
$xf = @('unins000.dat', 'unins000.exe', '*.pyc', '*.log', 'boot_progress.txt', 'Yume Companion.exe',
        (Join-Path $Source 'app\configuration\settings.json'), (Join-Path $Source 'app\configuration\api.json'),
        (Join-Path $Source 'app\configuration\characters.json'), (Join-Path $Source 'app\configuration\android_devices.json'))
$rcArgs = @($Source, $Stage, '/E', '/R:1', '/W:1', '/NFL', '/NDL', '/NJH', '/NJS', '/NP', '/MT:8', '/XD') + $xd + @('/XF') + $xf
& robocopy.exe @rcArgs | Out-Null
if ($LASTEXITCODE -ge 8) { Fail "robocopy Exitcode $LASTEXITCODE" }

# slim environment: keep only pip/setuptools/wheel so "python -m pip" works for installer.bat
$spSrc = "$envSow\Lib\site-packages"; $spDst = Join-Path $Stage 'app\data\envs\sow\Lib\site-packages'
New-Item -ItemType Directory -Path $spDst -Force | Out-Null
$keep = '^(pip|setuptools|wheel|pkg_resources|_distutils_hack|distutils-precedence|packaging)(-|\.|$)'
if (Test-Path $spSrc) {
    foreach ($i in Get-ChildItem $spSrc -Force | Where-Object { $_.Name -match $keep }) {
        Copy-Item $i.FullName -Destination $spDst -Recurse -Force
    }
}
# packages that came with the original archive and are NOT installed by installer.bat (e.g. rvc_python, fairseq) stay in the copy
$deltaJson = Join-Path $env:TEMP 'yume_env_delta.json'
Remove-Item $deltaJson -ErrorAction SilentlyContinue
if (Test-Path $pyExe) {
    & $pyExe -B -s (Join-Path $BuildDir 'env_delta.py') (Join-Path $Source 'installer.bat') $deltaJson | ForEach-Object { Say "  Umgebungs-Analyse: $_" }
    if (Test-Path $deltaJson) {
        $delta = Get-Content $deltaJson -Raw | ConvertFrom-Json
        $kept = 0
        foreach ($e in $delta.keep_entries) {
            $from = Join-Path $spSrc $e
            if (Test-Path $from) { Copy-Item $from -Destination $spDst -Recurse -Force; $kept++ }
        }
        Say ("  Mitgelieferte Zusatzpakete (nicht von installer.bat installiert): {0}" -f (($delta.extras | ForEach-Object { "$($_.name) $($_.version)" }) -join ', '))
    } else { Say '  HINWEIS  Umgebungs-Analyse lieferte kein Ergebnis - Zusatzpakete wurden NICHT uebernommen.' }
}
$scDst = Join-Path $Stage 'app\data\envs\sow\Scripts'
New-Item -ItemType Directory -Path $scDst -Force | Out-Null
if (Test-Path "$envSow\Scripts") { Get-ChildItem "$envSow\Scripts" -File -Force | Where-Object { $_.Extension -in '.bat', '.cmd' } | Copy-Item -Destination $scDst -Force }
# empty folders the app expects
foreach ($d in 'logs', 'app\cache', 'app\models', 'assets\vision_models', 'assets\local_llm', 'app\configuration\characters') { New-Item -ItemType Directory -Path (Join-Path $Stage $d) -Force | Out-Null }
New-Item -ItemType File -Path (Join-Path $Stage 'logs\.gitkeep') -Force | Out-Null
# clean config templates
$cfgDir = Join-Path $Stage 'app\configuration'
foreach ($f in 'settings.json', 'api.json', 'characters.json') { Copy-Item (Join-Path $Templates $f) (Join-Path $cfgDir $f) -Force }

# version number in the copy only
if (-not $NoPatch -and $old -and $old -ne $Version) {
    Set-Version $Stage $old $Version
    Say "  Version in der Kopie: $old -> $Version"
}
# sanity checks on the staged copy
$stagePy = Join-Path $Stage 'app\data\envs\sow\python.exe'
if (Test-Path $stagePy) {
    $pv = & $stagePy -m pip --version 2>&1
    if ($LASTEXITCODE -ne 0) { Fail "pip funktioniert in der sauberen Kopie nicht: $pv" }
    Say "  Pruefung: $pv"
    $left = & $stagePy -m pip list --format=freeze 2>&1 | Where-Object { $_ -match '^(torch|TTS|numpy|PyQt6)=' }
    if ($left) { Fail "Unerwartet installierte Pakete in der Kopie: $left" }
} else { Fail 'python.exe fehlt in der sauberen Kopie (app\data\envs\sow).' }
foreach ($need in 'main.py', 'installer.bat', 'start.bat', 'VERSION.txt', 'app\data\Scripts\activate.bat') {
    if (-not (Test-Path (Join-Path $Stage $need))) { Fail "In der Kopie fehlt: $need" }
}
Say ("  Kopie fertig: {0:N0} MB (Arbeitsordner: {1:N0} MB)" -f (SizeMB $Stage), (SizeMB $Source))

# ------------------------------------------------------------------ 4b. checks on the clean copy (before the exe is built)
$VerifyPs1 = Join-Path $PSScriptRoot 'Yume Verify.ps1'
$checkPython = $pyExe
function Invoke-Verify($tree, [string[]]$flags, $py = $checkPython) {
    $out = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $VerifyPs1 -Tree $tree -Templates $Templates -Python $py -ModelDir $ModelDir -KeepFile $deltaJson @flags
    $code = $LASTEXITCODE
    $out | ForEach-Object { Write-Host $_ }
    return ($code -eq 0)
}
function Clean-Stage {
    # undo everything a test run may have left behind, so that the exe never ships run traces
    Get-ChildItem $Stage -Recurse -Directory -Force -Filter '__pycache__' -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notlike "$Stage\app\data\*" } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    foreach ($d in '.soul_stage', '.soul', 'Backups', 'backups', 'app\data\.soul') { Remove-Item (Join-Path $Stage $d) -Recurse -Force -ErrorAction SilentlyContinue }
    foreach ($d in 'app\cache', 'app\models', 'assets\vision_models', 'assets\local_llm', 'app\configuration\characters') {
        $p = Join-Path $Stage $d
        if (Test-Path $p) { Get-ChildItem $p -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue } else { New-Item -ItemType Directory -Path $p -Force | Out-Null }
    }
    Get-ChildItem (Join-Path $Stage 'logs') -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne '.gitkeep' } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    foreach ($f in 'settings.json', 'api.json', 'characters.json') { Copy-Item (Join-Path $Templates $f) (Join-Path $Stage "app\configuration\$f") -Force }
}
if ($Verify) {
    Say '=== Pruefung der sauberen Kopie (vor dem Bau)'
    if (-not (Test-Path $checkPython)) { Fail "Pruefung nicht moeglich: Python fehlt ($checkPython)" }
    $okPre = Invoke-Verify $Stage @('-Reset', '-Syntax', '-Imports')
    Clean-Stage
    if (-not $okPre) { Fail 'Pruefung der Kopie fehlgeschlagen - es wird keine Exe gebaut.' }
    Say '  Aufgeraeumt: Pruefreste (Cache, __pycache__, Logs) wurden wieder entfernt.'
    if (-not (Invoke-Verify $Stage @('-Reset'))) { Fail 'Die Kopie ist nach dem Aufraeumen nicht sauber - es wird keine Exe gebaut.' }
}

# ------------------------------------------------------------------ 5. launcher + setup
Say '=== 5/5 Setup erstellen'
if ($Launcher) {
    Say '  Kompiliere Launcher...'
    & $Csc /nologo /codepage:65001 /target:winexe /optimize+ "/out:$BuildDir\launcher\Yume Companion.exe" "/win32icon:$BuildDir\setup_icon.ico" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll "$BuildDir\launcher\YumeLauncher.cs" | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail 'Launcher-Kompilierung fehlgeschlagen.' }
}
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }
$wizDir = Join-Path $env:TEMP 'yume_wizard_images'
try { New-WizardImages $Version $wizDir; $wizArg = @("/DWizardDir=$wizDir") } catch { Say "  HINWEIS  Setup-Bild konnte nicht mit der Version beschriftet werden: $($_.Exception.Message)"; $wizArg = @() }
$isccArgs = @('/Q', "/DAppVersion=$Version", "/DSourceDir=$Stage", "/DOutDir=$OutDir") + $wizArg + @('yume_setup.iss')
if ($Mode -eq 'Update') { $isccArgs = @('/DUpdateOnly=1') + $isccArgs }
Push-Location $BuildDir
& $Iscc @isccArgs | ForEach-Object { Say "  $_" }
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { Fail "ISCC Exitcode $code" }
$kind = if ($Mode -eq 'Update') { 'Update' } else { 'Setup' }
$exe = Join-Path $OutDir "Yume-Companion-$kind-$Version.exe"
if (-not (Test-Path $exe)) { Fail "Ausgabedatei fehlt: $exe" }
Say ("FERTIG: {0}  ({1:N0} MB)" -f $exe, ((Get-Item $exe).Length / 1MB))

# ------------------------------------------------------------------ 6. checks of the delivered exe
$problems = 0
if ($VerifyDeps) { $VerifyInstall = $true }
if ($VerifyInstall -or $VerifySmoke -or $VerifyAI) {
    Say '=== Pruefung der gebauten Exe'
    if (-not (Test-Path $checkPython)) { Say "FEHLER: Python fuer die Pruefung fehlt ($checkPython)"; $problems++ }
    else {
        $treeToTest = $Stage
        $installDir = $null
        if ($VerifyInstall) {
            $testOut = Join-Path $env:TEMP 'yume_test_setup'
            Remove-Item $testOut -Recurse -Force -ErrorAction SilentlyContinue
            Say '  Baue Test-Setup (eigene AppId, keine Kompression, kein Eintrag in "Apps & Features") ...'
            $targs = @('/Q', '/DTestMode=1', "/DAppVersion=$Version", "/DSourceDir=$Stage", "/DOutDir=$testOut", 'yume_setup.iss')
            if ($Mode -eq 'Update') { $targs = @('/DUpdateOnly=1') + $targs }
            Push-Location $BuildDir; & $Iscc @targs | Out-Null; $tc = $LASTEXITCODE; Pop-Location
            $testExe = Get-ChildItem $testOut -Filter *.exe -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($tc -ne 0 -or -not $testExe) { Say 'FEHLER: Test-Setup konnte nicht gebaut werden.'; $problems++ }
            else {
                $installDir = Join-Path $env:USERPROFILE 'Yume Verify'
                if (Test-Path $installDir) { & cmd.exe /c rd /s /q "`"$installDir`"" | Out-Null }
                Say "  Installiere still nach $installDir ..."
                $depsArg = if ($VerifyDeps -and $Mode -eq 'Full') { @('/INSTALLDEPS=1', '/TORCH=cpu', '/FLASH=0') } else { @('/INSTALLDEPS=0') }
                if ($VerifyDeps -and $Mode -eq 'Full') { Say '  PRAXISTEST: echte Installation mit installer.bat (CPU-PyTorch) - das dauert 15-30 Minuten und laedt mehrere GB ...' }
                $ip = Start-Process -FilePath $testExe.FullName -ArgumentList (@('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOICONS', '/TASKS=""', "/DIR=`"$installDir`"") + $depsArg) -Wait -PassThru
                if ($ip.ExitCode -ne 0 -or -not (Test-Path (Join-Path $installDir 'main.py'))) { Say "FEHLER: Test-Installation fehlgeschlagen (Code $($ip.ExitCode))"; $problems++ }
                else {
                    Say '  OK       Setup laeuft still durch und installiert die Programmdateien'
                    foreach ($need in 'Yume Companion.exe', 'main.py', 'installer.bat', 'start.bat', 'VERSION.txt') {
                        if (-not (Test-Path (Join-Path $installDir $need))) { Say "  FEHLER   installierte Datei fehlt: $need"; $problems++ }
                    }
                    $installedVersion = (Get-Content (Join-Path $installDir 'VERSION.txt') -Raw).Trim()
                    if ($installedVersion -eq $Version -or $installedVersion -eq ($Version -replace '-.*$', '') -or $Version -like "$installedVersion*") { Say "  OK       installierte Version: $installedVersion" }
                    else { Say "  HINWEIS  installierte Version $installedVersion, gebaut als $Version" }
                    $realDeps = ($VerifyDeps -and $Mode -eq 'Full')
                    if (-not (Invoke-Verify $installDir $(if ($realDeps) { @('-Reset', '-DepsInstalled') } else { @('-Reset') }))) { $problems++ }
                    if ($Mode -eq 'Full') { $treeToTest = $installDir }
                    if ($realDeps) {
                        $instPy = Join-Path $installDir 'app\data\envs\sow\python.exe'
                        if (-not (Test-Path $instPy)) { Say 'FEHLER   Praxistest: die installierte Python-Umgebung fehlt (installer.bat ist fehlgeschlagen).'; $problems++ }
                        else {
                            Say '  Praxistest: Import- und Start-Test mit der frisch installierten Umgebung ...'
                            $realFlags = @('-Imports', '-Smoke'); if ($VerifyAI) { $realFlags += '-AI' }
                            if (-not (Invoke-Verify $installDir $realFlags $instPy)) { $problems++ }
                            $VerifySmoke = $false; $VerifyAI = $false   # already done with the real environment
                        }
                    }
                }
            }
        }
        $flags = @()
        if ($VerifySmoke) { $flags += '-Smoke' }
        if ($VerifyAI) { $flags += '-AI' }
        if ($flags.Count -gt 0) {
            if ($Mode -eq 'Update' -and $VerifyInstall) { Say '  HINWEIS  Update-Setup enthaelt keine Python-Umgebung/Backends - Start- und KI-Test laufen mit der vollstaendigen sauberen Kopie.' }
            if (-not (Invoke-Verify $treeToTest $flags)) { $problems++ }
        }
        if ($installDir -and (Test-Path $installDir)) {
            # shortcuts the test setup may have made (desktop icon: same name as the real one) must not stay behind or point into the deleted test folder
            try {
                $wsh = New-Object -ComObject WScript.Shell
                foreach ($dir in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('CommonDesktopDirectory'), [Environment]::GetFolderPath('Programs'), (Join-Path ([Environment]::GetFolderPath('Programs')) 'Yume Companion'))) {
                    if (-not $dir -or -not (Test-Path $dir)) { continue }
                    foreach ($l in Get-ChildItem $dir -Filter '*.lnk' -ErrorAction SilentlyContinue) {
                        $target = $wsh.CreateShortcut($l.FullName).TargetPath
                        if ($target -and $target.StartsWith($installDir, [StringComparison]::OrdinalIgnoreCase)) { Remove-Item $l.FullName -Force -ErrorAction SilentlyContinue; Say "  Test-Verknuepfung entfernt: $($l.Name)" }
                    }
                }
            } catch { }
            & cmd.exe /c rd /s /q "`"$installDir`"" | Out-Null; Say '  Test-Installation wieder entfernt.'
        }
        Remove-Item (Join-Path $env:TEMP 'yume_test_setup') -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($problems -eq 0) { Say 'PRUEFUNG DER EXE: ALLES IN ORDNUNG' } else { Say "PRUEFUNG DER EXE: $problems Problem(e) - die Exe wurde gebaut, bitte Meldungen oben lesen." }
}
$fingerprintAfter = Get-Fingerprint $Source
if ($fingerprintAfter -eq $fingerprintBefore) { Say 'OK       Originalordner wurde nicht veraendert.' }
else { Say 'HINWEIS  Im Originalordner hat sich waehrend des Laufs etwas geaendert (z.B. weil das Programm gleichzeitig lief) - der Updater selbst schreibt dort nichts.' }
if (-not $KeepStage -and (Test-Path $Stage)) {
    & cmd.exe /c rd /s /q "`"$Stage`"" | Out-Null
    Say 'Arbeitskopie wieder geloescht.'
}
exit $(if ($problems -eq 0) { 0 } else { 2 })
