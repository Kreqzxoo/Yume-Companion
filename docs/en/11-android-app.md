# 11 Android App

The phone app **Yume Companion for Android** is a *client*: the computing power (language model, voice, memory) stays on your PC. The phone contributes microphone, speaker, camera and the control of the phone. If the PC fails, a small emergency model answers directly on the phone.

> The pictures in this chapter are created without a phone: the app renders its real screens on the PC (`android/run-unit-tests.ps1`, file `DocShotsTest.kt`) with made-up demo data (characters "Aiko" and "Mika", address `192.168.1.50`). On the phone, fonts and colors look the same.
>
> **Note:** The Android app's screens currently use **German** labels. This chapter gives the English meaning of each setting; the German label can differ slightly in wording.

## 11.1 Requirements

| | |
| --- | --- |
| Phone | Android **9 or newer** (API 28). Recommended: Android 12+ |
| Network | Phone and PC on the **same Wi-Fi** (on the go via your own domain, see 11.4) |
| PC | Yume Companion is running, **web server started** (Android Connector) |

## 11.2 Getting and installing the APK

* **Ready-made APK:** download `Yume-Companion.apk` under *Releases*, **or** on the PC *Settings → Android Connector → Save APK for the phone …* and copy it to the phone (USB, network folder, cloud).
* **Build it yourself** (see [Chapter 16](16-entwicklung.md)): `android\build-apk.bat` sets up JDK, Android SDK and Gradle if needed and produces the APK in `%LOCALAPPDATA%\YumeAndroidBuild\Yume-Companion.apk` (about 78 MB). Put it into `tools\android\` of the PC program so that the button "Save APK for the phone" offers it.
* On the phone open the APK and allow **installation from unknown sources** (only for this file/source).

## 11.3 Pairing

**On the PC:** *Settings → Android Connector*.

![Android Connector on the PC](../images/pc/optionen_10_android_connector.png)

1. **Start web server** (port 8000). If it is not running, the page warns: *"The web server is not running – otherwise the phone cannot pair."*
2. **Allow the phone through the Windows firewall …** (administrator prompt). The page reports if the firewall probably blocks connections.
3. A **QR code** appears. It is valid for only a few minutes and **can be used only once**; it is renewed automatically ("Code valid for … s"). With **Generate new QR code** you get a fresh one.
4. Alternatively **Copy pairing link** (instead of QR).

**On the phone:**

![Pairing screen of the app](../images/android/01_koppeln.png)

1. Open the app → **Pair with QR code** → scan the QR code on the PC (camera permission).
2. Or **Enter link or address manually** (e.g. `192.168.0.20:8000`).
3. The phone receives its **own key that can be revoked at any time**. On the PC you see all **Paired devices** and can block any of them with **Remove selected device (revoke access)**. After that it must be paired again.
4. The PC also shows "Last contact from phone: IP (N s ago)". If no contact arrives, it is usually the network (Wi-Fi isolation, guest Wi-Fi, VPN on the phone).

More switches on the PC (page *Android Connector*):

| Switch | Effect |
| --- | --- |
| **The AI may operate the phone** | allows opening apps, reading the screen, calling … |
| **During phone calls: voice only on the phone** | PC speakers stay silent |
| **Send only the spoken part to the phone** | without *actions* and descriptions (text in quotation marks) |
| **Start Android Connector together with the program** | web server starts automatically |

## 11.4 Connecting on the go (optional)

The app detects by itself whether it is in the home network (local address) or on the go (external domain). For the road you need an **HTTPS domain** that points to the PC web server, e.g. through a **Cloudflare Tunnel** to `http://localhost:8000`. In the app under *Settings → Connection* enter the **external domain**.

* **Wake-on-LAN** wakes the PC from standby: *Allow Wake-on-LAN*, *MAC address(es) of the PC*, *Wake PC automatically*. For the road there is a **wake webhook**.
* A Cloudflare error **523** means: Cloudflare cannot reach your PC (check tunnel/port/service), not that the model is missing.
* Protect the external access. Never share the web token publicly.

## 11.5 Replacing the Google Assistant

Yume can **replace the Google Assistant** on the phone. The app registers with Android as a *digital assistant* (`VoiceInteractionService`). That means:

