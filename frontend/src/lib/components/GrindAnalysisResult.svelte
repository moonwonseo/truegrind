<script lang="ts">
  import type { PsdResult } from '$lib/api';
  import { TrendingUp, TrendingDown, CheckCircle, AlertTriangle, Info } from 'lucide-svelte';

  let {
    psd,
    classificationMessage,
    grindCategory,
  }: {
    psd: PsdResult;
    classificationMessage: string;
    grindCategory: string;
  } = $props();

  function uniformityBadge(u: string): { text: string; class: string } {
    if (u === 'good') return { text: 'Good', class: 'bg-green-100 text-green-800' };
    if (u === 'moderate') return { text: 'Moderate', class: 'bg-yellow-100 text-yellow-800' };
    return { text: 'Poor', class: 'bg-red-100 text-red-800' };
  }

  function categoryLabel(cat: string): string {
    return cat.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  let badge = $derived(uniformityBadge(psd.uniformity));

  const distBars = $derived([
    { label: 'Fines (<200μm)', value: psd.fines_pct, color: 'bg-yellow-400' },
    { label: 'Uniform', value: psd.uniform_pct, color: 'bg-green-500' },
    { label: 'Boulders (>1000μm)', value: psd.boulders_pct, color: 'bg-red-400' },
  ]);
</script>

<div class="space-y-4">
  <!-- Classification Message -->
  <div class="p-5 bg-gradient-to-br from-amber-50 to-orange-50 border border-amber-200 rounded-xl">
    <div class="flex items-start gap-3">
      <div class="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
        <CheckCircle class="w-5 h-5 text-amber-700" />
      </div>
      <div>
        <h3 class="font-semibold text-amber-900 mb-0.5">Analysis Complete</h3>
        <p class="text-sm text-amber-800">{classificationMessage}</p>
      </div>
    </div>
  </div>

  <!-- Key Metrics -->
  <div class="p-5 bg-white border border-neutral-200 rounded-xl">
    <div class="grid grid-cols-3 gap-4 mb-4">
      <div class="text-center">
        <div class="text-2xl font-bold text-amber-900">{Math.round(psd.D50)}</div>
        <div class="text-xs text-neutral-500">D50 (μm)</div>
      </div>
      <div class="text-center">
        <div class="text-lg font-semibold text-neutral-700">{categoryLabel(grindCategory)}</div>
        <div class="text-xs text-neutral-500">Category</div>
      </div>
      <div class="text-center">
        <span class="inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full {badge.class}">
          {badge.text}
        </span>
        <div class="text-xs text-neutral-500 mt-1">Uniformity</div>
      </div>
    </div>

    <!-- D10 / D50 / D90 bar -->
    <div class="bg-neutral-50 rounded-lg p-3 border border-neutral-100">
      <div class="flex justify-between text-xs text-neutral-500 mb-1">
        <span>D10: {Math.round(psd.D10)}μm</span>
        <span class="font-semibold text-amber-900">D50: {Math.round(psd.D50)}μm</span>
        <span>D90: {Math.round(psd.D90)}μm</span>
      </div>
      <div class="h-3 bg-neutral-200 rounded-full overflow-hidden relative">
        <!-- D10-D90 range -->
        <div
          class="absolute h-full bg-amber-200 rounded-full"
          style="left: {Math.min(100, (psd.D10 / psd.D90) * 100)}%; width: {100 - Math.min(100, (psd.D10 / psd.D90) * 100)}%"
        ></div>
        <!-- D50 marker -->
        <div
          class="absolute h-full w-1 bg-amber-700 rounded-full"
          style="left: {Math.min(100, (psd.D50 / psd.D90) * 100)}%"
        ></div>
      </div>
      <div class="flex justify-between text-[10px] text-neutral-400 mt-1">
        <span>Fine</span>
        <span>Span: {psd.span.toFixed(2)}</span>
        <span>Coarse</span>
      </div>
    </div>
  </div>

  <!-- Distribution Breakdown -->
  <div class="p-5 bg-white border border-neutral-200 rounded-xl">
    <div class="flex items-center justify-between mb-3">
      <h4 class="font-semibold text-amber-900">Particle Distribution</h4>
      <span class="text-xs text-neutral-500">{psd.n_particles} particles</span>
    </div>
    <div class="space-y-3">
      {#each distBars as bar}
        <div>
          <div class="flex justify-between text-sm mb-1">
            <span class="text-neutral-600">{bar.label}</span>
            <span class="font-semibold text-neutral-800">{bar.value}%</span>
          </div>
          <div class="h-2.5 bg-neutral-100 rounded-full overflow-hidden">
            <div class="h-full {bar.color} rounded-full transition-all duration-500" style="width: {Math.max(bar.value, 1)}%"></div>
          </div>
        </div>
      {/each}
    </div>

    {#if psd.bimodal_flag}
      <div class="mt-3 flex items-start gap-2 text-sm text-red-700 bg-red-50 p-3 rounded-lg border border-red-200">
        <AlertTriangle class="w-4 h-4 flex-shrink-0 mt-0.5" />
        <p>Bimodal distribution detected — your grinder may need calibration or cleaning.</p>
      </div>
    {/if}
  </div>
</div>
