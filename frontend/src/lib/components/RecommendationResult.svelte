<script lang="ts">
  import type { RecommendationResult } from '$lib/api';
  import { ArrowDown, ArrowUp, Minus, AlertTriangle, CheckCircle, Wrench, Thermometer, Clock, Info } from 'lucide-svelte';

  let { result }: { result: RecommendationResult } = $props();

  let grind = $derived(result.grind_recommendation);
  let secondary = $derived(result.secondary_advice);
  let brew = $derived(result.brew_analysis);
  let dist = $derived(result.distribution);

  function modeColor(mode: string): string {
    if (mode === 'hold' || mode === 'secondary_variable') return 'border-green-200 bg-green-50';
    if (mode === 'primary_grind') return 'border-amber-200 bg-amber-50';
    if (mode === 'grinder_issue' || mode === 'poor_uniformity') return 'border-red-200 bg-red-50';
    if (mode === 'diagnose_evenness_first') return 'border-yellow-200 bg-yellow-50';
    return 'border-neutral-200 bg-white';
  }

  function modeIcon(mode: string) {
    if (mode === 'hold') return CheckCircle;
    if (mode === 'primary_grind') return grind.direction === 'finer' ? ArrowDown : ArrowUp;
    if (mode === 'grinder_issue') return Wrench;
    if (mode === 'poor_uniformity') return AlertTriangle;
    return Info;
  }

  function modeIconColor(mode: string): string {
    if (mode === 'hold') return 'text-green-600';
    if (mode === 'primary_grind') return 'text-amber-700';
    if (mode === 'grinder_issue' || mode === 'poor_uniformity') return 'text-red-600';
    return 'text-yellow-600';
  }

  function confidenceLabel(level: string): string {
    if (level === 'high') return '●●●';
    if (level === 'medium') return '●●○';
    return '●○○';
  }

  function confidenceColor(level: string): string {
    if (level === 'high') return 'text-green-600';
    if (level === 'medium') return 'text-amber-600';
    return 'text-red-500';
  }
</script>

<div class="space-y-4">
  <!-- Primary Recommendation -->
  <div class="p-5 border rounded-xl {modeColor(result.mode)}">
    <div class="flex items-start gap-3">
      <div class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 bg-white shadow-sm">
        <svelte:component this={modeIcon(result.mode)} class="w-5 h-5 {modeIconColor(result.mode)}" />
      </div>
      <div class="flex-1">
        <h4 class="font-semibold text-neutral-900 mb-1">
          {#if result.mode === 'primary_grind'}
            {grind.direction === 'finer' ? 'Grind Finer' : 'Grind Coarser'}
          {:else if result.mode === 'hold'}
            Keep This Setting
          {:else if result.mode === 'grinder_issue'}
            Grinder Check Needed
          {:else if result.mode === 'poor_uniformity'}
            Uniformity Issue
          {:else if result.mode === 'diagnose_evenness_first'}
            Technique Check
          {:else if result.mode === 'secondary_variable'}
            Adjust Brew Variables
          {:else}
            Recommendation
          {/if}
        </h4>
        <p class="text-sm text-neutral-700">{grind.message}</p>

        {#if result.mode === 'primary_grind' && grind.steps > 0}
          <div class="mt-3 flex items-center gap-3 bg-white rounded-lg p-3 border border-neutral-200">
            <div class="text-center">
              <div class="text-2xl font-bold text-amber-900">{grind.from_setting}</div>
              <div class="text-[10px] text-neutral-500 uppercase">Current</div>
            </div>
            <div class="flex-1 flex items-center justify-center">
              <div class="h-0.5 flex-1 bg-neutral-200"></div>
              <div class="mx-2 text-xs font-semibold text-amber-700">
                {grind.direction === 'finer' ? '←' : '→'} {grind.steps} {grind.steps === 1 ? 'step' : 'steps'}
              </div>
              <div class="h-0.5 flex-1 bg-neutral-200"></div>
            </div>
            <div class="text-center">
              <div class="text-2xl font-bold text-amber-700">{grind.to_setting}</div>
              <div class="text-[10px] text-neutral-500 uppercase">Target</div>
            </div>
          </div>
        {/if}
      </div>
    </div>
  </div>

  <!-- Secondary Advice -->
  {#if secondary.shown}
    <div class="p-4 bg-blue-50 border border-blue-200 rounded-xl">
      <div class="flex items-start gap-2">
        <div class="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 mt-0.5">
          {#if secondary.type === 'temperature'}
            <Thermometer class="w-3.5 h-3.5 text-blue-700" />
          {:else if secondary.type === 'grinder_maintenance'}
            <Wrench class="w-3.5 h-3.5 text-blue-700" />
          {:else}
            <Clock class="w-3.5 h-3.5 text-blue-700" />
          {/if}
        </div>
        <div>
          <h5 class="text-sm font-semibold text-blue-900">Also Consider</h5>
          <p class="text-sm text-blue-800 mt-0.5">{secondary.message}</p>
        </div>
      </div>
    </div>
  {/if}

  <!-- Brew Variable Issues -->
  {#if brew && brew.issues && brew.issues.length > 0}
    <div class="p-4 bg-yellow-50 border border-yellow-200 rounded-xl space-y-2">
      <h5 class="text-sm font-semibold text-yellow-900 flex items-center gap-1.5">
        <AlertTriangle class="w-3.5 h-3.5" /> Brew Variable Notes
      </h5>
      {#each brew.issues as issue}
        <p class="text-sm text-yellow-800 pl-5">• {issue}</p>
      {/each}
    </div>
  {/if}

  <!-- Parsed Tags + Confidence -->
  <div class="flex items-center justify-between px-1">
    <div class="flex flex-wrap gap-1.5">
      {#each result.parsed_tags as tag}
        <span class="text-xs border border-neutral-200 text-neutral-600 bg-white px-2 py-0.5 rounded-full">{tag}</span>
      {/each}
    </div>
    <div class="text-xs text-neutral-500 flex items-center gap-2">
      <span>Confidence: <span class="{confidenceColor(result.confidence.grind)}">{confidenceLabel(result.confidence.grind)}</span></span>
    </div>
  </div>
</div>
