// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
//
// Yume avatar: shows the character's VRM model on the phone and animates it (breathing, blinking, eye movement, idle gestures,
// emotions, listening / thinking pose, lip sync). Written from scratch for the Android app; it only uses the public APIs of
// three.js and @pixiv/three-vrm (both MIT, see THIRD_PARTY_NOTICES.txt).
//
// Page contract (called by the app through WebView.evaluateJavascript):
//   setZoom(factor)            size of the model in its frame (1 = whole body)
//   setAppState(name)          'LISTENING' | 'PROCESSING' | anything else = normal
//   setEmotion(name, strength) face + head pose, e.g. 'joy', 'sadness' (names of the PC's emotion detector)
//   loadFBX(url)               plays a body animation clip (Mixamo format) once, then returns to the idle pose
//   setMouthOpen(0..1)         lip sync from the voice volume
// Reports to the app through the YumeBridge object: avatarState(mode, ok) and log(message).

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import { loadMixamoAnimation } from './loadMixamoAnimation.js';
import { createIdleGestures } from './idleGestures.js';

const bridge = window.YumeBridge;
const log = (m) => { try { console.log(m); if (bridge && bridge.log) bridge.log(String(m)); } catch (_) { /* no bridge in a browser */ } };
const report = (mode, ok) => { try { if (bridge && bridge.avatarState) bridge.avatarState(mode, ok); } catch (_) { /* no bridge in a browser */ } };

const params = new URLSearchParams(location.search);
const MODEL_URL = params.get('model') || '';
const RAD = Math.PI / 180;
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const damp = (cur, target, rate, dt) => cur + (target - cur) * (1 - Math.exp(-rate * dt));      // frame-rate independent easing

// ------------------------------------------------------------------ renderer, camera, light
const canvas = document.getElementById('stage');
const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
renderer.setClearColor(0x000000, 0);
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(28, 1, 0.05, 50);
scene.add(new THREE.AmbientLight(0xffffff, 0.9));
const keyLight = new THREE.DirectionalLight(0xffffff, 1.5);
keyLight.position.set(0.8, 1.4, 1.6);
scene.add(keyLight);
const rimLight = new THREE.DirectionalLight(0xc7a6ff, 0.5);
rimLight.position.set(-1.2, 1.0, -1.0);
scene.add(rimLight);

// ------------------------------------------------------------------ state
let vrm = null;
let mixer = null;
let idleAction = null;
let clipAction = null;
let gestures = null;
let zoom = 1;
let appState = 'STOPPED';
let modelBox = new THREE.Box3();
let clock = new THREE.Clock();
let lastDraw = 0;
const lookTarget = new THREE.Object3D();
scene.add(lookTarget);

// ------------------------------------------------------------------ framing
function frame() {
    const w = Math.max(1, window.innerWidth), h = Math.max(1, window.innerHeight);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    let targetY = 1.0, dist = 3;
    if (vrm) {
        const size = modelBox.getSize(new THREE.Vector3());
        const tanHalf = Math.tan(camera.fov * RAD / 2);
        const visibleH = size.y * 1.1 / zoom;                     // height of the picture section in meters
        targetY = modelBox.max.y - visibleH / 2;                  // zoom in: the view moves up towards the head
        targetY = Math.max(targetY, modelBox.min.y + visibleH * 0.45);
        const distV = (visibleH / 2) / tanHalf;
        const distH = (Math.max(size.x, size.y * 0.45) * 1.15 / 2) / (tanHalf * camera.aspect);
        dist = Math.max(distV, distH);
    }
    camera.position.set(0, targetY, dist);
    camera.lookAt(0, targetY, 0);
    camera.updateProjectionMatrix();
}
window.addEventListener('resize', frame);

// Size of the standing model from its skeleton (a box around all meshes also contains invisible helper parts and hair physics)
function measure(model) {
    const hum = model.humanoid;
    const y = (name) => { const n = hum.getNormalizedBoneNode(name); return n ? n.getWorldPosition(new THREE.Vector3()).y : null; };
    const head = y('head'), footL = y('leftFoot'), footR = y('rightFoot');
    if (head === null || footL === null || footR === null) return new THREE.Box3().setFromObject(model.scene);
    const bottom = Math.min(footL, footR) - 0.07;
    const top = head + (head - bottom) * 0.16;
    const half = (top - bottom) * 0.27;
    return new THREE.Box3(new THREE.Vector3(-half, bottom, -half), new THREE.Vector3(half, top, half));
}

