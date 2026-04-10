<script lang="ts">
  const grindSizes = [
    { name: 'Extra Coarse', size: '1000-1400μm', description: 'Cold brew', color: 'bg-amber-900' },
    { name: 'Coarse', size: '700-1000μm', description: 'French press', color: 'bg-amber-800' },
    { name: 'Medium-Coarse', size: '600-700μm', description: 'Chemex, Clever', color: 'bg-amber-700' },
    { name: 'Medium', size: '500-600μm', description: 'Pour over, Drip', color: 'bg-amber-600' },
    { name: 'Medium-Fine', size: '400-500μm', description: 'AeroPress, Siphon', color: 'bg-amber-500' },
    { name: 'Fine', size: '300-400μm', description: 'Espresso, Moka pot', color: 'bg-amber-400' },
    { name: 'Extra Fine', size: '200-300μm', description: 'Turkish coffee', color: 'bg-amber-300' },
  ];
</script>

<div class="p-6 bg-white border border-neutral-200 rounded-lg">
  <h3 class="font-semibold text-amber-900 mb-4">Grind Size Reference Guide</h3>
  <div class="space-y-3">
    {#each grindSizes as grind, i}
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 rounded-full {grind.color} flex-shrink-0"></div>
        <div class="flex-1">
          <div class="flex items-baseline justify-between mb-0.5">
            <span class="font-semibold text-sm text-amber-900">{grind.name}</span>
            <span class="text-xs text-neutral-500">{grind.size}</span>
          </div>
          <p class="text-sm text-neutral-600">{grind.description}</p>
        </div>
      </div>
      {#if i < grindSizes.length - 1}
        <hr class="border-neutral-100" />
      {/if}
    {/each}
  </div>
</div>
