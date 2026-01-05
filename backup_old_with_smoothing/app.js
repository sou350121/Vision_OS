// ============================================
// VISION_OS - Neural Interface Terminal
// Hand Tracking Dashboard Application
// ============================================

// One Euro Filter for smooth, low-latency filtering
// Inline implementation to avoid module loading issues
class OneEuroFilterInline {
    constructor(freq = 30, minCutoff = 1.0, beta = 0.007, dCutoff = 1.0) {
        this.freq = freq;
        this.minCutoff = minCutoff;
        this.beta = beta;
        this.dCutoff = dCutoff;
        this.x = null;
        this.dx = null;
        this.lastTime = null;
        this.lastValue = null;
    }

    _alpha(cutoff) {
        const te = 1.0 / this.freq;
        const tau = 1.0 / (2 * Math.PI * cutoff);
        return 1.0 / (1.0 + tau / te);
    }

    filter(value, timestamp = null) {
        if (timestamp !== null && this.lastTime !== null) {
            const dt = (timestamp - this.lastTime) / 1000;
            if (dt > 0 && dt < 1) this.freq = 1.0 / dt;
        }
        this.lastTime = timestamp;

        if (this.lastValue === null) {
            this.lastValue = value;
            this.dx = 0;
            return value;
        }

        // Estimate derivative
        const dx = (value - this.lastValue) * this.freq;
        
        // Filter derivative
        const alphaDx = this._alpha(this.dCutoff);
        this.dx = alphaDx * dx + (1 - alphaDx) * (this.dx || 0);

        // Adaptive cutoff
        const cutoff = this.minCutoff + this.beta * Math.abs(this.dx);
        const alpha = this._alpha(cutoff);

        // Filter value
        const filtered = alpha * value + (1 - alpha) * this.lastValue;
        this.lastValue = filtered;
        return filtered;
    }

    reset() {
        this.lastValue = null;
        this.dx = null;
        this.lastTime = null;
    }
}

class VisionOS {
    constructor() {
        this.video = document.getElementById('webcam');
        this.handCanvas = document.getElementById('handCanvas');
        this.handCtx = this.handCanvas.getContext('2d');

        // Data visualization canvases
        this.compassCanvas = document.getElementById('compassCanvas');
        this.compassCtx = this.compassCanvas.getContext('2d');
        this.signalCanvas = document.getElementById('signalCanvas');
        this.signalCtx = this.signalCanvas.getContext('2d');

        // State
        this.hands = null;
        this.camera = null;
        this.lastFrameTime = performance.now();
        this.frameCount = 0;
        this.fps = 0;
        this.startTime = Date.now();

        // Signal history for graph
        this.pinchHistory = new Array(200).fill(0);

        // Gesture history for stabilization
        this.gestureHistory = [];
        this.gestureBufferLength = 7;

        // Neural Heatmap
        this.heatmapCells = [];

        // Wuji Bridge Connection (Vision_OS <-> wujihandpy)
        this.wujiSocket = null;
        this.wujiBridgeUrl = localStorage.getItem('wujiBridgeUrl') || 'ws://localhost:8765';
        this.wujiConnected = false;
        this.wujiHasHardware = false;
        this.wujiLastHwError = null;
        // Safety: always start DISARMED; user must explicitly click ARM each session.
        this.wujiArmed = false;
        this.wujiControlSide = localStorage.getItem('wujiControlSide') || 'auto'; // left | right | auto
        // Default to a higher send rate for smoother motion
        this.wujiSendHz = Number(localStorage.getItem('wujiSendHz') || '30') || 30;
        this.wujiLastSendAt = 0;
        this.wujiLastTelemetry = null;
        // One Euro Filters for each finger (adaptive smoothing)
        // minCutoff=1.0: smooth at low speed, beta=0.007: responsive at high speed
        this.wujiFingerFilters = {
            thumb: new OneEuroFilterInline(30, 1.0, 0.007, 1.0),
            index: new OneEuroFilterInline(30, 1.0, 0.007, 1.0),
            middle: new OneEuroFilterInline(30, 1.0, 0.007, 1.0),
            ring: new OneEuroFilterInline(30, 1.0, 0.007, 1.0),
            pinky: new OneEuroFilterInline(30, 1.0, 0.007, 1.0)
        };
        this.wujiTxCount = 0;
        this.wujiLastTxAt = 0;
        this._wujiTestTimer = null;

        // 3D Mode State
        this.is3DMode = false;
        this.renderer = null;
        this.scene = null;
        this.camera3D = null;
        this.hands3D = {
            left: { group: null, joints: [], bones: [], visible: false },
            right: { group: null, joints: [], bones: [], visible: false }
        };
        this.connections = [
            [0, 1], [1, 2], [2, 3], [3, 4], // Thumb
            [0, 5], [5, 6], [6, 7], [7, 8], // Index
            [0, 9], [9, 10], [10, 11], [11, 12], // Middle
            [0, 13], [13, 14], [14, 15], [15, 16], // Ring
            [0, 17], [17, 18], [18, 19], [19, 20], // Pinky
            [5, 9], [9, 13], [13, 17], [0, 17] // Palm
        ];

        // Initialize
        this.init();
    }

    async init() {
        // Setup View Toggles FIRST to ensure UI works even if 3D fails
        this.setupViewControls();

        // Setup Wuji bridge controls & connect (non-blocking)
        this.setupWujiControls();
        this.initWujiConnection();

        // Setup heatmap grid
        this.setupHeatmap();

        // Setup 3D Scene (Try-Catch to prevent crash if Three.js missing)
        try {
            this.init3D();
        } catch (e) {
            console.error("3D Init Failed:", e);
        }

        // Update time display
        this.updateTime();
        setInterval(() => this.updateTime(), 1000);

        // Setup MediaPipe Hands
        await this.setupHandTracking();

        // Start camera
        await this.startCamera();

        // Start visualization loops
        this.startVisualizationLoops();
    }

    setupViewControls() {
        const btn2D = document.getElementById('btn2D');
        const btn3D = document.getElementById('btn3D');
        const threeContainer = document.getElementById('threeContainer');
        const webcam = document.getElementById('webcam');
        const handCanvas = document.getElementById('handCanvas');

        if (!btn2D || !btn3D || !threeContainer || !webcam || !handCanvas) return;

        btn2D.addEventListener('click', () => {
            this.is3DMode = false;
            btn2D.classList.add('active');
            btn3D.classList.remove('active');
            threeContainer.style.display = 'none';
            webcam.style.display = 'block';
            handCanvas.style.display = 'block';
        });

        btn3D.addEventListener('click', () => {
            this.is3DMode = true;
            btn3D.classList.add('active');
            btn2D.classList.remove('active');
            threeContainer.style.display = 'block';
            webcam.style.display = 'none';
            handCanvas.style.display = 'none';

            // Handle resize on first show
            this.onWindowResize();
        });
    }