* **Long-press the home button** or **swipe from the corner** opens Yume instead of Google.
* **Wake word on the home screen:** If you say your wake word ("Yume …") while the home screen or any other app is in front, a **translucent assistant panel** slides up from the bottom over the screen. It shows that she is listening, what she understood and what she answers, and she speaks the answer aloud.
* The panel stays until **you** close it (*Close*, back, home, tap outside). It does not listen all the time: one question, one answer, then it waits for the wake word again. *Open app* jumps into the full app.

![Assistant panel over the home screen](../images/android/13_assistent_startbildschirm.png)

*Illustration reconstructed: the home screen in the background is a placeholder, the lower panel is the app's real assistant panel, rendered on the PC.*

**Setting it up:**

1. *Settings → Permissions:* allow **Display over other apps** (needed for the panel) and grant microphone and notifications. Exempt Yume from battery optimization so that the wake word listens in the background.
2. *Settings → Permissions → Set up as assistant → Choose default assistant …* opens Android's "Default apps" page. There set **Digital assistant** to **Yume Companion**.
3. *Settings → Speech & wake word:* turn on the wake word and keep **Assistant panel on detection** active. With **Only react to my voice** (like "Voice Match" of the Google Assistant) the wake word reacts only to you; this runs completely on the phone.

The name of the Android setting differs by manufacturer (Samsung, Xiaomi, Pixel …), usually under *Settings → Apps → Default apps*.

## 11.6 The main screens

At the bottom the menu bar: **Yume · Call · Offline · Settings**. At start you choose (or the app takes the default) the **character**.

![Choose character](../images/android/02_charakter_waehlen.png)

### Yume (chat)

![Chat, connected](../images/android/04_chat_verbunden.png)

* Header: **character name**, connection indicator (**Local**, **External**, **Offline**), switches for character list, call and settings.
* **Avatar**: her picture breathes lightly. With **Choose 3D model …** you download the VRM model from the PC once; afterwards it is animated on the phone itself (lip movement, emotions, body animations; also works without the PC).
* **Messages** like in a messenger with time; while she answers you see the text appear. The line *"✓ Spotify opened"* shows live what the AI is doing on the phone right now.
* If the PC is not reachable, the app offers **Wake PC (Wake-on-LAN)**, **Offline emergency mode** and **Try again**:

![PC not reachable](../images/android/03_start_offline.png)

### Call

![Start call](../images/android/05_anruf_start.png)

**Start call**: hands-free conversation with continuous microphone and voice activity detection. Every sentence goes to the PC, she answers with her PC voice. You can **interrupt her at any time**. During the conversation the app shows what she heard and what she answers:

![In conversation](../images/android/09_im_gespraech.png)

* **Video call:** The phone camera appears small in the call; with every sentence the newest camera image goes to the PC, whose vision model describes it. So she sees one moment per sentence, not a continuous video stream.
* **Car mode** (button at the bottom): hands-free, large controls, notifications are read aloud (see 11.10).

### Offline (emergency mode)

![Offline emergency mode](../images/android/06_offline_notfallmodus.png)

When the PC is missing, a **small language model directly on the phone** answers (much simpler than the PC AI). You download **model** (e.g. *Qwen 2.5 – 0.5 B*, about 560 MB, Wi-Fi recommended) and **speech recognition** (about 50 MB) once. Switches: **Switch automatically** (PC gone → phone answers itself), **Tell the PC about offline conversations** (short version after the return), **Synchronize on connecting** (fetch character and latest messages). If a model crashes on your phone, the app marks it as "crashed" and no longer uses it. This screen also shows a crash report.

## 11.7 Settings on the phone

The *Settings* page is divided into sections.

![Settings, connection](../images/android/07_einstellungen.png)

### Connection
**Local address (home network)**, **external domain**, **prefer local** (use the local address first even on mobile data, e.g. with VPN), **keep connection in the background** (permanent notification so that the PC can reach the phone), **adopt the PC's character**, **test connection**, **wake PC**, **connect to new PC / device**, **only unpair …**. Plus the Wake-on-LAN fields:

![Connection: Wake-on-LAN](../images/android/einstellungen_verbindung.png)

### App language
The app comes in **German and English**. The default is **Automatic**: a German phone shows German, every other phone English. Set it permanently under *Settings → App language*. The language applies to all menus, messages, the phone commands (e.g. "turn the flashlight on", "set a timer for 10 minutes", "interpreter French") and the default phrases of the wake word.

