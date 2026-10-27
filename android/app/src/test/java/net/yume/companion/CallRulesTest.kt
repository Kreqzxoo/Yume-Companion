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

    @Test fun numbersAreReadInGroups() {
        assertEquals("017 112 345 6", CallRules.speakable("0171123456"))
    }
}
