<script lang="ts">
  /**
   * CameraViewfinder — Live camera with framing guides + IMU tilt detection.
   * - Framing guide with quarter placement circle scaled to ~25% of frame width
   * - Real-time tilt indicator via DeviceOrientationEvent
   * - Shutter gated: warns if phone is tilted > 10°
   */

  let { onCapture, onClose }: {
    onCapture: (file: File) => void;
    onClose: () => void;
  } = $props();

  let videoEl: HTMLVideoElement;
  let canvasEl: HTMLCanvasElement;
  let stream: MediaStream | null = null;
  let cameraError = $state<string | null>(null);
  let isReady = $state(false);
  let flash = $state(false);

  // IMU tilt state
  let tiltAngle = $state<number | null>(null); // degrees from vertical
  let imuSupported = $state(true);
  let tiltWarningShown = $state(false);

  const TILT_OK_THRESHOLD = 5;   // green when within 5°
  const TILT_WARN_THRESHOLD = 10; // red when beyond 10°

  // Start camera + IMU on mount
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
        video: {
          facingMode: 'environment',
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      });
      if (videoEl) {
        videoEl.srcObject = stream;
        videoEl.onloadedmetadata = () => {
          videoEl.play();
          isReady = true;
        };
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

  let imuHandler: ((e: DeviceOrientationEvent) => void) | null = null;

  function startIMU() {
    if (typeof DeviceOrientationEvent === 'undefined') {
      imuSupported = false;
      return;
    }

    // iOS 13+ requires permission
    if (typeof (DeviceOrientationEvent as any).requestPermission === 'function') {
      (DeviceOrientationEvent as any).requestPermission()
        .then((perm: string) => {
          if (perm === 'granted') {
            attachIMUListener();
          } else {
            imuSupported = false;
          }
        })
        .catch(() => { imuSupported = false; });
    } else {
      attachIMUListener();
    }
  }

  function attachIMUListener() {
    imuHandler = (e: DeviceOrientationEvent) => {
      const beta = e.beta;  // front-back tilt (-180 to 180)
      const gamma = e.gamma; // left-right tilt (-90 to 90)
      if (beta === null || gamma === null) {
        imuSupported = false;
        return;
      }
      // When phone is flat face-down: beta ≈ 0 (or ±180), gamma ≈ 0
      // When phone is vertical: beta ≈ 90
      // We want to measure deviation from straight-down (beta=90 for rear camera pointing down)
      // Tilt from perpendicular = how far beta is from 90° + gamma deviation
      const betaDev = Math.abs(beta - 90); // deviation from pointing straight down
      const gammaDev = Math.abs(gamma);
      tiltAngle = Math.sqrt(betaDev ** 2 + gammaDev ** 2);
    };
    window.addEventListener('deviceorientation', imuHandler);

    // If no data comes in after 1s, assume not supported
    setTimeout(() => {
      if (tiltAngle === null) {
        imuSupported = false;
      }
    }, 1000);
  }

  function stopIMU() {
    if (imuHandler) {
      window.removeEventListener('deviceorientation', imuHandler);
      imuHandler = null;
    }
  }

  let tiltOk = $derived(tiltAngle !== null && tiltAngle <= TILT_WARN_THRESHOLD);
  let tiltGood = $derived(tiltAngle !== null && tiltAngle <= TILT_OK_THRESHOLD);

  // ── Capture ──

  function capturePhoto() {
    if (!videoEl || !canvasEl || !isReady) return;

    // If tilt is too steep and IMU is supported, warn once then allow
    if (imuSupported && !tiltOk && !tiltWarningShown) {
      tiltWarningShown = true;
      return; // first tap shows warning, second tap overrides
    }

    // Flash effect
    flash = true;
    tiltWarningShown = false;
    setTimeout(() => { flash = false; }, 200);

    const w = videoEl.videoWidth;
    const h = videoEl.videoHeight;
    canvasEl.width = w;
    canvasEl.height = h;
    const ctx = canvasEl.getContext('2d')!;
    ctx.drawImage(videoEl, 0, 0, w, h);

    canvasEl.toBlob(blob => {
      if (!blob) return;
      const file = new File([blob], `grounds_${Date.now()}.jpg`, { type: 'image/jpeg' });
      stopCamera();
      onCapture(file);
    }, 'image/jpeg', 0.92);
  }
</script>

<!-- Fullscreen viewfinder overlay -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="vf" onclick={(e) => e.stopPropagation()}>

  <video bind:this={videoEl} autoplay playsinline muted class="vf-video" />
  <canvas bind:this={canvasEl} class="hidden" />

  {#if flash}
    <div class="flash" />
  {/if}

  {#if cameraError}
    <div class="error-box">
      <p class="err-text">{cameraError}</p>
      <button onclick={onClose} class="err-btn">Use Photo Upload Instead</button>
    </div>
  {/if}

  {#if isReady && !cameraError}
    <div class="overlay">

      <!-- Top tip bar -->
      <div class="tip-bar">
        <p>📸 Hold directly above · Full quarter in frame</p>
      </div>

      <!-- Framing guides -->
      <div class="frame">
        <div class="corner tl"></div>
        <div class="corner tr"></div>
        <div class="corner bl"></div>
        <div class="corner br"></div>

        <!-- Quarter placement circle — sized to ~25% of screen width -->
        <div class="quarter-zone">
          <div class="quarter-ring">
            <span class="quarter-label">25¢</span>
          </div>
          <span class="quarter-text">Place quarter here</span>
        </div>

        <!-- Tilt warning overlay text -->
        {#if tiltWarningShown && !tiltOk}
          <div class="tilt-overlay-msg">
            <span>⚠️ Phone is tilted ~{tiltAngle?.toFixed(0)}°</span>
            <span class="tilt-sub">Tap again to capture anyway</span>
          </div>
        {/if}
      </div>

      <!-- Bottom info bar -->
      <div class="info-bar">
        {#if imuSupported && tiltAngle !== null}
          <div class="tilt-badge" class:tilt-good={tiltGood} class:tilt-warn={!tiltOk}>
            <span class="tilt-dot"></span>
            <span class="tilt-text">
              {#if tiltGood}
                Level ✓
              {:else if tiltOk}
                {tiltAngle.toFixed(0)}° — OK
              {:else}
                {tiltAngle.toFixed(0)}° — Hold overhead
              {/if}
            </span>
          </div>
        {:else}
          <span class="cal-hint">Quarter ≈ ¼ of frame width for best accuracy</span>
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
  /* ── Container ── */
  .vf {
    position: fixed; inset: 0; z-index: 100;
    background: #000;
    display: flex; align-items: center; justify-content: center;
  }
  .vf-video { width: 100%; height: 100%; object-fit: cover; }

  .flash {
    position: absolute; inset: 0;
    background: white; opacity: 0.8; pointer-events: none;
    animation: flash-out 0.2s ease-out forwards;
  }
  @keyframes flash-out { from { opacity: 0.8; } to { opacity: 0; } }

  .hidden { display: none; }

  /* ── Error ── */
  .error-box {
    position: absolute; inset: 0;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    background: rgba(0,0,0,0.85);
  }
  .err-text { color: #fff; font-size: 14px; text-align: center; padding: 0 24px; }
  .err-btn {
    margin-top: 12px; background: #92400e; color: white; border: none;
    padding: 10px 20px; border-radius: 12px; font-size: 14px; font-weight: 600; cursor: pointer;
  }

  /* ── Overlay ── */
  .overlay {
    position: absolute; inset: 0;
    display: flex; flex-direction: column;
    pointer-events: none;
  }

  .tip-bar {
    background: rgba(0,0,0,0.5); padding: 10px 16px; text-align: center;
  }
  .tip-bar p { color: #fff; font-size: 12px; font-weight: 500; }

  /* ── Frame guides ── */
  .frame { flex: 1; position: relative; margin: 8px 12px; }

  .corner {
    position: absolute; width: 32px; height: 32px;
    border-color: rgba(255,255,255,0.8); border-style: solid; border-width: 0;
  }
  .corner.tl { top:0; left:0;     border-top-width:3px; border-left-width:3px;   border-radius: 4px 0 0 0; }
  .corner.tr { top:0; right:0;    border-top-width:3px; border-right-width:3px;  border-radius: 0 4px 0 0; }
  .corner.bl { bottom:0; left:0;  border-bottom-width:3px; border-left-width:3px; border-radius: 0 0 0 4px; }
  .corner.br { bottom:0; right:0; border-bottom-width:3px; border-right-width:3px; border-radius: 0 0 4px 0; }

  /* ── Quarter indicator — 25% of viewport width ── */
  .quarter-zone {
    position: absolute;
    bottom: 10%;
    right: 8%;
    display: flex; flex-direction: column; align-items: center; gap: 6px;
  }

  .quarter-ring {
    /* 24vw = ~25% of phone width. On 375px = 90px, on 430px = 103px */
    width: 24vw;
    height: 24vw;
    max-width: 130px;
    max-height: 130px;
    border: 3px dashed rgba(255, 214, 0, 0.85);
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    background: rgba(255, 214, 0, 0.06);
    animation: subtle-pulse 2.5s ease-in-out infinite;
  }

  @keyframes subtle-pulse {
    0%, 100% {
      transform: scale(1.0);
      border-color: rgba(255,214,0,0.7);
      box-shadow: 0 0 0 0 rgba(255,214,0,0.25);
    }
    50% {
      transform: scale(1.06);
      border-color: rgba(255,214,0,1.0);
      box-shadow: 0 0 0 8px rgba(255,214,0,0);
    }
  }

  .quarter-label {
    color: rgba(255,214,0,0.95);
    font-size: clamp(14px, 4vw, 18px);
    font-weight: 700;
  }

  .quarter-text {
    color: rgba(255,214,0,0.85);
    font-size: clamp(10px, 2.8vw, 13px);
    font-weight: 500;
    text-shadow: 0 1px 4px rgba(0,0,0,0.7);
    white-space: nowrap;
  }

  /* ── Tilt warning overlay ── */
  .tilt-overlay-msg {
    position: absolute;
    top: 50%; left: 50%; transform: translate(-50%, -50%);
    background: rgba(239, 68, 68, 0.9);
    color: white; padding: 12px 20px; border-radius: 12px;
    text-align: center; display: flex; flex-direction: column; gap: 4px;
    font-size: 14px; font-weight: 600;
    animation: fade-in 0.2s ease;
  }
  .tilt-sub { font-size: 11px; font-weight: 400; opacity: 0.85; }
  @keyframes fade-in { from { opacity: 0; transform: translate(-50%,-50%) scale(0.95); } to { opacity: 1; transform: translate(-50%,-50%) scale(1); } }

  /* ── Info bar ── */
  .info-bar {
    background: rgba(0,0,0,0.5);
    padding: 6px 16px;
    display: flex; align-items: center; justify-content: center;
  }

  .tilt-badge {
    display: flex; align-items: center; gap: 6px;
    padding: 3px 10px; border-radius: 20px;
    background: rgba(255,255,255,0.1);
    transition: background 0.3s ease;
  }
  .tilt-badge.tilt-good { background: rgba(74, 222, 128, 0.2); }
  .tilt-badge.tilt-warn { background: rgba(239, 68, 68, 0.2); }

  .tilt-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #facc15; /* default yellow */
    transition: background 0.3s ease;
  }
  .tilt-good .tilt-dot { background: #4ade80; }
  .tilt-warn .tilt-dot { background: #ef4444; }

  .tilt-text { color: rgba(255,255,255,0.85); font-size: 11px; font-weight: 500; }

  .cal-hint { color: rgba(255,255,255,0.7); font-size: 11px; }

  /* ── Controls ── */
  .controls {
    background: rgba(0,0,0,0.65);
    padding: 16px 24px 32px;
    display: flex; align-items: center; justify-content: space-between;
    pointer-events: auto;
  }

  .btn-cancel {
    width: 56px; height: 44px;
    background: rgba(255,255,255,0.12); border: none; border-radius: 10px;
    color: rgba(255,255,255,0.75); font-size: 18px; cursor: pointer;
  }

  .btn-shutter {
    border: none; background: none; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    padding: 0;
  }

  .shutter-ring {
    width: 72px; height: 72px; border-radius: 50%;
    border: 4px solid rgba(255,255,255,0.85);
    display: flex; align-items: center; justify-content: center;
    transition: border-color 0.3s ease, transform 0.1s ease;
  }
  .ring-green { border-color: #4ade80; }
  .ring-yellow { border-color: #facc15; }
  .ring-red { border-color: #ef4444; }

  .btn-shutter:active .shutter-ring { transform: scale(0.92); }

  .shutter-dot {
    width: 56px; height: 56px; border-radius: 50%;
    background: white;
    transition: background 0.1s ease;
  }
  .btn-shutter:active .shutter-dot { background: #e5e5e5; }
</style>
