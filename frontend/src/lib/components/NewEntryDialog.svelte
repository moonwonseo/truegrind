<script lang="ts">
  let { open = $bindable(false), onSave }: { open: boolean; onSave: (entry: any) => void } = $props();

  let formData = $state({
    bean: '',
    grindSize: '',
    brewMethod: '',
    waterTemp: '',
    brewTime: '',
    rating: '3',
    notes: '',
  });

  function handleSubmit(e: Event) {
    e.preventDefault();
    onSave({
      id: Date.now().toString(),
      date: new Date().toISOString().split('T')[0],
      bean: formData.bean,
      grindSize: formData.grindSize,
      brewMethod: formData.brewMethod,
      waterTemp: parseInt(formData.waterTemp),
      brewTime: formData.brewTime,
      rating: parseInt(formData.rating),
      notes: formData.notes,
      taste: [],
    });
    formData = { bean: '', grindSize: '', brewMethod: '', waterTemp: '', brewTime: '', rating: '3', notes: '' };
    open = false;
  }
</script>

{#if open}
  <div class="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
    <button class="absolute inset-0 bg-black/50" onclick={() => (open = false)} aria-label="Close"></button>
    <div class="relative bg-white rounded-t-2xl sm:rounded-2xl w-full max-w-md max-h-[90vh] overflow-y-auto p-6 shadow-xl">
      <h2 class="text-lg font-semibold text-amber-900 mb-4">Log New Brew</h2>
      <form onsubmit={handleSubmit} class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-neutral-700 mb-1" for="bean">Coffee Bean</label>
          <input id="bean" bind:value={formData.bean} placeholder="e.g., Ethiopian Yirgacheffe" required
            class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
        </div>
        <div>
          <label class="block text-sm font-medium text-neutral-700 mb-1" for="brewMethod">Brew Method</label>
          <select id="brewMethod" bind:value={formData.brewMethod} required
            class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500">
            <option value="">Select method</option>
            <option>Pour Over</option>
            <option>French Press</option>
            <option>Espresso</option>
            <option>AeroPress</option>
            <option>Chemex</option>
            <option>Moka Pot</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-neutral-700 mb-1" for="grindSize">Grind Size</label>
          <input id="grindSize" bind:value={formData.grindSize} placeholder="e.g., Medium-Fine (650μm)" required
            class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-sm font-medium text-neutral-700 mb-1" for="waterTemp">Water Temp (°C)</label>
            <input id="waterTemp" type="number" bind:value={formData.waterTemp} placeholder="96" required
              class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
          </div>
          <div>
            <label class="block text-sm font-medium text-neutral-700 mb-1" for="brewTime">Brew Time</label>
            <input id="brewTime" bind:value={formData.brewTime} placeholder="3:30" required
              class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
          </div>
        </div>
        <div>
          <label class="block text-sm font-medium text-neutral-700 mb-1" for="rating">Rating</label>
          <select id="rating" bind:value={formData.rating}
            class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500">
            <option value="1">1 - Poor</option>
            <option value="2">2 - Fair</option>
            <option value="3">3 - Good</option>
            <option value="4">4 - Great</option>
            <option value="5">5 - Excellent</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-neutral-700 mb-1" for="notes">Notes</label>
          <textarea id="notes" bind:value={formData.notes} rows={3}
            placeholder="How did it taste? Any adjustments needed?"
            class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 resize-none"></textarea>
        </div>
        <div class="flex gap-3 pt-2">
          <button type="button" onclick={() => (open = false)}
            class="flex-1 border border-neutral-300 text-neutral-700 py-2 px-4 rounded-lg text-sm font-medium hover:bg-neutral-50 transition-colors">
            Cancel
          </button>
          <button type="submit"
            class="flex-1 bg-amber-700 hover:bg-amber-800 text-white py-2 px-4 rounded-lg text-sm font-medium transition-colors">
            Save Entry
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
