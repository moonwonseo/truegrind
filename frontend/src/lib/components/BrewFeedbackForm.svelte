<script lang="ts">
  import GrinderDial from './GrinderDial.svelte';
  import { Clock, Thermometer, Droplets, Filter, Coffee, Send } from 'lucide-svelte';
  import { getSettings, inputTempToCelsius, inputWeightToGrams, displayTempUnit, displayWeightUnit, tempPlaceholder } from '$lib/settings.svelte';

  let {
    d50,
    onSubmit,
    initialBrewMethod = 'pour_over',
    initialTemp = '',
    initialDose = '',
    initialWater = '',
  }: {
    d50: number;
    onSubmit: (data: any) => void;
    initialBrewMethod?: string;
    initialTemp?: string;
    initialDose?: string;
    initialWater?: string;
  } = $props();

  let grindSetting = $state(5);
  let brewMethod = $state(initialBrewMethod);
  let waterTemp = $state(initialTemp);
  let extractionMin = $state('');
  let extractionSec = $state('');
  let filterType = $state('paper');
  let doseG = $state(initialDose);
  let waterG = $state(initialWater);
  let numPours = $state('');
  let tasteNotes = $state('');
  let selectedTags = $state<string[]>([]);
  let submitting = $state(false);

  let settings = $derived(getSettings());
  let tempUnit = $derived(displayTempUnit());
  let weightUnit = $derived(displayWeightUnit());
  let tempPh = $derived(tempPlaceholder());

  const QUICK_TAGS = [
    { label: 'Sour', value: 'sour', group: 'under' },
    { label: 'Thin', value: 'thin', group: 'under' },
    { label: 'Weak', value: 'weak', group: 'under' },
    { label: 'Bitter', value: 'bitter', group: 'over' },
    { label: 'Harsh', value: 'harsh', group: 'over' },
    { label: 'Muddy', value: 'muddy', group: 'over' },
    { label: 'Heavy', value: 'heavy', group: 'over' },
    { label: 'Dry', value: 'dry', group: 'over' },
    { label: 'Balanced', value: 'balanced', group: 'good' },
    { label: 'Sweet', value: 'sweet', group: 'good' },
    { label: 'Clean', value: 'clean', group: 'good' },
    { label: 'Smooth', value: 'smooth', group: 'good' },
  ];

  const BREW_METHOD_GROUPS = [
    { label: 'Pour Over', items: [
      { value: 'pour_over', label: 'V60' },
      { value: 'chemex', label: 'Chemex' },
      { value: 'pour_over', label: 'Kalita Wave' },
      { value: 'pour_over', label: 'Hario Switch' },
      { value: 'pour_over', label: 'Pour Over (Other)' },
    ]},
    { label: 'Immersion', items: [
      { value: 'french_press', label: 'French Press' },
      { value: 'aeropress', label: 'AeroPress' },
      { value: 'aeropress', label: 'AeroPress (Inverted)' },
      { value: 'cold_brew', label: 'Cold Brew' },
    ]},
    { label: 'Pressure', items: [
      { value: 'espresso', label: 'Espresso' },
      { value: 'moka_pot', label: 'Moka Pot' },
    ]},
  ];

  function toggleTag(tag: string) {
    if (selectedTags.includes(tag)) {
      selectedTags = selectedTags.filter(t => t !== tag);
    } else {
      selectedTags = [...selectedTags, tag];
    }
  }

  function tagColor(group: string, isSelected: boolean): string {
    if (!isSelected) return 'bg-neutral-100 text-neutral-600 border-neutral-200';
    if (group === 'under') return 'bg-yellow-100 text-yellow-800 border-yellow-300';
    if (group === 'over') return 'bg-red-100 text-red-800 border-red-300';
    return 'bg-green-100 text-green-800 border-green-300';
  }

  async function handleSubmit() {
    submitting = true;

    const extractionTimeS =
      (parseInt(extractionMin || '0') * 60) + parseInt(extractionSec || '0') || undefined;

    const payload = {
      current_d50: d50,
      current_setting: grindSetting,
      brew_method: brewMethod,
      taste_notes: tasteNotes,
      taste_tags: selectedTags.length > 0 ? selectedTags : undefined,
      water_temp_c: waterTemp ? inputTempToCelsius(parseFloat(waterTemp)) : undefined,
      extraction_time_s: extractionTimeS,
      filter_type: filterType || undefined,
      dose_g: doseG ? inputWeightToGrams(parseFloat(doseG)) : undefined,
      water_g: waterG ? inputWeightToGrams(parseFloat(waterG)) : undefined,
      num_pours: numPours ? parseInt(numPours) : undefined,
    };

    onSubmit(payload);
    submitting = false;
  }
</script>

