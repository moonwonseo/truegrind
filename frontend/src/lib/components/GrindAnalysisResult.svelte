<script lang="ts">
  import { TrendingUp, TrendingDown, AlertCircle, CheckCircle, ChevronRight } from 'lucide-svelte';

  const analysis = {
    averageSize: 650,
    sizeCategory: 'Medium-Fine',
    distribution: { uniform: 78, fines: 12, boulders: 10 },
    recommendation: {
      message: 'Your grind is well-suited for pour-over brewing. Consider going slightly coarser for better clarity.',
      adjustment: '+2 clicks on your Baratza Encore',
    },
    brewMethods: [
      { name: 'Pour Over', suitability: 92 },
      { name: 'Chemex', suitability: 88 },
      { name: 'AeroPress', suitability: 75 },
      { name: 'Espresso', suitability: 35 },
    ],
  };
</script>

<div class="space-y-4">
  <!-- Main Result -->
  <div class="p-6 bg-white border border-neutral-200 rounded-lg space-y-4">
    <div class="flex items-start justify-between">
      <div>
        <h3 class="text-lg font-semibold text-amber-900">Analysis Complete</h3>
        <p class="text-sm text-neutral-600">Based on visual measurement</p>
      </div>
      <span class="inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full bg-green-100 text-green-800">
        <CheckCircle class="w-3 h-3" /> Good
      </span>
    </div>
    <div class="bg-amber-50 rounded-lg p-4 border border-amber-200">
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm text-neutral-600">Average Size</span>
        <span class="font-semibold text-amber-900">{analysis.averageSize}μm</span>
      </div>
      <div class="flex items-center justify-between">
        <span class="text-sm text-neutral-600">Category</span>
        <span class="font-semibold text-amber-900">{analysis.sizeCategory}</span>
      </div>
    </div>
  </div>

  <!-- Distribution -->
  <div class="p-6 bg-white border border-neutral-200 rounded-lg">
    <h4 class="font-semibold text-amber-900 mb-4">Particle Distribution</h4>
    <div class="space-y-3">
      {#each [['Uniform Particles', analysis.distribution.uniform], ['Fines (<200μm)', analysis.distribution.fines], ['Boulders (>1000μm)', analysis.distribution.boulders]] as [label, value]}
        <div>
          <div class="flex justify-between text-sm mb-1">
            <span class="text-neutral-600">{label}</span>
            <span class="font-semibold text-amber-900">{value}%</span>
          </div>
          <div class="h-2 bg-neutral-100 rounded-full overflow-hidden">
            <div class="h-full bg-amber-500 rounded-full" style="width: {value}%"></div>
          </div>
        </div>
      {/each}
    </div>
  </div>

  <!-- Recommendation -->
  <div class="p-6 bg-white border border-neutral-200 rounded-lg">
    <div class="flex items-start gap-3">
      <div class="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
        <AlertCircle class="w-5 h-5 text-blue-700" />
      </div>
      <div class="flex-1">
        <h4 class="font-semibold text-amber-900 mb-1">Recommendation</h4>
        <p class="text-sm text-neutral-600 mb-3">{analysis.recommendation.message}</p>
        <div class="bg-neutral-50 rounded-lg p-3 border border-neutral-200">
          <p class="text-sm font-semibold text-amber-900">Suggested Adjustment</p>
          <p class="text-sm text-neutral-700">{analysis.recommendation.adjustment}</p>
        </div>
      </div>
    </div>
  </div>

  <!-- Brew Method Compatibility -->
  <div class="p-6 bg-white border border-neutral-200 rounded-lg">
    <h4 class="font-semibold text-amber-900 mb-4">Brewing Method Compatibility</h4>
    <div class="space-y-3">
      {#each analysis.brewMethods as method}
        <div>
          <div class="flex justify-between text-sm mb-1">
            <span class="text-neutral-700">{method.name}</span>
            <div class="flex items-center gap-1">
              <span class="font-semibold text-amber-900">{method.suitability}%</span>
              {#if method.suitability >= 80}
                <TrendingUp class="w-4 h-4 text-green-600" />
              {:else}
                <TrendingDown class="w-4 h-4 text-neutral-400" />
              {/if}
            </div>
          </div>
          <div class="h-2 bg-neutral-100 rounded-full overflow-hidden">
            <div class="h-full bg-amber-500 rounded-full" style="width: {method.suitability}%"></div>
          </div>
        </div>
      {/each}
    </div>
  </div>

  <!-- Actions -->
  <div class="flex gap-3">
    <button class="flex-1 flex items-center justify-center gap-2 bg-amber-700 hover:bg-amber-800 text-white py-2 px-4 rounded-lg text-sm font-medium transition-colors">
      Save to Journal <ChevronRight class="w-4 h-4" />
    </button>
    <button class="flex-1 border border-neutral-300 text-neutral-700 py-2 px-4 rounded-lg text-sm font-medium hover:bg-neutral-50 transition-colors">
      Share Results
    </button>
  </div>
</div>
