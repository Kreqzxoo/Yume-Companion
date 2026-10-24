# 15 Troubleshooting

Always first: **look at the log.** The console window at start shows it live; in addition every session is stored in `logs\sow_<date>_<time>.log`, the installation in `logs\installer.log`. The **dashboard** ([Chapter 13](13-web-und-dashboard.md)) has a **self-test** that says in plain language what is missing.

> Logs can contain paths and computer names. Read them and black out names before sharing (e.g. in a GitHub issue).

## Installation and start

| Problem | Cause and solution |
| --- | --- |
| **"Data folder was not found"** in `installer.bat` | The folder `app\data` (Miniconda) is missing. For a source installation run `tools\setup_from_source.bat` first, not `installer.bat` directly |
| Installation aborts with errors for individual packages | The failed parts are listed at the end and in `logs\installer.log`. Running it again (network) usually helps. FlashAttention-2 is optional |
| PyTorch download aborts | The installer retries automatically and waits longer; with very slow connections start it again later |
| **Installer started as administrator** | do not; it changes the working directory and paths. Start normally |
| Crash at start with `ModuleNotFoundError` | Packages are missing: run `installer.bat` again |
| Crash at start, message about `settings.json` / `NoneType` | `settings.json` is damaged or too old. Rename the file, the app recreates it from `settings.template.json` (back up first!) |
| "FFmpeg …" error in `start.bat` | `app\ffmpeg\bin\ffmpeg.exe` is missing (for a source installation `tools\setup_from_source.bat`) |
| Error about embedding model / emotion detection | `app\utils\e5-small-en-ru` or `app\utils\emotions\detector` are missing: `app\data\envs\sow\python.exe tools\fetch_models.py` |
| OneDrive/path with spaces or special characters | Install the program into a short, simple path (e.g. `C:\Yume`) |
| Window stays empty / very slow | Update the graphics driver; *Windows Settings → System → Display → Graphics*: give the app the fast GPU |

## Language model

| Problem | Solution |
| --- | --- |
| **No answer / error 400, "context too small"** | Set *context size* in *Language model & APIs* to at least 8192 (the system prompt needs room) |
| Local model does not load ("model lacks VRAM") | smaller model or quantization (Q4_K_M), fewer **GPU layers**, smaller context, KV cache `q8_0`; otherwise CPU |
| Very slow answers | Model does not fit into VRAM (partly in RAM). Smaller model, Flash Attention on, reasoning mode off, shorter maximum length |
| Strange special-character output (e.g. "im_end") | wrong **chat template**: instead of *Auto* force e.g. ChatML or Llama-3 |
| Character writes for you too | Set **stop strings** (`\nUser:`) |
| **Remote server not reachable** | Is `llama-server` running there with `--host 0.0.0.0`? Firewall rule? Same network? IP correct? Port correct? With the Yume LLM Server: status green, *Check firewall* |
| Remote server answers, but "model not listed" | use the exact model ID from `/v1/models` (Ollama: name and tag) |
| Cloud: "401 / invalid key" | Copy the key again (without spaces), correct provider chosen? |
| After switching to the remote PC characters do not answer | Check *AI services → LLM execution target* and the connection test; there is no automatic fallback to local |

## Voice and ears

| Problem | Solution |
| --- | --- |
| No voice | **assign a voice** to the character; on the first start of a local engine models are downloaded (watch the console) |
| Voice cuts off at the end of a sentence (Qwen3-TTS) | *Maximum characters per segment* 220–280, *silence at the end* 100–250 ms, *maximum new tokens* ≥ 1500 |
| The character hears itself | **Echo protection**: *Half duplex* or **WebRTC AEC3**; check the status ("Recheck AEC3"), test the reference delay |
| Microphone not detected / wrong device | *System & user interface → Audio devices* |
| Wake word reacts too often/too rarely | other phrases (short, distinctive names), Whisper device, silence settings; it is transcript-based and not a special detector |
| Live2D/VRM loads "forever" | wait briefly and do not close; *Yume system* must be active; Live2D only **.moc3** |
| No expression image for an emotion | The file name must match the emotion exactly (`joy.png`); otherwise `neutral.png` is missing |

## Phone and network

| Problem | Solution |
| --- | --- |
| Phone does not pair (no contact) | Web server on the PC **started**? Windows firewall opened (*Android Connector*)? Same Wi-Fi? **Guest Wi-Fi/Wi-Fi isolation** and **VPN on the phone** block it |
| QR code expired | it is valid only a few minutes and once; **Generate new QR code** |
| Connection only in the home network | set up an external HTTPS domain (e.g. Cloudflare Tunnel) and enter it on the phone |
| Cloudflare **error 523** | the tunnel does not reach your PC (check service/port/tunnel), not a model problem |
| Phone does not find the PC (mobile data) | *Prefer local* off, enter external domain, possibly Wake-on-LAN |
| Wake word on the phone does not react in the background | Exempt the app from battery optimization; some manufacturers (e.g. HyperOS) restrict background services; the microphone service can only be started from a visible app |
| Phone control does not work | Turn on the app's *accessibility* service and *notification access*; main switch *Allow control* |
| Offline model crashes | The app marks it as "crashed"; choose a smaller model (Qwen 0.5 B) |

## Integrations

| Problem | Solution |
| --- | --- |
| Spotify controls nothing | **Premium** needed; redirect URI entered exactly as shown; sign in again |
| Home Assistant does not answer | URL reachable from the PC (host address, not Docker bridge), token valid, for control commands the entity in the list |
| Mail login rejected | **App password** instead of main password (Gmail: enable IMAP) |
| Calendar shows nothing | Check the iCal link (secret address); ICS is read-only |
| Image generation fails | Service (A1111/Forge with `--api --listen`, ComfyUI `--listen`) reachable? Enough VRAM (LLM + image at the same time)? |
| Discord bot does not answer | Token correct, bot on the server, intents on in the developer portal |

## Resetting and getting help

* **Reset settings:** rename `app\configuration\settings.json`. At the next start it is created from the clean template.
* **Start over but keep characters:** delete `settings.json`, keep `characters.json` and `.soul`.
* **Report a bug:** as an issue on GitHub with version (`VERSION.txt`), Windows version, graphics card, description, steps and a shortened log (without names/keys). Questions are welcome on [Discord](https://discord.gg/5RBgNMCPKC).
