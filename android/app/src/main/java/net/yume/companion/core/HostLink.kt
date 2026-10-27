// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion.core

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.os.BatteryManager
import android.os.Build
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import net.yume.companion.App
import net.yume.companion.device.CommandExecutor
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONArray
import org.json.JSONObject

enum class Link { OFFLINE, CONNECTING, CONNECTED }

/** Persistent WebSocket to the Yume PC (role=phone): chat events in, device commands in, results out. */
object HostLink {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var job: Job? = null
    @Volatile private var socket: WebSocket? = null

    private val _state = MutableStateFlow(Link.OFFLINE)
    val state = _state.asStateFlow()
    private val _where = MutableStateFlow("offline")
    val where = _where.asStateFlow()
    private val _events = MutableSharedFlow<JSONObject>(extraBufferCapacity = 128)
    val events: SharedFlow<JSONObject> = _events.asSharedFlow()
    private val _detail = MutableStateFlow("")
    val detail = _detail.asStateFlow()
    private var netCallback: ConnectivityManager.NetworkCallback? = null
    @Volatile private var kick: CompletableDeferred<Unit>? = null

    val connected: Boolean get() = _state.value == Link.CONNECTED

    fun start() {
        if (job?.isActive == true || !Prefs.paired) return
        val ctx = App.instance
        registerNetwork(ctx)
        job = scope.launch { loop(ctx) }
    }

    fun stop() {
        job?.cancel(); job = null
        socket?.close(1000, "bye"); socket = null
        _state.value = Link.OFFLINE
    }

    fun restart() { stop(); start() }

    private fun registerNetwork(ctx: Context) {
        if (netCallback != null) return
        val cm = ctx.getSystemService(ConnectivityManager::class.java)
        val cb = object : ConnectivityManager.NetworkCallback() {
            // Wi-Fi <-> mobile data switch: the old socket is dead, reconnect (and re-detect local vs. external)
            override fun onAvailable(network: Network) { socket?.cancel(); kick?.complete(Unit) }
            override fun onLost(network: Network) { socket?.cancel() }
        }
        netCallback = cb
        try { cm.registerDefaultNetworkCallback(cb) } catch (_: Exception) {}
    }

    private suspend fun loop(ctx: Context) {
        var attempt = 0
        while (currentCoroutineContext().isActive) {
            if (!Prefs.paired) { delay(3000); continue }
            _state.value = Link.CONNECTING
            val base = Host.resolve(ctx)
            _where.value = Host.where
            if (base == null) {
                _state.value = Link.OFFLINE
                _detail.value = tr("PC nicht erreichbar", "PC not reachable")
                if (Prefs.wolEnabled && Prefs.wolAuto && attempt % 4 == 0) WakeOnLan.wake()
                attempt++
                val wait = CompletableDeferred<Unit>(); kick = wait
                withTimeoutOrNull((3000L * minOf(attempt, 8))) { wait.await() }
                continue
            }
            attempt = 0
            val closed = CompletableDeferred<Unit>()
            val wsUrl = base.replaceFirst("http", "ws") + "/ws?role=phone&token=" + java.net.URLEncoder.encode(Prefs.token, "UTF-8")
            val ws = Host.clientFor(base).newBuilder().pingInterval(20, java.util.concurrent.TimeUnit.SECONDS).build()
                .newWebSocket(Request.Builder().url(wsUrl).build(), object : WebSocketListener() {
                    override fun onOpen(webSocket: WebSocket, response: Response) {
                        socket = webSocket
                        _state.value = Link.CONNECTED
                        _detail.value = ""
                        webSocket.send(hello().toString())
                        scope.launch { Sync.onConnected() }
                    }
                    override fun onMessage(webSocket: WebSocket, text: String) { handle(webSocket, text) }
                    override fun onClosed(webSocket: WebSocket, code: Int, reason: String) { closed.complete(Unit) }
                    override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                        if (response?.code == 1008 || response?.code == 403) _detail.value = tr("Zugriff entzogen – bitte neu koppeln", "Access revoked – please pair again")
                        closed.complete(Unit)
                    }
                })
            val wait = CompletableDeferred<Unit>(); kick = wait
            select2(closed, wait)
            socket = null
            ws.cancel()
            _state.value = Link.OFFLINE
            delay(1500)
        }
    }

    private suspend fun select2(a: CompletableDeferred<Unit>, b: CompletableDeferred<Unit>) {
        coroutineScope {
            val j1 = launch { a.await() }
            val j2 = launch { b.await() }
            while (isActive && !j1.isCompleted && !j2.isCompleted) delay(300)
            j1.cancel(); j2.cancel()
        }
    }

    private fun hello(): JSONObject {
        val bm = App.instance.getSystemService(BatteryManager::class.java)
        return JSONObject().put("type", "hello").put("model", Host.deviceName())
            .put("battery", bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY))
            .put("caps", JSONArray(CommandExecutor.capabilities()))
            .put("sdk", Build.VERSION.SDK_INT)
    }

    private fun handle(ws: WebSocket, text: String) {
        val j = try { JSONObject(text) } catch (_: Exception) { return }
        when (j.optString("type")) {
            "device_command" -> scope.launch {
                val res = CommandExecutor.execute(j.optString("action"), j.optJSONObject("params") ?: JSONObject())
                res.put("type", "device_result").put("id", j.optString("id"))
                ws.send(res.toString())
            }
            "character_changed" -> {
                if (Prefs.followHostCharacter) j.optString("character").takeIf { it.isNotEmpty() }?.let { Prefs.character = it }
                _events.tryEmit(j)
            }
            else -> _events.tryEmit(j)
        }
    }

    fun send(obj: JSONObject): Boolean = socket?.send(obj.toString()) ?: false
    fun callStart() { send(JSONObject().put("type", "call_start")) }
    fun callEnd() { send(JSONObject().put("type", "call_end")) }
    fun sendText(text: String): Boolean =
        send(JSONObject().put("type", "user_input").put("character", Prefs.character).put("text", text).apply { if (Quiet.active()) put("mode", "quiet"); if (!Prefs.chatVoice) put("text_only", true) })
}
