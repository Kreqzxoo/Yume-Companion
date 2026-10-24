package net.yume.companion

import net.yume.companion.device.QuickCommands
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

/** Which sentences are quick commands (carried out without the PC) and which ones are left to the language model. Spotify is not connected here. */
class QuickCommandsTest {
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
    @Test fun repliesAreRecognised() {
        assertEquals("Antworte auf die Nachricht …", QuickCommands.detect("antworte ich bin gleich da")?.label)
        assertEquals("Antworte auf die Nachricht …", QuickCommands.detect("schreib ihm zurück ich komme später")?.label)
        assertEquals("Antworte auf die Nachricht …", QuickCommands.detect("sag ihr ich rufe heute Abend an")?.label)
        assertNull(QuickCommands.detect("antworte"))
    }
}
