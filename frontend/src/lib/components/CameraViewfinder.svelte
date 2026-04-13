<script lang="ts">
  /**
   * CameraViewfinder — Live camera with framing guides.
   * Uses getUserMedia() for a custom viewfinder with overlays.
   * Falls back gracefully if camera API is unavailable.
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

  // Start camera on mount
  $effect(() => {
    startCamera();
    return () => stopCamera();
  });

  async function startCamera() {
    cameraError = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'environment',   // rear camera
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

  function capturePhoto() {
    if (!videoEl || !canvasEl || !isReady) return;

    // Flash effect
    flash = true;
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
<div class="viewfinder-container" onclick={(e) => e.stopPropagation()}>

  <!-- Video stream -->
  <video bind:this={videoEl} autoplay playsinline muted class="viewfinder-video" />

  <!-- Hidden canvas for capture -->
  <canvas bind:this={canvasEl} class="hidden" />

  <!-- Flash overlay -->
  {#if flash}
    <div class="flash-overlay" />
  {/if}

  <!-- Error state -->
  {#if cameraError}
    <div class="error-box">
      <p class="text-sm text-white text-center px-4">{cameraError}</p>
      <button onclick={onClose} class="close-btn mt-3">Use Photo Upload Instead</button>
    </div>
  {/if}

  <!-- Framing guide overlay (only when camera ready) -->
  {#if isReady && !cameraError}
    <div class="guide-overlay">

      <!-- Top tip bar -->
      <div class="tip-bar">
        <p>📸 Hold directly above · Tap to focus · Full quarter in frame</p>
      </div>

      <!-- Corner bracket guides (centre composition zone) -->
      <div class="guide-frame">
        <!-- Top-left corner -->
        <div class="corner tl"></div>
        <!-- Top-right corner -->
        <div class="corner tr"></div>
        <!-- Bottom-left corner -->
        <div class="corner bl"></div>
        <!-- Bottom-right corner -->
        <div class="corner br"></div>

        <!-- Quarter placement hint -->
        <div class="quarter-hint">
          <div class="quarter-circle">
            <span class="quarter-label">25¢</span>
          </div>
          <div class="quarter-tip-text">Place quarter here</div>
        </div>
      </div>

      <!-- Calibration range reminder -->
      <div class="cal-bar">
        <span class="cal-dot good"></span>
        <span class="cal-text">Aim for quarter to fill ~¼ of frame width for best calibration</span>
      </div>

      <!-- Controls -->
      <div class="controls">
        <button onclick={onClose} class="ctrl-btn secondary">✕ Cancel</button>
        <button onclick={capturePhoto} class="ctrl-btn capture" aria-label="Capture photo">
          <span class="shutter-outer"><span class="shutter-inner"></span></span>
        </button>
        <!-- spacer -->
        <div style="width:64px"></div>
      </div>
    </div>
  {/if}
</div>

<style>
  .viewfinder-container {
    position: fixed;
    inset: 0;
    z-index: 100;
    background: #000;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }

  .viewfinder-video {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .flash-overlay {
    position: absolute;
    inset: 0;
    background: white;
    opacity: 0.8;
    pointer-events: none;
    animation: flash-fade 0.2s ease-out forwards;
  }

  @keyframes flash-fade {
    from { opacity: 0.8; }
    to   { opacity: 0;   }
  }

  .error-box {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: rgba(0,0,0,0.85);
  }

  .close-btn {
    background: #92400e;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
  }

  /* ── Guide overlay ── */
  .guide-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    pointer-events: none;
  }

  .tip-bar {
    background: rgba(0,0,0,0.55);
    padding: 10px 16px;
    text-align: center;
    pointer-events: none;
  }

  .tip-bar p {
    color: #fff;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.02em;
  }

  .guide-frame {
    flex: 1;
    position: relative;
    margin: 12px 16px;
  }

  /* Corner brackets */
  .corner {
    position: absolute;
    width: 28px;
    height: 28px;
    border-color: rgba(255,255,255,0.85);
    border-style: solid;
    border-width: 0;
  }
  .corner.tl { top: 0; left: 0;  border-top-width: 3px; border-left-width: 3px;  border-top-left-radius: 4px; }
  .corner.tr { top: 0; right: 0; border-top-width: 3px; border-right-width: 3px; border-top-right-radius: 4px; }
  .corner.bl { bottom: 0; left: 0;  border-bottom-width: 3px; border-left-width: 3px;  border-bottom-left-radius: 4px; }
  .corner.br { bottom: 0; right: 0; border-bottom-width: 3px; border-right-width: 3px; border-bottom-right-radius: 4px; }

  /* Quarter placement indicator — bottom-right area */
  .quarter-hint {
    position: absolute;
    bottom: 24px;
    right: 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
  }

  .quarter-circle {
    width: 22vw;
    height: 22vw;
    border: 2.5px dashed rgba(255, 214, 0, 0.85);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 214, 0, 0.08);
    animation: pulse-ring 2s ease-in-out infinite;
  }

  @keyframes pulse-ring {
    0%, 100% { border-color: rgba(255,214,0,0.7); box-shadow: 0 0 0 0 rgba(255,214,0,0.3); }
    50%       { border-color: rgba(255,214,0,1.0); box-shadow: 0 0 0 6px rgba(255,214,0,0); }
  }

  .quarter-label {
    color: rgba(255, 214, 0, 0.95);
    font-size: 16px;
    font-weight: 700;
    letter-spacing: -0.5px;
  }

  .quarter-tip-text {
    color: rgba(255, 214, 0, 0.9);
    font-size: 12px;
    font-weight: 500;
    text-shadow: 0 1px 3px rgba(0,0,0,0.6);
    white-space: nowrap;
  }

  .cal-bar {
    background: rgba(0,0,0,0.55);
    padding: 6px 16px;
    display: flex;
    align-items: center;
    gap: 6px;
    pointer-events: none;
  }

  .cal-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .cal-dot.good { background: #4ade80; }

  .cal-text {
    color: rgba(255,255,255,0.8);
    font-size: 11px;
  }

  /* ── Controls ── */
  .controls {
    background: rgba(0,0,0,0.7);
    padding: 20px 24px 36px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    pointer-events: auto;
  }

  .ctrl-btn {
    cursor: pointer;
    border: none;
    background: none;
  }

  .ctrl-btn.secondary {
    color: rgba(255,255,255,0.75);
    font-size: 14px;
    font-weight: 500;
    padding: 8px 12px;
    background: rgba(255,255,255,0.12);
    border-radius: 10px;
    width: 64px;
  }

  .ctrl-btn.capture {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .shutter-outer {
    width: 72px;
    height: 72px;
    border-radius: 50%;
    border: 4px solid rgba(255,255,255,0.9);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.1s ease;
  }

  .ctrl-btn.capture:active .shutter-outer {
    transform: scale(0.92);
  }

  .shutter-inner {
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: white;
    transition: background 0.1s ease;
  }

  .ctrl-btn.capture:active .shutter-inner {
    background: #e5e5e5;
  }

  .hidden { display: none; }
</style>