// ------------------------------------------------------------------ face
// How each emotion of the PC's detector shows on a VRM face (preset names exist in VRM 0.x and 1.0 through three-vrm).
const EMOTIONS = {
    neutral: {},
    joy: { happy: 1 }, amusement: { happy: 0.9 }, excitement: { happy: 1 }, optimism: { happy: 0.7 }, pride: { happy: 0.6 },
    approval: { happy: 0.5 }, gratitude: { happy: 0.6, relaxed: 0.3 }, admiration: { happy: 0.5, surprised: 0.2 },
    relief: { relaxed: 0.9 }, caring: { relaxed: 0.7, happy: 0.3 }, love: { happy: 0.7, relaxed: 0.4 }, desire: { relaxed: 0.6, happy: 0.3 },
    sadness: { sad: 1 }, grief: { sad: 1 }, disappointment: { sad: 0.8 }, remorse: { sad: 0.7 },
    anger: { angry: 1 }, annoyance: { angry: 0.6 }, disgust: { angry: 0.5, sad: 0.3 },
    surprise: { surprised: 1 }, realization: { surprised: 0.6 }, fear: { surprised: 0.5, sad: 0.5 }, nervousness: { sad: 0.3, surprised: 0.3 },
    curiosity: { surprised: 0.35 }, confusion: { surprised: 0.3, sad: 0.2 }, embarrassment: { happy: 0.4, sad: 0.25 },
};
// Head pose per emotion in degrees [nod (+ = down), turn, tilt]
const HEAD_POSE = {
    sadness: [9, 0, 3], grief: [10, 0, 4], disappointment: [8, 0, 2], remorse: [9, 0, 3],
    joy: [-3, 0, 3], amusement: [-2, 0, 4], excitement: [-4, 0, 2], love: [1, 0, 5], embarrassment: [6, 7, 6],
    curiosity: [-1, 0, 8], confusion: [0, 0, 9], surprise: [-5, 0, 0], anger: [4, 0, 0], fear: [3, 0, 0],
};
const FACE_NAMES = ['happy', 'angry', 'sad', 'relaxed', 'surprised'];
const face = { cur: {}, tgt: {} };
for (const n of FACE_NAMES) { face.cur[n] = 0; face.tgt[n] = 0; }
const headTarget = { nod: 0, turn: 0, tilt: 0 };
const headCur = { nod: 0, turn: 0, tilt: 0 };
let emotionUntil = 0;                // emotions fade back to neutral after a while
let blink = { next: 2.5, t: -1, double: false };
let mouthTarget = 0, mouth = 0;
let gaze = { x: 0, y: 0, nextSaccade: 1.5, tx: 0, ty: 0 };

function setFace(values) {
    for (const n of FACE_NAMES) face.tgt[n] = clamp(values[n] || 0, 0, 1);
}

function updateFace(dt, time) {
    const em = vrm.expressionManager;
    if (!em) return;
    if (time > emotionUntil && emotionUntil > 0) { setFace({}); headTarget.nod = headTarget.turn = headTarget.tilt = 0; emotionUntil = 0; }
    for (const n of FACE_NAMES) {
        face.cur[n] = damp(face.cur[n], face.tgt[n], 6, dt);
        em.setValue(n, face.cur[n]);
    }
    // blinking: a short, soft closing every few seconds, sometimes twice in a row; a surprised face blinks less
    blink.next -= dt;
    if (blink.t < 0 && blink.next <= 0) { blink.t = 0; }
    let blinkValue = 0;
    if (blink.t >= 0) {
        blink.t += dt;
        const dur = 0.17;
        blinkValue = Math.sin(Math.PI * clamp(blink.t / dur, 0, 1));
        if (blink.t >= dur) {
            blink.t = -1;
            if (!blink.double && Math.random() < 0.18) { blink.double = true; blink.next = 0.12; }
            else { blink.double = false; blink.next = 2.2 + Math.random() * 4.5; }
        }
    }
    em.setValue('blink', blinkValue * (1 - 0.7 * face.cur.surprised));
    // lip sync: opens fast, closes a bit slower; a little "o" and "i" variation keeps it from looking like a flap
    mouth = damp(mouth, mouthTarget, mouthTarget > mouth ? 28 : 14, dt);
    em.setValue('aa', clamp(mouth * 0.95, 0, 1));
    em.setValue('oh', clamp(mouth * 0.28 * (0.5 + 0.5 * Math.sin(time * 9.0)), 0, 1));
    em.setValue('ih', clamp(mouth * 0.18 * (0.5 + 0.5 * Math.sin(time * 6.3 + 1.7)), 0, 1));
}