    setupWujiControls() {
        const urlInput = document.getElementById('wujiUrl');
        const sideSelect = document.getElementById('wujiSide');
        const armBtn = document.getElementById('wujiArmBtn');
        const hzSelect = document.getElementById('wujiHz');
        const reconnectBtn = document.getElementById('wujiReconnectBtn');
        const testOpenBtn = document.getElementById('wujiTestOpen');
        const testFistBtn = document.getElementById('wujiTestFist');
        const resetBtn = document.getElementById('wujiResetBtn');
        const hardUnjamBtn = document.getElementById('wujiHardUnjamBtn');

        if (urlInput) {
            urlInput.value = this.wujiBridgeUrl;
            urlInput.addEventListener('change', () => {
                const next = (urlInput.value || '').trim();
                if (!next) return;
                this.wujiBridgeUrl = next;
                localStorage.setItem('wujiBridgeUrl', this.wujiBridgeUrl);
                this.closeWujiSocket();
                this.initWujiConnection();
            });
        }

        if (sideSelect) {
            sideSelect.value = this.wujiControlSide;
            sideSelect.addEventListener('change', () => {
                this.wujiControlSide = sideSelect.value;
                localStorage.setItem('wujiControlSide', this.wujiControlSide);
                this.updateWujiUi();
            });
        }

        if (armBtn) {
            armBtn.addEventListener('click', () => this.setWujiArmed(!this.wujiArmed));
        }

        if (reconnectBtn) {
            reconnectBtn.addEventListener('click', () => this.requestWujiReconnect());
        }

        if (testOpenBtn) {
            testOpenBtn.addEventListener('click', () => this.sendWujiTestPose('OPEN'));
        }
        if (testFistBtn) {
            testFistBtn.addEventListener('click', () => this.sendWujiTestPose('FIST'));
        }
        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.sendWujiReset());
        }
        if (hardUnjamBtn) {
            hardUnjamBtn.addEventListener('click', () => this.sendWujiHardUnjam());
        }

        if (hzSelect) {
            hzSelect.value = String(this.wujiSendHz);
            hzSelect.addEventListener('change', () => {
                const v = Number(hzSelect.value);
                this.wujiSendHz = Number.isFinite(v) ? v : 20;
                localStorage.setItem('wujiSendHz', String(this.wujiSendHz));
                this.updateWujiUi();
            });
        }

        this.updateWujiUi();
    }

    updateWujiUi() {
        const connEl = document.getElementById('wujiConn');
        const armBtn = document.getElementById('wujiArmBtn');
        const vinEl = document.getElementById('wujiVin');
        const hwEl = document.getElementById('wujiHw');
        const armStateEl = document.getElementById('wujiArmState');
        const vin2El = document.getElementById('wujiVin2');
        const jointsEl = document.getElementById('wujiJoints');
        const errEl = document.getElementById('wujiError');
        const ctrlSideEl = document.getElementById('wujiCtrlSide');
        const txEl = document.getElementById('wujiTx');
        const rxEl = document.getElementById('wujiRxHz');
        const ageEl = document.getElementById('wujiCmdAge');

        if (connEl) {
            if (!this.wujiConnected) {
                connEl.textContent = 'DISCONNECTED';
                connEl.classList.add('disconnected');
                connEl.classList.remove('connected');
            } else {
                connEl.textContent = this.wujiHasHardware ? 'CONNECTED' : 'CONNECTED (MOCK)';
                connEl.classList.add('connected');
                connEl.classList.remove('disconnected');
            }
        }

        if (hwEl) {
            hwEl.textContent = this.wujiHasHardware ? 'HW:ON' : 'HW:OFF';
            hwEl.title = this.wujiLastHwError ? String(this.wujiLastHwError) : '';
        }

        if (vinEl) {
            const v = this.wujiLastTelemetry?.input_voltage;
            vinEl.textContent = (typeof v === 'number' && Number.isFinite(v)) ? v.toFixed(2) : '--';
        }

        if (vin2El) {
            const v = this.wujiLastTelemetry?.input_voltage;
            vin2El.textContent = (typeof v === 'number' && Number.isFinite(v)) ? v.toFixed(2) : '--';
        }

        if (armStateEl) {
            armStateEl.textContent = this.wujiArmed ? 'ON' : 'OFF';
        }

        if (ctrlSideEl) {
            ctrlSideEl.textContent = String(this.wujiControlSide || 'right').toUpperCase();
        }

        if (txEl) txEl.textContent = String(this.wujiTxCount || 0);
        if (rxEl) {
            const rx = this.wujiLastTelemetry?.cmd_hz;
            rxEl.textContent = (typeof rx === 'number' && Number.isFinite(rx)) ? String(Math.round(rx)) : '0';
        }
        if (ageEl) {
            const age = this.wujiLastTelemetry?.cmd_age_ms;
            ageEl.textContent = (typeof age === 'number' && Number.isFinite(age)) ? String(Math.max(0, Math.round(age))) : '--';
        }

        if (jointsEl) {
            const pos = this.wujiLastTelemetry?.joint_actual_position;
            const err = this.wujiLastTelemetry?.joint_error_code;
            if (Array.isArray(pos) && pos.length === 5) {
                const labels = ['THM', 'IDX', 'MID', 'RNG', 'PNK'];
                const lines = pos.map((row, i) => {
                    const vals = Array.isArray(row) ? row.map(x => (typeof x === 'number' ? x.toFixed(3) : '--')).join(' ') : '--';
                    let errPart = '';
                    if (Array.isArray(err) && Array.isArray(err[i])) {
                        const errVals = err[i].map(x => (typeof x === 'number' ? String(x) : '--')).join(' ');
                        errPart = ` | E: ${errVals}`;
                    }
                    return `${labels[i]}: ${vals}${errPart}`;
                });
                jointsEl.textContent = lines.join('\n');
            } else {
                jointsEl.textContent = '--';
            }
        }

        if (errEl) {
            const resetActive = Boolean(this.wujiLastTelemetry?.reset_active);
            const resetPhase = this.wujiLastTelemetry?.reset_phase;
            const resetLabel = this.wujiLastTelemetry?.reset_label;
            const resetReason = this.wujiLastTelemetry?.reset_reason;
            const phaseStr = (typeof resetPhase === 'number' ? String(resetPhase) : '?');
            const labelStr = (typeof resetLabel === 'string' && resetLabel) ? ` ${resetLabel}` : '';
            const resetTxt = resetActive ? `RESET: PHASE ${phaseStr}${labelStr}` : '';
            const reasonTxt = (resetActive && typeof resetReason === 'string' && resetReason)
                ? `UNJAM:${String(resetReason).toUpperCase()}`
                : '';
            const errTxt = this.wujiLastHwError ? `ERR: ${this.wujiLastHwError}` : '';
            errEl.textContent = [reasonTxt, resetTxt, errTxt].filter(Boolean).join(' | ');
        }

        if (armBtn) {
            armBtn.disabled = !this.wujiConnected;
            armBtn.textContent = this.wujiArmed ? 'DISARM' : 'ARM';
            if (this.wujiArmed) armBtn.classList.add('armed');
            else armBtn.classList.remove('armed');
        }
    }

    setWujiArmed(enabled) {
        this.wujiArmed = Boolean(enabled);
        localStorage.setItem('wujiArmed', String(this.wujiArmed));
        this.updateWujiUi();

        if (this.wujiSocket && this.wujiSocket.readyState === WebSocket.OPEN) {
            this.wujiSocket.send(JSON.stringify({
                type: 'arm',
                enabled: this.wujiArmed,
                ts: Date.now()
            }));
        }
    }

    closeWujiSocket() {
        try {
            if (this.wujiSocket) this.wujiSocket.close();
        } catch (_) {
            // ignore
        }
        this.wujiSocket = null;
        this.wujiConnected = false;
        this.wujiHasHardware = false;
        this.updateWujiUi();
    }

    requestWujiReconnect() {
        // Force an immediate hardware connect attempt on the bridge (bypasses backoff)
        if (this.wujiSocket && this.wujiSocket.readyState === WebSocket.OPEN) {
            try {
                this.wujiSocket.send(JSON.stringify({ type: 'connect', ts: Date.now() }));
            } catch (_) {
                // ignore
            }
        } else {
            this.closeWujiSocket();
            this.initWujiConnection();
        }
    }

    initWujiConnection() {
        if (!('WebSocket' in window)) return;
        if (this.wujiSocket && this.wujiSocket.readyState === WebSocket.OPEN) return;

        console.log("[WUJI] Connecting to bridge at " + this.wujiBridgeUrl);
        this.wujiSocket = new WebSocket(this.wujiBridgeUrl);

        this.wujiSocket.onopen = () => {
            console.log("[WUJI] Bridge Connected");
            this.wujiConnected = true;
            this.updateWujiUi();

            // Hello + push current ARM state
            this.wujiSocket.send(JSON.stringify({ type: 'hello', client: 'vision-os', ts: Date.now() }));
            this.setWujiArmed(this.wujiArmed);
        };

        this.wujiSocket.onclose = () => {
            console.log("[WUJI] Bridge Disconnected. Retrying in 5s...");
            this.wujiConnected = false;
            this.wujiHasHardware = false;
            this.updateWujiUi();
            setTimeout(() => this.initWujiConnection(), 5000);
        };

        this.wujiSocket.onerror = (error) => {
            console.error("[WUJI] WebSocket Error:", error);
        };

        this.wujiSocket.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg?.type === 'status') {
                    this.wujiHasHardware = Boolean(msg.has_hardware);
                    this.wujiLastHwError = msg.last_hw_error || null;
                    if (typeof msg.armed === 'boolean') {
                        this.wujiArmed = msg.armed;
                        localStorage.setItem('wujiArmed', String(this.wujiArmed));
                    }
                    this.updateWujiUi();
                } else if (msg?.type === 'telemetry') {
                    this.wujiLastTelemetry = msg;
                    this.updateWujiUi();
                }
            } catch (_) {
                // ignore malformed message
            }
        };
    }

    // Apply ease-in-out curve for more natural motion
    // t: 0-1 input, returns 0-1 with smooth acceleration/deceleration
    easeInOutCurve(t) {
        // Attempt to make motion feel more natural
        // Using smoothstep: 3t² - 2t³
        t = Math.max(0, Math.min(1, t));
        return t * t * (3 - 2 * t);
    }

    // Apply per-finger response curves for better mapping
    applyFingerCurve(finger, value) {
        // Normalize to 0-1
        const t = value / 100;
        
        // Different curves for different fingers
        let curved;
        switch (finger) {
            case 'thumb':
                // Thumb needs more aggressive response in the middle range
                curved = this.easeInOutCurve(t);
                break;
            case 'index':
            case 'middle':
                // Index/middle: slightly more linear for precision
                curved = 0.3 * t + 0.7 * this.easeInOutCurve(t);
                break;
            case 'ring':
            case 'pinky':
                // Ring/pinky: more aggressive curve (harder to control individually)
                curved = this.easeInOutCurve(this.easeInOutCurve(t));
                break;
            default:
                curved = t;
        }
        
        return curved * 100;
    }

    sendWujiData(extensions, side) {
        if (!this.wujiArmed) return;
        if (!this.wujiSocket || this.wujiSocket.readyState !== WebSocket.OPEN) return;

        const now = performance.now();
        const minInterval = 1000 / (this.wujiSendHz || 30);
        if (now - this.wujiLastSendAt < minInterval) return;
        this.wujiLastSendAt = now;

        // Clamp extensions: max 75 so "fully open" gesture still shows natural bend
        const clampedExtensions = {};
        for (const finger of ['thumb', 'index', 'middle', 'ring', 'pinky']) {
            const val = extensions[finger] || 0;
            clampedExtensions[finger] = Math.min(val, 75);
        }

        // Apply One Euro Filter for adaptive smoothing
        // - Low speed: more smoothing (reduce jitter)
        // - High speed: less smoothing (reduce lag)
        const filteredExtensions = {};
        for (const finger of ['thumb', 'index', 'middle', 'ring', 'pinky']) {
            const raw = clampedExtensions[finger] || 0;
            filteredExtensions[finger] = this.wujiFingerFilters[finger].filter(raw, now);
        }

        this.wujiSocket.send(JSON.stringify({
            type: 'hand_data',
            side: side,
            extensions: filteredExtensions,
            timestamp: Date.now()
        }));

        this.wujiTxCount += 1;
        this.wujiLastTxAt = Date.now();
    }

    sendWujiTestPose(poseName) {
        // Manual commands to validate hardware movement even if the webcam tracking is flaky.
        if (!this.wujiArmed) {
            console.warn('[WUJI] Not armed - test pose ignored');
            return;
        }
        if (!this.wujiSocket || this.wujiSocket.readyState !== WebSocket.OPEN) {
            console.warn('[WUJI] Socket not connected - test pose ignored');
            return;
        }

        const name = String(poseName || '').toUpperCase();
        let extensions = null;
        if (name === 'OPEN') {
            extensions = { thumb: 100, index: 100, middle: 100, ring: 100, pinky: 100 };
        } else if (name === 'FIST') {
            // Soft grip only (avoid a "perfect fist" which can jam some hardware batches).
            extensions = { thumb: 30, index: 30, middle: 30, ring: 30, pinky: 30 };
        } else {
            return;
        }

        // Send a short burst so the bridge can safely ramp targets (even if no hands are currently tracked).
        const hz = Math.max(1, Number(this.wujiSendHz || 10));
        const intervalMs = Math.max(20, Math.floor(1000 / hz));
        const endAt = performance.now() + 4000; // 4s burst (bridge ramps targets for safer/slower motion)

        const sendOnce = () => {
            if (!this.wujiArmed) return false;
            if (!this.wujiSocket || this.wujiSocket.readyState !== WebSocket.OPEN) return false;
            this.wujiSocket.send(JSON.stringify({
                type: 'hand_data',
                side: 'manual',
                extensions,
                timestamp: Date.now()
            }));
            this.wujiTxCount += 1;
            this.wujiLastTxAt = Date.now();
            return true;
        };

        if (this._wujiTestTimer) {
            clearInterval(this._wujiTestTimer);
            this._wujiTestTimer = null;
        }

        // Kick immediately, then keep sending until endAt.
        sendOnce();
        this._wujiTestTimer = setInterval(() => {
            if (performance.now() >= endAt) {
                clearInterval(this._wujiTestTimer);
                this._wujiTestTimer = null;
                return;
            }
            sendOnce();
        }, intervalMs);
    }

    sendWujiReset() {
        // Recovery: ask bridge to perform disable->enable->reset OPEN (4 fingers then thumb).
        if (!this.wujiSocket || this.wujiSocket.readyState !== WebSocket.OPEN) {
            console.warn('[WUJI] Socket not connected - RESET ignored');
            return;
        }

        // Ensure ARMED so the bridge control loop can actually drive the reset motion.
        if (!this.wujiArmed) {
            this.setWujiArmed(true);
            setTimeout(() => this.sendWujiReset(), 150);
            return;
        }

        try {
            this.wujiSocket.send(JSON.stringify({ type: 'reset_open', ts: Date.now(), reason: 'ui_reset' }));
            this.wujiTxCount += 1;
            this.wujiLastTxAt = Date.now();
        } catch (e) {
            console.warn('[WUJI] RESET send failed', e);
        }
    }

    sendWujiHardUnjam() {
        // Aggressive recovery for a stuck fist: lower current + longer relax + reset OPEN.
        if (!this.wujiSocket || this.wujiSocket.readyState !== WebSocket.OPEN) {
            console.warn('[WUJI] Socket not connected - HARD UNJAM ignored');
            return;
        }

        // Ensure ARMED so the bridge control loop can actually drive the reset motion.
        if (!this.wujiArmed) {
            this.setWujiArmed(true);
            setTimeout(() => this.sendWujiHardUnjam(), 150);
            return;
        }

        try {
            this.wujiSocket.send(JSON.stringify({ type: 'hard_unjam', ts: Date.now(), reason: 'ui_hard_unjam' }));
            this.wujiTxCount += 1;
            this.wujiLastTxAt = Date.now();
        } catch (e) {
            console.warn('[WUJI] HARD UNJAM send failed', e);
        }
    }

    init3D() {
        const container = document.getElementById('threeContainer');
        if (!container) return;

        // Scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x050505);

        // Fog for depth
        this.scene.fog = new THREE.Fog(0x050505, 5, 25);

        // Camera
        this.camera3D = new THREE.PerspectiveCamera(60, container.clientWidth / container.clientHeight, 0.1, 1000);
        this.camera3D.position.set(0, 3, 8);
        this.camera3D.lookAt(0, 0, 0);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(container.clientWidth, container.clientHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        container.appendChild(this.renderer.domElement);

        // Lights
        const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
        this.scene.add(ambientLight);

        const spotLight = new THREE.SpotLight(0xffffff, 1);
        spotLight.position.set(5, 10, 5);
        this.scene.add(spotLight);

        // Grid (Circular Scanner Style)
        for (let i = 1; i <= 5; i++) {
            const circleGeo = new THREE.RingGeometry(i * 2, i * 2 + 0.02, 64);
            const circleMat = new THREE.MeshBasicMaterial({ color: 0x00ff66, transparent: true, opacity: 0.1, side: THREE.DoubleSide });
            const circle = new THREE.Mesh(circleGeo, circleMat);
            circle.rotation.x = -Math.PI / 2;
            this.scene.add(circle);
        }

        // Background Particles
        const partGeo = new THREE.BufferGeometry();
        const partCount = 500;
        const partPos = new Float32Array(partCount * 3);
        for (let i = 0; i < partCount * 3; i++) {
            partPos[i] = (Math.random() - 0.5) * 40;
        }
        partGeo.setAttribute('position', new THREE.BufferAttribute(partPos, 3));
        const partMat = new THREE.PointsMaterial({ color: 0x00ff66, size: 0.05, transparent: true, opacity: 0.4 });
        this.particles = new THREE.Points(partGeo, partMat);
        this.scene.add(this.particles);

        // Setup Hand Models
        this.createHandModel('left', 0x00ff66);  // Green
        this.createHandModel('right', 0x00ffff); // Cyan

        // Start render loop
        this.animate3D();

        // Resize listener
        window.addEventListener('resize', () => this.onWindowResize());
    }

    createHandModel(side, color) {
        const group = new THREE.Group();
        const joints = [];
        const bones = [];

        // Joint Material (Holographic)
        const jointMat = new THREE.MeshStandardMaterial({
            color: color,
            emissive: color,
            emissiveIntensity: 1.0,
            transparent: true,
            opacity: 0.8,
            wireframe: true
        });

        // Core Point Material
        const coreMat = new THREE.MeshBasicMaterial({ color: 0xffffff });

        const jointGeo = new THREE.SphereGeometry(0.08, 8, 8);
        const coreGeo = new THREE.SphereGeometry(0.03, 4, 4);

        for (let i = 0; i < 21; i++) {
            const jointGroup = new THREE.Group();

            const outer = new THREE.Mesh(jointGeo, jointMat);
            const core = new THREE.Mesh(coreGeo, coreMat);

            jointGroup.add(outer);
            jointGroup.add(core);

            group.add(jointGroup);
            joints.push(jointGroup);
        }

        // Bone Material
        const boneMat = new THREE.MeshStandardMaterial({
            color: color,
            transparent: true,
            opacity: 0.3,
            emissive: color,
            emissiveIntensity: 0.2
        });

        const boneGeo = new THREE.CylinderGeometry(0.04, 0.04, 1, 8);

        for (let i = 0; i < this.connections.length; i++) {
            const bone = new THREE.Mesh(boneGeo, boneMat);
            group.add(bone);
            bones.push(bone);
        }

        this.scene.add(group);
        this.hands3D[side] = { group, joints, bones, visible: false };
        group.visible = false;
    }

    onWindowResize() {
        const container = document.getElementById('threeContainer');
        if (this.camera3D && this.renderer && container) {
            this.camera3D.aspect = container.clientWidth / container.clientHeight;
            this.camera3D.updateProjectionMatrix();
            this.renderer.setSize(container.clientWidth, container.clientHeight);
        }
    }

    animate3D() {
        requestAnimationFrame(() => this.animate3D());

        if (this.is3DMode && this.renderer && this.scene && this.camera3D) {
            // Breathing camera animation
            const time = Date.now() * 0.001;
            this.camera3D.position.y = 3 + Math.sin(time * 0.5) * 0.5;
            this.camera3D.lookAt(0, 0, 0);

            // Rotate particles
            if (this.particles) {
                this.particles.rotation.y += 0.001;
            }

            this.renderer.render(this.scene, this.camera3D);
        }
    }

    update3DHand(landmarks, side) {
        if (!this.hands3D[side]) return;
        const handData = this.hands3D[side];

        handData.group.visible = true;
        handData.visible = true;

        const scale = 5;

        for (let i = 0; i < 21; i++) {
            const lm = landmarks[i];
            const mesh = handData.joints[i];

            // Map to 3D World
            mesh.position.x = -(lm.x - 0.5) * scale * 1.5;
            mesh.position.y = -(lm.y - 0.5) * scale;
            mesh.position.z = -lm.z * scale * 2;
        }

        // Update Bones
        for (let i = 0; i < this.connections.length; i++) {
            const [startIdx, endIdx] = this.connections[i];
            const startNode = handData.joints[startIdx];
            const endNode = handData.joints[endIdx];
            const bone = handData.bones[i];

            bone.position.copy(startNode.position).add(endNode.position).multiplyScalar(0.5);
            bone.lookAt(endNode.position);
            bone.rotateX(Math.PI / 2);

            const dist = startNode.position.distanceTo(endNode.position);
            bone.scale.set(1, dist, 1);
        }
    }

    reset3DHands() {
        if (this.hands3D) {
            this.hands3D.left.group.visible = false;
            this.hands3D.left.visible = false;
            this.hands3D.right.group.visible = false;
            this.hands3D.right.visible = false;
        }
    }

    setupHeatmap() {
        const grid = document.getElementById('heatmapGrid');
        // Clear existing (in case of re-init)
        grid.innerHTML = '';
        this.heatmapCells = [];

        // 12 columns * 8 rows = 96 cells
        for (let i = 0; i < 96; i++) {
            const cell = document.createElement('div');
            cell.className = 'heatmap-cell';
            grid.appendChild(cell);
            this.heatmapCells.push(cell);
        }
    }

    updateTime() {
        const now = new Date();
        const hours = now.getHours();
        const minutes = now.getMinutes().toString().padStart(2, '0');
        const seconds = now.getSeconds().toString().padStart(2, '0');
        const ampm = hours >= 12 ? 'PM' : 'AM';
        const displayHours = hours % 12 || 12;
        document.getElementById('currentTime').textContent =
            `${displayHours}:${minutes}:${seconds} ${ampm}`;

        // Update timer
        const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
        const mins = Math.floor(elapsed / 60);
        const secs = elapsed % 60;
        document.getElementById('timer').textContent =
            `${mins}:${secs.toString().padStart(2, '0')}`;

        // Simulate CPU/Memory
        const cpuMem = Math.floor(10 + Math.random() * 8);
        document.getElementById('cpuMem').textContent = cpuMem;
    }

    async setupHandTracking() {
        this.hands = new Hands({
            locateFile: (file) => {
                return `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`;
            }
        });

        this.hands.setOptions({
            maxNumHands: 2,
            modelComplexity: 1,
            minDetectionConfidence: 0.7,
            minTrackingConfidence: 0.5
        });

        this.hands.onResults((results) => this.onHandResults(results));
    }

    async startCamera() {
        this.camera = new Camera(this.video, {
            onFrame: async () => {
                await this.hands.send({ image: this.video });
                this.updateFPS();
            },
            width: 1280,
            height: 720
        });

        await this.camera.start();
    }

    updateFPS() {
        this.frameCount++;
        const now = performance.now();
        const elapsed = now - this.lastFrameTime;

        if (elapsed >= 1000) {
            this.fps = Math.round((this.frameCount * 1000) / elapsed);
            document.getElementById('fpsValue').textContent = this.fps;
            this.frameCount = 0;
            this.lastFrameTime = now;
        }
    }

    onHandResults(results) {
        // Resize canvas to match video
        this.handCanvas.width = this.video.videoWidth;
        this.handCanvas.height = this.video.videoHeight;

        // Clear canvas
        this.handCtx.clearRect(0, 0, this.handCanvas.width, this.handCanvas.height);

        // Update hands count
        const handsCount = results.multiHandLandmarks ? results.multiHandLandmarks.length : 0;
        document.getElementById('handsCount').textContent = handsCount;

        if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
            this.resetHandVisualizations();
            for (let i = 0; i < results.multiHandLandmarks.length; i++) {
                const landmarks = results.multiHandLandmarks[i];
                const handedness = results.multiHandedness ? results.multiHandedness[i] : null;
                const side = handedness ? handedness.label.toLowerCase() : (i === 0 ? 'left' : 'right');

                // Draw 2D connections if NOT in 3D mode
                if (!this.is3DMode) {
                    this.drawHandConnections(landmarks);
                    this.drawHandLandmarks(landmarks);
                }

                // Update 3D Hand if in 3D mode
                if (this.is3DMode) {
                    this.update3DHand(landmarks, side);
                }

                // Update specific hand blocks
                this.updateFingerExtension(landmarks, side, i === 0);
                this.updateHandHUD(landmarks, handedness, side);

                // Update primary visualizations (Global) with first hand
                if (i === 0) {
                    this.updateHandOpenness(landmarks);
                    this.updateOrientation(landmarks);
                    this.updateHeatmap(landmarks);
                    this.detectGesture(landmarks);
                }
            }
        } else {
            this.resetVisualizations();
        }
    }

    drawHandConnections(landmarks) {
        const connections = [
            // Thumb
            [0, 1], [1, 2], [2, 3], [3, 4],
            // Index
            [0, 5], [5, 6], [6, 7], [7, 8],
            // Middle
            [0, 9], [9, 10], [10, 11], [11, 12],
            // Ring
            [0, 13], [13, 14], [14, 15], [15, 16],
            // Pinky
            [0, 17], [17, 18], [18, 19], [19, 20],
            // Palm connections
            [5, 9], [9, 13], [13, 17]
        ];

        this.handCtx.strokeStyle = '#00ff66';
        this.handCtx.lineWidth = 2;
        this.handCtx.shadowColor = '#00ff66';
        this.handCtx.shadowBlur = 10;

        for (const [start, end] of connections) {
            const startPoint = landmarks[start];
            const endPoint = landmarks[end];

            this.handCtx.beginPath();
            this.handCtx.moveTo(
                startPoint.x * this.handCanvas.width,
                startPoint.y * this.handCanvas.height
            );
            this.handCtx.lineTo(
                endPoint.x * this.handCanvas.width,
                endPoint.y * this.handCanvas.height
            );
            this.handCtx.stroke();
        }

        this.handCtx.shadowBlur = 0;
    }

    drawHandLandmarks(landmarks) {
        for (let i = 0; i < landmarks.length; i++) {
            const landmark = landmarks[i];
            const x = landmark.x * this.handCanvas.width;
            const y = landmark.y * this.handCanvas.height;

            // Outer glow
            this.handCtx.beginPath();
            this.handCtx.arc(x, y, 6, 0, Math.PI * 2);
            this.handCtx.fillStyle = 'rgba(0, 255, 102, 0.3)';
            this.handCtx.fill();

            // Inner point
            this.handCtx.beginPath();
            this.handCtx.arc(x, y, 3, 0, Math.PI * 2);
            this.handCtx.fillStyle = '#ffffff';
            this.handCtx.fill();
        }
    }

    updateFingerExtension(landmarks, side, isPrimaryHand = false) {
        // Calculate extension for each finger
        const extensions = {
            thumb: this.getFingerExtension(landmarks, [1, 2, 3, 4]),
            index: this.getFingerExtension(landmarks, [5, 6, 7, 8]),
            middle: this.getFingerExtension(landmarks, [9, 10, 11, 12]),
            ring: this.getFingerExtension(landmarks, [13, 14, 15, 16]),
            pinky: this.getFingerExtension(landmarks, [17, 18, 19, 20])
        };

        // We set fingerStates for EVERY hand processed, but since global analyzers are called
        // right after the first hand's updateFingerExtension, they will use the first hand's data.
        // We set fingerStates for EVERY hand processed, but since global analyzers are called
        // right after the first hand's updateFingerExtension, they will use the first hand's data.
        this.fingerStates = extensions;

        // Update specific bar heights based on prefix (left or right)
        const prefix = side === 'left' ? 'left' : 'right';
        document.getElementById(`${prefix}ThumbBar`).style.height = `${extensions.thumb}%`;
        document.getElementById(`${prefix}IndexBar`).style.height = `${extensions.index}%`;
        document.getElementById(`${prefix}MiddleBar`).style.height = `${extensions.middle}%`;
        document.getElementById(`${prefix}RingBar`).style.height = `${extensions.ring}%`;
        document.getElementById(`${prefix}PinkyBar`).style.height = `${extensions.pinky}%`;

        // Send data to Wuji Bridge for the selected control side
        const mode = this.wujiControlSide;
        const shouldSend = (mode === 'auto') ? isPrimaryHand : (side === mode);
        if (shouldSend) this.sendWujiData(extensions, side);
    }

    updateHandHUD(landmarks, handedness, side) {
        if (!handedness) return;

        const prefix = side === 'left' ? 'left' : 'right';
        const sideEl = document.getElementById(`${prefix}HandSide`);
        const posEl = document.getElementById(`${prefix}HandPos`);

        if (sideEl) {
            sideEl.textContent = handedness.label.toUpperCase();
        }

        // Position: Use Wrist (Landmark 0)
        const wrist = landmarks[0];
        const posX = wrist.x.toFixed(2);
        const posY = wrist.y.toFixed(2);

        if (posEl) {
            posEl.textContent = `X:${posX} Y:${posY}`;
        }
    }

    getAngle(p1, p2, p3) {
        // Calculate angle at p2 between p1-p2 and p3-p2
        const v1 = { x: p1.x - p2.x, y: p1.y - p2.y, z: p1.z - p2.z };
        const v2 = { x: p3.x - p2.x, y: p3.y - p2.y, z: p3.z - p2.z };
        const dot = v1.x * v2.x + v1.y * v2.y + v1.z * v2.z;
        const mag1 = Math.sqrt(v1.x * v1.x + v1.y * v1.y + v1.z * v1.z);
        const mag2 = Math.sqrt(v2.x * v2.x + v2.y * v2.y + v2.z * v2.z);
        if (mag1 * mag2 === 0) return 180;
        const rad = Math.acos(Math.max(-1, Math.min(1, dot / (mag1 * mag2))));
        return rad * (180 / Math.PI);
    }

    getFingerExtension(landmarks, indices) {
        // THUMB: Compound Logic (Structure + Position)
        if (indices[0] === 1) {
            const cmc = landmarks[1];
            const mcpThumb = landmarks[2];
            const ip = landmarks[3];
            const tipThumb = landmarks[4];
            const angleMCP = this.getAngle(cmc, mcpThumb, ip);
            const angleIP = this.getAngle(mcpThumb, ip, tipThumb);
            const avgAngle = (angleMCP + angleIP) / 2;
            // Map Angle: 142 (Bent) -> 0%, 175 (Straight) -> 100%
            // Increased baseline from 130 to 142 for much stricter curling detection
            const angleScore = Math.max(0, Math.min(100, (avgAngle - 142) * 3.0));
            const wrist = landmarks[0];
            const indexMCP = landmarks[5];
            const middleMCP = landmarks[9];
            const handScale = Math.sqrt(Math.pow(middleMCP.x - wrist.x, 2) + Math.pow(middleMCP.y - wrist.y, 2) + Math.pow(middleMCP.z - wrist.z, 2));
            const zWeight = 4.0;
            const spread = Math.sqrt(Math.pow(tipThumb.x - indexMCP.x, 2) + Math.pow(tipThumb.y - indexMCP.y, 2) + Math.pow((tipThumb.z - indexMCP.z) * zWeight, 2));
            const ratio = spread / (handScale || 1);
            // Map Spread: 0.30 (Tucked) -> 0%, 0.65 (Open) -> 100%
            // Increased baseline from 0.22 to 0.30 to ensure tucked thumb registers 0%
            const spreadScore = Math.max(0, Math.min(100, (ratio - 0.30) * 285));
            return Math.max(0, Math.min(angleScore, spreadScore));
        }

        // FINGERS: Robust Angle-Based Check (Straightness)
        // Include MCP (base) joint angle for better tracking
        const wrist = landmarks[0];
        const mcp = landmarks[indices[0]];
        const pip = landmarks[indices[1]];
        const dip = landmarks[indices[2]];
        const tip = landmarks[indices[3]];

        // MCP angle: wrist -> mcp -> pip (base joint flexion)
        const angleMCP = this.getAngle(wrist, mcp, pip);
        // PIP angle: mcp -> pip -> dip
        const anglePIP = this.getAngle(mcp, pip, dip);
        // DIP angle: pip -> dip -> tip
        const angleDIP = this.getAngle(pip, dip, tip);
        
        // Weighted average: MCP contributes more to overall extension
        // MCP (base) is the primary driver of finger curl
        const avgAngle = (angleMCP * 0.4 + anglePIP * 0.35 + angleDIP * 0.25);

        // Map Angle: 100 (Bent) -> 0% to 165 (Straight) -> 100%
        // Adjusted range to account for MCP joint
        return Math.max(0, Math.min(100, (avgAngle - 100) * 1.54));
    }

    updateHandOpenness(landmarks) {
        // Use pre-calculated finger states to ensure perfect synchronization
        const sum = this.fingerStates.thumb + this.fingerStates.index +
            this.fingerStates.middle + this.fingerStates.ring +
            this.fingerStates.pinky;

        // Sum is 0-500. Hand is "Fairly Open" if sum > 350.
        // We'll map 80 (mostly fist) to 0.0 and 420 (mostly open) to 1.0
        const averageOpenness = Math.max(0, Math.min(1, (sum - 80) / 340));

        // Update display
        document.getElementById('pinchValue').textContent = averageOpenness.toFixed(3);

        // Add to history
        this.pinchHistory.shift();
        this.pinchHistory.push(averageOpenness);

        // Ensure graph redraw happens
        this.drawSignalGraph();
    }

    updateOrientation(landmarks) {
        // Calculate hand orientation based on wrist and middle finger base
        const wrist = landmarks[0];
        const middleBase = landmarks[9];

        // Calculate angle
        const dx = middleBase.x - wrist.x;
        const dy = middleBase.y - wrist.y;
        let angle = Math.atan2(dy, dx) * (180 / Math.PI);

        // Convert to compass heading (0-360)
        angle = (angle + 90 + 360) % 360;

        document.getElementById('headingValue').textContent = Math.round(angle);

        // Store for drawing
        this.handOrientation = angle;
    }

    updateHeatmap(landmarks) {
        // Reset all cells
        this.heatmapCells.forEach(cell => {
            cell.classList.remove('active', 'medium');
        });

        // Use counts array to handle overlaps and spread
        // 12x8 grid = 96 cells
        const counts = new Array(96).fill(0);

        for (const landmark of landmarks) {
            // Map to 12x8 grid
            const col = Math.floor(landmark.x * 12);
            const row = Math.floor(landmark.y * 8);

            if (col >= 0 && col < 12 && row >= 0 && row < 8) {
                // Central cell (High weight)
                const index = row * 12 + col;
                counts[index] += 3;

                // Spread to neighbors (Medium weight)
                const neighbors = [
                    [col + 1, row], [col - 1, row],
                    [col, row + 1], [col, row - 1]
                ];

                for (const [nc, nr] of neighbors) {
                    if (nc >= 0 && nc < 12 && nr >= 0 && nr < 8) {
                        const nindex = nr * 12 + nc;
                        counts[nindex] += 1;
                    }
                }
            }
        }

        // Apply classes based on counts
        let activeCount = 0;
        this.heatmapCells.forEach((cell, i) => {
            if (counts[i] >= 3) {
                cell.classList.add('active');
                activeCount++;
            } else if (counts[i] > 0) {
                cell.classList.add('medium');
                activeCount++;
            }
        });

        document.getElementById('activeCount').textContent = activeCount;
    }

    detectGesture(landmarks) {
        const rawGesture = this.classifyGesture(landmarks);

        // Add to history
        this.gestureHistory.push(rawGesture);
        if (this.gestureHistory.length > this.gestureBufferLength) {
            this.gestureHistory.shift();
        }

        // Find most frequent gesture in history (Voting/Filtering noise)
        const counts = {};
        let maxCount = 0;
        let stableGesture = rawGesture;

        for (const g of this.gestureHistory) {
            const key = g.name;
            counts[key] = (counts[key] || 0) + 1;
            if (counts[key] > maxCount) {
                maxCount = counts[key];
                stableGesture = g;
            }
        }

        document.getElementById('gestureName').textContent = stableGesture.name;
        document.getElementById('gestureIcon').textContent = stableGesture.icon;
    }

    classifyGesture(landmarks) {
        // Measure extension for each finger (0-100) using pre-calculated states
        const thumb = this.fingerStates.thumb;
        const index = this.fingerStates.index;
        const middle = this.fingerStates.middle;
        const ring = this.fingerStates.ring;
        const pinky = this.fingerStates.pinky;

        const fingers = { thumb, index, middle, ring, pinky };

        // Helper: Check if specific fingers are Straight (>75) and others are Tucked (<25)
        const check = (straightNames, tuckedNames) => {
            const straightOk = straightNames.every(name => fingers[name] > 65); // Slightly more tolerant
            const tuckedOk = tuckedNames.every(name => fingers[name] < 35);    // Slightly more tolerant
            return straightOk && tuckedOk;
        };

        // Check for PINCH interactions
        const thumbTip = landmarks[4];
        const indexTip = landmarks[8];
        const pinchDist = Math.sqrt(
            Math.pow(thumbTip.x - indexTip.x, 2) +
            Math.pow(thumbTip.y - indexTip.y, 2)
        );

        // 1. OK SIGN (👌) - Specific Pinch + 3 Static fingers straight
        if (pinchDist < 0.08 && fingers.middle > 60 && fingers.ring > 60 && fingers.pinky > 60) {
            return { name: 'OK', icon: '👌' };
        }

        // 2. PEACE (✌️) - Strict: ONLY index/middle
        if (check(['index', 'middle'], ['thumb', 'ring', 'pinky'])) {
            return { name: 'PEACE', icon: '✌️' };
        }

        // 4. THREE (3️⃣) - Index/Middle/Ring
        if (check(['index', 'middle', 'ring'], ['thumb', 'pinky'])) {
            return { name: 'THREE', icon: '3️⃣' };
        }

        // 5. THREE (3️⃣) - German/Thumb variant
        if (check(['thumb', 'index', 'middle'], ['ring', 'pinky'])) {
            return { name: 'THREE', icon: '3️⃣' };
        }

        // 6. FOUR (4️⃣)
        if (check(['index', 'middle', 'ring', 'pinky'], ['thumb'])) {
            return { name: 'FOUR', icon: '4️⃣' };
        }

        // 7. OPEN (🖐️) - High threshold for ALL
        if (fingers.thumb > 80 && fingers.index > 80 && fingers.middle > 80 && fingers.ring > 80 && fingers.pinky > 80) {
            return { name: 'OPEN', icon: '🖐️' };
        }

        // 8. FIST (✊)
        if (fingers.thumb < 20 && fingers.index < 20 && fingers.middle < 20 && fingers.ring < 20 && fingers.pinky < 20) {
            return { name: 'FIST', icon: '✊' };
        }

        // 9. CALL / 666 (🤙)
        if (check(['thumb', 'pinky'], ['index', 'middle', 'ring'])) {
            return { name: 'CALL / 666', icon: '🤙' };
        }

        // 10. THUMBS_UP (👍)
        if (check(['thumb'], ['index', 'middle', 'ring', 'pinky'])) {
            return { name: 'THUMBS_UP', icon: '👍' };
        }

        // 11. POINT (👆)
        if (check(['index'], ['thumb', 'middle', 'ring', 'pinky'])) {
            return { name: 'POINT', icon: '👆' };
        }

        // 12. ROCK (🤘)
        if (check(['index', 'pinky'], ['thumb', 'middle', 'ring'])) {
            return { name: 'ROCK', icon: '🤘' };
        }

        // 13. MIDDLE (🖕)
        if (check(['middle'], ['thumb', 'index', 'ring', 'pinky'])) {
            return { name: 'MIDDLE', icon: '🖕' };
        }

        return { name: 'DETECTED', icon: '🤚' };
    }

    isFingerExtended(landmarks, indices, isThumb = false) {
        return this.getFingerExtension(landmarks, indices) > 50;
    }

    resetHandVisualizations() {
        this.reset3DHands();
        ['left', 'right'].forEach(prefix => {
            const sideEl = document.getElementById(`${prefix}HandSide`);
            const posEl = document.getElementById(`${prefix}HandPos`);
            if (sideEl) sideEl.textContent = '--';
            if (posEl) posEl.textContent = 'X:0.0 Y:0.0';

            ['Thumb', 'Index', 'Middle', 'Ring', 'Pinky'].forEach(finger => {
                const bar = document.getElementById(`${prefix}${finger}Bar`);
                if (bar) bar.style.height = '0%';
            });
        });
    }

    resetGlobalVisualizations() {
        // Reset heatmap
        this.heatmapCells.forEach(cell => {
            cell.classList.remove('active', 'medium');
        });
        const activeCountEl = document.getElementById('activeCount');
        if (activeCountEl) activeCountEl.textContent = '0';

        // Reset gesture
        const gestureNameEl = document.getElementById('gestureName');
        const gestureIconEl = document.getElementById('gestureIcon');
        if (gestureNameEl) gestureNameEl.textContent = 'NONE';
        if (gestureIconEl) gestureIconEl.textContent = '✋';

        // Reset Analysis
        const pinchValueEl = document.getElementById('pinchValue');
        if (pinchValueEl) pinchValueEl.textContent = '0.000';

        // Add zero to pinch history
        this.pinchHistory.shift();
        this.pinchHistory.push(0);
    }

    resetVisualizations() {
        this.resetHandVisualizations();
        this.resetGlobalVisualizations();
    }

    startVisualizationLoops() {
        // Compass drawing loop
        this.drawCompass();

        // Signal graph drawing loop
        this.drawSignalGraph();
    }

    drawCompass() {
        const canvas = this.compassCanvas;
        const ctx = this.compassCtx;

        // Set canvas size
        canvas.width = 120;
        canvas.height = 120;

        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        const radius = 45;

        // Clear
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Draw outer circle (dashed)
        ctx.beginPath();
        ctx.setLineDash([3, 3]);
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        ctx.strokeStyle = '#333';
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.setLineDash([]);

        // Draw compass directions
        ctx.font = '10px JetBrains Mono';
        ctx.fillStyle = '#666';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        ctx.fillText('N', centerX, centerY - radius - 10);
        ctx.fillText('S', centerX, centerY + radius + 10);
        ctx.fillText('E', centerX + radius + 10, centerY);
        ctx.fillText('W', centerX - radius - 10, centerY);

        // Draw cross
        ctx.beginPath();
        ctx.strokeStyle = '#444';
        ctx.lineWidth = 1;
        ctx.moveTo(centerX, centerY - radius + 5);
        ctx.lineTo(centerX, centerY + radius - 5);
        ctx.moveTo(centerX - radius + 5, centerY);
        ctx.lineTo(centerX + radius - 5, centerY);
        ctx.stroke();

        // Draw pointer
        const angle = ((this.handOrientation || 0) - 90) * (Math.PI / 180);
        const pointerLength = 35;

        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.lineTo(
            centerX + Math.cos(angle) * pointerLength,
            centerY + Math.sin(angle) * pointerLength
        );
        ctx.strokeStyle = '#00ff66';
        ctx.lineWidth = 2;
        ctx.shadowColor = '#00ff66';
        ctx.shadowBlur = 10;
        ctx.stroke();
        ctx.shadowBlur = 0;

        // Draw center dot
        ctx.beginPath();
        ctx.arc(centerX, centerY, 4, 0, Math.PI * 2);
        ctx.fillStyle = '#00ff66';
        ctx.fill();

        // North indicator (green when pointing north)
        if (this.handOrientation !== undefined) {
            const isNorth = this.handOrientation >= 350 || this.handOrientation <= 10;
            ctx.beginPath();
            ctx.arc(centerX, centerY - radius - 10, 3, 0, Math.PI * 2);
            ctx.fillStyle = isNorth ? '#00ff66' : '#333';
            ctx.fill();
        }

        requestAnimationFrame(() => this.drawCompass());
    }

    drawSignalGraph() {
        const canvas = this.signalCanvas;
        const ctx = this.signalCtx;

        // Set canvas size - use parent container if canvas rect is 0
        const rect = canvas.getBoundingClientRect();
        const parent = canvas.parentElement;
        const parentRect = parent ? parent.getBoundingClientRect() : null;

        // Get dimensions, with fallback to parent or minimum size
        // Use 1.2fr height ~ 140px minimum if possible
        let width = rect.width || (parentRect ? parentRect.width - 24 : 400);
        let height = rect.height || (parentRect ? Math.max(140, parentRect.height - 40) : 140);

        // Ensure minimum dimensions
        width = Math.max(100, width);
        height = Math.max(80, height);

        canvas.width = width;
        canvas.height = height;

        // Clear
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Draw background
        ctx.fillStyle = '#0a0a0a';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Draw grid lines
        ctx.strokeStyle = '#1f1f1f';
        ctx.lineWidth = 1;

        // Horizontal lines
        for (let i = 0; i <= 4; i++) {
            const y = (canvas.height / 5) * i + 20;
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(canvas.width, y);
            ctx.stroke();
        }

        // Calculate graph area (leave space for baseline visibility)
        const graphTop = 10;
        const graphBottom = canvas.height - 30; // Leave 30px at bottom for baseline visibility
        const graphHeight = graphBottom - graphTop;

        // Draw baseline (always visible dim line at bottom)
        ctx.beginPath();
        ctx.strokeStyle = '#1a3d1a';
        ctx.lineWidth = 1;
        ctx.moveTo(0, graphBottom);
        ctx.lineTo(canvas.width, graphBottom);
        ctx.stroke();

        // Draw signal line
        ctx.beginPath();
        ctx.strokeStyle = '#00ff66';
        ctx.lineWidth = 5;
        ctx.shadowColor = '#00ff66';
        ctx.shadowBlur = 20;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';

        const stepX = canvas.width / (this.pinchHistory.length - 1);

        for (let i = 0; i < this.pinchHistory.length; i++) {
            const x = i * stepX;
            // Map pinch value to graph area (0 = graphBottom, 1 = graphTop)
            const y = graphBottom - (this.pinchHistory[i] * graphHeight);

            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }

        ctx.stroke();
        ctx.shadowBlur = 0;

        // Draw fill gradient (from line to bottom)
        ctx.lineTo(canvas.width, graphBottom);
        ctx.lineTo(0, graphBottom);
        ctx.closePath();

        const gradient = ctx.createLinearGradient(0, graphTop, 0, graphBottom);
        gradient.addColorStop(0, 'rgba(0, 255, 102, 0.5)');
        gradient.addColorStop(0.5, 'rgba(0, 255, 102, 0.2)');
        gradient.addColorStop(1, 'rgba(0, 255, 102, 0.05)');
        ctx.fillStyle = gradient;
        ctx.fill();

        requestAnimationFrame(() => this.drawSignalGraph());
    }
}

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    new VisionOS();
});
