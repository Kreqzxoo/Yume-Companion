package net.yume.companion.core

import android.content.Context
import android.content.SharedPreferences
import kotlin.reflect.KProperty

/** All settings of the app. Everything has a sensible default; the external domain is empty until the user enters one. */
object Prefs {
    lateinit var sp: SharedPreferences
    fun init(ctx: Context) { sp = ctx.applicationContext.getSharedPreferences("yume", Context.MODE_PRIVATE) }

    class S(private val k: String, private val d: String) {
        operator fun getValue(o: Any?, p: KProperty<*>): String = sp.getString(k, d) ?: d
        operator fun setValue(o: Any?, p: KProperty<*>, v: String) { sp.edit().putString(k, v).apply() }
    }
    class B(private val k: String, private val d: Boolean) {
        operator fun getValue(o: Any?, p: KProperty<*>): Boolean = sp.getBoolean(k, d)
        operator fun setValue(o: Any?, p: KProperty<*>, v: Boolean) { sp.edit().putBoolean(k, v).apply() }
    }
    class L(private val k: String, private val d: Long) {
        operator fun getValue(o: Any?, p: KProperty<*>): Long = sp.getLong(k, d)
        operator fun setValue(o: Any?, p: KProperty<*>, v: Long) { sp.edit().putLong(k, v).apply() }
    }
    class I(private val k: String, private val d: Int) {
        operator fun getValue(o: Any?, p: KProperty<*>): Int = sp.getInt(k, d)
        operator fun setValue(o: Any?, p: KProperty<*>, v: Int) { sp.edit().putInt(k, v).apply() }
    }

    // ---- connection / pairing
    var hostId by S("host_id", "")
    var hostName by S("host_name", "")
    var token by S("token", "")
    var deviceId by S("device_id", "")
    var localUrl by S("local_url", "")
    var externalUrl by S("external_url", "")          // empty by default: any domain pointing to the Yume PC can be entered later
    var lastUrl by S("last_url", "")
    var macs by S("macs", "")                         // comma separated MAC addresses of the PC (Wake-on-LAN)
    var character by S("character", "")
    var spotifyClientId by S("spotify_client_id", "")
    var followHostCharacter by B("follow_host_character", true)
    var preferLocal by B("prefer_local", true)
    var keepConnected by B("keep_connected", true)

    // ---- language
    var speakerLock by B("speaker_lock", false)       // the wake word only reacts to the enrolled voice
    var speakerVec by S("speaker_vec", "")            // voice print = mean of all samples (comma separated numbers)
    var speakerPrints by S("speaker_prints", "")      // the single samples (JSON list): enrolled ones + the ones learned while it is used
    var voiceId by B("voice_id", false)               // tell voices apart: owner / named guests / unknown (sent with every sentence)
    var voiceGuests by S("voice_guests", "")          // JSON {name: [[vector samples]]}
    var speakerStrict by I("speaker_strict", 50)      // accepted distance to the voice print x 100 (lower = stricter)
    var wakeLang by S("wake_lang", "")                // language of the wake word listener ("" = same as the speech recognition)
    fun wakeLanguage(): String = wakeLang.ifEmpty { language }
    var language by S("language", Lang.defaultSpeechLanguage())   // speech recognition / wake word language (de, en, ru, ...); default = language of the phone
    var uiLang by S("ui_lang", "auto")                // language of the app texts: auto (follow the phone) | de | en

    // ---- wake word
    var wakeEnabled by B("wake_enabled", false)       // switched on manually by the user
    var wakeWords by S("wake_words", "yume, hey yume, hallo yume")
    var wakeSensitivity by I("wake_sensitivity", 60)  // 0..100
    var wakeBeep by B("wake_beep", true)
    var wakeVibrate by B("wake_vibrate", false)
    var wakeReplyOn by B("wake_reply_on", true)      // she answers the wake word with her voice
    var wakeReplies by S("wake_replies", net.yume.companion.voice.WakeVoice.DEFAULT_PHRASES)
    var wakeOverlay by B("wake_overlay", true)       // assistant panel over other apps when the wake word is heard
    var wakeOnlyCharging by B("wake_only_charging", false)
    var wakeScreenOffOk by B("wake_screen_off_ok", true)

    // ---- call / voice
    var bargeIn by S("barge_in", "voice")             // off | voice | word
    var bargeWords by S("barge_words", "yume, stopp, stop, halt, warte, wait")
    var vadSensitivity by I("vad_sensitivity", 55)    // 0..100
    var ttsVolume by I("tts_volume", 100)             // 0..200 %: her voice (above 100 it is amplified)
    var silenceMs by I("silence_ms", 900)
    var echoCancel by B("echo_cancel", true)
    var speaker by B("speaker", true)                 // speakerphone vs. earpiece
    var oneShotIdleSec by I("oneshot_idle_sec", 12)   // after wake word: hang up after this much silence
    var hangupWords by S("hangup_words", "auflegen, tschüss, ende, hang up, goodbye")
    var callKeepScreenOn by B("call_keep_screen_on", true)
    var greetOnWake by B("greet_on_wake", false)
    var phoneTtsRate by I("phone_tts_rate", 100)

