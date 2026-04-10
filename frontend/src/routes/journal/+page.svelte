<script lang="ts">
  import PageLayout from '$lib/components/PageLayout.svelte';
  import NewEntryDialog from '$lib/components/NewEntryDialog.svelte';
  import { Plus, Calendar, Coffee, Droplets, Thermometer, Clock, ChevronRight } from 'lucide-svelte';

  interface JournalEntry {
    id: string; date: string; bean: string; grindSize: string;
    brewMethod: string; waterTemp: number; brewTime: string;
    rating: number; notes: string; taste: string[];
  }

  let showNewEntry = $state(false);
  let activeTab = $state('all');
  let entries = $state<JournalEntry[]>([
    { id: '1', date: '2026-02-24', bean: 'Ethiopian Yirgacheffe', grindSize: 'Medium-Fine (650μm)', brewMethod: 'Pour Over', waterTemp: 96, brewTime: '3:30', rating: 4, notes: 'Bright and floral, slight bitterness at the end. Try going coarser next time.', taste: ['Floral', 'Bright', 'Berry'] },
    { id: '2', date: '2026-02-23', bean: 'Colombian Supremo', grindSize: 'Medium (700μm)', brewMethod: 'French Press', waterTemp: 93, brewTime: '4:00', rating: 5, notes: 'Perfect balance! Sweet and chocolatey with a smooth finish.', taste: ['Chocolate', 'Nutty', 'Smooth'] },
    { id: '3', date: '2026-02-22', bean: 'Brazilian Santos', grindSize: 'Fine (400μm)', brewMethod: 'Espresso', waterTemp: 94, brewTime: '0:28', rating: 3, notes: 'A bit too bitter. Need to increase grind size slightly.', taste: ['Bitter', 'Bold', 'Caramel'] },
  ]);

  function avgRating() {
    return (entries.reduce((s, e) => s + e.rating, 0) / entries.length).toFixed(1);
  }

  function formatDate(d: string) {
    return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  const tabs = ['all', 'favorites', 'recent'];
  let filtered = $derived(
    activeTab === 'favorites' ? entries.filter(e => e.rating >= 4) :
    activeTab === 'recent' ? entries.slice(0, 3) : entries
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
          <div class="p-4 bg-white border border-neutral-200 rounded-lg hover:border-amber-300 transition-colors cursor-pointer space-y-3">
            <div class="flex items-start justify-between">
              <div>
                <h4 class="font-semibold text-amber-900">{entry.bean}</h4>
                <div class="flex items-center gap-2 mt-1">
                  <Calendar class="w-3 h-3 text-neutral-500" />
                  <span class="text-xs text-neutral-600">{formatDate(entry.date)}</span>
                </div>
              </div>
              <div class="flex items-center gap-1">
                {#each Array(5) as _, i}
                  <div class="w-2 h-2 rounded-full {i < entry.rating ? 'bg-amber-500' : 'bg-neutral-200'}"></div>
                {/each}
              </div>
            </div>
            <div class="grid grid-cols-2 gap-2 text-xs">
              <div class="flex items-center gap-1.5 text-neutral-600"><Coffee class="w-3.5 h-3.5" /><span>{entry.brewMethod}</span></div>
              <div class="flex items-center gap-1.5 text-neutral-600"><Droplets class="w-3.5 h-3.5" /><span>{entry.grindSize}</span></div>
              <div class="flex items-center gap-1.5 text-neutral-600"><Thermometer class="w-3.5 h-3.5" /><span>{entry.waterTemp}°C</span></div>
              <div class="flex items-center gap-1.5 text-neutral-600"><Clock class="w-3.5 h-3.5" /><span>{entry.brewTime}</span></div>
            </div>
            <div class="flex flex-wrap gap-1.5">
              {#each entry.taste as tag}
                <span class="text-xs border border-amber-200 text-amber-800 bg-amber-50 px-2 py-0.5 rounded-full">{tag}</span>
              {/each}
            </div>
            {#if entry.notes}
              <p class="text-sm text-neutral-600 line-clamp-2">{entry.notes}</p>
            {/if}
            <button class="w-full flex items-center justify-between text-amber-700 hover:text-amber-800 text-sm font-medium">
              View Details <ChevronRight class="w-4 h-4" />
            </button>
          </div>
        {/each}
      </div>
    </div>
  </div>

  <NewEntryDialog bind:open={showNewEntry} onSave={(e) => { entries = [e, ...entries]; }} />
</PageLayout>
