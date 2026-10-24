// Idle micro-gestures for VRM models: small, slow, human things - tucking hair behind the ear, a hand at the cheek, a deep breath,
// shifting weight, a little head tilt ... Pure rotation overlay on the *normalized* humanoid bones (same axes for every VRM),
// blended on top of whatever the animation clip is doing.
//
//   const gestures = createIdleGestures({ THREE, getVrm: () => currentVrm, isBusy: () => speaking });
//   per frame:  mixer.update(dt);  gestures.update(dt, time);  vrm.update(dt);
//
// What makes it look natural (instead of a robot raising an arm):
//  * every bone starts at its own moment - shoulder first, then upper arm, forearm, hand; the head leads a little - and on the way
//    back the hand leaves first;
//  * minimum-jerk easing (slow start, slow stop), long blend times, a tiny overshoot when the arm arrives;
//  * the "alive" part during the hold is a mix of two slow sines per bone (never a metronome), amplitudes are only a few degrees;
//  * gestures are rare and mostly very small; the big arm gestures are the exception.
// Arm angles of the hair / cheek / eye poses come from a solver that puts the palm on the head of a standard VRM (checked visually).

const RAD = Math.PI / 180;
const clamp01 = (x) => Math.max(0, Math.min(1, x));
const smoother = (t) => { t = clamp01(t); return t * t * t * (t * (t * 6 - 15) + 10); };      // minimum-jerk: zero speed AND acceleration at both ends
const withOvershoot = smoother;

// Euler angles in degrees (XYZ, local bone space) per bone for the RIGHT side; the left side is mirrored automatically
// (names swapped, Y and Z rotation negated). "wave" adds a slow wobble: [bone, axis(0..2), amplitude deg, freq Hz, phase].
export const GESTURES = {
    // tuck a strand behind the ear
    fixHair: {
        dur: 4.6, weight: 4,
        pose: { rightShoulder: [0, 0, 3], rightUpperArm: [-58, 96, -42], rightLowerArm: [0, 98, 0], rightHand: [0, 0, 8], head: [0, 7, -5], neck: [0, 3, -2] },
        wave: [['rightHand', 0, 5, 0.55, 0], ['rightLowerArm', 1, 2.5, 0.43, 1.3], ['head', 2, 1.2, 0.31, 0.6]],
    },
    // shy: fingertips at the cheek
    cheek: {
        dur: 4.8, weight: 3,
        pose: { rightShoulder: [0, 0, 2], rightUpperArm: [-15, 64, -70], rightLowerArm: [0, 118, 0], head: [4, -5, 5], neck: [2, -2, 2] },
        wave: [['head', 2, 1.4, 0.27, 0.2], ['rightHand', 2, 3, 0.4, 2.1]],
    },
    // sleepy: rub an eye
    rubEye: {
        dur: 3.6, weight: 1,
        pose: { rightShoulder: [0, 0, 2], rightUpperArm: [-12, 58, -92], rightLowerArm: [0, 108, 0], head: [5, 0, 0], neck: [2, 0, 0] },
        wave: [['rightHand', 0, 5, 1.1, 0], ['rightLowerArm', 1, 2, 1.1, 0.7]],
    },
    // a deep breath: chest lifts, shoulders rise and fall, head dips a little on the exhale
    sigh: {
        dur: 4.4, weight: 4,
        pose: { chest: [-3, 0, 0], upperChest: [-2, 0, 0], leftShoulder: [0, 0, -3], rightShoulder: [0, 0, 3], head: [3, 0, 0], neck: [1.5, 0, 0], spine: [1, 0, 0] },
        wave: [['chest', 0, 2.2, 0.23, 0], ['leftShoulder', 2, 1.5, 0.23, 0], ['rightShoulder', 2, -1.5, 0.23, 0], ['head', 0, 1.6, 0.23, 1.2]],
    },
    // shift the weight from one foot to the other
    shift: {
        dur: 4.2, weight: 4,
        pose: { hips: [0, 0, 2.2], spine: [0, 0, -1.8], chest: [0, 0, -1.2], head: [0, 0, 1.5], leftShoulder: [0, 0, 1], rightShoulder: [0, 0, -1] },
        wave: [['hips', 1, 0.8, 0.2, 0]],
    },
    // curious little head tilt
    tilt: {
        dur: 3.8, weight: 4,
        pose: { head: [-2, 4, 8], neck: [-1, 2, 4], chest: [0, 0, -1.2] },
        wave: [['head', 2, 1, 0.3, 0.5]],
    },
    // roll the shoulders
    shoulders: {
        dur: 3.8, weight: 2,
        pose: { leftShoulder: [0, 0, -4], rightShoulder: [0, 0, 4], head: [0, 0, 0], neck: [-1, 0, 0] },
        wave: [['leftShoulder', 2, 2.2, 0.5, 0], ['rightShoulder', 2, -2.2, 0.5, 1.6], ['head', 2, 2.5, 0.28, 0.9], ['neck', 0, 2, 0.28, 0]],
    },
    // both arms up, a gentle stretch (rare)
    stretch: {
        dur: 5.6, weight: 1, both: true,
        pose: { rightShoulder: [0, 0, 5], rightUpperArm: [-12, 6, -150], rightLowerArm: [0, 12, 0], chest: [-6, 0, 0], upperChest: [-4, 0, 0], spine: [-3, 0, 0], head: [-8, 0, 0], neck: [-4, 0, 0] },
        wave: [['chest', 0, 1.2, 0.2, 0]],
    },
};

