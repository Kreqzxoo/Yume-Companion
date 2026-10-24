# Yume Doctor - explains why a build failed and proposes safe fixes.
#   1. rule check: known problems of this pipeline -> plain explanation + (optional) safe fix id
#   2. local AI (only if a model that is strong enough is installed: >= 3.5 GB, i.e. a 7B+ class model):
#      reads the end of the log and returns cause / solution / one of the allowed fix ids
# The AI never executes anything. Fixes are limited to the ids below and are applied by the tool after confirmation.
param(
    [Parameter(Mandatory = $true)][string]$LogFile,
    [Parameter(Mandatory = $true)][string]$Source,
    [Parameter(Mandatory = $true)][string]$OutJson,
    [switch]$UseAI,
    [double]$MinModelGB = 3.5,        # "strong enough": a 7B-class model at Q4 is about 4-5 GB
    [string]$ExtraModelDir = ''       # (tests) additional folder with .gguf models
)
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

$AllowedFixes = [ordered]@{
    retry          = 'Den Lauf einfach wiederholen (zeitweiliger Fehler)'
    clear_stage    = 'Alte Arbeitskopie loeschen und neu bauen'
    kill_leftovers = 'Haengende Test-Prozesse (llama-server, Test-Python) beenden und neu bauen'
    install_inno   = 'Inno Setup 6 per winget (nur fuer deinen Benutzer) installieren'
    skip_ai        = 'Den Mini-KI-Test fuer diesen Lauf ausschalten'
    skip_smoke     = 'Den Start-Test fuer diesen Lauf ausschalten'
    skip_install   = 'Den Installationstest fuer diesen Lauf ausschalten'
}

$lines = @(Get-Content $LogFile -Encoding UTF8 -ErrorAction SilentlyContinue)
$text = $lines -join "`n"
$tail = ($lines | Select-Object -Last 140) -join "`n"