### Speech & wake word
The wake word ("Hey Yume") listens in the background **offline** (Vosk) without an account.

![Wake word](../images/android/einstellungen_wake_word.png)

| Setting | Meaning |
| --- | --- |
| **Recognition language** | German or English; one speech model each to download (about 40–50 MB). English names are recognized much better by the English model |
| **Wake word active** | Microphone listens in the background (also via quick-settings tile and app switch) |
| **Wake words** | several, comma separated; mishearings are tolerated too ("hai jume") |
| **Sensitivity** | higher = reacts faster, but more often by mistake |
| **Test wake word …** | shows what is recognized and whether it would wake her; tapping a mishearing turns it into another wake word |
| **Only react to my voice** | Speaker model (about 13 MB, Vosk) remembers your voiceprint; TV and other people are ignored. Runs completely on the phone; a comfort filter, **not a security feature** |
| **Tell voices apart / teach a guest** | teach further people by name |
| **Beep / vibration / assistant panel on detection** | how she signals |
| **Yume answers with voice** | Instead of a beep she says e.g. "Yes, I'm listening?" with **her PC voice** (incl. RVC). The sentences are generated on the PC in the best quality, checked with speech recognition and loaded to the phone; several recordings per sentence that you listen to, choose, delete, export or replace with your own audio files |
| **Listen only while charging** | saves battery |

### Conversation

![Conversation](../images/android/einstellungen_gespraech.png)

