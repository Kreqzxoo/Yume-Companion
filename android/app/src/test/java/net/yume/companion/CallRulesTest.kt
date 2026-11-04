// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion

import net.yume.companion.device.CallDecision
import net.yume.companion.device.CallRules
import org.junit.Assert.assertEquals
import org.junit.Test

class CallRulesTest {
    private val block = CallRules.prefixes("0900, 0137,01805")

    @Test fun knownContactsAreAlwaysLetThrough() {
        assertEquals(CallDecision.ALLOW, CallRules.decide("0900123456", true, block, true, true))
    }

    @Test fun spamPrefixesAreRejected() {
        assertEquals(CallDecision.REJECT, CallRules.decide("0900123456", false, block, false, false))
        assertEquals(CallDecision.REJECT, CallRules.decide("+49 137 12345", false, block, false, false))      // international form of 0137
        assertEquals(CallDecision.REJECT, CallRules.decide("0049180512345", false, block, false, false))
    }

    @Test fun unknownNumbersAtNightAreSilencedOnlyWhenSwitchedOn() {
        assertEquals(CallDecision.SILENCE, CallRules.decide("0171123456", false, block, true, true))
        assertEquals(CallDecision.ALLOW, CallRules.decide("0171123456", false, block, true, false))
        assertEquals(CallDecision.ALLOW, CallRules.decide("0171123456", false, block, false, true))
    }

    @Test fun spamListEntriesAreRejected() {
        val prefixes = listOf("0700", "032")
        val numbers = setOf("030123456")
        assertEquals(CallDecision.REJECT, CallRules.decide("+49 700 1234", false, emptyList(), false, false, prefixes, numbers))
        assertEquals(CallDecision.REJECT, CallRules.decide("0049 30 123456", false, emptyList(), false, false, prefixes, numbers))
        assertEquals(CallDecision.ALLOW, CallRules.decide("0171123456", false, emptyList(), false, false, prefixes, numbers))
        assertEquals(CallDecision.ALLOW, CallRules.decide("0700123", true, emptyList(), false, false, prefixes, numbers))     // contacts always get through
    }

    @Test fun spamListTextIsParsedAndBadListsAreRefused() {
        val ok = net.yume.companion.core.SpamList.parse("# c\nformat: 1\nversion: 2026-11-04\nprefix: +49 700\nnumber: 030-123456\n")!!
        assertEquals(listOf("0700"), ok.prefixes)
        assertEquals(setOf("030123456"), ok.numbers)
        assertEquals(null, net.yume.companion.core.SpamList.parse("format: 2\nversion: 1\nprefix: 0900"))
        assertEquals(null, net.yume.companion.core.SpamList.parse("format: 1\nversion: 1\nprefix: <script>"))
        assertEquals(null, net.yume.companion.core.SpamList.parse("format: 1\nprefix: 0900"))
        assertEquals(null, net.yume.companion.core.SpamList.parse("<html>not a list</html>"))
    }

    @Test fun shippedListIsValid() {
        val text = java.io.File("src/main/assets/spamlist.txt").readText()
        assertEquals(true, net.yume.companion.core.SpamList.parse(text)!!.size > 0)
        assertEquals(text, java.io.File("../spamlist.txt").readText())          // the copy in the app equals the published list
    }
}
