<#
  Upload-Pruefung fuer GitHub: findet Geheimnisse, private Daten, zu grosse und verbotene Dateien,
  BEVOR du sie hochlaedst. Aendert nichts.

  Aufruf (PowerShell, im Projektordner):
      powershell -ExecutionPolicy Bypass -File tools\dev\check_upload.ps1
  Mit Git (empfohlen, prueft nur das, was wirklich hochgeladen wuerde):
      powershell -ExecutionPolicy Bypass -File tools\dev\check_upload.ps1 -UseGit
#>
param([switch]$UseGit)

$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $root

if ($UseGit) {
    $files = & git ls-files --cached --others --exclude-standard | ForEach-Object { Join-Path $root $_ } | Where-Object { Test-Path $_ -PathType Leaf }
} else {
    $files = Get-ChildItem -Recurse -File -Force | Where-Object { $_.FullName -notmatch '\\\.git\\' } | ForEach-Object { $_.FullName }
}
$files = @($files)
"Gepruefte Dateien: $($files.Count)"
$problems = 0
function Bad([string]$kind, [string]$path, [string]$detail = '') {
    $script:problems++
    $rel = $path.Replace("$root\", '')
    Write-Host ("[{0}] {1} {2}" -f $kind, $rel, $detail) -ForegroundColor Red
}

# 1) Dateien, die nie ins oeffentliche Repo gehoeren
$forbiddenNames = 'api.json', 'settings.json', 'characters.json', 'android_devices.json', 'local.properties', 'db.json', 'panel-token'
$forbiddenExt = '.gguf', '.pth', '.index', '.vrm', '.fbx', '.moc3', '.exe', '.apk', '.sowpack', '.yumepack', '.log', '.safetensors', '.bin', '.onnx', '.zip', '.rar', '.7z'
foreach ($f in $files) {
    $name = [IO.Path]::GetFileName($f); $ext = [IO.Path]::GetExtension($f).ToLower()
    $isTemplate = $f -match '\\installer_build\\templates\\'                      # leere Vorlagen des Release-Werkzeugs
    $isSilero = $f -match '\\speech-to-text\\silero-vad\\' -or $f -match '\\assets\\emotions\\vrm\\Anime (Girl|Man)\.vrm$'   # Silero-VAD (MIT) und die zwei VRoid-Beispielmodelle (Weitergabe erlaubt)
    if (-not $isTemplate -and ($forbiddenNames -contains $name)) { Bad 'PRIVAT' $f; continue }
    if (-not $isSilero -and ($forbiddenExt -contains $ext)) { Bad 'DATEITYP' $f "($ext)"; continue }
    if ($f -match '\\(Backups|logs)\\' -and $name -ne '.gitkeep') { Bad 'PRIVAT' $f }
    if ($f -match '\\\.soul(_stage)?\\') { Bad 'PRIVAT' $f '(Gedaechtnis / Buehne)' }
}

# 2) Zu gross fuer GitHub (Warnung ab 50 MB, harte Grenze 100 MB)
foreach ($f in $files) {
    $len = (Get-Item $f).Length
    if ($len -ge 100MB) { Bad 'ZU GROSS' $f ("{0:N0} MB (Grenze 100 MB)" -f ($len / 1MB)) }
    elseif ($len -ge 50MB) { Write-Host ("[WARNUNG] {0}: {1:N0} MB" -f $f.Replace("$root\", ''), ($len / 1MB)) -ForegroundColor Yellow }
}

# 3) Geheimnisse und persoenliche Muster in Textdateien
$textExt = '.py', '.kt', '.kts', '.json', '.yaml', '.yml', '.md', '.txt', '.bat', '.cmd', '.ps1', '.cs', '.iss', '.xml', '.properties', '.html', '.js', '.css', '.cfg', '.ini'
$patterns = @{
    'API-Schluessel (sk-...)'      = 'sk-[A-Za-z0-9]{20,}'
    'Google-Schluessel (AIza...)'  = 'AIza[0-9A-Za-z_\-]{30,}'
    'GitHub-Token'                 = 'gh[pousr]_[A-Za-z0-9]{30,}'
    'Slack-Token'                  = 'xox[baprs]-[A-Za-z0-9-]{10,}'
    'Discord-Bot-Token'            = '[MNO][A-Za-z0-9_-]{23,25}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,}'
    'Privater Schluessel'          = '-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----'
    'Windows-Benutzerpfad'         = 'C:\\Users\\(?!\<|Name|Benutzer|DEIN|dein|user|User|%|\.)[A-Za-z0-9_.-]{3,}'
}
foreach ($f in $files) {
    $ext = [IO.Path]::GetExtension($f).ToLower()
    if ($textExt -notcontains $ext) { continue }
    if ((Get-Item $f).Length -gt 3MB) { continue }
    if ($f -match 'three|fflate|GLTFLoader|tokenizer|vocab') { continue }
    $text = [IO.File]::ReadAllText($f)
    foreach ($k in $patterns.Keys) {
        if ($text -match $patterns[$k]) { Bad 'GEHEIMNIS?' $f "-> $k" }
    }
}

""
if ($problems -eq 0) { Write-Host 'Alles in Ordnung: keine Funde.' -ForegroundColor Green }
else { Write-Host "$problems Fund(e). Erst beheben, dann hochladen." -ForegroundColor Red; exit 1 }