    // ---- phone control
    var allowControl by B("allow_control", true)
    var allowApps by B("allow_apps", true)
    var allowCalls by B("allow_calls", true)
    var allowSms by B("allow_sms", true)
    var allowScreen by B("allow_screen", true)
    var allowCamera by B("allow_camera", true)
    var allowLocation by B("allow_location", true)
    var allowNotifications by B("allow_notifications", true)
    var allowContacts by B("allow_contacts", true)
    var confirmRisky by B("confirm_risky", true)      // calls / SMS / typing must be confirmed on the phone
    var autoWifiOn by B("auto_wifi_on", false)            // "when I come home": one sentence is carried out when the phone joins the home Wi-Fi
    var autoWifiSsid by S("auto_wifi_ssid", "")
    var autoWifiSentence by S("auto_wifi_sentence", "")
    var autoWifiLast by L("auto_wifi_last", 0L)
    var shareAutoAsk by B("share_auto_ask", true)         // after "Share -> Yume" Yume tells right away what is in the item
    var quietOn by B("quiet_on", false)                   // quiet mode: softer voice at night, the PC answers calmly and short
    var quietFrom by S("quiet_from", "22:00")
    var quietTo by S("quiet_to", "07:00")
    var quietVolume by I("quiet_volume", 50)
    var callScreenOn by B("call_screen_on", false)        // call protection (needs the role "caller ID & spam app")
    var callAnnounce by B("call_announce", true)          // announce who is calling (name of the contact / unknown number)
    var callBlockPrefixes by S("call_block_prefixes", "0900,0137,01805")
    var callSilenceNight by B("call_silence_night", false)
    var kioskCache by S("kiosk_cache", "")                // last data of the wall / tablet display (shown when the PC is away)
    var kioskNightDim by B("kiosk_night_dim", true)
    var pinHash by S("pin_hash", "")                  // security PIN (SHA-256): when set, risky actions need the PIN in the confirmation
    fun hashPin(pin: String): String = java.security.MessageDigest.getInstance("SHA-256").digest(("yume:" + pin).toByteArray()).joinToString("") { "%02x".format(it) }
    var autoScreenshot by B("auto_screenshot", true)  // after every operated step the AI gets a fresh screenshot
    var screenshotQuality by I("screenshot_quality", 60)
    var screenshotMaxEdge by I("screenshot_max_edge", 1280)
    var agentLogMax by I("agent_log_max", 200)

    // ---- car mode
    var carAutoStart by B("car_auto_start", false)
    var carBtNames by S("car_bt_names", "")
    var carReadNotifications by B("car_read_notifications", true)
    var carBigUi by B("car_big_ui", true)
    var driveDash by B("drive_dash", true)                // car mode shows the drive dashboard (next appointment + navigation, music keys)

    // ---- offline emergency mode
    var offlineEnabled by B("offline_enabled", true)
    var offlineAutoSwitch by B("offline_auto_switch", true)
    var offlineModel by S("offline_model", "qwen05")
    var offlineLoading by S("offline_loading", "")       // model that is being loaded right now (still set at the next start = the load crashed the app)
    var offlineBroken by S("offline_broken", "")         // ids of offline models that crashed while loading on this phone
    var offlineHandoverBack by B("offline_handover_back", true)
    var offlineMaxTokens by I("offline_max_tokens", 384)
    var syncOnConnect by B("sync_on_connect", true)

    // ---- wake on LAN
    var wolEnabled by B("wol_enabled", true)
    var wolAuto by B("wol_auto", false)               // wake the PC automatically when it cannot be reached
    var wolWebhook by S("wol_webhook", "")            // optional URL (router / smart plug) for waking from outside the home network

    // ---- characters / start
    var defaultCharacter by S("default_character", "")
    var askCharacterOnStart by B("ask_character_on_start", true)
    var cachedCharacters by S("cached_characters", "")   // comma separated, for the picker when the PC is not reachable

    // ---- look: background, avatar, chat
    var bgMode by S("bg_mode", "anim")                // anim | host | custom
    var bgDim by I("bg_dim", 35)
    var bgParticles by B("bg_particles", true)
    var bgCustomPath by S("bg_custom_path", "")
    var showAvatar by B("show_avatar", true)
    var avatarPercent by I("avatar_percent", 45)
    var avatarZoom by I("avatar_zoom", 85)             // size of the 3D model in its frame, percent
    var avatarBodyAnim by B("avatar_body_anim", true)  // full-body animations to the emotions of the chat (3D avatar)
    var chatVoice by B("chat_voice", false)            // the character's voice in the chat (not only in calls)
    var chatFontPercent by I("chat_font_percent", 100)

    // ---- look & feel
    var keepScreenOnHome by B("keep_screen_on_home", false)
    var haptics by B("haptics", true)
    var firstRunDone by B("first_run_done", false)

    fun wakeWordList(): List<String> = wakeWords.split(',', ';').map { it.trim().lowercase() }.filter { it.isNotEmpty() }
    fun bargeWordList(): List<String> = bargeWords.split(',', ';').map { it.trim().lowercase() }.filter { it.isNotEmpty() }
    fun hangupWordList(): List<String> = hangupWords.split(',', ';').map { it.trim().lowercase() }.filter { it.isNotEmpty() }
    fun macList(): List<String> = macs.split(',').map { it.trim() }.filter { it.isNotEmpty() }
    val paired: Boolean get() = token.isNotEmpty() && (localUrl.isNotEmpty() || externalUrl.isNotEmpty())
}
