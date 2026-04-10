<script lang="ts">
  import PageLayout from '$lib/components/PageLayout.svelte';
  import GrindAnalysisResult from '$lib/components/GrindAnalysisResult.svelte';
  import GrindSizeGuide from '$lib/components/GrindSizeGuide.svelte';
  import { Camera, Upload, Info, ChevronRight } from 'lucide-svelte';

  let uploadedImage = $state<string | null>(null);
  let analyzing = $state(false);
  let showResult = $state(false);
  let fileInput: HTMLInputElement;

  function handleFileChange(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        uploadedImage = reader.result as string;
        analyzeGrind();
      };
      reader.readAsDataURL(file);
    }
  }

  function analyzeGrind() {
    analyzing = true;
    showResult = false;
    setTimeout(() => {
      analyzing = false;
      showResult = true;
    }, 2000);
  }
</script>

<PageLayout>
  <div class="space-y-6">
    <!-- Header -->
    <div class="text-center space-y-2">
      <h1 class="text-amber-900 text-3xl">TrueGrind</h1>
      <p class="text-neutral-600">Measure and optimize your coffee grind size</p>
    </div>

    <!-- Upload Card -->
    <div class="p-6 bg-white border border-neutral-200 rounded-lg space-y-4">
      <div class="flex items-start gap-2 text-sm text-neutral-600 bg-amber-50 p-3 rounded-lg">
        <Info class="w-5 h-5 text-amber-700 flex-shrink-0 mt-0.5" />
        <p>Take a clear photo of your coffee grounds on a white surface for best results.</p>
      </div>

      <button
        class="w-full border-2 border-dashed border-neutral-300 rounded-lg p-8 text-center bg-neutral-50 cursor-pointer hover:border-amber-500 transition-colors"
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
              <p class="text-neutral-700 mb-1">Upload a photo of your grounds</p>
              <p class="text-sm text-neutral-500">JPG, PNG up to 10MB</p>
            </div>
          </div>
        {/if}
      </button>
      <input bind:this={fileInput} type="file" accept="image/*" onchange={handleFileChange} class="hidden" />

      {#if !uploadedImage}
        <div class="flex gap-2">
          <button onclick={() => fileInput.click()} class="flex-1 flex items-center justify-center gap-2 bg-amber-700 hover:bg-amber-800 text-white py-2 px-4 rounded-lg text-sm font-medium transition-colors">
            <Upload class="w-4 h-4" /> Choose Photo
          </button>
          <button onclick={() => fileInput.click()} class="flex-1 flex items-center justify-center gap-2 border border-neutral-300 text-neutral-700 py-2 px-4 rounded-lg text-sm font-medium hover:bg-neutral-50 transition-colors">
            <Camera class="w-4 h-4" /> Take Photo
          </button>
        </div>
      {/if}
    </div>

    <!-- Analysis Progress -->
    {#if analyzing}
      <div class="p-6 bg-white border border-neutral-200 rounded-lg">
        <div class="space-y-3 text-center">
          <div class="flex justify-center">
            <div class="w-12 h-12 border-4 border-amber-700 border-t-transparent rounded-full animate-spin"></div>
          </div>
          <div>
            <p class="text-neutral-700">Analyzing grind size...</p>
            <p class="text-sm text-neutral-500">This may take a moment</p>
          </div>
        </div>
      </div>
    {/if}

    <!-- Analysis Result -->
    {#if showResult && uploadedImage}
      <GrindAnalysisResult />
    {/if}

    <!-- Grind Size Guide -->
    <GrindSizeGuide />

    <!-- Pro Tip -->
    <div class="p-6 bg-gradient-to-br from-amber-700 to-amber-800 text-white rounded-lg">
      <h3 class="font-semibold mb-2">Pro Tip</h3>
      <p class="text-sm text-amber-50 mb-3">
        Consistent grind size is more important than the exact size. Make sure your grinder produces uniform particles.
      </p>
      <button class="w-full flex items-center justify-center gap-2 bg-white/10 border border-white/20 text-white hover:bg-white/20 py-2 px-4 rounded-lg text-sm font-medium transition-colors">
        Learn More <ChevronRight class="w-4 h-4" />
      </button>
    </div>
  </div>
</PageLayout>