// ------------------------------------------------------------------ eyes
function updateGaze(dt, time) {
    gaze.nextSaccade -= dt;
    if (gaze.nextSaccade <= 0) {
        gaze.nextSaccade = 1.2 + Math.random() * 3.2;
        const wander = appState === 'PROCESSING' ? 0.35 : 0.14;
        gaze.tx = (Math.random() - 0.5) * wander * 2;
        gaze.ty = (Math.random() - 0.5) * wander;
    }
    // thinking: the eyes drift up and to the side, listening: straight at the camera
    const base = appState === 'PROCESSING' ? { x: -0.45, y: 0.35 } : { x: 0, y: 0 };
    gaze.x = damp(gaze.x, base.x + gaze.tx, 9, dt);
    gaze.y = damp(gaze.y, base.y + gaze.ty, 9, dt);
    lookTarget.position.set(camera.position.x + gaze.x, camera.position.y + gaze.y, camera.position.z);
}

// ------------------------------------------------------------------ body
const RELAXED_POSE = {
    // [x, y, z] in degrees on the normalized humanoid bones (facing +Z, arms along +-X in the rest pose)
    leftUpperArm: [0, 0, -68], rightUpperArm: [0, 0, 68],
    leftLowerArm: [0, 0, -6], rightLowerArm: [0, 0, 6],
    leftShoulder: [0, 0, -3], rightShoulder: [0, 0, 3],
    leftHand: [0, 0, -4], rightHand: [0, 0, 4],
};
const HELD_BONES = ['hips', 'spine', 'chest', 'upperChest', 'neck', 'head'];     // the idle clip keeps them at rest so that code can layer on top

function buildIdleClip() {
    const tracks = [];
    const q = new THREE.Quaternion(), e = new THREE.Euler();
    const still = (bone, qq) => {
        const node = vrm.humanoid.getNormalizedBoneNode(bone);
        if (!node) return;
        tracks.push(new THREE.QuaternionKeyframeTrack(node.name + '.quaternion', [0, 1], [qq.x, qq.y, qq.z, qq.w, qq.x, qq.y, qq.z, qq.w]));
    };
    // The mixer only writes a bone when its animated value changed. The bones that code layers motion on top of (head, neck, spine ...)
    // must be reset every frame, otherwise the layered rotations would add up: their track therefore moves by a tiny, invisible amount.
    const alive = (bone) => {
        const node = vrm.humanoid.getNormalizedBoneNode(bone);
        if (!node) return;
        const a = new THREE.Quaternion(), b = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), 2e-4);
        tracks.push(new THREE.QuaternionKeyframeTrack(node.name + '.quaternion', [0, 0.5, 1], [a.x, a.y, a.z, a.w, b.x, b.y, b.z, b.w, a.x, a.y, a.z, a.w]));
    };
    for (const b of HELD_BONES) alive(b);
    for (const [b, a] of Object.entries(RELAXED_POSE)) still(b, q.setFromEuler(e.set(a[0] * RAD, a[1] * RAD, a[2] * RAD)));
    return new THREE.AnimationClip('yume-idle', 1, tracks);
}

function updateBody(dt, time) {
    const hum = vrm.humanoid;
    const head = hum.getNormalizedBoneNode('head');
    const neck = hum.getNormalizedBoneNode('neck');
    const chest = hum.getNormalizedBoneNode('chest') || hum.getNormalizedBoneNode('spine');
    const spine = hum.getNormalizedBoneNode('spine');
    const listening = appState === 'LISTENING', thinking = appState === 'PROCESSING';
    // head pose: emotion + state + a slow sway so that the model is never frozen
    const tNod = headTarget.nod + (listening ? -2 : 0) + (thinking ? -3 : 0);
    const tTurn = headTarget.turn + (thinking ? 9 : 0);
    const tTilt = headTarget.tilt + (listening ? 4 : 0) + (thinking ? -5 : 0);
    headCur.nod = damp(headCur.nod, tNod, 3.2, dt);
    headCur.turn = damp(headCur.turn, tTurn, 3.2, dt);
    headCur.tilt = damp(headCur.tilt, tTilt, 3.2, dt);
    const swayX = Math.sin(time * 0.61) * 1.1 + Math.sin(time * 1.37) * 0.4;
    const swayY = Math.sin(time * 0.43 + 1.0) * 1.6;
    const swayZ = Math.sin(time * 0.37 + 2.0) * 0.9;
    const e = new THREE.Euler(), q = new THREE.Quaternion();
    const add = (node, x, y, z) => { if (node) { q.setFromEuler(e.set(x * RAD, y * RAD, z * RAD)); node.quaternion.multiply(q); } };
    add(head, (headCur.nod + swayX) * 0.6, (headCur.turn + swayY) * 0.6, (headCur.tilt + swayZ) * 0.6);
    add(neck, (headCur.nod + swayX) * 0.4, (headCur.turn + swayY) * 0.4, (headCur.tilt + swayZ) * 0.4);
    // breathing: chest rises and falls, the shoulders follow a little
    const breath = Math.sin(time * 1.55);
    add(chest, breath * 0.9 - 0.2, 0, 0);
    add(spine, breath * 0.4, Math.sin(time * 0.31) * 0.8, 0);
}

