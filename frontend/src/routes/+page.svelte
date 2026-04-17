<script lang="ts">
  import PageLayout from '$lib/components/PageLayout.svelte';
  import GrindAnalysisResult from '$lib/components/GrindAnalysisResult.svelte';
  import BrewFeedbackForm from '$lib/components/BrewFeedbackForm.svelte';
  import RecommendationResult from '$lib/components/RecommendationResult.svelte';
  import GrindSizeGuide from '$lib/components/GrindSizeGuide.svelte';
  import CameraViewfinder from '$lib/components/CameraViewfinder.svelte';
  import { Camera, Upload, Info, ChevronRight, AlertCircle, Wifi, WifiOff, ChevronDown } from 'lucide-svelte';
  import { analyzePhoto, getRecommendation, getLLMRecommendation, checkHealth, preflightCheck } from '$lib/api';
  import type { PsdResult, AnalyzeResponse, RecommendationResult as RecResult, PreflightResult } from '$lib/api';

  // ── State ─────────────────────────────────────────────

  type AppStep = 'upload' | 'preflight' | 'analyzing' | 'results' | 'feedback' | 'recommendation';

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
  let capturedTiltAngle = $state(0);
  let preflightResult = $state<PreflightResult | null>(null);

  async function handleCameraCapture(file: File, tiltAngleDeg: number) {
    showCamera = false;
    uploadedFile = file;
    uploadedImage = URL.createObjectURL(file);
    capturedTiltAngle = tiltAngleDeg;
    step = 'preflight';
    preflightResult = null;

    try {
      preflightResult = await preflightCheck(file);
      // Show calibration feedback for 2s, then auto-proceed
      setTimeout(() => {
        if (step === 'preflight') analyzeGrind();
      }, 2000);
    } catch {
      // If preflight fails, just proceed to analysis
      analyzeGrind();
    }
  }

  function skipPreflight() {
    if (step === 'preflight') analyzeGrind();
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
      capturedTiltAngle = 0;
      analyzeGrind();
    }
  }

  import type { QualityWarning } from '$lib/api';

  // Quality warnings from analysis
  let qualityWarnings = $state<QualityWarning[]>([]);
  let showWarningModal = $state(false);

  // Coffee trivia for the analyzing wait screen (~126 items)
  const COFFEE_TRIVIA: Array<{type: string; text?: string; question?: string; options?: string[]; answer?: number}> = [
    // ── Origins & History ──
    { type: 'fact', text: 'Coffee was discovered in Ethiopia around the 9th century — legend says a goat herder noticed his goats dancing after eating coffee cherries.' },
    { type: 'fact', text: 'The word "coffee" comes from the Arabic "qahwa," which became "kahve" in Turkish and "koffie" in Dutch.' },
    { type: 'fact', text: 'The first coffeehouse opened in Constantinople (Istanbul) in 1475.' },
    { type: 'fact', text: 'Coffee was banned in Mecca in 1511 because leaders believed it stimulated radical thinking.' },
    { type: 'fact', text: 'Brazil has been the world\'s largest coffee producer for over 150 years.' },
    { type: 'fact', text: 'The Boston Tea Party of 1773 made coffee the patriotic drink of choice in America.' },
    { type: 'fact', text: 'Italy\'s first coffee house opened in Venice in 1629 — espresso came much later in 1906.' },
    { type: 'fact', text: 'The Moka Pot was invented by Alfonso Bialetti in Italy in 1933.' },
    { type: 'fact', text: 'Instant coffee was invented by Satori Kato, a Japanese-American chemist, in 1901.' },
    { type: 'fact', text: 'The AeroPress was invented by Alan Adler — the same person who invented the Aerobie frisbee.' },
    { type: 'fact', text: 'Kaldi, the Ethiopian goat herder, is considered the legendary discoverer of coffee — around 850 AD.' },
    { type: 'fact', text: 'Coffee spread from Ethiopia to Yemen, where Sufi monks used it for late-night prayers.' },
    { type: 'fact', text: 'European coffeehouses in the 1600s were called "penny universities" — a penny bought a cup and access to intellectual conversation.' },

    // ── Science & Chemistry ──
    { type: 'fact', text: 'A coffee bean contains over 1,000 chemical compounds — more complex than wine.' },
    { type: 'fact', text: 'Caffeine is a natural insecticide — coffee plants evolved it to ward off pests.' },
    { type: 'fact', text: 'The Maillard reaction during roasting creates the brown color and complex flavors in coffee.' },
    { type: 'fact', text: 'Coffee extracts fastest in the first 30 seconds — that\'s why espresso shots are so short.' },
    { type: 'fact', text: 'Water makes up 98.5% of brewed coffee — water quality dramatically affects taste.' },
    { type: 'fact', text: 'Lighter roasts have more caffeine than dark roasts — roasting burns off caffeine.' },
    { type: 'fact', text: 'The ideal water temperature for brewing is 92–96°C (197–205°F) — just below boiling.' },
    { type: 'fact', text: 'Coffee grounds are about 28% soluble — the rest is cellulose fiber that stays in the filter.' },
    { type: 'fact', text: 'Chlorogenic acids in coffee break down during roasting, producing the acidity in lighter roasts.' },
    { type: 'fact', text: 'CO₂ produced during roasting can take 2–14 days to fully degas from whole beans.' },
    { type: 'fact', text: 'The "ideal" extraction yield is 18–22% — below is sour (under-extracted), above is bitter (over-extracted).' },
    { type: 'fact', text: 'Arabica coffee has 44 chromosomes — twice as many as Robusta\'s 22.' },
    { type: 'fact', text: 'A single espresso shot contains about 63mg of caffeine, while a standard drip cup has ~95mg.' },

    // ── Grind Science ──
    { type: 'fact', text: 'D50 means the diameter where 50% of particles are smaller — it\'s the "median" grind size.' },
    { type: 'fact', text: 'A US quarter is exactly 24.26mm in diameter — that\'s how TrueGrind calibrates your photo.' },
    { type: 'fact', text: 'Fines (<200µm) over-extract quickly and add bitterness. Boulders (>1200µm) under-extract.' },
    { type: 'fact', text: 'A uniform grind distribution is just as important as the D50 for a balanced cup.' },
    { type: 'fact', text: 'Burr grinders produce more uniform particles than blade grinders — blade grinders create lots of fines and boulders.' },
    { type: 'fact', text: 'Conical burrs tend to produce a bimodal distribution (two peaks), while flat burrs produce a more unimodal (single peak) distribution.' },
    { type: 'fact', text: 'Espresso grind is about 200–300µm — roughly the texture of powdered sugar.' },
    { type: 'fact', text: 'French press grind is about 800–1000µm — roughly the texture of coarse sea salt.' },
    { type: 'fact', text: 'Static cling causes fine particles to stick to the burrs — that\'s why some grinders have anti-static features.' },
    { type: 'fact', text: 'RDT (Ross Droplet Technique) adds a tiny spray of water to beans before grinding to reduce static and fines.' },
    { type: 'fact', text: 'Grind retention is coffee that stays trapped inside the grinder — single-dosing helps minimize it.' },
    { type: 'fact', text: 'The Weber EG-1 grinder has 83mm flat burrs — one of the largest in home grinders.' },
    { type: 'fact', text: 'Popcorning happens when beans bounce around in the hopper instead of feeding into the burrs — single-dosing eliminates this.' },
    { type: 'fact', text: 'Sieve analysis is the industry standard for measuring grind distribution — TrueGrind gives you a digital alternative.' },

    // ── Brew Methods ──
    { type: 'fact', text: 'The V60 was designed by Hario in 2005 — the 60° angle of the cone gives it its name.' },
    { type: 'fact', text: 'James Hoffmann\'s V60 technique calls for a 15:1 ratio and a 3:30 total brew time.' },
    { type: 'fact', text: 'The Chemex was invented in 1941 by Peter Schlumbohm, a German chemist.' },
    { type: 'fact', text: 'Chemex filters are 20–30% thicker than standard paper filters — they remove more oils and fines.' },
    { type: 'fact', text: 'The Hario Switch combines pour-over and immersion — you start with a sealed valve for steeping, then open it for percolation.' },
    { type: 'fact', text: 'French press was patented by Italian designer Attilio Calimani in 1929 — not a French person.' },
    { type: 'fact', text: 'Cold brew concentrates can have 2–3x more caffeine per ounce than hot-brewed coffee.' },
    { type: 'fact', text: 'The AeroPress Championship has been held annually since 2008 — competitors tweak every variable for the perfect cup.' },
    { type: 'fact', text: 'Espresso machines generate about 9 bars of pressure — that\'s 130 PSI forcing water through the puck.' },
    { type: 'fact', text: 'The Kalita Wave uses a flat-bottom bed — this promotes more even extraction than conical drippers.' },
    { type: 'fact', text: 'Turkish coffee uses the finest grind of any method — almost powder — and is boiled directly in a cezve.' },
    { type: 'fact', text: 'Siphon (vacuum) brewers heat water in a lower chamber, forcing it up into the grounds — cooling creates a vacuum to pull the brew back down.' },
    { type: 'fact', text: 'The "bypass" technique adds hot water after brewing to adjust strength without changing extraction.' },
    { type: 'fact', text: 'Pour-over typically uses a 1:15 to 1:17 coffee-to-water ratio.' },

    // ── Roasting ──
    { type: 'fact', text: 'Coffee beans expand 50–100% in volume during roasting but lose about 15–20% of their weight.' },
    { type: 'fact', text: 'First crack during roasting happens around 196°C (385°F) — the bean structure fractures and releases steam.' },
    { type: 'fact', text: 'Second crack happens around 224°C (435°F) — the oils migrate to the surface, creating a shiny dark roast.' },
    { type: 'fact', text: 'Light roasts (City/City+) preserve more origin character — you can taste where the bean was grown.' },
    { type: 'fact', text: 'Dark roasts taste more like the roast itself — smoky and bittersweet — while origin flavors fade.' },
    { type: 'fact', text: 'Green (unroasted) coffee beans can be stored for over a year. Roasted beans are best within 2–4 weeks.' },
    { type: 'fact', text: 'The term "third wave coffee" was coined in 2002 — it treats coffee as an artisanal product, like wine.' },
    { type: 'fact', text: 'Omni roasts are designed to taste good in both espresso and filter — a modern trend in specialty roasting.' },

    // ── Origins & Varieties ──
    { type: 'fact', text: 'There are over 120 species of coffee, but Arabica and Robusta account for 99% of global production.' },
    { type: 'fact', text: 'Arabica grows best at 1,200–2,200m elevation — higher altitude = denser beans = more complex flavors.' },
    { type: 'fact', text: 'Robusta has about twice the caffeine of Arabica and is often used in instant coffee and espresso blends.' },
    { type: 'fact', text: 'Geisha (Gesha) coffee from Panama regularly sells for over $100/lb due to its jasmine-like floral notes.' },
    { type: 'fact', text: 'Ethiopian natural process coffees are dried with the cherry fruit intact — this adds fruity, wine-like flavors.' },
    { type: 'fact', text: 'Washed (wet) processing removes the cherry pulp before drying — producing a cleaner, brighter cup.' },
    { type: 'fact', text: 'Honey process leaves some of the mucilage on the bean during drying — creating a sweet, syrupy body.' },
    { type: 'fact', text: 'Colombia produces exclusively Arabica coffee and is the third-largest producer worldwide.' },
    { type: 'fact', text: 'Kona coffee from Hawaii is one of the most expensive in the world due to high labor costs and limited land.' },
    { type: 'fact', text: 'Vietnam is the world\'s second-largest coffee producer — mostly Robusta, used for Vietnamese iced coffee (cà phê sữa đá).' },
    { type: 'fact', text: 'Jamaican Blue Mountain coffee is prized for its mild, clean flavor — most of it is exported to Japan.' },
    { type: 'fact', text: 'The "coffee belt" spans roughly 25°N to 30°S latitude — the tropical zone where coffee grows best.' },

    // ── Business & Culture ──
    { type: 'fact', text: 'Coffee is the second most traded commodity in the world, after crude oil.' },
    { type: 'fact', text: 'A single coffee tree produces about 1 pound of roasted coffee per year.' },
    { type: 'fact', text: 'Finland consumes the most coffee per capita — about 12 kg per person per year.' },
    { type: 'fact', text: 'Americans consume about 400 million cups of coffee per day.' },
    { type: 'fact', text: 'The specialty coffee industry is worth over $50 billion globally.' },
    { type: 'fact', text: 'The word "barista" is Italian for "bartender" — it was adopted by coffee culture in the 1980s.' },
    { type: 'fact', text: 'Starbucks opens an average of 2 new stores per day worldwide.' },
    { type: 'fact', text: 'The most expensive coffee in the world is Black Ivory — it costs over $500/lb and is processed through elephants.' },
    { type: 'fact', text: 'Coffee beans are actually the pits of a cherry-like fruit called a "coffee cherry."' },

    // ── Latte Art & Milk ──
    { type: 'fact', text: 'Latte art became mainstream in the late 1980s — barista David Schomer pioneered the rosetta pattern.' },
    { type: 'fact', text: 'Milk steamed to 60–65°C has the best sweetness and texture for latte art.' },
    { type: 'fact', text: 'Oat milk froths better than most plant milks because of its higher protein and fat content.' },
    { type: 'fact', text: 'A "flat white" originated in Australia/New Zealand and uses microfoam — less frothy than a latte.' },

    // ── Health ──
    { type: 'fact', text: 'Moderate coffee consumption (3–5 cups/day) is associated with reduced risk of type 2 diabetes.' },
    { type: 'fact', text: 'Caffeine blocks adenosine receptors in the brain — that\'s what makes you feel alert.' },
    { type: 'fact', text: 'Coffee contains antioxidants — it\'s the #1 source of antioxidants in the Western diet.' },
    { type: 'fact', text: 'Caffeine reaches peak blood levels about 30–60 minutes after consumption.' },
    { type: 'fact', text: 'The half-life of caffeine is about 5 hours — that\'s why afternoon coffee can affect sleep.' },
    { type: 'fact', text: 'Decaf coffee still contains about 2–15mg of caffeine per cup.' },

    // ── TrueGrind Specific ──
    { type: 'fact', text: 'TrueGrind uses a YOLOv8 segmentation model trained on real coffee ground photos to detect individual particles.' },
    { type: 'fact', text: 'The "bloom" pour releases CO₂ trapped during roasting — fresh beans bloom more.' },
    { type: 'fact', text: 'The word "espresso" means "pressed out" in Italian — referring to water forced through the grounds.' },
    { type: 'fact', text: 'Cold brew uses coarse grounds steeped 12–24 hours — time replaces heat for extraction.' },
    { type: 'fact', text: 'A channeling shot occurs when water finds a path of least resistance through the puck — uneven extraction results.' },

    // ── Quizzes (interspersed) ──
    { type: 'quiz', question: 'Which grind size is coarser?', options: ['Espresso', 'French Press'], answer: 1 },
    { type: 'quiz', question: 'What does a sour-tasting brew usually mean?', options: ['Over-extracted', 'Under-extracted'], answer: 1 },
    { type: 'quiz', question: 'Which brew method uses the finest grind?', options: ['Chemex', 'Espresso', 'French Press'], answer: 1 },
    { type: 'quiz', question: 'What\'s the ideal extraction yield?', options: ['10–14%', '18–22%', '30–35%'], answer: 1 },
    { type: 'quiz', question: 'Which country consumes the most coffee per capita?', options: ['USA', 'Italy', 'Finland'], answer: 2 },
    { type: 'quiz', question: 'What temperature should milk be steamed to for latte art?', options: ['50°C', '60–65°C', '80°C'], answer: 1 },
    { type: 'quiz', question: 'What does RDT stand for in the context of grinding?', options: ['Rapid Dose Technique', 'Ross Droplet Technique', 'Reverse Distribution Test'], answer: 1 },
    { type: 'quiz', question: 'How many bars of pressure does an espresso machine use?', options: ['3 bars', '9 bars', '15 bars'], answer: 1 },
    { type: 'quiz', question: 'Which processing method dries coffee with the cherry fruit still on?', options: ['Washed', 'Natural', 'Honey'], answer: 1 },
    { type: 'quiz', question: 'What is "first crack" in roasting?', options: ['When the bag opens', 'When the bean structure fractures at ~196°C', 'When the roaster door opens'], answer: 1 },
    { type: 'quiz', question: 'Which has more caffeine?', options: ['Light roast', 'Dark roast'], answer: 0 },
    { type: 'quiz', question: 'What\'s the coffee-to-water ratio for most pour-overs?', options: ['1:8', '1:15', '1:25'], answer: 1 },
    { type: 'quiz', question: 'Arabica or Robusta — which has more caffeine?', options: ['Arabica', 'Robusta'], answer: 1 },
    { type: 'quiz', question: 'What year was the V60 designed?', options: ['1985', '2005', '2015'], answer: 1 },
    { type: 'quiz', question: 'What is the "coffee belt"?', options: ['A fashion brand', 'The tropical zone where coffee grows (25°N–30°S)', 'A conveyor belt in coffee factories'], answer: 1 },
    { type: 'quiz', question: 'How long can green (unroasted) coffee beans be stored?', options: ['2 weeks', '3 months', 'Over a year'], answer: 2 },
    { type: 'quiz', question: 'What makes Geisha coffee special?', options: ['It\'s grown in Japan', 'Its jasmine-like floral notes', 'It has no caffeine'], answer: 1 },
    { type: 'quiz', question: 'What does "omni roast" mean?', options: ['Roasted at every temperature', 'Designed to taste good in both espresso and filter', 'Only sold online'], answer: 1 },
  ];
  let triviaIndex = $state(0);
  let triviaFade = $state(true);
  let triviaInterval: ReturnType<typeof setInterval> | null = null;
  let quizAnswer = $state<number | null>(null);

  function startTrivia() {
    // Shuffle trivia so quizzes are interspersed with facts
    for (let i = COFFEE_TRIVIA.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [COFFEE_TRIVIA[i], COFFEE_TRIVIA[j]] = [COFFEE_TRIVIA[j], COFFEE_TRIVIA[i]];
    }
    triviaIndex = 0;
    triviaFade = true;
    quizAnswer = null;
    triviaInterval = setInterval(() => {
      triviaFade = false;
      setTimeout(() => {
        triviaIndex = (triviaIndex + 1) % COFFEE_TRIVIA.length;
        quizAnswer = null;
        triviaFade = true;
      }, 300);
    }, 6000);
  }

  function stopTrivia() {
    if (triviaInterval) { clearInterval(triviaInterval); triviaInterval = null; }
  }

  async function analyzeGrind() {
    if (!uploadedFile) return;
    step = 'analyzing';
    startTrivia();
    errorMessage = null;
    qualityWarnings = [];

    try {
      const result = await analyzePhoto(uploadedFile, surveyBrewMethod, capturedTiltAngle);
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

      stopTrivia();
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
      stopTrivia();
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
      const result = await getLLMRecommendation(payload);
      recommendation = result.recommendation;
      step = 'recommendation';
    } catch (err: any) {
      errorMessage = err.message || 'Recommendation failed';
    }
  }

  const JOURNAL_KEY = 'truegrind-journal';

  const BREW_METHOD_LABELS: Record<string, string> = {
    pour_over: 'V60', french_press: 'French Press',
    aeropress: 'AeroPress', drip: 'Drip Machine', moka_pot: 'Moka Pot',
    espresso: 'Espresso', chemex: 'Chemex', cold_brew: 'Cold Brew',
    hario_switch: 'Hario Switch', kalita_wave: 'Kalita Wave',
    aeropress_inverted: 'AeroPress (Inverted)',
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
                  <option value="kalita_wave">Kalita Wave</option>
                  <option value="hario_switch">Hario Switch</option>
                </optgroup>
                <optgroup label="Immersion">
                  <option value="french_press">French Press</option>
                  <option value="aeropress">AeroPress</option>
                  <option value="aeropress_inverted">AeroPress (Inverted)</option>
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
        <input bind:this={fileInput} type="file" accept="image/*,.heic,.heif,image/heic,image/heif" onchange={handleFileChange} class="hidden" />

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

    <!-- Preflight: calibration check after camera capture -->
    {#if step === 'preflight'}
      <div class="p-6 bg-white border border-neutral-200 rounded-xl text-center space-y-4">
        {#if uploadedImage}
          <img src={uploadedImage} alt="Captured" class="w-full max-h-48 object-contain rounded-lg" />
        {/if}

        {#if preflightResult === null}
          <div class="flex items-center justify-center gap-2 text-neutral-500">
            <div class="w-4 h-4 border-2 border-amber-600 border-t-transparent rounded-full animate-spin"></div>
            <span class="text-sm">Checking calibration…</span>
          </div>
        {:else}
          <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium
            {preflightResult.quality === 'good' ? 'bg-green-100 text-green-800' :
             preflightResult.quality === 'ok' ? 'bg-amber-100 text-amber-800' :
             'bg-red-100 text-red-800'}">
            <span class="w-2.5 h-2.5 rounded-full
              {preflightResult.quality === 'good' ? 'bg-green-500' :
               preflightResult.quality === 'ok' ? 'bg-amber-500' :
               'bg-red-500'}"></span>
            {preflightResult.message}
          </div>

          {#if preflightResult.quality === 'too_far' || preflightResult.quality === 'too_close' || preflightResult.quality === 'not_found'}
            <div class="flex gap-3 justify-center">
              <button onclick={() => { step = 'upload'; showCamera = true; }} class="px-4 py-2 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700 transition-colors">
                Retake Photo
              </button>
              <button onclick={skipPreflight} class="px-4 py-2 bg-neutral-200 text-neutral-700 rounded-lg text-sm font-medium hover:bg-neutral-300 transition-colors">
                Analyze Anyway
              </button>
            </div>
          {:else}
            <p class="text-xs text-neutral-400">Proceeding to analysis…</p>
          {/if}
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

          <!-- Coffee Trivia -->
          <div class="mt-6 pt-4 border-t border-neutral-100">
            <div class="transition-opacity duration-300 {triviaFade ? 'opacity-100' : 'opacity-0'}">
              {#if COFFEE_TRIVIA[triviaIndex].type === 'fact'}
                <div class="flex items-start gap-2 text-left px-2">
                  <span class="text-amber-600 text-lg flex-shrink-0">☕</span>
                  <p class="text-sm text-neutral-600 italic">{COFFEE_TRIVIA[triviaIndex].text}</p>
                </div>
              {:else}
                <div class="text-left px-2 space-y-2">
                  <p class="text-sm font-medium text-amber-900">🧠 Quick Quiz</p>
                  <p class="text-sm text-neutral-700">{COFFEE_TRIVIA[triviaIndex].question}</p>
                  <div class="flex flex-wrap gap-2">
                    {#each COFFEE_TRIVIA[triviaIndex].options || [] as opt, i}
                      <button
                        onclick={() => quizAnswer = i}
                        disabled={quizAnswer !== null}
                        class="px-3 py-1.5 text-xs rounded-full border transition-all
                          {quizAnswer === null ? 'bg-amber-50 border-amber-200 text-amber-800 hover:bg-amber-100' :
                           i === COFFEE_TRIVIA[triviaIndex].answer ? 'bg-green-100 border-green-300 text-green-800' :
                           quizAnswer === i ? 'bg-red-100 border-red-300 text-red-800' :
                           'bg-neutral-100 border-neutral-200 text-neutral-500'}"
                      >{opt}</button>
                    {/each}
                  </div>
                  {#if quizAnswer !== null}
                    <p class="text-xs {quizAnswer === COFFEE_TRIVIA[triviaIndex].answer ? 'text-green-600' : 'text-red-500'}">
                      {quizAnswer === COFFEE_TRIVIA[triviaIndex].answer ? '✓ Correct!' : '✗ Not quite!'}
                    </p>
                  {/if}
                </div>
              {/if}
            </div>
            <div class="flex justify-center gap-1 mt-3">
              {#each Array(Math.min(COFFEE_TRIVIA.length, 5)) as _, i}
                <div class="w-1.5 h-1.5 rounded-full transition-colors {i === triviaIndex % 5 ? 'bg-amber-500' : 'bg-neutral-200'}"></div>
              {/each}
            </div>
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