# ------------------------------------------------------------------ 1. rules
$rules = @(
    @{ id = 'module_missing'; rx = 'ModuleNotFoundError|No module named'; explain = 'Ein Python-Paket fehlt in der getesteten Umgebung. Ursache: Es steckt im Arbeitsordner, wird aber von installer.bat nicht installiert. Der Updater uebernimmt solche Pakete automatisch (siehe Zeile "Mitgelieferte Zusatzpakete") - fehlt eines trotzdem, muss es in installer.bat ergaenzt werden.'; fix = $null },
    @{ id = 'busy'; rx = 'Ein anderer Build laeuft bereits'; explain = 'Es laeuft schon ein zweiter Build (auch ueber ein zweites Fenster). Beide benutzen dieselbe Arbeitskopie und wuerden sich gegenseitig loeschen - deshalb wartet dieser Lauf.'; fix = 'retry' },
    @{ id = 'inno_missing'; rx = 'Inno Setup nicht gefunden'; explain = 'Inno Setup 6 ist nicht installiert - ohne den Compiler kann keine Exe gebaut werden.'; fix = 'install_inno' },
    @{ id = 'stage_locked'; rx = 'Staging-Ordner konnte nicht geloescht werden'; explain = 'Die temporaere Arbeitskopie ist noch in Benutzung (oft ein haengendes Test-Programm oder der Explorer).'; fix = 'kill_leftovers' },
    @{ id = 'install_fail'; rx = 'Test-Installation fehlgeschlagen'; explain = 'Die Test-Installation ist fehlgeschlagen - meist blockiert ein haengender Prozess den Testordner oder es fehlt Speicherplatz.'; fix = 'kill_leftovers' },
    @{ id = 'disk'; rx = '(?i)not enough (disk )?space|Nicht genug Speicherplatz|Kein Speicherplatz'; explain = 'Auf dem Laufwerk ist zu wenig Platz. Eine Arbeitskopie braucht ca. 3 GB, der Voll-Installer zusaetzlich ca. 3 GB.'; fix = $null },
    @{ id = 'main_missing'; rx = 'main\.py nicht gefunden'; explain = 'Im gewaehlten Arbeitsordner liegt keine main.py - bitte den richtigen MAIN-Ordner waehlen.'; fix = $null },
    @{ id = 'python_missing'; rx = 'python\.exe fehlt in der sauberen Kopie|Pruefung nicht moeglich: Python fehlt|Python fuer die Pruefung fehlt'; explain = 'Im Arbeitsordner gibt es keine Python-Umgebung (app\data\envs\sow\python.exe). Der Updater braucht sie fuer die Kopie und die Pruefungen - der Arbeitsordner muss die installierte Umgebung enthalten (einmal installer.bat ausfuehren).'; fix = $null },
    @{ id = 'copy_missing'; rx = 'In der Kopie fehlt:'; explain = 'Eine wichtige Datei fehlt im Arbeitsordner (der Name steht im Protokoll) - ist der richtige MAIN-Ordner gewaehlt?'; fix = $null },
    @{ id = 'pip_broken'; rx = 'pip funktioniert in der sauberen Kopie nicht'; explain = 'Die Python-Umgebung im Arbeitsordner (app\data\envs\sow) ist beschaedigt: pip startet nicht. Repariere sie z.B. mit installer.bat im Arbeitsordner.'; fix = $null },
    @{ id = 'packages_left'; rx = 'Unerwartet installierte Pakete|Python-Umgebung enthaelt vorinstallierte Pakete'; explain = 'In der Kopie sind Pakete, die installer.bat erst nachladen soll. Meist liegt eine zweite Python-Umgebung unter app\data\envs im Arbeitsordner.'; fix = $null },
    @{ id = 'personal_path'; rx = 'persoenlicher Pfad in'; explain = 'Eine Datei im Programm enthaelt deinen persoenlichen Pfad (C:\Users\...). Im Arbeitsordner darf der Updater nichts aendern - die genannte Datei dort bereinigen.'; fix = $null },
    @{ id = 'settings_diff'; rx = 'settings\.json weicht von der sauberen Vorlage ab'; explain = 'Die ausgelieferte settings.json entspricht nicht der Vorlage. Die Vorlage wird bei jedem Bau neu aus dem Arbeitsordner erzeugt - pruefe, ob eine Aenderung an den Einstellungs-Schluesseln fehlschlug.'; fix = 'retry' },
    @{ id = 'syntax'; rx = 'Syntaxfehler:'; explain = 'In einer Python-Datei ist ein Syntaxfehler (Datei und Zeile stehen im Protokoll). Im Arbeitsordner korrigieren.'; fix = $null },
    @{ id = 'import_fail'; rx = 'Import fehlgeschlagen'; explain = 'Ein Kernmodul laesst sich nicht importieren (fehlende Datei oder Abhaengigkeit im Arbeitsordner).'; fix = $null },
    @{ id = 'smoke_fail'; rx = 'Start-Test:'; explain = 'Das Programm startet in der Kopie nicht fehlerfrei. Die Zeile im Protokoll nennt den Fehler.'; fix = 'skip_smoke' },
    @{ id = 'model_dl'; rx = 'Testmodell konnte nicht geladen werden'; explain = 'Das kleine Testmodell liess sich nicht herunterladen (Internet oder Hugging Face nicht erreichbar).'; fix = 'skip_ai' },
    @{ id = 'ai_fail'; rx = 'Mini-KI-Test fehlgeschlagen|llama-server.exe .* fehlt'; explain = 'Die mitgelieferte llama.cpp hat das Testmodell nicht geladen oder nicht geantwortet (z.B. Port belegt, Backend-Datei fehlt).'; fix = 'kill_leftovers' },
    @{ id = 'iscc'; rx = 'ISCC Exitcode|Error on line'; explain = 'Der Inno-Setup-Compiler hat einen Fehler gemeldet - die Zeile davor im Protokoll nennt die Ursache (oft fehlende Datei oder gesperrte Ausgabedatei).'; fix = 'retry' },
    @{ id = 'robocopy'; rx = 'robocopy Exitcode'; explain = 'Das Kopieren des Arbeitsordners ist fehlgeschlagen (Zugriffsrechte, OneDrive-Platzhalter oder zu lange Pfade).'; fix = 'retry' },
    @{ id = 'verify_aborted'; rx = 'Pruefung der Kopie fehlgeschlagen|keine Exe gebaut'; explain = 'Die Basis-Pruefung hat Probleme gefunden, deshalb wurde bewusst keine Exe gebaut. Die FEHLER-Zeilen darueber nennen sie.'; fix = $null }
)
$hits = @()
foreach ($r in $rules) { if ($text -match $r.rx) { $hits += [pscustomobject]@{ id = $r.id; explain = $r.explain; fix = $r.fix } } }
$errorLines = @($lines | Where-Object { $_ -match '^\s*FEHLER' } | Select-Object -First 8)