function playClip(clip) {
    if (!mixer || !idleAction) return;
    const next = mixer.clipAction(clip);
    if (clipAction && clipAction !== next) clipAction.fadeOut(0.4);
    next.reset();
    next.setLoop(THREE.LoopOnce, 1);
    next.clampWhenFinished = true;
    next.fadeIn(0.5).play();
    idleAction.fadeOut(0.5);
    clipAction = next;
}

const clipCache = new Map();
let wantedClip = '';
window.loadFBX = async (url) => {
    if (!vrm || !url) return;
    wantedClip = url;
    try {
        let clip = clipCache.get(url);
        if (!clip) {
            clip = await loadMixamoAnimation(url, vrm);
            clipCache.set(url, clip);
        }
        if (wantedClip === url && vrm) playClip(clip);        // a newer request wins
    } catch (err) {
        log('animation ' + url + ': ' + (err && err.message ? err.message : err));
    }
};

// ------------------------------------------------------------------ calls from the app
window.setZoom = (z) => { const v = Number(z); if (v > 0.2 && v < 4) { zoom = v; frame(); } };
window.setAppState = (s) => { appState = String(s || 'STOPPED').toUpperCase(); };
window.setMouthOpen = (v) => { mouthTarget = clamp(Number(v) || 0, 0, 1); };
window.setEmotion = (name, strength) => {
    if (!vrm) return;
    const key = String(name || 'neutral').toLowerCase();
    const k = clamp(Number(strength) || 1, 0, 1);
    const mix = EMOTIONS[key] || {};
    const scaled = {};
    for (const n of FACE_NAMES) scaled[n] = (mix[n] || 0) * k;
    setFace(scaled);
    const pose = HEAD_POSE[key] || [0, 0, 0];
    headTarget.nod = pose[0] * k; headTarget.turn = pose[1] * k; headTarget.tilt = pose[2] * k;
    emotionUntil = key === 'neutral' ? 0 : clock.elapsedTime + 12;
};

// ------------------------------------------------------------------ loop
function tick() {
    requestAnimationFrame(tick);
    if (document.hidden) return;
    const now = performance.now();
    if (now - lastDraw < 30) return;                           // about 30 pictures per second are plenty and spare the battery
    lastDraw = now;
    const dt = Math.min(clock.getDelta(), 0.1);
    const time = clock.elapsedTime;
    if (vrm && mixer && gestures) {
        mixer.update(dt);
        gestures.update(dt, time);
        updateBody(dt, time);
        updateFace(dt, time);
        updateGaze(dt, time);
        vrm.update(dt);
    }
    renderer.render(scene, camera);
}

// ------------------------------------------------------------------ load the model
async function load() {
    if (!MODEL_URL) { log('no model given'); report('none', false); return; }
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));
    try {
        const gltf = await loader.loadAsync(MODEL_URL);
        const model = gltf.userData.vrm;
        if (!model) throw new Error('the file is not a VRM model');
        VRMUtils.removeUnnecessaryVertices(gltf.scene);
        VRMUtils.combineSkeletons(gltf.scene);
        VRMUtils.rotateVRM0(model);                            // VRM 0.x models look towards -Z: turn them to the camera
        model.scene.traverse((o) => { o.frustumCulled = false; });
        scene.add(model.scene);
        vrm = model;
        model.scene.updateMatrixWorld(true);
        modelBox = measure(model);
        if (model.lookAt) { model.lookAt.target = lookTarget; }
        mixer = new THREE.AnimationMixer(model.scene);
        idleAction = mixer.clipAction(buildIdleClip());
        idleAction.play();
        mixer.addEventListener('finished', (ev) => {
            if (ev.action !== clipAction) return;
            idleAction.reset().fadeIn(0.6).play();
            clipAction.fadeOut(0.6);
        });
        gestures = createIdleGestures({ THREE, getVrm: () => vrm, isBusy: () => appState !== 'STOPPED' || mouth > 0.05 || !!(clipAction && clipAction.isRunning() && clipAction.getEffectiveWeight() > 0.1) });
        frame();
        report('vrm', true);
    } catch (err) {
        log('model: ' + (err && err.message ? err.message : err));
        report('error', false);
    }
}

window.addEventListener('error', (ev) => log('error: ' + ev.message));
window.addEventListener('unhandledrejection', (ev) => log('error: ' + (ev.reason && ev.reason.message ? ev.reason.message : ev.reason)));
canvas.addEventListener('webglcontextlost', () => { log('graphics context lost'); report('error', false); });

frame();
load();
tick();
