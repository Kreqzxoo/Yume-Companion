# Yume Verify - checks a staged / installed Yume Companion folder:
#   Reset   : delivered with default settings, nothing personal, nothing the installer.bat would add
#   Syntax  : every Python file parses
#   Imports : the main modules import
#   Smoke   : the whole UI starts (headless) and every page renders
#   AI      : the shipped llama.cpp backend loads a tiny model and the app's own provider gets an answer
# Output lines: "  OK ", "  FEHLER ", "  HINWEIS ". Exit code 1 when anything failed.
param(
    [Parameter(Mandatory = $true)][string]$Tree,
    [Parameter(Mandatory = $true)][string]$Templates,
    [Parameter(Mandatory = $true)][string]$Python,
    [string]$ModelDir = '',
    [string]$KeepFile = '',          # json from env_delta.py: packages that legitimately ship in the environment
    [switch]$DepsInstalled,          # the tree went through a real installer.bat run (packages + installer.log are expected)
    [switch]$Reset, [switch]$Syntax, [switch]$Imports, [switch]$Smoke, [switch]$AI
)
$ErrorActionPreference = 'Continue'
if (-not $ModelDir) { $ModelDir = Join-Path $env:LOCALAPPDATA 'Yume Updater\testmodel' }
$script:failed = 0
function Ok($m) { Write-Output "  OK       $m" }
function Bad($m) { $script:failed++; Write-Output "  FEHLER   $m" }
function Note($m) { Write-Output "  HINWEIS  $m" }

if (-not (Test-Path (Join-Path $Tree 'main.py'))) { Bad "main.py fehlt in $Tree"; exit 1 }
if (-not (Test-Path $Python)) { Bad "Python fuer die Pruefung fehlt: $Python"; exit 1 }

function Run-Python($pyFile, $argList, $cwd, $timeoutSec, $extraEnv) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Python
    $psi.Arguments = ('-B -E -s "{0}" {1}' -f $pyFile, $argList)   # no .pyc, ignore PYTHON* env, keep the script folder importable
    $psi.WorkingDirectory = $cwd
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $psi.EnvironmentVariables['QT_QPA_PLATFORM'] = 'offscreen'
    $psi.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
    $psi.EnvironmentVariables['PYTHONDONTWRITEBYTECODE'] = '1'
    foreach ($k in $extraEnv.Keys) { $psi.EnvironmentVariables[$k] = $extraEnv[$k] }
    $p = [System.Diagnostics.Process]::Start($psi)
    $outTask = $p.StandardOutput.ReadToEndAsync()
    $errTask = $p.StandardError.ReadToEndAsync()
    if (-not $p.WaitForExit($timeoutSec * 1000)) { try { $p.Kill() } catch {}; return @{ Code = -1; Out = $outTask.Result; Err = 'Zeitlimit ueberschritten'; Timeout = $true } }
    return @{ Code = $p.ExitCode; Out = $outTask.Result; Err = $errTask.Result; Timeout = $false }
}

$tmp = Join-Path $env:TEMP 'yume_verify'
New-Item -ItemType Directory -Path $tmp -Force | Out-Null