<div class="space-y-5">
  <!-- Section: Grinder Setting -->
  <div class="p-5 bg-white border border-neutral-200 rounded-xl">
    <h4 class="font-semibold text-amber-900 mb-1 text-center">Your Grinder Setting</h4>
    <p class="text-xs text-neutral-500 text-center mb-3">Fellow Ode Brew Grinder</p>
    <GrinderDial bind:value={grindSetting} min={1} max={11} />
  </div>

  <!-- Section: Brew Variables -->
  <div class="p-5 bg-white border border-neutral-200 rounded-xl space-y-4">
    <h4 class="font-semibold text-amber-900">Brew Details</h4>

    <!-- Brew Method -->
    <div>
      <label class="block text-sm font-medium text-neutral-700 mb-1.5" for="brewMethod">
        <Coffee class="w-3.5 h-3.5 inline mr-1" />Brew Method
      </label>
      <select id="brewMethod" bind:value={brewMethod}
        class="w-full border border-neutral-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 bg-white">
        {#each BREW_METHOD_GROUPS as group}
          <optgroup label={group.label}>
            {#each group.items as method}
              <option value={method.value}>{method.label}</option>
            {/each}
          </optgroup>
        {/each}
      </select>
    </div>

    <!-- Temp + Time row -->
    <div class="grid grid-cols-2 gap-3">
      <div>
        <label class="block text-sm font-medium text-neutral-700 mb-1.5" for="waterTemp">
          <Thermometer class="w-3.5 h-3.5 inline mr-1" />Water Temp
        </label>
        <div class="relative">
          <input id="waterTemp" type="number" bind:value={waterTemp} placeholder={tempPh}
            class="w-full border border-neutral-200 rounded-lg px-3 py-2.5 text-sm pr-8 focus:outline-none focus:ring-2 focus:ring-amber-500" />
          <span class="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-neutral-400">{tempUnit}</span>
        </div>
      </div>
      <div>
        <label class="block text-sm font-medium text-neutral-700 mb-1.5" for="extractionMin">
          <Clock class="w-3.5 h-3.5 inline mr-1" />Brew Time
        </label>
        <div class="flex gap-1 items-center">
          <input id="extractionMin" type="number" bind:value={extractionMin} placeholder="3" min="0" max="15"
            class="w-full border border-neutral-200 rounded-lg px-2 py-2.5 text-sm text-center focus:outline-none focus:ring-2 focus:ring-amber-500" />
          <span class="text-neutral-400 text-sm font-medium">:</span>
          <input type="number" bind:value={extractionSec} placeholder="30" min="0" max="59"
            class="w-full border border-neutral-200 rounded-lg px-2 py-2.5 text-sm text-center focus:outline-none focus:ring-2 focus:ring-amber-500" />
        </div>
      </div>
    </div>

    <!-- Dose + Water row -->
    <div class="grid grid-cols-2 gap-3">
      <div>
        <label class="block text-sm font-medium text-neutral-700 mb-1.5" for="doseG">
          <Droplets class="w-3.5 h-3.5 inline mr-1" />Dose
        </label>
        <div class="relative">
          <input id="doseG" type="number" bind:value={doseG} placeholder="20"
            class="w-full border border-neutral-200 rounded-lg px-3 py-2.5 text-sm pr-6 focus:outline-none focus:ring-2 focus:ring-amber-500" />
          <span class="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-neutral-400">{weightUnit}</span>
        </div>
      </div>
      <div>
        <label class="block text-sm font-medium text-neutral-700 mb-1.5" for="waterG">
          <Droplets class="w-3.5 h-3.5 inline mr-1" />Water
        </label>
        <div class="relative">
          <input id="waterG" type="number" bind:value={waterG} placeholder="320"
            class="w-full border border-neutral-200 rounded-lg px-3 py-2.5 text-sm pr-6 focus:outline-none focus:ring-2 focus:ring-amber-500" />
          <span class="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-neutral-400">{weightUnit}</span>
        </div>
      </div>
    </div>

    <!-- Filter type toggle -->
    <div>
      <label class="block text-sm font-medium text-neutral-700 mb-1.5">
        <Filter class="w-3.5 h-3.5 inline mr-1" />Filter Type
      </label>
      <div class="grid grid-cols-2 bg-neutral-100 rounded-lg p-1 gap-1">
        <button
          onclick={() => filterType = 'paper'}
          class="py-2 text-sm rounded-md transition-all {filterType === 'paper' ? 'bg-white text-amber-900 shadow-sm font-medium' : 'text-neutral-600'}"
        >Paper</button>
        <button
          onclick={() => filterType = 'metal'}
          class="py-2 text-sm rounded-md transition-all {filterType === 'metal' ? 'bg-white text-amber-900 shadow-sm font-medium' : 'text-neutral-600'}"
        >Metal</button>
      </div>
    </div>
  </div>

  <!-- Section: Taste Feedback -->
  <div class="p-5 bg-white border border-neutral-200 rounded-xl space-y-4">
    <h4 class="font-semibold text-amber-900">How Did It Taste?</h4>

    <!-- Quick tags -->
    <div class="flex flex-wrap gap-2">
      {#each QUICK_TAGS as tag}
        <button
          onclick={() => toggleTag(tag.value)}
          class="px-3 py-1.5 text-xs font-medium rounded-full border transition-all {tagColor(tag.group, selectedTags.includes(tag.value))}"
        >
          {tag.label}
        </button>
      {/each}
    </div>

    <!-- Free text -->
    <textarea
      bind:value={tasteNotes}
      rows={3}
      placeholder="Describe the taste in your own words... e.g. 'A bit sour and watery, lacked body'"
      class="w-full border border-neutral-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 resize-none"
    ></textarea>
  </div>

  <!-- Submit -->
  <button
    onclick={handleSubmit}
    disabled={submitting || (!tasteNotes && selectedTags.length === 0)}
    class="w-full flex items-center justify-center gap-2 bg-amber-700 hover:bg-amber-800 disabled:bg-neutral-300 disabled:cursor-not-allowed text-white py-3 px-4 rounded-xl text-sm font-semibold transition-colors"
  >
    <Send class="w-4 h-4" />
    {submitting ? 'Getting Recommendation...' : 'Get Grind Recommendation'}
  </button>
</div>
