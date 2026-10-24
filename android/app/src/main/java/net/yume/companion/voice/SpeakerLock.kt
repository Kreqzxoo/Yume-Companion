package net.yume.companion.voice

import net.yume.companion.core.Prefs
import org.json.JSONObject
import org.vosk.Recognizer
import org.vosk.SpeakerModel
import kotlin.math.sqrt

/**
 * "Only my voice": a small offline speaker model (Vosk, ~13 MB) turns every sentence into a voice print (x-vector). You say the wake word a
 * few times once; the average is your voice print. Later the wake word only works when the voice print of what was said is close enough
 * to yours. It runs on the phone, nothing is sent anywhere. It is a convenience filter against other people and the TV - not a security feature.
 */
object SpeakerLock {
    private var model: SpeakerModel? = null

    fun installed(): Boolean = VoskStore.installed("spk")

    @Synchronized fun model(): SpeakerModel? {
        if (!installed()) return null
        return model ?: SpeakerModel(VoskStore.dir("spk").absolutePath).also { model = it }
    }

    fun enrolled(): FloatArray? =
        Prefs.speakerVec.takeIf { it.isNotEmpty() }?.split(',')?.mapNotNull { it.toFloatOrNull() }?.toFloatArray()?.takeIf { it.size >= 64 }

    fun save(v: FloatArray) { Prefs.speakerVec = v.joinToString(",") }
    fun clear() { Prefs.speakerVec = ""; Prefs.speakerPrints = ""; Prefs.speakerLock = false }

    /** the single voice prints (enrolled samples first, then those learned during use) */
    fun prints(): List<FloatArray> = try {
        val arr = org.json.JSONArray(Prefs.speakerPrints.ifEmpty { "[]" })
        (0 until arr.length()).map { i -> arr.getJSONArray(i).let { a -> FloatArray(a.length()) { a.getDouble(it).toFloat() } } }
    } catch (_: Exception) { emptyList() }

    /** stores the samples and the mean that goes with them */
    fun saveAll(list: List<FloatArray>) {
        val arr = org.json.JSONArray()
        list.forEach { v -> arr.put(org.json.JSONArray().also { a -> v.forEach { x -> a.put(x.toDouble()) } }) }
        Prefs.speakerPrints = arr.toString()
        save(average(list))
    }

    /**
     * How far a voice print is from yours (lower = more like you): the better of "distance to the mean" and "the three closest single
     * samples" - a mean alone is too strict when your voice varies (tired, close to / far from the phone).
     */
    fun score(v: FloatArray): Double {
        val mean = enrolled() ?: return 9.0
        val dMean = distance(v, mean)
        val ds = prints().map { distance(v, it) }.sorted()
        val knn = if (ds.size >= 3) ds.take(3).average() else dMean
        return minOf(dMean, knn)
    }

    /** a clearly accepted wake word improves the profile a little (like Google's Voice Match): newest samples replace the oldest learned ones */
    fun learn(v: FloatArray) {
        val list = prints().toMutableList()
        if (list.isEmpty()) return
        list.add(v)
        while (list.size > 24) list.removeAt(10.coerceAtMost(list.size - 1))      // the first 10 (enrolled) stay
        saveAll(list)
    }

    // ---------------------------------------------------------------- several voices (owner, named guests, unknown)
    fun guests(): Map<String, List<FloatArray>> = try {
        val o = org.json.JSONObject(Prefs.voiceGuests.ifEmpty { "{}" })
        o.keys().asSequence().associateWith { k ->
            val arr = o.getJSONArray(k)
            (0 until arr.length()).map { i -> arr.getJSONArray(i).let { a -> FloatArray(a.length()) { a.getDouble(it).toFloat() } } }
        }
    } catch (_: Exception) { emptyMap() }

    fun saveGuest(name: String, list: List<FloatArray>) {
        val o = try { org.json.JSONObject(Prefs.voiceGuests.ifEmpty { "{}" }) } catch (_: Exception) { org.json.JSONObject() }
        val arr = org.json.JSONArray()
        list.forEach { v -> arr.put(org.json.JSONArray().also { a -> v.forEach { x -> a.put(x.toDouble()) } }) }
        o.put(name.trim(), arr)
        Prefs.voiceGuests = o.toString()
    }

    fun deleteGuest(name: String) {
        val o = try { org.json.JSONObject(Prefs.voiceGuests.ifEmpty { "{}" }) } catch (_: Exception) { return }
        o.remove(name); Prefs.voiceGuests = o.toString()
    }

    /** voice print of a whole recorded sentence (16 kHz mono PCM), or null (too short / models missing) */
    fun vectorOfPcm(pcm: ByteArray): FloatArray? {
        val rec = newRecognizer(Prefs.wakeLanguage()) ?: return null
        return try {
            var i = 0
            while (i < pcm.size) { val n = minOf(3200, pcm.size - i); rec.acceptWaveForm(pcm.copyOfRange(i, i + n), n); i += n }
            vectorOf(rec.finalResult)
        } catch (_: Exception) { null } finally { try { rec.close() } catch (_: Exception) {} }
    }

    /** "owner", a guest's name, "unknown" - or "" when voices are not told apart (switch off / no voice print / no model) */
    fun identify(pcm: ByteArray): String {
        if (!Prefs.voiceId || !installed() || enrolled() == null) return ""
        val v = vectorOfPcm(pcm) ?: return ""
        if (score(v) <= threshold()) return "owner"
        val best = guests().mapValues { (_, list) -> if (list.isEmpty()) 9.0 else distance(v, average(list)) }.minByOrNull { it.value }
        return if (best != null && best.value <= 0.55) best.key else "unknown"
    }

    /** the lock is switched on, a voice print exists and the model is there */
    fun active(): Boolean = Prefs.speakerLock && enrolled() != null && installed()

    /** distances up to this value count as "you" (cosine distance 0..2; same voice is usually below 0.5) */
    fun threshold(): Double = Prefs.speakerStrict / 100.0

    /** recogniser for the wake word; with the speaker model attached its final results carry the voice print */
    fun newRecognizer(lang: String): Recognizer? {
        val m = VoskStore.model(lang) ?: return null
        val s = model()
        return if (s != null) Recognizer(m, 16000f, s) else Recognizer(m, 16000f)
    }

    /** voice print of a final recogniser result, or null (too short / no speaker model) */
    fun vectorOf(resultJson: String): FloatArray? = try {
        val j = JSONObject(resultJson)
        val arr = j.optJSONArray("spk")
        if (arr == null || j.optInt("spk_frames", 0) < 20) null else FloatArray(arr.length()) { arr.getDouble(it).toFloat() }
    } catch (_: Exception) { null }

    fun distance(a: FloatArray, b: FloatArray): Double {
        if (a.size != b.size) return 2.0
        var dot = 0.0; var na = 0.0; var nb = 0.0
        for (i in a.indices) { dot += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i] }
        return if (na == 0.0 || nb == 0.0) 2.0 else 1.0 - dot / (sqrt(na) * sqrt(nb))
    }

    /** mean of several voice prints (each one length-normalised first) */
    fun average(list: List<FloatArray>): FloatArray {
        val out = FloatArray(list[0].size)
        for (v in list) {
            val n = sqrt(v.fold(0.0) { s, x -> s + x * x }).toFloat().coerceAtLeast(1e-6f)
            for (i in v.indices) out[i] += v[i] / n / list.size
        }
        return out
    }
}
