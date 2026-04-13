<script lang="ts">
  /**
   * GrinderDial — A circular dial component that mimics a coffee grinder knob.
   * 
   * Features:
   * - Draggable circular dial with tick marks for each setting
   * - Tap on a number around the dial to jump to that setting
   * - Number input overlay for precise entry
   * - Haptic-style visual feedback on setting changes
   */

  let { value = $bindable(5), min = 1, max = 11 }: { value: number; min?: number; max?: number } = $props();
  const STEP = 1/3; // Fellow Ode has 2 notches between each integer (thirds)

  let isDragging = $state(false);
  let showInput = $state(false);
  let inputValue = $state('');
  let dialElement: SVGElement;

  function formatSetting(val: number): string {
    const whole = Math.floor(val);
    const frac = Math.round((val - whole) * 3) / 3;
    if (Math.abs(frac - 1/3) < 0.05) return `${whole}⅓`;
    if (Math.abs(frac - 2/3) < 0.05) return `${whole}⅔`;
    if (Math.abs(frac - 1.0) < 0.05) return `${whole + 1}`;
    return `${whole}`;
  }

  const TOTAL_STEPS = max - min + 1;
  const RADIUS = 100;
  const TICK_INNER = 72;
  const TICK_OUTER = 85;
  const SUB_TICK_INNER = 78;  // shorter sub-ticks
  const SUB_TICK_OUTER = 85;
  const LABEL_RADIUS = 58;
  const INDICATOR_RADIUS = 90;

  // Map value to angle (270° sweep, starting from bottom-left)
  const START_ANGLE = 135; // degrees from top (= 7:30 on clock)
  const SWEEP = 270;       // total sweep degrees

  function valueToAngle(val: number): number {
    const fraction = (val - min) / (max - min);
    return START_ANGLE + fraction * SWEEP;
  }

  function angleToValue(angleDeg: number): number {
    // Normalize angle to our sweep range
    let a = angleDeg - START_ANGLE;
    if (a < -20) a += 360;
    if (a > SWEEP + 20) a = SWEEP;
    const fraction = Math.max(0, Math.min(1, a / SWEEP));
    const raw = min + fraction * (max - min);
    // Snap to nearest 1/3 step
    return Math.round(raw / STEP) * STEP;
  }

  function getPointOnCircle(angleDeg: number, r: number): { x: number; y: number } {
    const rad = (angleDeg - 90) * (Math.PI / 180);
    return { x: 120 + r * Math.cos(rad), y: 120 + r * Math.sin(rad) };
  }

  function handlePointerDown(e: PointerEvent) {
    isDragging = true;
    updateFromPointer(e);
    (e.target as Element)?.setPointerCapture?.(e.pointerId);
  }

  function handlePointerMove(e: PointerEvent) {
    if (!isDragging) return;
    updateFromPointer(e);
  }

  function handlePointerUp() {
    isDragging = false;
  }

  function updateFromPointer(e: PointerEvent) {
    if (!dialElement) return;
    const rect = dialElement.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const dx = e.clientX - cx;
    const dy = e.clientY - cy;
    let angle = Math.atan2(dy, dx) * (180 / Math.PI) + 90;
    if (angle < 0) angle += 360;
    value = angleToValue(angle);
  }

  function handleNumberSubmit() {
    const num = parseFloat(inputValue);
    if (!isNaN(num) && num >= min && num <= max) {
      value = num;
    }
    showInput = false;
    inputValue = '';
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') handleNumberSubmit();
    if (e.key === 'Escape') { showInput = false; inputValue = ''; }
  }

  // Integer tick marks and labels
  let ticks = $derived(
    Array.from({ length: TOTAL_STEPS }, (_, i) => {
      const val = min + i;
      const angle = valueToAngle(val);
      const inner = getPointOnCircle(angle, TICK_INNER);
      const outer = getPointOnCircle(angle, TICK_OUTER);
      const label = getPointOnCircle(angle, LABEL_RADIUS);
      return { val, angle, inner, outer, label };
    })
  );

  // Sub-tick marks (2 between each integer = thirds)
  let subTicks = $derived(
    Array.from({ length: (TOTAL_STEPS - 1) * 2 }, (_, i) => {
      const intIndex = Math.floor(i / 2);
      const subIndex = (i % 2) + 1; // 1 or 2
      const val = min + intIndex + subIndex / 3;
      const angle = valueToAngle(val);
      const inner = getPointOnCircle(angle, SUB_TICK_INNER);
      const outer = getPointOnCircle(angle, SUB_TICK_OUTER);
      return { val, angle, inner, outer };
    })
  );

  let indicatorAngle = $derived(valueToAngle(value));
  let indicatorPoint = $derived(getPointOnCircle(indicatorAngle, INDICATOR_RADIUS));

  // Arc path for the active sweep
  function describeArc(startAngle: number, endAngle: number, r: number): string {
    const start = getPointOnCircle(startAngle, r);
    const end = getPointOnCircle(endAngle, r);
    const sweep = endAngle - startAngle;
    const largeArc = sweep > 180 ? 1 : 0;
    return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 1 ${end.x} ${end.y}`;
  }

  let activeArc = $derived(describeArc(START_ANGLE, indicatorAngle, RADIUS));
  let bgArc = $derived(describeArc(START_ANGLE, START_ANGLE + SWEEP, RADIUS));
</script>

<div class="grinder-dial-container">
  <svg
    bind:this={dialElement}
    viewBox="0 0 240 240"
    class="grinder-dial {isDragging ? 'dragging' : ''}"
    onpointerdown={handlePointerDown}
    onpointermove={handlePointerMove}
    onpointerup={handlePointerUp}
    onpointerleave={handlePointerUp}
    role="slider"
    aria-valuemin={min}
    aria-valuemax={max}
    aria-valuenow={value}
    aria-label="Grinder setting"
    tabindex="0"
  >
    <!-- Outer ring shadow -->
    <defs>
      <filter id="dial-shadow" x="-20%" y="-20%" width="140%" height="140%">
        <feDropShadow dx="0" dy="2" stdDeviation="4" flood-color="rgba(0,0,0,0.15)" />
      </filter>
      <linearGradient id="knob-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#f5f0eb" />
        <stop offset="50%" stop-color="#e8e0d6" />
        <stop offset="100%" stop-color="#d4c8ba" />
      </linearGradient>
      <linearGradient id="active-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#92400e" />
        <stop offset="100%" stop-color="#d97706" />
      </linearGradient>
    </defs>

    <!-- Knob body -->
    <circle cx="120" cy="120" r="108" fill="url(#knob-gradient)" filter="url(#dial-shadow)" />
    <circle cx="120" cy="120" r="106" fill="none" stroke="#c9bfb0" stroke-width="1" />

    <!-- Background arc track -->
    <path d={bgArc} fill="none" stroke="#d6cfc5" stroke-width="6" stroke-linecap="round" />

    <!-- Active arc -->
    <path d={activeArc} fill="none" stroke="url(#active-gradient)" stroke-width="6" stroke-linecap="round" />

    <!-- Sub-tick marks (2 between each integer) -->
    {#each subTicks as st}
      <line
        x1={st.inner.x} y1={st.inner.y}
        x2={st.outer.x} y2={st.outer.y}
        stroke={Math.abs(st.val - value) < 0.01 ? '#92400e' : '#c4b8a8'}
        stroke-width="1"
        stroke-linecap="round"
      />
    {/each}

    <!-- Integer tick marks -->
    {#each ticks as tick}
      <line
        x1={tick.inner.x} y1={tick.inner.y}
        x2={tick.outer.x} y2={tick.outer.y}
        stroke={Math.abs(tick.val - value) < 0.01 ? '#92400e' : '#a89888'}
        stroke-width={Math.abs(tick.val - value) < 0.01 ? 3 : 1.5}
        stroke-linecap="round"
      />
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <text
        x={tick.label.x} y={tick.label.y}
        text-anchor="middle"
        dominant-baseline="central"
        class="tick-label {Math.abs(tick.val - value) < 0.5 ? 'active' : ''}"
        onclick={() => value = tick.val}
      >
        {tick.val}
      </text>
    {/each}

    <!-- Indicator dot -->
    <circle
      cx={indicatorPoint.x} cy={indicatorPoint.y} r="8"
      fill="#92400e" stroke="#fff" stroke-width="2.5"
      class="indicator-dot"
    />
  </svg>

  <!-- Center display -->
  <div class="center-display">
    {#if showInput}
      <input
        type="number"
        class="setting-input"
        min={min}
        max={max}
        bind:value={inputValue}
        onkeydown={handleKeydown}
        onblur={handleNumberSubmit}
        placeholder={String(value)}
        autofocus
      />
    {:else}
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="setting-display" onclick={() => { showInput = true; inputValue = String(value); }}>
        <span class="setting-number">{formatSetting(value)}</span>
        <span class="setting-label">Setting</span>
        <span class="setting-hint">tap to type</span>
      </div>
    {/if}
  </div>
</div>

<style>
  .grinder-dial-container {
    position: relative;
    width: 240px;
    height: 240px;
    margin: 0 auto;
    touch-action: none;
    user-select: none;
  }

  .grinder-dial {
    width: 100%;
    height: 100%;
    cursor: grab;
    transition: transform 0.1s ease;
  }

  .grinder-dial.dragging {
    cursor: grabbing;
    transform: scale(1.02);
  }

  .tick-label {
    font-size: 11px;
    font-weight: 500;
    fill: #8b7e6e;
    cursor: pointer;
    transition: fill 0.15s ease, font-size 0.15s ease;
  }

  .tick-label.active {
    fill: #92400e;
    font-size: 13px;
    font-weight: 700;
  }

  .tick-label:hover {
    fill: #d97706;
  }

  .indicator-dot {
    filter: drop-shadow(0 1px 3px rgba(0, 0, 0, 0.3));
    transition: cx 0.15s ease, cy 0.15s ease;
  }

  .center-display {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    text-align: center;
    pointer-events: auto;
  }

  .setting-display {
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0;
  }

  .setting-number {
    font-size: 36px;
    font-weight: 700;
    color: #44260a;
    line-height: 1;
  }

  .setting-label {
    font-size: 11px;
    font-weight: 500;
    color: #8b7e6e;
    text-transform: uppercase;
    letter-spacing: 1.5px;
  }

  .setting-hint {
    font-size: 9px;
    color: #b5a898;
    margin-top: 2px;
  }

  .setting-input {
    width: 60px;
    text-align: center;
    font-size: 28px;
    font-weight: 700;
    color: #44260a;
    background: rgba(255, 255, 255, 0.9);
    border: 2px solid #d97706;
    border-radius: 8px;
    padding: 4px;
    outline: none;
  }

  .setting-input::-webkit-inner-spin-button,
  .setting-input::-webkit-outer-spin-button {
    -webkit-appearance: none;
  }
</style>
