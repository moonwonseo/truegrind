<script lang="ts">
  import PageLayout from '$lib/components/PageLayout.svelte';
  import GrindAnalysisResult from '$lib/components/GrindAnalysisResult.svelte';
  import BrewFeedbackForm from '$lib/components/BrewFeedbackForm.svelte';
  import RecommendationResult from '$lib/components/RecommendationResult.svelte';
  import GrindSizeGuide from '$lib/components/GrindSizeGuide.svelte';
  import { Camera, Upload, Info, ChevronRight, AlertCircle, Wifi, WifiOff } from 'lucide-svelte';
  import { analyzePhoto, getRecommendation, checkHealth } from '$lib/api';
  import type { PsdResult, RecommendationResult as RecResult } from '$lib/api';

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

  // Recommendation
  let recommendation = $state<RecResult | null>(null);

  let fileInput: HTMLInputElement;
  let cameraInput: HTMLInputElement;

  // ── Health check on mount ─────────────────────────────

  $effect(() => {
    checkHealth().then(ok => { apiConnected = ok; });
  });

  // ── Handlers ──────────────────────────────────────────

  /**
   * Convert any image (including HEIC/HEIF from iPhone) to JPEG via canvas.
   * The browser decodes HEIC natively; we re-export as JPEG for OpenCV.
   */
  async function convertToJpeg(file: File): Promise<File> {
    if (file.type === 'image/jpeg' || file.type === 'image/png') {
      return file;
    }

    return new Promise((resolve, reject) => {
      const img = new Image();
      const url = URL.createObjectURL(file);

      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        const ctx = canvas.getContext('2d')!;
        ctx.drawImage(img, 0, 0);
        URL.revokeObjectURL(url);

        canvas.toBlob(
          (blob) => {
            if (blob) {
              const jpegFile = new File(
                [blob],
                file.name.replace(/\.[^.]+$/, '.jpg'),
                { type: 'image/jpeg' }
              );
              resolve(jpegFile);
            } else {
              reject(new Error('Failed to convert image'));
            }
          },
          'image/jpeg',
          0.92
        );
      };

      img.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error('Could not load image — format may not be supported'));
      };

      img.src = url;
    });
  }

  async function handleFileChange(event: Event) {
    const rawFile = (event.target as HTMLInputElement).files?.[0];
    if (rawFile) {
      try {
        const file = await convertToJpeg(rawFile);
        uploadedFile = file;
        const reader = new FileReader();
        reader.onloadend = () => {
          uploadedImage = reader.result as string;
          analyzeGrind();
        };
        reader.readAsDataURL(file);
      } catch (err: any) {
        errorMessage = err.message || 'Could not process image';
      }
    }
  }

  async function analyzeGrind() {
    if (!uploadedFile) return;
    step = 'analyzing';
    errorMessage = null;

    try {
      const result = await analyzePhoto(uploadedFile);
      psdResult = result.psd;
      classificationMessage = result.classification_message;
      grindCategory = result.grind_category;
      step = 'results';
    } catch (err: any) {
      errorMessage = err.message || 'Analysis failed';
      step = 'upload';
    }
  }

  function startFeedback() {
    step = 'feedback';
  }

  async function handleFeedbackSubmit(payload: any) {
    errorMessage = null;
    try {
      const result = await getRecommendation(payload);
      recommendation = result.recommendation;
      step = 'recommendation';
    } catch (err: any) {
      errorMessage = err.message || 'Recommendation failed';
    }
  }

  function startOver() {
    step = 'upload';
    uploadedImage = null;
    uploadedFile = null;
    psdResult = null;
    recommendation = null;
    errorMessage = null;
    classificationMessage = '';
    grindCategory = '';
  }
</script>

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

    <!-- Step 1: Upload -->
    {#if step === 'upload'}
      <div class="p-5 bg-white border border-neutral-200 rounded-xl space-y-4">
        <div class="flex items-start gap-2 text-sm text-neutral-600 bg-amber-50 p-3 rounded-lg">
          <Info class="w-5 h-5 text-amber-700 flex-shrink-0 mt-0.5" />
          <p>Spread your grounds on white paper with a US quarter for scale. Take a clear, well-lit photo.</p>
        </div>

        <button
          class="w-full border-2 border-dashed border-neutral-300 rounded-xl p-8 text-center bg-neutral-50 cursor-pointer hover:border-amber-500 hover:bg-amber-50/30 transition-all"
          onclick={() => fileInput.click()}
        >
          {#if uploadedImage}
            <div class="space-y-3">
              <img src={uploadedImage} alt="Uploaded grounds" class="w-full h-48 object-cover rounded-lg" />
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
        <input bind:this={cameraInput} type="file" accept="image/*" capture="environment" onchange={handleFileChange} class="hidden" />

        {#if !uploadedImage}
          <div class="flex gap-2">
            <button onclick={() => fileInput.click()} class="flex-1 flex items-center justify-center gap-2 bg-amber-700 hover:bg-amber-800 text-white py-2.5 px-4 rounded-xl text-sm font-semibold transition-colors">
              <Upload class="w-4 h-4" /> Choose Photo
            </button>
            <button onclick={() => cameraInput.click()} class="flex-1 flex items-center justify-center gap-2 border border-neutral-300 text-neutral-700 py-2.5 px-4 rounded-xl text-sm font-medium hover:bg-neutral-50 transition-colors">
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
            <div class="w-14 h-14 border-4 border-amber-700 border-t-transparent rounded-full animate-spin"></div>
          </div>
          <div>
            <p class="text-neutral-800 font-medium">Analyzing your grind...</p>
            <p class="text-sm text-neutral-500 mt-1">Detecting particles and measuring sizes</p>
          </div>
        </div>
      </div>
    {/if}

    <!-- Step 3: PSD Results -->
    {#if step === 'results' && psdResult}
      <GrindAnalysisResult psd={psdResult} classificationMessage={classificationMessage} grindCategory={grindCategory} />

      <button
        onclick={startFeedback}
        class="w-full flex items-center justify-center gap-2 bg-amber-700 hover:bg-amber-800 text-white py-3 px-4 rounded-xl text-sm font-semibold transition-colors"
      >
        Log Brew & Get Advice <ChevronRight class="w-4 h-4" />
      </button>

      <button onclick={startOver} class="w-full text-center text-sm text-neutral-500 hover:text-neutral-700 transition-colors py-1">
        Analyze a different photo
      </button>
    {/if}

    <!-- Step 4: Brew Feedback -->
    {#if step === 'feedback' && psdResult}
      <BrewFeedbackForm d50={psdResult.D50} onSubmit={handleFeedbackSubmit} />

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
