# 16 Development

For everyone who wants to change the code, build installers or contribute to the project.

## 16.1 Project structure

```text
Yume-Companion/
├─ main.py                  Entry point of the PC app (PyQt6, qasync)
├─ installer.bat / start.bat Install packages / start the program
├─ app/
│  ├─ configuration/        Settings, characters, template settings.template.json, branding
│  ├─ gui/                  Interface: sowInterface.py (layout), interface_signals.py (logic),
│  │                        custom_widgets.py, organizer, dashboard, Spotify, backup, vision pages …
│  ├─ translations/         de.yaml, en.yaml, ru.yaml
│  ├─ utils/
│  │  ├─ ai_clients/        Providers (OpenAI, Anthropic, Gemini, …), llama.cpp management, tools (tools.py),
│  │  │                     prompt building, Yume Stage engine, MCP client
│  │  ├─ soul_companion/    Desktop companion (hormone model, plugins)
│  │  ├─ integrations/      Home Assistant
│  │  ├─ speech-to-text/    Whisper, Silero VAD
│  │  └─ *.py               Memory, organizer, routines, skills, knowledge base, documents, web server,
│  │                        dashboard, Spotify, mobile devices, backups, TTS, vision, image generation, Discord …
│  ├─ web_client/           Browser interface (port 8000)
│  └─ models/, voices/, font/, cache/   Runtime data (not in the repository, except font)
├─ assets/                  Backgrounds, ambient, avatars (demo images), branding
├─ android/                 Phone app (Kotlin, Jetpack Compose), Gradle project
├─ llm-server/              Yume LLM Server (C#), build and installer scripts
├─ updater/                 Release tools (build setup/update, verify, error analysis)
├─ rebrand/                 Change name, logo, links (branding)
├─ tests/                   Developer tests (Python)
├─ tools/                   SOW Studio, demo content, screenshot tools, checks
└─ docs/                    this documentation (German in docs/, English in docs/en/)
```

## 16.2 Working from source