// when each bone starts (seconds after the gesture began); the way back is the mirror image, so the hand leaves first
const DELAY = { shoulder: 0, upperArm: 0.06, lowerArm: 0.14, hand: 0.24, head: 0.10, neck: 0.05, chest: 0, upperChest: 0.03, spine: 0, hips: 0 };
function delayOf(name) {
    const base = name.replace(/^(left|right)/, '');
    const key = base.charAt(0).toLowerCase() + base.slice(1);
    return DELAY[key] ?? 0;
}
const MAX_DELAY = 0.24;

function mirrorName(name) {
    return name.startsWith('right') ? 'left' + name.slice(5) : name.startsWith('left') ? 'right' + name.slice(4) : name;
}
const isSided = (name) => name.startsWith('right') || name.startsWith('left');

export function createIdleGestures({ THREE, getVrm, isBusy = () => false, intensity = () => 1 }) {
    const state = new Map();               // bone name -> { base, out, has }
    const qDelta = new THREE.Quaternion();
    const eTmp = new THREE.Euler();
    let active = null;                     // { name, def, side, t, dur }
    let cooldown = 12 + Math.random() * 10;   // first gesture a little after the model appeared
    let enabled = true;
    let lastName = '';
    let hold = false;                      // developer aid: freeze the clock of the running gesture (see scrub)

    const boneOf = (vrm, name) => vrm.humanoid?.getNormalizedBoneNode?.(name) || null;

    function pick() {
        const names = Object.keys(GESTURES).filter((n) => n !== lastName);       // never the same one twice in a row
        const total = names.reduce((s, n) => s + GESTURES[n].weight, 0);
        let r = Math.random() * total;
        for (const n of names) { r -= GESTURES[n].weight; if (r <= 0) return n; }
        return names[0];
    }

    function start(name, side) {
        const def = GESTURES[name];
        if (!def) return false;
        active = { name, def, side: side || (Math.random() < 0.5 ? 'right' : 'left'), t: 0, dur: def.dur };
        lastName = name;
        return true;
    }

    // per-bone blend factor: staggered start, hand-first exit, minimum-jerk easing
    function blend(boneName, t, dur) {
        const d = delayOf(boneName);
        const IN = 1.5, OUT = 1.5;
        const inF = withOvershoot((t - d) / IN);
        const outF = smoother((dur - t - (MAX_DELAY - d)) / OUT);
        return Math.min(inF, outF);
    }

    function apply(vrm, name, rx, ry, rz) {
        const bone = boneOf(vrm, name);
        if (!bone) return;
        let st = state.get(name);
        if (!st) { st = { base: new THREE.Quaternion(), out: new THREE.Quaternion(), has: false }; state.set(name, st); }
        if (!(st.has && bone.quaternion.equals(st.out))) st.base.copy(bone.quaternion);   // the animation wrote a fresh pose
        if (vrm.meta?.metaVersion === '0') { rx = -rx; rz = -rz; }       // VRM 0.x normalized bones are mirrored (same flip the Mixamo retargeting uses)
        eTmp.set(rx * RAD, ry * RAD, rz * RAD, 'XYZ');
        qDelta.setFromEuler(eTmp);
        bone.quaternion.copy(st.base).multiply(qDelta);
        st.out.copy(bone.quaternion);
        st.has = true;
    }

    function release(vrm) {
        for (const [name, st] of state) {
            const bone = boneOf(vrm, name);
            if (bone && st.has && bone.quaternion.equals(st.out)) bone.quaternion.copy(st.base);
            st.has = false;
        }
    }

    function update(dt, time) {
        const vrm = getVrm();
        if (!vrm || !enabled) return;
        const k = Math.max(0, Math.min(1.5, intensity()));
        if (!active) {
            if (state.size) release(vrm);
            cooldown -= dt;
            if (cooldown <= 0) {
                if (isBusy() || k <= 0) cooldown = 4;             // she is talking / thinking: try again shortly
                else { start(pick()); cooldown = 20 + Math.random() * 30; }
            }
            return;
        }
        if (!hold) active.t += dt;
        if (!hold && isBusy()) active.t = Math.max(active.t, active.dur - 1.6);   // she starts talking: finish the gesture gracefully
        if (active.t >= active.dur) { active = null; release(vrm); return; }
        const t = active.t, dur = active.dur;
        const def = active.def;
        const mirror = active.side === 'left' && !def.both;

        const pose = {};
        for (const [name, v] of Object.entries(def.pose)) {
            if (def.both && name.startsWith('right')) {
                pose[name] = v;
                pose[mirrorName(name)] = [v[0], -v[1], -v[2]];
            } else if (mirror) {
                pose[isSided(name) ? mirrorName(name) : name] = [v[0], -v[1], -v[2]];
            } else {
                pose[name] = v;
            }
        }
        for (const [name, v] of Object.entries(pose)) {
            const e = blend(name, t, dur) * k;
            apply(vrm, name, v[0] * e, v[1] * e, v[2] * e);
        }

        // slow, never-repeating wobble on top: two sines per bone with different phases
        const wave = {};
        for (const [bone, axis, amp, freq, phase = 0] of def.wave || []) {
            const b = mirror && isSided(bone) ? mirrorName(bone) : bone;
            const sgn = mirror && axis > 0 ? -1 : 1;
            const e = blend(b, t, dur) * k;
            const a = wave[b] || (wave[b] = [0, 0, 0]);
            const s = Math.sin((t * freq + phase) * 2 * Math.PI) * 0.7 + Math.sin((t * freq * 0.37 + phase * 1.7) * 2 * Math.PI) * 0.3;
            a[axis] += s * amp * e * sgn;
        }
        for (const [b, a] of Object.entries(wave)) {
            if (pose[b]) {
                const bone = boneOf(vrm, b);
                if (!bone) continue;
                const f0 = vrm.meta?.metaVersion === '0' ? -1 : 1;
                eTmp.set(a[0] * f0 * RAD, a[1] * RAD, a[2] * f0 * RAD, 'XYZ');
                qDelta.setFromEuler(eTmp);
                bone.quaternion.multiply(qDelta);
                state.get(b).out.copy(bone.quaternion);
            } else {
                apply(vrm, b, a[0], a[1], a[2]);
            }
        }
    }

    return {
        update,
        trigger: (name, side) => { hold = false; return start(name, side); },
        // jump to second `t` of a gesture and keep it there (for tuning the poses); scrub() with no name releases it
        scrub: (name, side, t) => { if (!name) { hold = false; return; } if (start(name, side)) { active.t = t; hold = true; } },
        names: () => Object.keys(GESTURES),
        setEnabled: (v) => { enabled = !!v; if (!enabled && active) { active = null; const vrm = getVrm(); if (vrm) release(vrm); } },
        get active() { return active ? active.name : null; },
        defs: GESTURES,
    };
}