# ------------------------------------------------------------------ RESET
if ($Reset) {
    Write-Output '--- Pruefung: Standardzustand & Aufraeumen'
    $cfg = Join-Path $Tree 'app\configuration'
    # settings = clean template (the installer may only change the program language)
    try {
        $a = Get-Content (Join-Path $cfg 'settings.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $b = Get-Content (Join-Path $Templates 'settings.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $a.main_settings.program_language = 0; $b.main_settings.program_language = 0
        if (($a | ConvertTo-Json -Depth 40 -Compress) -eq ($b | ConvertTo-Json -Depth 40 -Compress)) { Ok 'settings.json entspricht der sauberen Vorlage' }
        else { Bad 'settings.json weicht von der sauberen Vorlage ab (persoenliche Werte?)' }
    } catch { Bad "settings.json nicht lesbar: $_" }
    try {
        $api = Get-Content (Join-Path $cfg 'api.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $filled = @($api.PSObject.Properties | Where-Object { "$($_.Value)".Length -gt 0 })
        if ($filled.Count -eq 0) { Ok 'api.json ist leer (keine Schluessel)' } else { Bad "api.json enthaelt Werte: $($filled.Name -join ', ')" }
    } catch { Bad "api.json nicht lesbar: $_" }
    try {
        $ch = Get-Content (Join-Path $cfg 'characters.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $n = @($ch.character_list.PSObject.Properties).Count
        if ($n -eq 0) { Ok 'keine Charaktere enthalten' } else { Bad "$n Charakter(e) im Paket" }
    } catch { Bad "characters.json nicht lesbar: $_" }
    foreach ($d in 'app\configuration\characters', 'app\cache', 'app\models', 'assets\vision_models', 'assets\local_llm') {
        $path = Join-Path $Tree $d
        $items = if (Test-Path $path) { @(Get-ChildItem $path -Recurse -File -Force -ErrorAction SilentlyContinue) } else { @() }
        if ($items.Count -eq 0) { Ok "$d ist leer" } else { Bad "$d enthaelt $($items.Count) Datei(en), z.B. $($items[0].Name)" }
    }
    foreach ($d in '.soul', '.soul_stage', 'Backups', 'backups', 'app\data\.soul') {
        if (Test-Path (Join-Path $Tree $d)) { Bad "Nutzerdaten-Ordner vorhanden: $d" }
    }
    $logs = @(Get-ChildItem (Join-Path $Tree 'logs') -File -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -notin '.gitkeep', 'update_packages.log' -and -not ($DepsInstalled -and $_.Name -eq 'installer.log') })
    if ($logs.Count -eq 0) { Ok 'keine Logdateien' } else { Bad "Logdateien im Paket: $($logs[0].Name) ..." }
    $junk = @(Get-ChildItem $Tree -Recurse -Force -ErrorAction SilentlyContinue | Where-Object {
        $_.FullName -notlike "$Tree\app\data\*" -and ($_.Name -like 'unins000.*' -or $_.Name -eq '__pycache__' -or $_.Extension -in '.pyc', '.pyo' -or $_.Name -eq 'boot_progress.txt') })
    if ($junk.Count -eq 0) { Ok 'keine Installer-Reste, __pycache__ oder .pyc' } else { Bad "Ueberfluessiges: $($junk[0].FullName.Substring($Tree.Length)) (+$($junk.Count - 1))" }
    # nothing that installer.bat downloads
    $sp = Join-Path $Tree 'app\data\envs\sow\Lib\site-packages'
    $shipped = @()
    if ($KeepFile -and (Test-Path $KeepFile)) { try { $shipped = @((Get-Content $KeepFile -Raw | ConvertFrom-Json).keep_entries) } catch {} }
    if ($DepsInstalled) { Note 'Praxistest: Pakete wurden von installer.bat installiert - Paketliste wird nicht geprueft.' }
    elseif (Test-Path $sp) {
        # the setup itself installs the packages of requirements_extra.txt after copying (update mechanism): what pip reports as installed there is expected
        function Test-ViaSetup($entry, $names) {
            $e = $entry.ToLower().Replace('-', '_')
            foreach ($n in $names) { if ($e -eq $n -or $e -like ($n + '_*')) { return $true } }
            return $false
        }
        $viaSetup = @()
        $upLog = Join-Path $Tree 'logs\update_packages.log'
        if (Test-Path $upLog) {
            $line = Get-Content $upLog -ErrorAction SilentlyContinue | Where-Object { $_ -match '^Successfully installed ' } | Select-Object -Last 1
            if ($line) { $viaSetup = @(($line -replace '^Successfully installed ', '') -split '\s+' | Where-Object { $_ } | ForEach-Object { ($_ -replace '-[0-9][^-]*$', '').ToLower().Replace('-', '_') }) }
        }
        $extra = @(Get-ChildItem $sp -Force | Where-Object {
            $_.Name -notmatch '^(pip|setuptools|wheel|pkg_resources|_distutils_hack|distutils-precedence|packaging)(-|\.|$)' -and ($shipped -notcontains $_.Name) -and
            -not (Test-ViaSetup $_.Name $viaSetup)
        })
        if ($extra.Count -eq 0) { Ok "Python-Umgebung enthaelt nur pip/setuptools und $($shipped.Count) mitgelieferte Zusatz-Eintraege (rvc_python, fairseq ...)" }
        else { Bad "Python-Umgebung enthaelt vorinstallierte Pakete: $(($extra | Select-Object -First 5).Name -join ', ')" }
        foreach ($need in 'rvc_python', 'fairseq') { if ($shipped -contains $need -and -not (Test-Path (Join-Path $sp $need))) { Bad "mitgeliefertes Paket fehlt in der Kopie: $need" } }
        foreach ($big in 'torch', 'torchaudio', 'TTS', 'PyQt6') { if (Test-Path (Join-Path $sp $big)) { Bad "$big ist vorinstalliert" } }
    }
    # personal strings in shipped text files
    $user = $env:USERNAME
    $needles = @("C:\Users\$user", "C:/Users/$user", "\Users\$user")
    $hits = @()
    Get-ChildItem $Tree -Recurse -File -Force -ErrorAction SilentlyContinue | Where-Object {
        $_.FullName -notlike "$Tree\app\data\*" -and $_.FullName -notlike "$Tree\assets\*" -and $_.FullName -notlike "$Tree\app\utils\ai_clients\backend\*" -and
        $_.Length -lt 3MB -and $_.Extension -in '.json', '.yaml', '.yml', '.txt', '.ini', '.cfg', '.bat', '.cmd', '.md', '.py' } | ForEach-Object {
        $text = [IO.File]::ReadAllText($_.FullName)
        foreach ($n in $needles) { if ($text.Contains($n)) { $hits += $_.FullName.Substring($Tree.Length + 1); break } }
    }
    if ($hits.Count -eq 0) { Ok "keine persoenlichen Pfade ($user) in Konfigurations-/Textdateien" }
    else { Bad "persoenlicher Pfad in: $(($hits | Select-Object -First 4) -join ', ')" }
    $mb = [math]::Round((Get-ChildItem $Tree -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB)
    Note "Paketgroesse: $mb MB"
}

# ------------------------------------------------------------------ SYNTAX
if ($Syntax) {
    Write-Output '--- Pruefung: Python-Syntax'
    $py = Join-Path $tmp 'syntax.py'
    Set-Content $py -Encoding UTF8 -Value @'
import ast, os, sys
root = os.getcwd(); bad = []; n = 0
for dp, dn, fn in os.walk(root):
    rel = os.path.relpath(dp, root)
    if rel.startswith(os.path.join("app", "data")) or rel.startswith("assets") or "__pycache__" in dp:
        dn[:] = []; continue
    for f in fn:
        if f.endswith(".py"):
            n += 1
            try:
                with open(os.path.join(dp, f), "rb") as fh: ast.parse(fh.read(), f)
            except SyntaxError as e:
                bad.append(f"{os.path.relpath(os.path.join(dp, f), root)}:{e.lineno} {e.msg}")
print(n); [print(b) for b in bad]
sys.exit(1 if bad else 0)
'@
    $r = Run-Python $py '' $Tree 120 @{}
    $lines = @($r.Out -split "`r?`n" | Where-Object { $_ })
    if ($r.Code -eq 0) { Ok "alle $($lines[0]) Python-Dateien sind syntaktisch korrekt" } else { Bad "Syntaxfehler: $(($lines | Select-Object -Skip 1 -First 4) -join ' | ')" }
}

# ------------------------------------------------------------------ IMPORTS
if ($Imports) {
    Write-Output '--- Pruefung: Kernmodule importieren'
    $py = Join-Path $tmp 'imports.py'
    Set-Content $py -Encoding UTF8 -Value @'
import importlib, os, sys, traceback
sys.path.insert(0, os.getcwd())
mods = ["app.configuration.configuration", "app.utils.branding", "app.utils.runtime_stats", "app.utils.alerts", "app.utils.tool_log",
        "app.utils.profile_backup", "app.utils.auto_backup", "app.utils.dashboard_server", "app.utils.app_scanner",
        "app.utils.ai_clients.tools", "app.utils.ai_clients.ai_factory", "app.utils.vision_manager",
        "app.gui.yume_decor", "app.gui.sowInterface", "app.gui.interface_signals", "app.gui.backup_settings",
        "app.gui.dashboard_settings", "app.gui.agent_models", "app.gui.tool_log_ui", "app.gui.presets_ui",
        "app.gui.app_picker", "app.gui.home_welcome"]
bad = 0
for m in mods:
    try:
        importlib.import_module(m); print("OK", m)
    except Exception as e:
        bad += 1; print("FAIL", m, type(e).__name__, str(e)[:160])
sys.exit(1 if bad else 0)
'@
    $r = Run-Python $py '' $Tree 240 @{}
    $okc = @($r.Out -split "`r?`n" | Where-Object { $_ -like 'OK *' }).Count
    $fails = @($r.Out -split "`r?`n" | Where-Object { $_ -like 'FAIL *' })
    if ($fails.Count -eq 0 -and -not $r.Timeout) { Ok "alle $okc Kernmodule lassen sich importieren" }
    else { Bad "Import fehlgeschlagen: $(($fails | Select-Object -First 3) -join ' | ') $(if ($r.Timeout) { '(Zeitlimit)' })" }
}

# ------------------------------------------------------------------ SMOKE (UI starts, every page renders)
if ($Smoke) {
    Write-Output '--- Pruefung: Programm startet (ohne Fenster) und alle Seiten werden gezeichnet'
    $shots = Join-Path $tmp 'shots'
    Remove-Item $shots -Recurse -Force -ErrorAction SilentlyContinue
    $logDir = Join-Path $Tree 'logs'
    $before = @(Get-ChildItem $logDir -Filter 'sow_*.log' -ErrorAction SilentlyContinue | ForEach-Object Name)
    $r = Run-Python (Join-Path $Tree 'main.py') '' $Tree 300 @{ YUME_SHOT_DIR = $shots; YUME_SHOT_DELAY = '5000' }
    $pngs = @(Get-ChildItem $shots -Filter *.png -ErrorAction SilentlyContinue).Count
    $newLog = Get-ChildItem $logDir -Filter 'sow_*.log' -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Name } | Sort-Object LastWriteTime | Select-Object -Last 1
    $trace = @()
    if ($newLog) { $trace = @(Select-String -Path $newLog.FullName -Pattern 'Traceback|CRITICAL' | Select-Object -First 3 | ForEach-Object Line) }
    if ($pngs -ge 20 -and $trace.Count -eq 0) { Ok "Programm gestartet, $pngs Seiten/Reiter fehlerfrei gerendert" }
    else { Bad "Start-Test: $pngs Seiten gerendert (erwartet >= 20) $(if ($r.Timeout) { '- Zeitlimit' }) $(if ($trace) { '- ' + ($trace -join ' | ') }) $($r.Err.Trim().Split("`n")[-1])" }
    # leave no run traces behind in the folder under test
    Get-ChildItem $logDir -Filter 'sow_*.log' -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
}

# ------------------------------------------------------------------ AI (tiny model through the shipped backend + app provider)
if ($AI) {
    Write-Output '--- Pruefung: Mini-KI (gelieferte llama.cpp + eigener Provider)'
    $server = Join-Path $Tree 'app\utils\ai_clients\backend\cpu\llama-server.exe'
    if (-not (Test-Path $server)) { Bad 'llama-server.exe (CPU) fehlt im Paket'; }
    else {
        New-Item -ItemType Directory -Path $ModelDir -Force | Out-Null
        $model = Join-Path $ModelDir 'qwen2.5-0.5b-instruct-q4_k_m.gguf'
        if (-not (Test-Path $model) -or (Get-Item $model).Length -lt 400MB) {
            Note 'Lade einmalig das kleine Testmodell (Qwen2.5-0.5B, ca. 470 MB) ...'
            try {
                $ProgressPreference = 'SilentlyContinue'
                Invoke-WebRequest -Uri 'https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf' -OutFile "$model.part" -UseBasicParsing
                Move-Item "$model.part" $model -Force
            } catch { Bad "Testmodell konnte nicht geladen werden: $($_.Exception.Message)" }
        }
        if (Test-Path $model) {
            $py = Join-Path $tmp 'ai_test.py'
            Set-Content $py -Encoding UTF8 -Value @'
import asyncio, json, os, subprocess, sys, time, urllib.request
sys.path.insert(0, os.getcwd())
server, model, port = sys.argv[1], sys.argv[2], 48611
proc = subprocess.Popen([server, "-m", model, "--host", "127.0.0.1", "--port", str(port), "-c", "2048", "-ngl", "0"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
result = {"ok": False}
try:
    t0 = time.time()
    while time.time() - t0 < 120:
        try:
            if urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2).status == 200: break
        except Exception: time.sleep(1)
    else:
        raise RuntimeError("Server wurde nicht bereit")
    from app.utils.ai_clients.providers.local_provider import LocalProvider
    from app.utils.ai_clients.ai_factory import _MeteredProvider
    from app.utils.runtime_stats import stats
    prov = _MeteredProvider(LocalProvider(port=port), "Local LLM")
    async def go():
        return "".join([c async for c in prov.generate_stream([{"role": "user", "content": "Antworte nur mit dem Wort OK."}], max_tokens=24, temperature=0.2)])
    text = asyncio.run(go()).strip()
    last = stats.snapshot()["llm"]["last"] or {}
    result = {"ok": bool(text) and not text.startswith("\u26a0"), "text": text[:80], "exact": last.get("exact"), "in": last.get("in"), "out": last.get("out"),
              "tps": round(last.get("tps") or 0, 1), "load_s": round(time.time() - t0, 1)}
except Exception as e:
    result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
finally:
    proc.kill()
print(json.dumps(result, ensure_ascii=False))
sys.exit(0 if result.get("ok") else 1)
'@
            $r = Run-Python $py ('"{0}" "{1}"' -f $server, $model) $Tree 240 @{}
            try { $res = ($r.Out.Trim().Split("`n")[-1] | ConvertFrom-Json) } catch { $res = $null }
            if ($res -and $res.ok) { Ok "Mini-KI antwortet: '$($res.text)' ($($res.out) Tokens, $($res.tps) Tokens/s, exakte Zaehler: $($res.exact), bereit nach $($res.load_s) s)" }
            else { Bad "Mini-KI-Test fehlgeschlagen: $(if ($res) { $res.error } else { $r.Err })" }
        }
    }
}

Write-Output ''
if ($script:failed -eq 0) { Write-Output 'PRUEFUNG: ALLES IN ORDNUNG' } else { Write-Output "PRUEFUNG: $($script:failed) FEHLER" }
exit $(if ($script:failed -eq 0) { 0 } else { 1 })
