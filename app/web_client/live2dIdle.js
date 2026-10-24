// Idle micro-gestures for Live2D models in the web / Android avatar view (pixi-live2d-display).
// Gestures come from live2d_gestures.json (shared with the desktop program) and are added as offsets on top of the model's own
// motion, eye tracking and breathing, right before every model update.

const CUBISM2_IDS = {
    ParamAngleX: 'PARAM_ANGLE_X', ParamAngleY: 'PARAM_ANGLE_Y', ParamAngleZ: 'PARAM_ANGLE_Z',
    ParamBodyAngleX: 'PARAM_BODY_ANGLE_X', ParamBodyAngleY: 'PARAM_BODY_ANGLE_Y', ParamBodyAngleZ: 'PARAM_BODY_ANGLE_Z',
    ParamEyeBallX: 'PARAM_EYE_BALL_X', ParamEyeBallY: 'PARAM_EYE_BALL_Y',
    ParamEyeLOpen: 'PARAM_EYE_L_OPEN', ParamEyeROpen: 'PARAM_EYE_R_OPEN',
    ParamBreath: 'PARAM_BREATH', ParamCheek: 'PARAM_CHEEK',
};

const smooth = (x) => x * x * (3 - 2 * x);

function sample(track, t) {
    if (!track.length) return 0;
    if (t <= track[0][0]) return track[0][1];
    for (let i = 1; i < track.length; i++) {
        if (t <= track[i][0]) {
            const [t0, v0] = track[i - 1], [t1, v1] = track[i];
            return v0 + (v1 - v0) * smooth((t - t0) / Math.max(1e-6, t1 - t0));
        }
    }
    return track[track.length - 1][1];
}

export async function startLive2DIdle(model, isBusy = () => false, url = '/static/live2d_gestures.json') {
    let defs;
    try { defs = (await (await fetch(url)).json()).gestures; } catch (e) { console.log('[Live2D] gestures unavailable', e.message); return null; }
    const internal = model && model.internalModel;
    const core = internal && internal.coreModel;
    if (!internal || !core) return null;
    const v2 = typeof core.setParamFloat === 'function';
    const names = Object.keys(defs);
    const total = names.reduce((s, n) => s + defs[n].weight, 0);
    let active = null;
    let cooldown = 6 + Math.random() * 6;
    let last = performance.now();

    function pick() {
        let r = Math.random() * total;
        for (const n of names) { r -= defs[n].weight; if (r <= 0) return n; }
        return names[0];
    }

    function addParam(id, value) {
        try {
            if (v2) core.addToParamFloat(CUBISM2_IDS[id] || id, value, 1);
            else core.addParameterValueById(id, value, 1);
        } catch (e) { /* the model does not have this parameter */ }
    }

    internal.on('beforeModelUpdate', () => {
        const now = performance.now();
        const dt = Math.min(0.1, (now - last) / 1000);
        last = now;
        if (!active) {
            cooldown -= dt;
            if (cooldown <= 0) {
                if (isBusy()) cooldown = 3;
                else { active = { name: pick(), t: 0 }; cooldown = 12 + Math.random() * 20; }
            }
            return;
        }
        const def = defs[active.name];
        active.t += dt;
        if (isBusy() && active.t < def.dur - 0.8) active.t = def.dur - 0.8;     // she starts talking: end gracefully
        if (active.t >= def.dur) { active = null; return; }
        for (const [id, track] of Object.entries(def.tracks)) {
            const isEye = id === 'ParamEyeLOpen' || id === 'ParamEyeROpen';
            const value = sample(track, active.t);
            addParam(id, isEye ? value - 1 : value);
        }
    });
    return { trigger: (name) => { if (defs[name]) active = { name, t: 0 }; }, names: () => names, get active() { return active && active.name; } };
}
