package net.yume.companion

import net.yume.companion.device.QuickCommands
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Rule
import org.junit.Test
import org.junit.rules.ExternalResource
import java.util.Locale

/** the app speaks German on a German phone and English otherwise: the tests pin the phone language */
class PhoneLocale(private val locale: Locale) : ExternalResource() {
    private lateinit var before: Locale
    override fun before() { before = Locale.getDefault(); Locale.setDefault(locale) }
    override fun after() { Locale.setDefault(before) }
}

/** Which sentences are quick commands (carried out without the PC) and which ones are left to the language model. Spotify is not connected here. */
class QuickCommandsTest {
    @get:Rule val phone = PhoneLocale(Locale.GERMAN)
    private fun label(s: String) = QuickCommands.detect(s)?.label

    @Test fun phoneCommandsAreRecognised() {
        assertEquals("Schalte die Taschenlampe …", label("Taschenlampe an"))
        assertEquals("Schalte die Taschenlampe …", label("mach bitte die Taschenlampe aus"))
        assertEquals("Öffne whatsapp …", label("öffne WhatsApp"))
        assertEquals("Öffne spotify …", label("kannst du mir bitte Spotify öffnen"))
        assertEquals("Öffne instagram …", label("öffne mir Instagram auf dem Handy"))
        assertEquals("Stelle den Timer …", label("stelle einen Timer auf 10 Minuten"))
        assertEquals("Stelle den Wecker …", label("weck mich morgen um 6:30"))
        assertEquals("Stelle den Wecker …", label("Wecker auf 7 Uhr"))
        assertEquals("Starte die Navigation …", label("navigiere nach Hamburg Hauptbahnhof"))
        assertEquals("Lese deine Nachrichten …", label("lies mir meine Nachrichten vor"))
        assertEquals("Schaue auf die Uhr …", label("wie spät ist es"))
        assertEquals("Prüfe den Akku …", label("wie ist der Akkustand"))
        assertEquals("Rufe mama an …", label("ruf Mama an"))
        assertEquals("Stelle die Lautstärke auf 30 % …", label("Lautstärke auf 30"))
        assertEquals("Lauter …", label("lauter"))
    }

    @Test fun everythingElseGoesToTheModel() {
        assertNull(label("erzähl mir einen Witz"))
        assertNull(label("wie war dein Tag"))
        assertNull(label("öffne den Ordner Downloads am PC"))
        assertNull(label("ich habe gestern die Musik von Queen gehört"))
        assertNull(label("öffne Spotify auf dem PC"))
        assertNull(label("stopp die Musik"))       // Spotify is not connected in this test: no music commands
        assertNotNull(label("stelle einen Timer auf 5 Minuten"))
    }
}

/** Interpreter mode phrases (the translation itself needs the PC and is tested there). */
class InterpreterCommandsTest {
    @get:Rule val phone = PhoneLocale(Locale.GERMAN)
    private fun label(s: String) = QuickCommands.detectInterpreter(s)?.label

    @Test fun startPhrases() {
        assertEquals("Starte den Dolmetscher …", label("Dolmetscher Englisch"))
        assertEquals("Starte den Dolmetscher …", label("Dolmetscher an Französisch"))
        assertEquals("Starte den Dolmetscher …", label("übersetze alles ins Spanische"))
        assertEquals("Starte den Dolmetscher …", label("übersetze auf Italienisch"))
    }

    @Test fun otherSentencesAreNotInterpreterCommands() {
        assertNull(label("wie spät ist es"))
        assertNull(label("Dolmetscher aus"))          // not active here: nothing to end
        assertNull(label("übersetze mir bitte dieses Wort"))   // no language named
        assertEquals("Spanisch", net.yume.companion.device.Interpreter.languageIn("übersetze ins spanische")?.let { "Spanisch" })
    }
}

class ReplyCommandTest {
    @get:Rule val phone = PhoneLocale(Locale.GERMAN)
    @Test fun repliesAreRecognised() {
        assertEquals("Antworte auf die Nachricht …", QuickCommands.detect("antworte ich bin gleich da")?.label)
        assertEquals("Antworte auf die Nachricht …", QuickCommands.detect("schreib ihm zurück ich komme später")?.label)
        assertEquals("Antworte auf die Nachricht …", QuickCommands.detect("sag ihr ich rufe heute Abend an")?.label)
        assertNull(QuickCommands.detect("antworte"))
    }
}

/** the same commands, spoken in English on an English phone */
class EnglishCommandsTest {
    @get:Rule val phone = PhoneLocale(Locale.ENGLISH)
    private fun label(s: String) = QuickCommands.detect(s)?.label

    @Test fun phoneCommandsAreRecognised() {
        assertEquals("Switching the flashlight …", label("turn the flashlight on"))
        assertEquals("Opening whatsapp …", label("open WhatsApp"))
        assertEquals("Opening spotify …", label("can you please open Spotify"))
        assertEquals("Setting the timer …", label("set a timer for 10 minutes"))
        assertEquals("Setting the alarm …", label("wake me tomorrow at 6:30"))
        assertEquals("Setting the alarm …", label("set an alarm for 7 am"))
        assertEquals("Starting navigation …", label("navigate to Hamburg central station"))
        assertEquals("Reading your messages …", label("read my messages"))
        assertEquals("Looking at the clock …", label("what time is it"))
        assertEquals("Checking the battery …", label("how is the battery"))
        assertEquals("Calling mom …", label("call mom"))
        assertEquals("Setting the volume to 30 % …", label("volume 30"))
        assertEquals("Louder …", label("louder"))
        assertEquals("Replying to the message …", label("reply I'll be right there"))
    }

    @Test fun interpreter() {
        assertEquals("Starting the interpreter …", QuickCommands.detectInterpreter("interpreter French")?.label)
        assertEquals("Starting the interpreter …", QuickCommands.detectInterpreter("translate to Spanish")?.label)
        assertNull(QuickCommands.detectInterpreter("what time is it"))
    }

    @Test fun everythingElseGoesToTheModel() {
        assertNull(label("tell me a joke"))
        assertNull(label("how was your day"))
        assertNull(label("open the downloads folder on the PC"))
        assertNull(label("I listened to Queen yesterday"))
    }
}
