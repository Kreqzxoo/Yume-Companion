# Builds a CLEAN source folder for a release: the program and Python environment of your working copy (-Beta) WITHOUT any private data
# (settings, API keys, characters, logs, backups, chats), with the cleaned files of this repository laid over it.
# Afterwards build with:  "Yume Build.ps1" -Mode Full -Launcher -Version <x> -Source <Work>\src -OutDir <Out> -Verify
# Nothing in -Beta or in the repository is changed. -Work is deleted and recreated.
param(
    [Parameter(Mandatory = $true)][string]$Beta,                                    # your working copy with the finished Python environment (app\data\envs\sow)
    [string]$Repo = (Split-Path -Parent $PSScriptRoot),                             # this repository
    [string]$Work = 'C:\YumeBuild'
)
$ErrorActionPreference = 'Stop'
$src = "$Work\src"
if (Test-Path $Work) {
    if (Test-Path "$src\app\data\envs\sow\Lib\site-packages") { cmd /c rmdir "$src\app\data\envs\sow\Lib\site-packages" | Out-Null }
    cmd /c rd /s /q "$Work" | Out-Null
}
New-Item -ItemType Directory -Path $src -Force | Out-Null

# 1) Programm und Umgebung der Beta, ohne private Daten, ohne Assets, ohne die Paketordner der Umgebung
$xd = @('.soul', '.soul_stage', 'logs', 'Backups', 'docs', '__pycache__', "$Beta\assets", "$Beta\app\cache", "$Beta\app\models", "$Beta\app\data\pkgs",
        "$Beta\app\configuration\characters", "$Beta\app\data\.soul", "$Beta\app\data\envs\sow\Lib\site-packages")
$xf = @('unins000.dat', 'unins000.exe', '*.pyc', '*.log', 'boot_progress.txt', 'Yume Companion.exe',
        "$Beta\app\configuration\settings.json", "$Beta\app\configuration\api.json", "$Beta\app\configuration\characters.json", "$Beta\app\configuration\android_devices.json",
        '*_backup*.json', '*original*.json')
& robocopy.exe $Beta $src /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /MT:8 /XD @xd /XF @xf | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy 1: $LASTEXITCODE" }

# 2) site-packages der Beta nur als Verknuepfung (wird vom Build-Werkzeug gelesen, nicht veraendert)
cmd /c mklink /J "$src\app\data\envs\sow\Lib\site-packages" "$Beta\app\data\envs\sow\Lib\site-packages" | Out-Null

# 3) die bereinigten Dateien aus dem GitHub-Ordner darueberlegen (Programmcode, Assets, Vorlagen, Branding)
$xd2 = @('.git', '.github', 'android', 'llm-server', 'rebrand', 'tests', 'updater', 'docs', 'Backups', 'logs', '__pycache__')
$xf2 = @('README.md', 'README.de.md', 'CONTRIBUTING.md', 'SECURITY.md', 'CHANGELOG.md', '.gitignore', 'settings.json', 'api.json', 'characters.json', 'android_devices.json')
& robocopy.exe $Repo $src /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /MT:8 /XD @xd2 /XF @xf2 | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy 2: $LASTEXITCODE" }

# 4) saubere Grundeinstellungen, damit make_templates.py etwas zum Einlesen hat
Copy-Item "$Repo\app\configuration\settings.template.json" "$src\app\configuration\settings.json" -Force
Copy-Item "$Repo\updater\installer_build\templates\api.json" "$src\app\configuration\api.json" -Force
New-Item -ItemType Directory -Path "$src\assets" -Force | Out-Null
foreach ($d in 'logs', 'Backups') { New-Item -ItemType Directory -Path "$src\$d" -Force | Out-Null }

# 5) eine Kopie der Release-Werkzeuge, damit der Build nichts im Repo veraendert
& robocopy.exe "$Repo\updater" "$Work\updater" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy 3: $LASTEXITCODE" }

$n = (Get-ChildItem $src -Recurse -File -Force -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notlike "$src\app\data\envs\sow\Lib\site-packages\*" } | Measure-Object Length -Sum)
"Quelle fertig: {0} Dateien, {1:N0} MB (ohne site-packages)" -f $n.Count, ($n.Sum / 1MB)

# Leak check: no configuration with personal data and nothing that looks like a key may be in the source folder
$bad = @(Get-ChildItem "$src\app\configuration" -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'backup|original|characters\.json|android_devices' })
$keys = @(Get-ChildItem "$src\app" -Recurse -File -Include *.json,*.py,*.ini,*.txt -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notlike "$src\app\data\*" -and $_.Name -notmatch '^(tokenizer|vocab|merges|special_tokens_map|added_tokens)' -and $_.FullName -notmatch '\\(e5-small-en-ru|models|detector)\\' } |
    Select-String -Pattern 'sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_\-]{30,}|ghp_[A-Za-z0-9]{30,}|xox[bp]-[A-Za-z0-9\-]{20,}' -List -ErrorAction SilentlyContinue)
if ($bad.Count -or $keys.Count) {
    $bad | ForEach-Object { Write-Host "Private file: $($_.FullName)" -ForegroundColor Red }
    $keys | ForEach-Object { Write-Host "Looks like a key: $($_.Path)" -ForegroundColor Red }
    throw 'Leak check failed - do not build a release from this folder.'
}
Write-Host 'Leak check passed.' -ForegroundColor Green
Get-Content "$src\VERSION.txt"
