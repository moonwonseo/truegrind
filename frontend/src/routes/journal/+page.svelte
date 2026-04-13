<script lang="ts">
  import PageLayout from '$lib/components/PageLayout.svelte';
  import NewEntryDialog from '$lib/components/NewEntryDialog.svelte';
  import { Plus, Calendar, Coffee, Droplets, Thermometer, Clock, ChevronRight, Trash2, BarChart3, Pencil, Save, X, Heart, Scale } from 'lucide-svelte';
  import { displayTemp, displayTempUnit, celsiusToDisplay, inputTempToCelsius, displayWeight, displayWeightUnit } from '$lib/settings.svelte';
  import { onMount } from 'svelte';

  interface JournalEntry {
    id: string; date: string; bean: string; grindSize: string;
    brewMethod: string; waterTemp: number; brewTime: string;
    rating: number; notes: string; taste: string[];
    d50?: number; d10?: number; d90?: number;
    particles?: number; uniformity?: string; autoSaved?: boolean;
    favorite?: boolean; dose_g?: number; water_g?: number;
  }

  const STORAGE_KEY = 'truegrind-journal';

  const DEFAULT_ENTRIES: JournalEntry[] = [
    { id: '1', date: '2026-02-24', bean: 'Ethiopian Yirgacheffe', grindSize: 'Medium-Fine (650μm)', brewMethod: 'Pour Over', waterTemp: 96, brewTime: '3:30', rating: 4, notes: 'Bright and floral, slight bitterness at the end. Try going coarser next time.', taste: ['Floral', 'Bright', 'Berry'] },
    { id: '2', date: '2026-02-23', bean: 'Colombian Supremo', grindSize: 'Medium (700μm)', brewMethod: 'French Press', waterTemp: 93, brewTime: '4:00', rating: 5, notes: 'Perfect balance! Sweet and chocolatey with a smooth finish.', taste: ['Chocolate', 'Nutty', 'Smooth'] },
    { id: '3', date: '2026-02-22', bean: 'Brazilian Santos', grindSize: 'Fine (400μm)', brewMethod: 'Espresso', waterTemp: 94, brewTime: '0:28', rating: 3, notes: 'A bit too bitter. Need to increase grind size slightly.', taste: ['Bitter', 'Bold', 'Caramel'] },
  ];

  let showNewEntry = $state(false);
  let activeTab = $state('all');
  let entries = $state<JournalEntry[]>([]);
  let loaded = $state(false);
  let expandedId = $state<string | null>(null);
  let editingId = $state<string | null>(null);
  let editDraft = $state<JournalEntry | null>(null);

  onMount(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      entries = stored ? JSON.parse(stored) : [...DEFAULT_ENTRIES];
    } catch {
      entries = [...DEFAULT_ENTRIES];
    }
    loaded = true;
  });

  $effect(() => {
    if (loaded) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
    }
  });

  function avgRating() {
    const rated = entries.filter(e => e.rating > 0);
    if (rated.length === 0) return '—';
    return (rated.reduce((s, e) => s + e.rating, 0) / rated.length).toFixed(1);
  }

  function formatDate(d: string) {
    return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function toggleExpand(id: string) {
    if (editingId === id) return; // don't collapse while editing
    expandedId = expandedId === id ? null : id;
    if (expandedId !== id) {
      editingId = null;
      editDraft = null;
    }
  }

  // startEdit is defined below after toggleFavorite

  function saveEdit() {
    if (!editDraft) return;
    entries = entries.map(e => e.id === editDraft!.id ? { ...editDraft! } : e);
    editingId = null;
    editDraft = null;
  }

  function cancelEdit() {
    editingId = null;
    editDraft = null;
  }

  function deleteEntry(id: string) {
    entries = entries.filter(e => e.id !== id);
    if (expandedId === id) expandedId = null;
    if (editingId === id) { editingId = null; editDraft = null; }
  }

  function toggleFavorite(id: string) {
    entries = entries.map(e => e.id === id ? { ...e, favorite: !e.favorite } : e);
  }

  // Temp edit helpers: store internally as °C, display in user's unit
  let editTempDisplay = $state(0);
  function startEdit(entry: JournalEntry) {
    editingId = entry.id;
    editDraft = JSON.parse(JSON.stringify(entry));
    editTempDisplay = celsiusToDisplay(entry.waterTemp || 0);
  }

  const tabs = ['all', 'favorites', 'recent'];
  let filtered = $derived(
    activeTab === 'favorites' ? entries.filter(e => e.favorite) :
    activeTab === 'recent' ? entries.slice(0, 5) : entries
  );
</script>

<PageLayout title="Coffee Journal">
  <div class="space-y-4">
    <!-- Stats -->
    <div class="grid grid-cols-3 gap-3">
      {#each [[entries.length, 'Total Brews'], [avgRating(), 'Avg Rating'], [7, 'Day Streak']] as [val, label]}
        <div class="p-4 bg-white border border-neutral-200 rounded-lg text-center">
          <div class="text-2xl font-semibold text-amber-900">{val}</div>
          <div class="text-xs text-neutral-600">{label}</div>
        </div>
      {/each}
    </div>

    <button onclick={() => (showNewEntry = true)} class="w-full flex items-center justify-center gap-2 bg-amber-700 hover:bg-amber-800 text-white py-2.5 px-4 rounded-lg font-medium transition-colors">
      <Plus class="w-4 h-4" /> Log New Brew
    </button>

    <!-- Tabs -->
    <div class="w-full">
      <div class="grid grid-cols-3 bg-neutral-100 rounded-lg p-1 gap-1">
        {#each tabs as tab}
          <button
            onclick={() => (activeTab = tab)}
            class="py-1.5 text-sm rounded-md capitalize transition-colors {activeTab === tab ? 'bg-white text-neutral-900 shadow-sm' : 'text-neutral-600 hover:text-neutral-900'}"
          >
            {tab}
          </button>
        {/each}
      </div>

      <div class="space-y-3 mt-4">
        {#each filtered as entry (entry.id)}
          <div class="bg-white border border-neutral-200 rounded-lg hover:border-amber-300 transition-colors overflow-hidden">
            <!-- Card summary -->
            <button class="w-full p-4 text-left space-y-3" onclick={() => toggleExpand(entry.id)}>
              <div class="flex items-start justify-between">
                <div>
                  <h4 class="font-semibold text-amber-900">
                    {entry.bean || entry.grindSize || 'Grind Analysis'}
                  </h4>
                  <div class="flex items-center gap-2 mt-1">
                    <Calendar class="w-3 h-3 text-neutral-500" />
                    <span class="text-xs text-neutral-600">{formatDate(entry.date)}</span>
                    {#if entry.autoSaved}
                      <span class="text-xs bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded">Auto</span>
                    {/if}
                  </div>
                </div>
                <div class="flex items-center gap-2">
                  <!-- svelte-ignore a11y_click_events_have_key_events -->
                  <!-- svelte-ignore a11y_no_static_element_interactions -->
                  <div class="p-1 cursor-pointer" onclick={(e) => { e.stopPropagation(); toggleFavorite(entry.id); }}>
                    <Heart class="w-4 h-4 {entry.favorite ? 'fill-red-500 text-red-500' : 'text-neutral-300 hover:text-red-300'}" />
                  </div>
                  {#if entry.rating > 0}
                    <div class="flex items-center gap-0.5">
                      {#each Array(5) as _, i}
                        <span class="text-xs {i < entry.rating ? 'opacity-100' : 'opacity-20'}" style="color: {i < entry.rating ? 'var(--accent)' : 'var(--text-faint)'};">☕</span>
                      {/each}
                    </div>
                  {/if}
                  <div class="transition-transform duration-200 {expandedId === entry.id ? 'rotate-90' : ''}">
                    <ChevronRight class="w-4 h-4 text-neutral-400" />
                  </div>
                </div>
              </div>

              <div class="grid grid-cols-2 gap-2 text-xs">
                {#if entry.brewMethod}
                  <div class="flex items-center gap-1.5 text-neutral-600"><Coffee class="w-3.5 h-3.5" /><span>{entry.brewMethod}</span></div>
                {/if}
                {#if entry.grindSize}
                  <div class="flex items-center gap-1.5 text-neutral-600"><Droplets class="w-3.5 h-3.5" /><span>{entry.grindSize}</span></div>
                {/if}
                {#if entry.waterTemp}
                  <div class="flex items-center gap-1.5 text-neutral-600"><Thermometer class="w-3.5 h-3.5" /><span>{displayTemp(entry.waterTemp)}</span></div>
                {/if}
                {#if entry.brewTime}
                  <div class="flex items-center gap-1.5 text-neutral-600"><Clock class="w-3.5 h-3.5" /><span>{entry.brewTime}</span></div>
                {/if}
                {#if entry.dose_g}
                  <div class="flex items-center gap-1.5 text-neutral-600"><Scale class="w-3.5 h-3.5" /><span>{displayWeight(entry.dose_g)} dose</span></div>
                {/if}
                {#if entry.water_g}
                  <div class="flex items-center gap-1.5 text-neutral-600"><Droplets class="w-3.5 h-3.5" /><span>{displayWeight(entry.water_g)} water</span></div>
                {/if}
              </div>

              {#if entry.taste && entry.taste.length > 0}
                <div class="flex flex-wrap gap-1.5">
                  {#each entry.taste as tag}
                    <span class="text-xs border border-amber-200 text-amber-800 bg-amber-50 px-2 py-0.5 rounded-full">{tag}</span>
                  {/each}
                </div>
              {/if}
            </button>

            <!-- Expanded detail panel -->
            {#if expandedId === entry.id}
              <div class="border-t border-neutral-200 p-4 bg-neutral-50 space-y-4">

                {#if editingId === entry.id && editDraft}
                  <!-- ═══ EDIT MODE ═══ -->
                  <div class="space-y-3">
                    <div>
                      <label class="block text-xs font-medium text-neutral-500 mb-1">Coffee Bean</label>
                      <input bind:value={editDraft.bean} placeholder="e.g., Ethiopian Yirgacheffe"
                        class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                      <div>
                        <label class="block text-xs font-medium text-neutral-500 mb-1">Brew Method</label>
                        <select bind:value={editDraft.brewMethod}
                          class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500">
                          <option value="">None</option>
                          <optgroup label="Pour Over">
                            <option>V60</option>
                            <option>Chemex</option>
                            <option>Kalita Wave</option>
                            <option>Hario Switch</option>
                            <option>Pour Over (Other)</option>
                          </optgroup>
                          <optgroup label="Immersion">
                            <option>French Press</option>
                            <option>AeroPress</option>
                            <option>AeroPress (Inverted)</option>
                            <option>Cold Brew</option>
                          </optgroup>
                          <optgroup label="Pressure">
                            <option>Espresso</option>
                            <option>Moka Pot</option>
                          </optgroup>
                        </select>
                      </div>
                      <div>
                        <label class="block text-xs font-medium text-neutral-500 mb-1">Grind Size</label>
                        <input bind:value={editDraft.grindSize} placeholder="e.g., Medium (600μm)"
                          class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
                      </div>
                    </div>
                    <div class="grid grid-cols-3 gap-3">
                      <div>
                        <label class="block text-xs font-medium text-neutral-500 mb-1">Water Temp ({displayTempUnit()})</label>
                        <input type="number" bind:value={editTempDisplay} placeholder={displayTempUnit() === '°F' ? '200' : '96'}
                          onchange={() => { if (editDraft) editDraft.waterTemp = inputTempToCelsius(editTempDisplay); }}
                          class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
                      </div>
                      <div>
                        <label class="block text-xs font-medium text-neutral-500 mb-1">Brew Time</label>
                        <input bind:value={editDraft.brewTime} placeholder="3:30"
                          class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
                      </div>
                      <div>
                        <label class="block text-xs font-medium text-neutral-500 mb-1">Rating</label>
                        <select bind:value={editDraft.rating}
                          class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500">
                          <option value={0}>—</option>
                          <option value={1}>☕</option>
                          <option value={2}>☕☕</option>
                          <option value={3}>☕☕☕</option>
                          <option value={4}>☕☕☕☕</option>
                          <option value={5}>☕☕☕☕☕</option>
                        </select>
                      </div>
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                      <div>
                        <label class="block text-xs font-medium text-neutral-500 mb-1">Dose ({displayWeightUnit()})</label>
                        <input type="number" bind:value={editDraft.dose_g} placeholder="18"
                          class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
                      </div>
                      <div>
                        <label class="block text-xs font-medium text-neutral-500 mb-1">Water ({displayWeightUnit()})</label>
                        <input type="number" bind:value={editDraft.water_g} placeholder="300"
                          class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
                      </div>
                    </div>
                    <div>
                      <label class="block text-xs font-medium text-neutral-500 mb-1">Notes</label>
                      <textarea bind:value={editDraft.notes} rows={3} placeholder="How did it taste?"
                        class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 resize-none"></textarea>
                    </div>
                    <div class="flex gap-2 pt-1">
                      <button onclick={cancelEdit}
                        class="flex-1 flex items-center justify-center gap-1.5 border border-neutral-300 text-neutral-600 py-2 px-3 rounded-lg text-sm font-medium hover:bg-neutral-100 transition-colors">
                        <X class="w-3.5 h-3.5" /> Cancel
                      </button>
                      <button onclick={saveEdit}
                        class="flex-1 flex items-center justify-center gap-1.5 bg-amber-700 hover:bg-amber-800 text-white py-2 px-3 rounded-lg text-sm font-medium transition-colors">
                        <Save class="w-3.5 h-3.5" /> Save
                      </button>
                    </div>
                  </div>

                {:else}
                  <!-- ═══ VIEW MODE ═══ -->

                  <!-- PSD data -->
                  {#if entry.d50}
                    <div>
                      <div class="flex items-center gap-1.5 text-sm font-medium text-amber-900 mb-2">
                        <BarChart3 class="w-4 h-4" /> Particle Size Distribution
                      </div>
                      <div class="grid grid-cols-3 gap-2">
                        <div class="bg-white p-3 rounded-lg border border-neutral-200 text-center">
                          <div class="text-lg font-semibold text-amber-800">{Math.round(entry.d10 || 0)}</div>
                          <div class="text-xs text-neutral-500">D10 (μm)</div>
                        </div>
                        <div class="bg-white p-3 rounded-lg border border-amber-300 text-center">
                          <div class="text-lg font-bold text-amber-900">{Math.round(entry.d50)}</div>
                          <div class="text-xs text-neutral-500">D50 (μm)</div>
                        </div>
                        <div class="bg-white p-3 rounded-lg border border-neutral-200 text-center">
                          <div class="text-lg font-semibold text-amber-800">{Math.round(entry.d90 || 0)}</div>
                          <div class="text-xs text-neutral-500">D90 (μm)</div>
                        </div>
                      </div>
                      <div class="grid grid-cols-2 gap-2 mt-2 text-xs">
                        {#if entry.particles}
                          <div class="bg-white p-2 rounded-lg border border-neutral-200 text-center">
                            <span class="font-medium text-neutral-700">{entry.particles}</span>
                            <span class="text-neutral-500"> particles</span>
                          </div>
                        {/if}
                        {#if entry.uniformity}
                          <div class="bg-white p-2 rounded-lg border border-neutral-200 text-center">
                            <span class="font-medium text-neutral-700 capitalize">{entry.uniformity}</span>
                            <span class="text-neutral-500"> uniformity</span>
                          </div>
                        {/if}
                      </div>
                    </div>
                  {/if}

                  <!-- Notes -->
                  {#if entry.notes}
                    <div>
                      <div class="text-sm font-medium text-neutral-700 mb-1">Notes</div>
                      <p class="text-sm text-neutral-600 bg-white p-3 rounded-lg border border-neutral-200">{entry.notes}</p>
                    </div>
                  {/if}

                  <!-- Action buttons -->
                  <div class="flex items-center justify-between pt-1">
                    <button
                      onclick={() => startEdit(entry)}
                      class="flex items-center gap-1.5 text-xs text-amber-700 hover:text-amber-900 font-medium transition-colors"
                    >
                      <Pencil class="w-3.5 h-3.5" /> Edit Entry
                    </button>
                    <button
                      onclick={() => deleteEntry(entry.id)}
                      class="flex items-center gap-1.5 text-xs text-red-500 hover:text-red-700 transition-colors"
                    >
                      <Trash2 class="w-3.5 h-3.5" /> Delete
                    </button>
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {/each}

        {#if filtered.length === 0}
          <div class="text-center py-8 text-neutral-500 text-sm">
            No entries yet. Run a grind analysis or log a brew to get started!
          </div>
        {/if}
      </div>
    </div>
  </div>

  <NewEntryDialog bind:open={showNewEntry} onSave={(e) => { entries = [e, ...entries]; }} />
</PageLayout>
