// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion

import net.yume.companion.voice.WakeMatch
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class WakeMatchTest {
    private val words = listOf("hey yume")

    private fun hears(text: String, sensitivity: Int = 60) = WakeMatch.matches(text, words, sensitivity)

    @Test fun englishNameHeardByTheGermanModel() {
        assertTrue(hears("hey yume"))
        assertTrue(hears("hai jume"))
        assertTrue(hears("he yume"))
        assertTrue(hears("hey jume"))
        assertTrue(hears("yume"))
        assertTrue(hears("ey ju me"))
        assertTrue(hears("na hey yume wie geht es dir"))
    }

    @Test fun ordinarySpeechDoesNotWakeHer() {
        assertFalse(hears("guten morgen zusammen"))
        assertFalse(hears("hallo wie geht es dir"))
        assertFalse(hears("zwei bier bitte"))
        assertFalse(hears("ich muss noch einkaufen gehen"))
        assertFalse(hears("hey du"))
    }

    @Test fun shortNamesStillWork() {
        val yume = listOf("yume", "hey yume")
        assertTrue(WakeMatch.matches("jume", yume, 60))
        assertTrue(WakeMatch.matches("hey ju me", yume, 60))
        assertFalse(WakeMatch.matches("heute abend", yume, 60))
    }
}