1. Set up: [Chapter 01](01-installation.md#13-way-b-from-source) (`tools\setup_from_source.bat`).
2. Start: `start.bat`, or in the activated environment `python main.py`.
3. Settings and characters are created at the first start from `app\configuration\settings.template.json`. Your own test data: `app\data\envs\sow\python.exe tools\demo\make_demo_content.py`.

**Important conventions**
* Interface texts are in `app/translations/*.yaml`. Add new texts as keys in **all** three files; new pages use `tr("key", "default text")`.
* New AI tools: a class in `app/utils/ai_clients/tools.py` (from `BaseTool`) and register it in the `ToolRegistry`; link permissions in the settings.
* Paths always **relative to the project folder** and without fixed user names. Personal data belongs in `%LOCALAPPDATA%\YumeCompanion`, not in the project.
* Never put secrets into the repository: see `.gitignore` and `tools/dev/check_upload.ps1`.

## 16.3 Tests

```powershell
powershell -ExecutionPolicy Bypass -File tests\run_tests.ps1          # offline, safe
powershell -ExecutionPolicy Bypass -File tests\run_tests.ps1 -Live    # additionally: real connections (LLM server, Spotify, routes)
```

The tests run with the app's Python environment (`app\data\envs\sow`) in "offscreen" mode and cover, among other things, quick commands, organizer, routines, lists, undo, diary, scenes, inbox, knowledge base, rain alert, tool model, presence, documents and skills (see `tests/Testliste.md` for the manual test list and `tests/README.txt`). **Caution:** Run the tests with a test profile (set `LOCALAPPDATA` to an empty folder) if you have real organizer data:

```powershell
$env:LOCALAPPDATA = "$env:TEMP\yume-test"; powershell -File tests\run_tests.ps1
```

Android: `android\run-unit-tests.ps1` (see 16.5). In addition there is a simple check in `.github/workflows` (syntax of all Python files).

## 16.4 Building setup and updates (Windows)

The **Yume Release Tool** (`updater\Yume Release Tool.bat`) builds a clean setup from your **working folder**:

* works only in a **temporary copy**, your original stays unchanged;
* removes everything `installer.bat` installs afterwards, as well as cache, logs and personal data;
* resets settings to the **templates** (`updater\installer_build\templates`);
* **Full installer** (about 2 GB, with component selection) or **Update only** (small: only program code and new packages from `requirements_extra.txt`);
* checks the result on request (`Yume Verify.ps1`: reset state, syntax, imports, interface starts headless, AI smoke test with a mini model);
* on errors `Yume Doctor.ps1` explains with rules (and, if a strong local model is installed, with AI) what went wrong and offers **safe** fixes.

Requirements: **Inno Setup 6** (the tool offers to install it with `winget`) and a working folder **with** the installed environment `app\data\envs\sow` (that is, a normally installed program, not the bare repository). The tool assumes no paths: you choose source and output folder in the window.

Tip: The working folder should stay **clean** (do not start it before you build), otherwise chats and logs end up in the setup. The templates and the check catch this but do not replace a look at `check_upload.ps1`. Also check for **private files in `app/configuration`** (backup copies of characters) and for third-party assets (backgrounds, emoji images, voices) before you build.

> **Note on the templates:** `templates\make_templates.py` creates the templates from your working folder. It resets personal values, devices, **tokens and device IDs**. (In this version `dashboard_token` and `android_host_id` were added; earlier setups otherwise carried the same dashboard token in every installation.)

The **Yume Updater** (`updater\YumeUpdaterLauncher.cs`, `yume_updater_setup.iss`) is only the **starter** of the Release Tool (opens the PowerShell interface without a console window). `Build Updater Installer.ps1` builds the installer of the Release Tool from it.

## 16.5 Building and testing the Android app

```powershell
android\build-apk.bat                  # build APK (sets up JDK, Android SDK, Gradle if needed, several GB)
android\run-unit-tests.ps1             # tests; also writes pictures of the screens (YUME_SHOTS=…)
```

* Result: `%LOCALAPPDATA%\YumeAndroidBuild\Yume-Companion.apk` (debug-signed, for your own use). Put it into `tools\android\` so that the PC app offers it for saving. For a release in the Play Store you need your own signing key (never in the repository).
* `app/src/test/…` contains JVM tests without a phone: `LayoutTest` and `DocShotsTest` render real Compose screens (Robolectric) and save PNGs; `WakeMatchTest`, `QuickCommandsTest`, `CallRulesTest` check the logic.
* Structure: `core/` (connection, chat, settings), `voice/` (call, wake word, speaker recognition, assistant panel), `device/` (phone control, alarm clock, Spotify, call protection, camera, automations), `ui/` (Compose screens, 3D avatar), `offline/` (emergency model).
* The project does **not** contain `android/local.properties` (it holds your SDK path); it is created when building.

## 16.6 Building the LLM server

See [Chapter 12.7](12-llm-server.md#127-building-it-yourself): `llm-server\Build Yume LLM Server.ps1` (compiler `csc.exe` from Windows, Inno Setup for the installer).

## 16.7 Branding (name, logo, links)

`rebrand\SoW-Rebrand.bat` changes **only** `app/configuration/branding.json` and the images under `assets/custom_branding/` (with a backup of the old file in `rebrand\backups`): program name, short name, author ("Made by" with link), logos, **links** (website, docs, support, Discord, GitHub, YouTube) and **update repository**, info text and additional credits, start window (banner text). *Use default* = original value, own value = your text, *leave empty* = hide the element. Saving/loading profiles switches complete brands.

* Python: `rebrand\python_path.txt` (one line, path to a `python.exe` with PyQt6) or the project's environment (`..\app\data\envs\sow`).
* **Important for the GPL:** You may change name and logo, but you **must not remove the credit to the original author (jofizcd)** (`NOTICE.md`, About dialog, `LICENSE`).
* Restart the app after saving.
* Before the release, add the **update repository** (`Kreqzxoo/Yume-Companion`) so that the check at program start asks your repository.

## 16.8 SOW Studio and other helper programs

| Program | Purpose |
| --- | --- |
| `tools\SOW-Studio.bat` (`sow_studio.py`) | small extra tool for wake word/echo protection, audio/GPU values, logo, title, credits and the German translations (entries that still equal the English can be filtered). **Close the app first** |
| `tools\demo\make_demo_content.py` | Sample characters, images, persona, lorebook, scene (made up, free) |
| `tools\dev\take_screenshots.py` | Pictures of the PC app for the docs (see 16.9) |
| `tools\dev\take_web_screenshots.py` | Pictures of web client and dashboard (Playwright) |
| `tools\dev\capture_window.ps1` | Photograph the window of a Windows program (e.g. LLM server) |
| `tools\dev\check_upload.ps1` | Upload check for secrets, large/forbidden files |
| `tools\dev\make_yume_icons.py` | Create the interface icons |
| `tools\fetch_models.py` | download the two small models |
| `tools\setup_from_source.bat` | Installation from source |

## 16.9 Regenerating documentation and images

All pictures in `docs/images` come from the real software with demo data and can be regenerated:

```powershell
# 1) Demo content (characters Yume, Mika, Kai, persona, lorebook, scene)
app\data\envs\sow\python.exe tools\demo\make_demo_content.py

# 2) PC app: pages, settings, dialogs, chat (uses an empty LOCALAPPDATA so that no private data is visible)
$env:YUME_ROOT = (Get-Location).Path
$env:LOCALAPPDATA = "$env:TEMP\yume-shots"
app\data\envs\sow\python.exe tools\dev\take_screenshots.py docs\images\pc alle

# 3) Web client and dashboard: first start  take_screenshots.py <folder> web  (prints the token), then
app\data\envs\sow\python.exe tools\dev\take_web_screenshots.py <token> docs\images\web

# 4) Phone app (without a phone)
$env:YUME_SHOTS = "$PWD\docs\images\android"; android\run-unit-tests.ps1
```

The script `take_screenshots.py` replaces user names and paths in labels as well as fields with token/key/address by placeholders. Still check the pictures before you publish them.

## 16.10 Contributing

* Issues and pull requests are welcome (see [CONTRIBUTING.md](../../CONTRIBUTING.md)).
* Keep changes small, test them (16.3) and describe them briefly.
* Every file you add must be under **GPL-3.0-compatible** terms. No models, voices, images or characters without a clear license.
