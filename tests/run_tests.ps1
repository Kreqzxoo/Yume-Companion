param([string]$Project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path, [switch]$Live)
$py = Join-Path $Project 'app\data\envs\sow\python.exe'
if (-not (Test-Path $py)) { throw "Python der App nicht gefunden: $py" }
$env:QT_QPA_PLATFORM = 'offscreen'
Push-Location $Project
try {
    $tests = @('test_quick_commands.py', 'test_organizer.py', 'test_routines.py', 'test_lists_memory.py', 'test_undo.py', 'test_mood_journal.py', 'test_scenes.py', 'test_inbox.py', 'test_knowledge.py', 'test_rain_alert.py', 'test_weather_tips.py', 'test_agent_jobs_macros.py', 'test_skills.py', 'test_people_trips.py', 'test_pc_wake.py', 'test_kiosk.py', 'test_report_mood_history.py', 'test_voice_mood.py', 'test_documents.py', 'test_drafts_sources_nearby.py', 'test_presence.py', 'test_voice_guard.py', 'test_tool_llm.py', 'test_theme.py')  # test_commute.py needs internet: use -Live
    if ($Live) { $tests += 'test_dashboard_extra.py', 'test_spotify_live.py', 'test_llm_tool_decision.py', 'test_commute.py' }
    foreach ($t in $tests) {
        Write-Host "== $t" -ForegroundColor Cyan
        & $py (Join-Path $PSScriptRoot $t)
        if ($LASTEXITCODE -ne 0) { Write-Host "FEHLER in $t" -ForegroundColor Red }
    }
} finally { Pop-Location }