# ------------------------------------------------------------------ 2. local AI (only when strong enough)
$ai = [ordered]@{ used = $false; model = ''; note = ''; cause = ''; solution = ''; fix = '' }
if ($UseAI) {
    $modelDirs = @((Join-Path $Source 'assets\local_llm'))
    if ($ExtraModelDir) { $modelDirs += $ExtraModelDir }
    $models = @()
    foreach ($d in $modelDirs) {
        if (Test-Path $d) {
            $models += Get-ChildItem $d -Recurse -Filter *.gguf -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch 'mmproj|embed|vision' -and $_.Length -ge ($MinModelGB * 1GB) -and $_.Length -le 22GB }
        }
    }
    if ($models.Count -eq 0) {
        $ai.note = 'Kein ausreichend starkes lokales Modell gefunden (noetig: ein 7B-Modell oder groesser, ab ca. 3,5 GB) - es gilt nur die Regelpruefung. Ein passendes Modell kannst du unter Einstellungen > Werkzeuge & Plugins > Empfohlene Modelle laden.'
    } else {
        # best fit: prefer a mid-size instruct model (~5-10 GB) that fits graphics memory
        $pick = $models | Sort-Object { [math]::Abs($_.Length - 6GB) } | Select-Object -First 1
        $backendRoot = Join-Path $Source 'app\utils\ai_clients\backend'
        $freeMb = 0
        try { $freeMb = [int]((& nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>$null | Select-Object -First 1)) } catch {}
        $useGpu = ($freeMb -gt (($pick.Length / 1MB) + 1800)) -and (Test-Path (Join-Path $backendRoot 'cuda\llama-server.exe'))
        $server = Join-Path $backendRoot $(if ($useGpu) { 'cuda\llama-server.exe' } else { 'cpu\llama-server.exe' })
        if (-not (Test-Path $server)) { $ai.note = 'llama-server.exe fehlt im Arbeitsordner - nur Regelpruefung.' }
        else {
            $port = 48612
            $proc = Start-Process -FilePath $server -ArgumentList '-m', "`"$($pick.FullName)`"", '--host', '127.0.0.1', '--port', $port, '-c', '8192', '-ngl', $(if ($useGpu) { '99' } else { '0' }), '--jinja' -WindowStyle Hidden -PassThru
            try {
                $ready = $false
                for ($i = 0; $i -lt 150; $i++) {
                    Start-Sleep -Seconds 2
                    if ($proc.HasExited) { break }
                    try { if ((Invoke-WebRequest "http://127.0.0.1:$port/health" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200) { $ready = $true; break } } catch {}
                }
                if (-not $ready) { $ai.note = 'Das lokale Modell wurde nicht rechtzeitig bereit - nur Regelpruefung.' }
                else {
                    $ids = ($AllowedFixes.Keys -join ', ')
                    $ruleText = if ($hits.Count) { ($hits | ForEach-Object { "- $($_.id): $($_.explain)" }) -join "`n" } else { '(keine Regel hat angeschlagen)' }
                    $sys = 'Du bist der Build-Assistent des Programms "Yume Release Tool". Es kopiert einen Arbeitsordner (Python/PyQt-App), raeumt ihn auf, prueft ihn und baut mit Inno Setup eine Exe. ' +
                           'WICHTIG: Der Originalordner darf nie veraendert werden. Antworte knapp auf Deutsch und NUR mit einem JSON-Objekt: {"ursache": "...", "loesung": "...", "fix": "<eine der erlaubten IDs oder none>"}. ' +
                           "Erlaubte fix-IDs: $ids. Waehle 'none', wenn keine davon wirklich hilft."
                    $user = "/no_think`nEnde des Protokolls:`n$tail`n`nBereits erkannte Regeln:`n$ruleText`n`nWas ist die wahrscheinlichste Ursache, und was soll der Nutzer tun?"
                    $body = @{ model = 'local'; temperature = 0.1; max_tokens = 450; messages = @(@{ role = 'system'; content = $sys }, @{ role = 'user'; content = $user }) } | ConvertTo-Json -Depth 6
                    $resp = Invoke-RestMethod "http://127.0.0.1:$port/v1/chat/completions" -Method Post -Body ([Text.Encoding]::UTF8.GetBytes($body)) -ContentType 'application/json; charset=utf-8' -TimeoutSec 240
                    $reply = [string]$resp.choices[0].message.content
                    $reply = [regex]::Replace($reply, '(?s)<think>.*?</think>', '').Trim()
                    $json = [regex]::Match($reply, '(?s)\{.*\}')
                    $ai.used = $true; $ai.model = $pick.Name + $(if ($useGpu) { ' (GPU)' } else { ' (CPU)' })
                    if ($json.Success) {
                        try {
                            $o = $json.Value | ConvertFrom-Json
                            $ai.cause = [string]$o.ursache; $ai.solution = [string]$o.loesung
                            $f = [string]$o.fix
                            if ($AllowedFixes.Contains($f)) { $ai.fix = $f }
                        } catch { $ai.cause = $reply }
                    } else { $ai.cause = $reply }
                }
            } catch { $ai.note = "KI-Analyse nicht moeglich: $($_.Exception.Message)" }
            finally { try { $proc.Kill() } catch {} }
        }
    }
}

$fixes = @()
foreach ($id in (@($hits | ForEach-Object { $_.fix }) + @($ai.fix) | Where-Object { $_ } | Select-Object -Unique)) {
    $fixes += [pscustomobject]@{ id = $id; text = $AllowedFixes[$id] }
}
[pscustomobject]@{ hits = $hits; errors = $errorLines; ai = [pscustomobject]$ai; fixes = $fixes } | ConvertTo-Json -Depth 6 | Set-Content $OutJson -Encoding UTF8