**Stop words** (interrupt her), **hang-up words** (end the call), **test volume**, **test microphone …** (shows live what the speech recognition sees; the bar is your voice, the line the sensitivity threshold), **Interrupt** (*By speaking*, *Only with stop word* or *Off*), **Echo suppression** (full duplex: telephone audio path plus the phone's echo canceller, so you can talk over her; explanation of the methods in [Chapter 05](05-stimme-und-avatare.md#echo-protection-anti-echo-in-detail)), **speaker**, **keep screen on during conversation**.

![Microphone test](../images/android/12_mikrofontest.png)

### Phone control by the AI

![Phone control](../images/android/einstellungen_handy_steuerung.png)

The AI on the PC may operate your phone. Everything can be switched off individually:

* **Allow control** (main switch) · **Open apps** · **Operate apps** (read screen, type, scroll, back/home, screenshot; via the accessibility service) · **Calls** · **Contacts** · **Camera** · **Location** · **Read notifications**.
* **Confirm risky actions**: calls, SMS and text input are asked by the phone **itself via notification**; with a **PIN** set, an input field appears in the notification instead.
* **Messenger replies:** "Reply I'll be there soon" answers the last message (last 10 minutes) through the messenger's reply function, after confirmation on the phone.
* **View shared files immediately** (Share → Yume, see [Organizer](10-organizer.md#1015-inbox-share-to-yume)).
* **Security PIN (optional, 4–8 digits):** in addition to the confirmation a PIN must be entered (*Save PIN* / *Remove PIN*).
* **Screenshot after every step** (the AI sees what it did, through the vision model on the PC), with **screenshot quality** (default 60 %) and **size** (default 1280 px).

![Security PIN and screenshot settings](../images/android/einstellungen_pin_screenshot.png)
* **Log:** at the bottom you see what Yume did on the phone (stays on the phone; *Clear*).

### Call protection (spam protection)

![Call protection](../images/android/einstellungen_anrufschutz.png)

Set as the **call protection app**, Yume decides on every incoming call: **known contacts** are let through and the name is announced hands-free; **unknown numbers** are blocked by prefix (e.g. `0900`), silenced at night or announced. Settings: *Announce callers*, *Silence unknown callers at night*, *Blocked prefixes*. Answering by voice is not possible for ordinary apps: Yume blocks, silences and tells you.

### Quiet mode
*Quiet mode at night* (from HH:MM to HH:MM, default 10 pm–7 am): quieter voice (volume factor), the PC answers calmly and briefly.

### Automation

![Automation](../images/android/einstellungen_ruhemodus_automatisierung.png)

**"When I come home"**: As soon as the phone enters your **home Wi-Fi** (enter the name or **adopt current Wi-Fi**; needs location permission), Yume executes **one sentence** as if you had said it (e.g. "Good evening" or "Play my playlist Car"). **Try it now** tests it.

### Spotify

![Spotify on the phone](../images/android/einstellungen_spotify_wecker.png)

Enter the client ID of your Spotify app, **Sign in to Spotify** (PKCE; no secret). **Phone and PC share one login**: whoever is signed in passes it on to the other. Yume searches and starts music, pauses, skips and says what is playing (Premium needed). If Spotify is not running, she starts the app and waits.

### Yume alarm clock
"Wake me tomorrow at 8": the phone rings (as a real alarm clock, exact even in sleep mode). **Yume wakes you with words she makes up herself** (from the PC in her voice) and asks how you slept. Without the PC the phone voice says a short "Good morning". After a restart/update the alarms are set again. *Set alarm*, *Test in 30 s*, *Delete*.

### Car mode

![Car mode settings](../images/android/einstellungen_auto_modus.png)

**Start car mode now**, **start automatically** (when the phone connects to the **Bluetooth name of your car**), **read notifications aloud**, **driving dashboard**, **large interface**. This is Yume's **own screen**, not Android Auto (Google does not allow free assistants there):

![Car mode](../images/android/11_auto_modus.png)

Next appointment with a **Navigate** button, music keys and "I'm listening …"; Yume keeps listening by voice.

### Wall and tablet mode

![Wall mode](../images/android/10_wandmodus.png)

For a tablet on the wall or a phone in a dock: large **clock and date**, **weather, appointments, reminders, lists, birthdays, music, mails** and the character (3D model if loaded). She hears the wake word; **tap me to speak**. *Dim at night*. Start via **Start wall/tablet mode**.

### Permissions and assistant role

![Permissions](../images/android/einstellungen_berechtigungen.png)

The list shows every necessary permission with a button to grant it. The app uses: internet/network, microphone, camera, notifications, overlay (assistant panel), phone, SMS, contacts, calendar, location, Bluetooth, autostart, vibration, alarms, exemption from battery optimization.

**Set up as assistant:** Yume replaces the Google Assistant: *long-press the home button* or *swipe from the corner* opens her. If she hears the wake word while another app is in front, a **translucent assistant panel** slides up from below: it shows that she is listening, what she understood and what she answers. It stays until **you** close it (*Close*, back, home, tap outside). It does not listen all the time: one question, one answer, then it waits for the wake word again. Needs "Display over other apps". Details in [11.5](#115-replacing-the-google-assistant).

### Characters and start, background, avatar

* **Choose character at start**, **default character** (with "always ask" off: quiet start with the default).
* **Background:** animated night sky with **floating petals**, the PC's background image or **your own image**.
* **Show avatar (3D / Live2D)**, **body animations for emotions**, **choose 3D model**, **voice in chat**.

![Background and avatar](../images/android/einstellungen_hintergrund_avatar.png)

### Reset

**Reset app …** restores the state of a fresh installation (pairing, settings, alarms, Spotify login, chat cache). Large downloads (3D models, speech models, offline AI) stay unless you choose *delete as well*. **Only unpair** is the smaller variant.

## 11.8 Interpreter mode

"Interpreter English" starts it, "Interpreter off" ends it. Everything you say or type is translated by the **PC's language model**, and the phone **speaks** the translation in the other language (one direction: your language → target language).

## 11.9 Quick commands without a PC

Short commands also work **without the PC and without a language model**: music, flashlight, opening apps, timer, alarm, volume, navigation, reading notifications aloud, time, battery, calls.

## 11.10 Car mode while driving

See above. As soon as the Bluetooth connection to the car is established, the app switches to car mode (hands-free call). Android only allows starting the microphone from a visible app; that is why a notification asks with one tap if the app is not in front.

## 11.11 Privacy on the phone

* All phone actions run **only** if you approve them and can each be switched off individually.
* Wake word, speaker recognition and offline AI run **on the phone**, without an account.
* The phone log stays on the phone.
* The device token can be revoked individually on the PC.

## 11.12 Building your own APK

See [Chapter 16](16-entwicklung.md). The app is open source (`android/`, GPL-3.0 recommended). Dependencies: Jetpack Compose, AndroidX, CameraX, OkHttp, Vosk, MediaPipe GenAI, ML Kit Barcode (Apache-2.0; ML Kit has its own terms of use). Details: [LIZENZEN_UND_UPLOAD.md](../LIZENZEN_UND_UPLOAD.md) (German).
