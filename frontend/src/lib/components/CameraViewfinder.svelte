<script lang="ts">
  /**
   * CameraViewfinder — Live camera with framing guides + IMU tilt detection.
   * - Corner bracket framing guides
   * - Real-time tilt indicator via DeviceOrientationEvent
   * - Shutter gated: warns if phone is tilted > 10°
   */

  let { onCapture, onClose }: {
    onCapture: (file: File, tiltAngleDeg: number) => void;
    onClose: () => void;
  } = $props();

  let videoEl: HTMLVideoElement;
  let canvasEl: HTMLCanvasElement;
  let stream: MediaStream | null = null;
  let cameraError = $state<string | null>(null);
  let isReady = $state(false);
  let flash = $state(false);

  // IMU tilt state
  let tiltAngle = $state<number | null>(null);
  let imuSupported = $state(true);
  let tiltWarningShown = $state(false);

  const TILT_OK_THRESHOLD = 5;
  const TILT_WARN_THRESHOLD = 10;

  $effect(() => {
    startCamera();
    startIMU();
    return () => {
      stopCamera();
      stopIMU();
    };
  });

  // ── Camera ──

  async function startCamera() {
    cameraError = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false,
      });
      if (videoEl) {
        videoEl.srcObject = stream;
        videoEl.onloadedmetadata = () => { videoEl.play(); isReady = true; };
      }
    } catch (err: any) {
      cameraError = err.name === 'NotAllowedError'
        ? 'Camera permission denied. Please allow camera access in your browser settings.'
        : 'Could not open camera. Try uploading a photo instead.';
    }
  }

  function stopCamera() {
    stream?.getTracks().forEach(t => t.stop());
    stream = null;
    isReady = false;
  }

  // ── IMU Tilt Detection ──
  // beta=0 = phone flat (screen up, camera down) = ideal for top-down photo
  // beta=90 = phone vertical = bad
  // We measure deviation from beta=0 (flat horizontal)

  let imuHandler: ((e: DeviceOrientationEvent) => void) | null = null;

  function startIMU() {
    if (typeof DeviceOrientationEvent === 'undefined') {
      imuSupported = false;
      return;
    }

    if (typeof (DeviceOrientationEvent as any).requestPermission === 'function') {
      (DeviceOrientationEvent as any).requestPermission()
        .then((perm: string) => { if (perm === 'granted') attachIMUListener(); else imuSupported = false; })
        .catch(() => { imuSupported = false; });
    } else {
      attachIMUListener();
    }
  }

  function attachIMUListener() {
    imuHandler = (e: DeviceOrientationEvent) => {
      const beta = e.beta;   // front-back: 0=flat, 90=vertical
      const gamma = e.gamma; // left-right: 0=flat
      if (beta === null || gamma === null) { imuSupported = false; return; }

      // Deviation from flat (beta=0, gamma=0)
      // beta=0 means phone is horizontal with screen up / camera pointing down
      const betaDev = Math.abs(beta);
      const gammaDev = Math.abs(gamma);
      tiltAngle = Math.sqrt(betaDev ** 2 + gammaDev ** 2);
    };
    window.addEventListener('deviceorientation', imuHandler);

    setTimeout(() => { if (tiltAngle === null) imuSupported = false; }, 1000);
  }

  function stopIMU() {
    if (imuHandler) { window.removeEventListener('deviceorientation', imuHandler); imuHandler = null; }
  }

  let tiltOk = $derived(tiltAngle !== null && tiltAngle <= TILT_WARN_THRESHOLD);
  let tiltGood = $derived(tiltAngle !== null && tiltAngle <= TILT_OK_THRESHOLD);

  // ── Capture ──

  function capturePhoto() {
    if (!videoEl || !canvasEl || !isReady) return;

    if (imuSupported && !tiltOk && !tiltWarningShown) {
      tiltWarningShown = true;
      return;
    }

    flash = true;
    tiltWarningShown = false;
    setTimeout(() => { flash = false; }, 200);

    const w = videoEl.videoWidth;
    const h = videoEl.videoHeight;
    canvasEl.width = w;
    canvasEl.height = h;
    const ctx = canvasEl.getContext('2d')!;
    ctx.drawImage(videoEl, 0, 0, w, h);

    const capturedTilt = tiltAngle ?? 0;

    canvasEl.toBlob(blob => {
      if (!blob) return;
      const file = new File([blob], `grounds_${Date.now()}.jpg`, { type: 'image/jpeg' });
      stopCamera();
      onCapture(file, capturedTilt);
    }, 'image/jpeg', 0.92);
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="vf" onclick={(e) => e.stopPropagation()}>

  <video bind:this={videoEl} autoplay playsinline muted class="vf-video" />
  <canvas bind:this={canvasEl} class="hidden" />

  {#if flash}<div class="flash" />{/if}

  {#if cameraError}
    <div class="error-box">
      <p class="err-text">{cameraError}</p>
      <button onclick={onClose} class="err-btn">Use Photo Upload Instead</button>
    </div>
  {/if}

  {#if isReady && !cameraError}
    <div class="overlay">

      <div class="tip-bar">
        <p>📸 Hold flat above grounds · Quarter fully visible</p>
      </div>

      <!-- Corner brackets only -->
      <div class="frame">
        <div class="corner tl"></div>
        <div class="corner tr"></div>
        <div class="corner bl"></div>
        <div class="corner br"></div>

        {#if tiltWarningShown && !tiltOk}
          <div class="tilt-overlay-msg">
            <span>⚠️ Phone tilted ~{tiltAngle?.toFixed(0)}°</span>
            <span class="tilt-sub">Hold flat · Tap again to capture anyway</span>
          </div>
        {/if}
      </div>

      <!-- Bottom info -->
      <div class="info-bar">
        {#if imuSupported && tiltAngle !== null}
          <div class="tilt-badge" class:tilt-good={tiltGood} class:tilt-warn={!tiltOk}>
            <span class="tilt-dot"></span>
            <span class="tilt-text">
              {#if tiltGood}Level ✓
              {:else if tiltOk}{tiltAngle.toFixed(0)}° — OK
              {:else}{tiltAngle.toFixed(0)}° — Hold flat
              {/if}
            </span>
          </div>
        {/if}
      </div>

      <!-- Controls -->
      <div class="controls">
        <button onclick={onClose} class="btn-cancel">✕</button>
        <button onclick={capturePhoto} class="btn-shutter" aria-label="Capture photo">
          <span class="shutter-ring"
            class:ring-green={imuSupported && tiltGood}
            class:ring-yellow={imuSupported && tiltOk && !tiltGood}
            class:ring-red={imuSupported && !tiltOk}
          >
            <span class="shutter-dot"></span>
          </span>
        </button>
        <div style="width:56px"></div>
      </div>
    </div>
  {/if}
</div>

<style>
  .vf { position: fixed; inset: 0; z-index: 100; background: #000; display: flex; align-items: center; justify-content: center; }
  .vf-video { width: 100%; height: 100%; object-fit: cover; }
  .flash { position: absolute; inset: 0; background: white; opacity: 0.8; pointer-events: none; animation: flash-out 0.2s ease-out forwards; }
  @keyframes flash-out { from { opacity: 0.8; } to { opacity: 0; } }
  .hidden { display: none; }

  .error-box { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; background: rgba(0,0,0,0.85); }
  .err-text { color: #fff; font-size: 14px; text-align: center; padding: 0 24px; }
  .err-btn { margin-top: 12px; background: #92400e; color: white; border: none; padding: 10px 20px; border-radius: 12px; font-size: 14px; font-weight: 600; cursor: pointer; }

  .overlay { position: absolute; inset: 0; display: flex; flex-direction: column; pointer-events: none; }
  .tip-bar { background: rgba(0,0,0,0.5); padding: 10px 16px; text-align: center; }
  .tip-bar p { color: #fff; font-size: 12px; font-weight: 500; }

  .frame { flex: 1; position: relative; margin: 8px 12px; }
  .corner { position: absolute; width: 32px; height: 32px; border-color: rgba(255,255,255,0.8); border-style: solid; border-width: 0; }
  .corner.tl { top:0; left:0; border-top-width:3px; border-left-width:3px; border-radius: 4px 0 0 0; }
  .corner.tr { top:0; right:0; border-top-width:3px; border-right-width:3px; border-radius: 0 4px 0 0; }
  .corner.bl { bottom:0; left:0; border-bottom-width:3px; border-left-width:3px; border-radius: 0 0 0 4px; }
  .corner.br { bottom:0; right:0; border-bottom-width:3px; border-right-width:3px; border-radius: 0 0 4px 0; }

  .tilt-overlay-msg { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(239,68,68,0.9); color: white; padding: 12px 20px; border-radius: 12px; text-align: center; display: flex; flex-direction: column; gap: 4px; font-size: 14px; font-weight: 600; animation: fade-in 0.2s ease; }
  .tilt-sub { font-size: 11px; font-weight: 400; opacity: 0.85; }
  @keyframes fade-in { from { opacity: 0; transform: translate(-50%,-50%) scale(0.95); } to { opacity: 1; transform: translate(-50%,-50%) scale(1); } }

  .info-bar { background: rgba(0,0,0,0.5); padding: 6px 16px; display: flex; align-items: center; justify-content: center; }
  .tilt-badge { display: flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 20px; background: rgba(255,255,255,0.1); transition: background 0.3s ease; }
  .tilt-badge.tilt-good { background: rgba(74,222,128,0.2); }
  .tilt-badge.tilt-warn { background: rgba(239,68,68,0.2); }
  .tilt-dot { width: 8px; height: 8px; border-radius: 50%; background: #facc15; transition: background 0.3s ease; }
  .tilt-good .tilt-dot { background: #4ade80; }
  .tilt-warn .tilt-dot { background: #ef4444; }
  .tilt-text { color: rgba(255,255,255,0.85); font-size: 11px; font-weight: 500; }

  .controls { background: rgba(0,0,0,0.65); padding: 16px 24px 32px; display: flex; align-items: center; justify-content: space-between; pointer-events: auto; }
  .btn-cancel { width: 56px; height: 44px; background: rgba(255,255,255,0.12); border: none; border-radius: 10px; color: rgba(255,255,255,0.75); font-size: 18px; cursor: pointer; }
  .btn-shutter { border: none; background: none; cursor: pointer; display: flex; align-items: center; justify-content: center; padding: 0; }
  .shutter-ring { width: 72px; height: 72px; border-radius: 50%; border: 4px solid rgba(255,255,255,0.85); display: flex; align-items: center; justify-content: center; transition: border-color 0.3s ease, transform 0.1s ease; }
  .ring-green { border-color: #4ade80; }
  .ring-yellow { border-color: #facc15; }
  .ring-red { border-color: #ef4444; }
  .btn-shutter:active .shutter-ring { transform: scale(0.92); }
  .shutter-dot { width: 56px; height: 56px; border-radius: 50%; background: white; transition: background 0.1s ease; }
  .btn-shutter:active .shutter-dot { background: #e5e5e5; }
</style>
