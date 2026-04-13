<script lang="ts">
  import PageLayout from '$lib/components/PageLayout.svelte';
  import GrindAnalysisResult from '$lib/components/GrindAnalysisResult.svelte';
  import BrewFeedbackForm from '$lib/components/BrewFeedbackForm.svelte';
  import RecommendationResult from '$lib/components/RecommendationResult.svelte';
  import GrindSizeGuide from '$lib/components/GrindSizeGuide.svelte';
  import CameraViewfinder from '$lib/components/CameraViewfinder.svelte';
  import { Camera, Upload, Info, ChevronRight, AlertCircle, Wifi, WifiOff, ChevronDown } from 'lucide-svelte';
  import { analyzePhoto, getRecommendation, checkHealth } from '$lib/api';
  import type { PsdResult, AnalyzeResponse, RecommendationResult as RecResult } from '$lib/api';

  // ── State ─────────────────────────────────────────────

  type AppStep = 'upload' | 'analyzing' | 'results' | 'feedback' | 'recommendation';

  let step = $state<AppStep>('upload');
  let uploadedImage = $state<string | null>(null);
  let uploadedFile = $state<File | null>(null);
  let errorMessage = $state<string | null>(null);
  let apiConnected = $state<boolean | null>(null);

  // Analysis results
  let psdResult = $state<PsdResult | null>(null);
  let classificationMessage = $state('');
  let grindCategory = $state('');
  let analysisMetadata = $state<{ scale_px_per_mm: number; n_clumps: number; clump_ratio: number; n_silverskin: number } | null>(null);
  let showDetectionStats = $state(false);

  // Pre-analysis brew survey (optional)
  let surveyBrewMethod = $state('pour_over');
  let surveyTemp = $state('');
  let surveyDose = $state('');
  let surveyWater = $state('');

  // Recommendation
  let recommendation = $state<RecResult | null>(null);

  let fileInput: HTMLInputElement;
  let showCamera = $state(false);

  async function handleCameraCapture(file: File) {
    showCamera = false;
    uploadedFile = file;
    uploadedImage = URL.createObjectURL(file);
    analyzeGrind();
  }

  // ── Health check on mount ─────────────────────────────

  $effect(() => {
    checkHealth().then(ok => { apiConnected = ok; });
  });

  // ── Handlers ──────────────────────────────────────────

  async function handleFileChange(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (file) {
      uploadedFile = file;
      uploadedImage = URL.createObjectURL(file);
      analyzeGrind();
    }
  }

  import type { QualityWarning } from '$lib/api';

  // Quality warnings from analysis
  let qualityWarnings = $state<QualityWarning[]>([]);
  let showWarningModal = $state(false);

  async function analyzeGrind() {
    if (!uploadedFile) return;
    step = 'analyzing';
    errorMessage = null;
    qualityWarnings = [];

    try {
      const result = await analyzePhoto(uploadedFile, surveyBrewMethod);
      psdResult = result.psd;
      classificationMessage = result.classification_message;
      grindCategory = result.grind_category;
      qualityWarnings = result.quality_warnings || [];
      analysisMetadata = {
        scale_px_per_mm: result.scale_px_per_mm,
        n_clumps: result.n_clumps,
        clump_ratio: result.clump_ratio,
        n_silverskin: result.n_silverskin,
      };

      // If there are error-severity warnings, show popup before results
      if (qualityWarnings.some(w => w.severity === 'error')) {
        showWarningModal = true;
      }

      step = 'results';
    } catch (err: any) {
      errorMessage = err.message || 'Analysis failed';
      qualityWarnings = err.quality_warnings || [];
      // If backend didn't send structured warnings, create one from the error
      if (qualityWarnings.length === 0) {
        qualityWarnings = [{
          code: 'analysis_error',
          severity: 'error' as const,
          message: errorMessage,
          tip: 'Check that a US quarter is fully visible, the photo is taken from directly above, and the image is sharp and well-lit.',
        }];
      }
      showWarningModal = true;
      step = 'upload';
    }
  }

  function startFeedback() {
    step = 'feedback';
  }

  // Brew feedback data (captured when user submits feedback form)
  let lastFeedback = $state<any>(null);

  async function handleFeedbackSubmit(payload: any) {
    errorMessage = null;
    lastFeedback = payload;  // Store for journal saving
    try {
      const result = await getRecommendation(payload);
      recommendation = result.recommendation;
      step = 'recommendation';
    } catch (err: any) {
      errorMessage = err.message || 'Recommendation failed';
    }
  }

  const JOURNAL_KEY = 'truegrind-journal';

  const BREW_METHOD_LABELS: Record<string, string> = {
    pour_over: 'Pour Over', french_press: 'French Press',
    aeropress: 'AeroPress', drip: 'Drip Machine', moka_pot: 'Moka Pot',
    espresso: 'Espresso', chemex: 'Chemex', cold_brew: 'Cold Brew',
    hario_switch: 'Hario Switch', aeropress_inverted: 'AeroPress (Inverted)',
  };

  function formatBrewTime(seconds: number | undefined): string {
    if (!seconds) return '';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  function saveToJournal() {
    if (!psdResult) return;

    const fb = lastFeedback || {};

    const entry = {
      id: Date.now().toString(),
      date: new Date().toISOString().split('T')[0],
      bean: '',
      grindSize: `${grindCategory.replace('_', ' ')} (${Math.round(psdResult.D50)}μm)`,
      brewMethod: BREW_METHOD_LABELS[fb.brew_method] || BREW_METHOD_LABELS[surveyBrewMethod] || fb.brew_method || surveyBrewMethod || '',
      waterTemp: fb.water_temp_c || (surveyTemp ? ((parseFloat(surveyTemp) - 32) * 5 / 9) : 0),
      brewTime: formatBrewTime(fb.extraction_time_s),
      rating: 0,
      notes: fb.taste_notes || '',
      taste: fb.taste_tags || [],
      dose_g: fb.dose_g || (surveyDose ? parseFloat(surveyDose) : 0),
      water_g: fb.water_g || (surveyWater ? parseFloat(surveyWater) : 0),
      // Extra analysis data
      d50: psdResult.D50,
      d10: psdResult.D10,
      d90: psdResult.D90,
      particles: psdResult.n_particles,
      uniformity: psdResult.uniformity,
      autoSaved: true,
    };

    try {
      const stored = localStorage.getItem(JOURNAL_KEY);
      const entries = stored ? JSON.parse(stored) : [];
      entries.unshift(entry);
      localStorage.setItem(JOURNAL_KEY, JSON.stringify(entries));
    } catch (e) {
      console.error('Failed to save to journal:', e);
    }
  }

  let skipLog = $state(false);

  function startOver() {
    // Auto-save current analysis to journal (unless user opted out)
    if (!skipLog) saveToJournal();

    step = 'upload';
    uploadedImage = null;
    uploadedFile = null;
    psdResult = null;
    recommendation = null;
    errorMessage = null;
    classificationMessage = '';
    grindCategory = '';
    lastFeedback = null;
    qualityWarnings = [];
    showWarningModal = false;
    skipLog = false;
    analysisMetadata = null;
    showDetectionStats = false;
  }
</script>

<!-- Camera viewfinder fullscreen overlay -->
{#if showCamera}
  <CameraViewfinder
    onCapture={handleCameraCapture}
    onClose={() => showCamera = false}
  />
{/if}

<PageLayout>
  <div class="space-y-5">
    <!-- Header -->
    <div class="text-center space-y-2">
      <h1 class="text-amber-900 text-3xl font-bold tracking-tight">TrueGrind</h1>
      <p class="text-neutral-500 text-sm">Measure · Brew · Optimize</p>
      {#if apiConnected === false}
        <div class="flex items-center justify-center gap-1.5 text-xs text-red-600 bg-red-50 py-1.5 px-3 rounded-full mx-auto w-fit">
          <WifiOff class="w-3 h-3" /> Backend offline — start the API server
        </div>
      {:else if apiConnected === true}
        <div class="flex items-center justify-center gap-1.5 text-xs text-green-600 bg-green-50 py-1.5 px-3 rounded-full mx-auto w-fit">
          <Wifi class="w-3 h-3" /> Connected
        </div>
      {/if}
    </div>

    <!-- Error message -->
    {#if errorMessage}
      <div class="flex items-start gap-2 text-sm text-red-700 bg-red-50 p-4 rounded-xl border border-red-200">
        <AlertCircle class="w-5 h-5 flex-shrink-0 mt-0.5" />
        <div>
          <p class="font-medium">Something went wrong</p>
          <p class="mt-0.5">{errorMessage}</p>
        </div>
      </div>
    {/if}

    <!-- Quality Warning Modal -->
    {#if showWarningModal && qualityWarnings.length > 0}
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="fixed inset-0 z-50 flex items-center justify-center p-4" style="background: var(--overlay);" onclick={() => showWarningModal = false}>
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="rounded-2xl p-5 max-w-sm w-full space-y-4" style="background: var(--surface);" onclick={(e) => e.stopPropagation()}>
          <div class="flex items-center gap-2">
            <div class="w-10 h-10 rounded-full flex items-center justify-center" style="background: rgba(239,68,68,0.1);">
              <AlertCircle class="w-5 h-5" style="color: var(--danger);" />
            </div>
            <div>
              <h3 class="font-semibold" style="color: var(--text);">Image Quality Issues</h3>
              <p class="text-xs" style="color: var(--text-muted);">Your results may be less accurate</p>
            </div>
          </div>
          <div class="space-y-3">
            {#each qualityWarnings as warning}
              <div class="p-3 rounded-lg" style="background: {warning.severity === 'error' ? 'rgba(239,68,68,0.08)' : 'rgba(234,179,8,0.08)'}; border: 1px solid {warning.severity === 'error' ? 'rgba(239,68,68,0.2)' : 'rgba(234,179,8,0.2)'};">
                <span class="text-xs font-semibold px-1.5 py-0.5 rounded" style="background: {warning.severity === 'error' ? 'rgba(239,68,68,0.15)' : 'rgba(234,179,8,0.15)'}; color: {warning.severity === 'error' ? '#ef4444' : '#ca8a04'};">
                  {warning.severity === 'error' ? '⚠ Critical' : '⚡ Warning'}
                </span>
                <p class="text-sm font-medium mt-1" style="color: var(--text);">{warning.message}</p>
                <p class="text-xs mt-1" style="color: var(--text-muted);">💡 {warning.tip}</p>
              </div>
            {/each}
          </div>
          <div class="flex gap-2 pt-1">
            <button onclick={() => { showWarningModal = false; step = 'upload'; uploadedImage = null; uploadedFile = null; }}
              class="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white transition-colors bg-amber-700 hover:bg-amber-800">
              📸 Retake Photo
            </button>
            {#if step === 'results'}
              <button onclick={() => showWarningModal = false}
                class="flex-1 py-2.5 rounded-xl text-sm font-medium transition-colors border border-neutral-300 text-neutral-600">
                View Results
              </button>
            {/if}
          </div>
        </div>
      </div>
    {/if}

    <!-- Step 1: Upload -->
    {#if step === 'upload'}
      <div class="p-5 bg-white border border-neutral-200 rounded-xl space-y-4">
        <div class="flex items-start gap-2 text-sm text-neutral-600 bg-amber-50 p-3 rounded-lg">
          <Info class="w-5 h-5 text-amber-700 flex-shrink-0 mt-0.5" />
          <p>Spread your grounds on white paper with a US quarter for scale. Take a clear, well-lit photo.</p>
        </div>

        <!-- Pre-analysis brew survey (optional) -->
        <div class="space-y-3">
          <h4 class="text-sm font-semibold text-neutral-700">Brew Info <span class="font-normal text-neutral-400">(optional)</span></h4>
          <div class="grid grid-cols-2 gap-2">
            <div class="col-span-2">
              <select bind:value={surveyBrewMethod}
                class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 bg-white">
                <optgroup label="Pour Over">
                  <option value="pour_over">V60</option>
                  <option value="chemex">Chemex</option>
                  <option value="pour_over">Kalita Wave</option>
                  <option value="pour_over">Hario Switch</option>
                  <option value="pour_over">Pour Over (Other)</option>
                </optgroup>
                <optgroup label="Immersion">
                  <option value="french_press">French Press</option>
                  <option value="aeropress">AeroPress</option>
                  <option value="aeropress">AeroPress (Inverted)</option>
                  <option value="cold_brew">Cold Brew</option>
                </optgroup>
                <optgroup label="Pressure">
                  <option value="espresso">Espresso</option>
                  <option value="moka_pot">Moka Pot</option>
                  <option value="drip">Drip Machine</option>
                </optgroup>
              </select>
            </div>
            <input type="number" bind:value={surveyTemp} placeholder="Temp (°F)"
              class="border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
            <input type="number" bind:value={surveyDose} placeholder="Dose (g)"
              class="border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
            <input type="number" bind:value={surveyWater} placeholder="Water (g)"
              class="border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 col-span-2" />
          </div>
        </div>

        <button
          class="w-full border-2 border-dashed border-neutral-300 rounded-xl p-8 text-center bg-neutral-50 cursor-pointer hover:border-amber-500 hover:bg-amber-50/30 transition-all"
          onclick={() => fileInput.click()}
        >
          {#if uploadedImage}
            <div class="space-y-3">
              <img src={uploadedImage} alt="Uploaded grounds" class="w-full h-48 object-contain rounded-lg" />
              <p class="text-sm text-neutral-600">Tap to upload a different photo</p>
            </div>
          {:else}
            <div class="space-y-3">
              <div class="flex justify-center">
                <div class="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center">
                  <Camera class="w-8 h-8 text-amber-700" />
                </div>
              </div>
              <div>
                <p class="text-neutral-700 mb-1 font-medium">Upload a photo of your grounds</p>
                <p class="text-sm text-neutral-500">JPG, PNG, HEIC up to 10MB</p>
              </div>
            </div>
          {/if}
        </button>
        <input bind:this={fileInput} type="file" accept="image/*" onchange={handleFileChange} class="hidden" />

        {#if !uploadedImage}
          <div class="flex gap-2">
            <button onclick={() => fileInput.click()} class="flex-1 flex items-center justify-center gap-2 bg-amber-700 hover:bg-amber-800 text-white py-2.5 px-4 rounded-xl text-sm font-semibold transition-colors">
              <Upload class="w-4 h-4" /> Choose Photo
            </button>
            <button onclick={() => showCamera = true} class="flex-1 flex items-center justify-center gap-2 border border-neutral-300 text-neutral-700 py-2.5 px-4 rounded-xl text-sm font-medium hover:bg-neutral-50 transition-colors">
              <Camera class="w-4 h-4" /> Take Photo
            </button>
          </div>
        {/if}
      </div>
    {/if}

    <!-- Step 2: Analyzing -->
    {#if step === 'analyzing'}
      <div class="p-8 bg-white border border-neutral-200 rounded-xl">
        <div class="space-y-4 text-center">
          <div class="flex justify-center">
            <svg width="80" height="100" viewBox="0 0 80 100" fill="none" xmlns="http://www.w3.org/2000/svg">
              <!-- Grinder body -->
              <rect x="15" y="35" width="50" height="45" rx="4" fill="#92400e" stroke="#6b3410" stroke-width="2"/>
              <!-- Hopper (top funnel) -->
              <path d="M20 35 L25 18 L55 18 L60 35" fill="#a8571e" stroke="#6b3410" stroke-width="1.5"/>
              <!-- Drawer -->
              <rect x="20" y="72" width="40" height="12" rx="2" fill="#d4a574" stroke="#92400e" stroke-width="1.5"/>
              <circle cx="40" cy="78" r="2" fill="#6b3410"/>
              <!-- Grinder top plate -->
              <rect x="18" y="32" width="44" height="6" rx="2" fill="#b8651c" stroke="#6b3410" stroke-width="1"/>
              <!-- Crank arm (rotating) -->
              <g style="transform-origin: 40px 35px; animation: grind-spin 1.2s linear infinite;">
                <line x1="40" y1="35" x2="68" y2="25" stroke="#4a2c0a" stroke-width="3" stroke-linecap="round"/>
                <circle cx="68" cy="25" r="5" fill="#d97706" stroke="#92400e" stroke-width="1.5"/>
              </g>
              <!-- Center bolt -->
              <circle cx="40" cy="35" r="3.5" fill="#6b3410" stroke="#4a2c0a" stroke-width="1"/>
              <!-- Coffee particles falling -->
              <circle cx="32" cy="88" r="1.5" fill="#4a2c0a" style="animation: fall 0.8s ease-in infinite;"/>
              <circle cx="40" cy="90" r="1" fill="#6b3410" style="animation: fall 1s ease-in 0.3s infinite;"/>
              <circle cx="48" cy="87" r="1.5" fill="#4a2c0a" style="animation: fall 0.9s ease-in 0.6s infinite;"/>
            </svg>
          </div>
          <div>
            <p class="text-neutral-800 font-medium">Analyzing your grind<span class="analyzing-dots"></span></p>
            <p class="text-sm text-neutral-500 mt-1">Detecting particles and measuring sizes</p>
          </div>
        </div>
      </div>

      <style>
        @keyframes grind-spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @keyframes fall {
          0% { opacity: 1; transform: translateY(0); }
          100% { opacity: 0; transform: translateY(8px); }
        }
        .analyzing-dots::after {
          content: '';
          animation: dots 1.5s steps(4, end) infinite;
        }
        @keyframes dots {
          0% { content: ''; }
          25% { content: '.'; }
          50% { content: '..'; }
          75% { content: '...'; }
        }
      </style>
    {/if}

    <!-- Step 3: PSD Results -->
    {#if step === 'results' && psdResult}
      <!-- Quality warnings shown directly on results -->
      {#if qualityWarnings.length > 0}
        <div class="p-4 rounded-xl bg-amber-50 border border-amber-200 space-y-2">
          <div class="flex items-center gap-2">
            <AlertCircle class="w-4 h-4 text-amber-600 flex-shrink-0" />
            <span class="text-sm font-semibold text-amber-900">Accuracy Notes</span>
          </div>
          {#each qualityWarnings as warning}
            <div class="flex items-start gap-2 text-sm">
              <span class="text-amber-500 mt-0.5">•</span>
              <div>
                <span class="font-medium text-amber-900">{warning.message}</span>
                <span class="text-amber-700"> — {warning.tip}</span>
              </div>
            </div>
          {/each}
        </div>
      {/if}

      <GrindAnalysisResult psd={psdResult} classificationMessage={classificationMessage} grindCategory={grindCategory} />

      <!-- Detection Stats (expandable) -->
      {#if analysisMetadata}
        <button onclick={() => showDetectionStats = !showDetectionStats}
          class="w-full flex items-center justify-between p-3 rounded-xl text-sm bg-neutral-50 border border-neutral-200 hover:bg-neutral-100 transition-colors">
          <span class="text-neutral-600 font-medium">Detection Details</span>
          <ChevronDown class="w-4 h-4 text-neutral-400 transition-transform {showDetectionStats ? 'rotate-180' : ''}" />
        </button>
        {#if showDetectionStats}
          <div class="grid grid-cols-2 gap-2 text-sm">
            <!-- Particles -->
            <button class="p-3 bg-neutral-50 rounded-lg border border-neutral-100 text-left relative group"
              onclick={(e) => { const el = e.currentTarget.querySelector('.stat-tip'); if(el) el.classList.toggle('hidden'); }}>
              <div class="flex items-center gap-1 text-neutral-500 text-xs">Particles <Info class="w-3 h-3" /></div>
              <div class="font-semibold text-neutral-800">{psdResult.n_particles}</div>
              <div class="stat-tip hidden absolute z-10 left-0 right-0 top-full mt-1 p-2.5 bg-neutral-800 text-white text-xs rounded-lg shadow-lg" style="min-width: 200px;">
                Number of individual coffee particles measured. <strong>50+</strong> gives reliable results. Below 15 is unreliable — spread more grounds on the paper.
              </div>
            </button>
            <!-- Clumps -->
            <button class="p-3 bg-neutral-50 rounded-lg border border-neutral-100 text-left relative"
              onclick={(e) => { const el = e.currentTarget.querySelector('.stat-tip'); if(el) el.classList.toggle('hidden'); }}>
              <div class="flex items-center gap-1 text-neutral-500 text-xs">Clumps <Info class="w-3 h-3" /></div>
              <div class="font-semibold text-neutral-800">{analysisMetadata.n_clumps} ({(analysisMetadata.clump_ratio * 100).toFixed(0)}%)</div>
              <div class="stat-tip hidden absolute z-10 left-0 right-0 top-full mt-1 p-2.5 bg-neutral-800 text-white text-xs rounded-lg shadow-lg" style="min-width: 200px;">
                Clumps are particles stuck together. <strong>Under 20%</strong> is ideal. High clumping makes particles look larger than they are. Break up clumps before photographing.
              </div>
            </button>
            <!-- Silverskin -->
            <button class="p-3 bg-neutral-50 rounded-lg border border-neutral-100 text-left relative"
              onclick={(e) => { const el = e.currentTarget.querySelector('.stat-tip'); if(el) el.classList.toggle('hidden'); }}>
              <div class="flex items-center gap-1 text-neutral-500 text-xs">Silverskin <Info class="w-3 h-3" /></div>
              <div class="font-semibold text-neutral-800">{analysisMetadata.n_silverskin}</div>
              <div class="stat-tip hidden absolute z-10 left-0 right-0 top-full mt-1 p-2.5 bg-neutral-800 text-white text-xs rounded-lg shadow-lg" style="min-width: 200px;">
                Thin papery chaff from the coffee bean. These are <strong>excluded</strong> from size measurements so they don't skew your results.
              </div>
            </button>
            <!-- Calibration -->
            <button class="p-3 bg-neutral-50 rounded-lg border border-neutral-100 text-left relative"
              onclick={(e) => { const el = e.currentTarget.querySelector('.stat-tip'); if(el) el.classList.toggle('hidden'); }}>
              <div class="flex items-center gap-1 text-neutral-500 text-xs">Calibration <Info class="w-3 h-3" /></div>
              <div class="font-semibold text-neutral-800">{analysisMetadata.scale_px_per_mm.toFixed(1)} px/mm</div>
              <div class="stat-tip hidden absolute z-10 right-0 top-full mt-1 p-2.5 bg-neutral-800 text-white text-xs rounded-lg shadow-lg" style="min-width: 240px;">
                How many pixels = 1mm, based on the quarter. <strong>Normal range: 15–35.</strong>
                {#if analysisMetadata.scale_px_per_mm < 15}
                  <br/><br/>⚠️ <strong>Yours is low ({analysisMetadata.scale_px_per_mm.toFixed(1)})</strong> — the quarter may be partially visible or the photo was taken from too far away. Move closer and make sure the full quarter is in frame.
                {:else if analysisMetadata.scale_px_per_mm > 35}
                  <br/><br/>⚠️ <strong>Yours is high ({analysisMetadata.scale_px_per_mm.toFixed(1)})</strong> — the photo was taken very close. This is fine for accuracy but fewer particles may be in frame.
                {:else}
                  <br/><br/>✅ <strong>Yours is in the ideal range</strong> — the quarter was detected well.
                {/if}
              </div>
            </button>
          </div>
        {/if}
      {/if}

      <button
        onclick={startFeedback}
        class="w-full flex items-center justify-center gap-2 bg-amber-700 hover:bg-amber-800 text-white py-3 px-4 rounded-xl text-sm font-semibold transition-colors"
      >
        Log Brew & Get Advice <ChevronRight class="w-4 h-4" />
      </button>

      <div class="flex gap-2">
        <button onclick={() => { skipLog = false; startOver(); }}
          class="flex-1 flex items-center justify-center gap-1.5 border border-neutral-300 text-neutral-700 py-2.5 px-4 rounded-xl text-sm font-medium hover:bg-neutral-50 transition-colors">
          📓 Log & New Analysis
        </button>
        <button onclick={() => { skipLog = true; startOver(); }}
          class="flex-1 flex items-center justify-center gap-1.5 border border-red-200 text-red-600 py-2.5 px-4 rounded-xl text-sm font-medium hover:bg-red-50 transition-colors">
          🚫 Don't Log
        </button>
      </div>
    {/if}

    <!-- Step 4: Brew Feedback -->
    {#if step === 'feedback' && psdResult}
      <BrewFeedbackForm d50={psdResult.D50} onSubmit={handleFeedbackSubmit}
        initialBrewMethod={surveyBrewMethod}
        initialTemp={surveyTemp}
        initialDose={surveyDose}
        initialWater={surveyWater}
      />

      <button onclick={() => step = 'results'} class="w-full text-center text-sm text-neutral-500 hover:text-neutral-700 transition-colors py-1">
        ← Back to results
      </button>
    {/if}

    <!-- Step 5: Recommendation -->
    {#if step === 'recommendation' && recommendation}
      <RecommendationResult result={recommendation} />

      <div class="flex gap-2">
        <button onclick={startFeedback} class="flex-1 border border-neutral-300 text-neutral-700 py-2.5 px-4 rounded-xl text-sm font-medium hover:bg-neutral-50 transition-colors">
          Try Again
        </button>
        <button onclick={startOver} class="flex-1 bg-amber-700 hover:bg-amber-800 text-white py-2.5 px-4 rounded-xl text-sm font-semibold transition-colors">
          New Analysis
        </button>
      </div>
    {/if}

    <!-- Grind Size Guide (always visible on upload) -->
    {#if step === 'upload'}
      <GrindSizeGuide />

      <div class="p-5 bg-gradient-to-br from-amber-700 to-amber-800 text-white rounded-xl">
        <h3 class="font-semibold mb-2">How It Works</h3>
        <ol class="text-sm text-amber-50 space-y-2 list-decimal pl-4">
          <li>Photograph your grounds with a US quarter for scale</li>
          <li>We measure every particle and calculate the distribution</li>
          <li>Brew your coffee, then tell us how it tasted</li>
          <li>Get a specific recommendation for your next brew</li>
        </ol>
      </div>
    {/if}
  </div>
</PageLayout>
