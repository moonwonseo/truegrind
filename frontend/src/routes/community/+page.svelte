<script lang="ts">
  import PageLayout from '$lib/components/PageLayout.svelte';
  import { Search, TrendingUp, Star, MessageCircle, Bookmark, Coffee, Droplets, Thermometer, Users, Clock, ChevronDown, Scale, Plus, Pencil, Trash2, Save, X, Copy, BookOpen } from 'lucide-svelte';
  import { displayTemp, displayTempUnit, celsiusToDisplay, inputTempToCelsius } from '$lib/settings.svelte';
  import { onMount } from 'svelte';

  interface RecipeStep {
    time: string;
    instruction: string;
  }

  interface Recipe {
    id: string; author: string; bean: string; brewMethod: string; grindSize: string;
    waterTemp: number; ratio: string; brewTime: string; rating: number;
    reviews: number; saves: number; description: string; tags: string[];
    dose_g: number; water_g: number;
    steps: RecipeStep[];
    tips: string[];
  }

  const SAVED_KEY = 'truegrind-saved-recipes';
  const MY_RECIPES_KEY = 'truegrind-my-recipes';

  let searchQuery = $state('');
  let activeTab = $state('trending');
  let savedIds = $state<Set<string>>(new Set());
  let expandedId = $state<string | null>(null);
  let myRecipes = $state<Recipe[]>([]);
  let loaded = $state(false);

  // Recipe editor state
  let editingRecipe = $state<Recipe | null>(null);
  let showEditor = $state(false);

  // Ratio calculator state
  let calcDose = $state(0);
  let calcWater = $state(0);
  let calcRatioNum = $state(1);
  let calcRatioDen = $state(16);
  let lastChanged = $state<'dose' | 'water' | 'ratio'>('dose');

  onMount(() => {
    try {
      const stored = localStorage.getItem(SAVED_KEY);
      if (stored) savedIds = new Set(JSON.parse(stored));
      const myStored = localStorage.getItem(MY_RECIPES_KEY);
      if (myStored) myRecipes = JSON.parse(myStored);
    } catch {}
    loaded = true;
  });

  $effect(() => {
    if (!loaded) return;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(SAVED_KEY, JSON.stringify([...savedIds]));
      localStorage.setItem(MY_RECIPES_KEY, JSON.stringify(myRecipes));
    }
  });

  function toggleSave(id: string) {
    const s = new Set(savedIds);
    s.has(id) ? s.delete(id) : s.add(id);
    savedIds = s;
  }

  // Parse ratio string like "1:16" into [1, 16]
  function parseRatio(r: string): [number, number] {
    const parts = r.split(':').map(Number);
    if (parts.length === 2 && parts[0] > 0 && parts[1] > 0) return [parts[0], parts[1]];
    return [1, 16];
  }

  function initCalc(recipe: Recipe) {
    calcDose = recipe.dose_g;
    calcWater = recipe.water_g;
    const [n, d] = parseRatio(recipe.ratio);
    calcRatioNum = n;
    calcRatioDen = d;
    lastChanged = 'dose';
  }

  function onDoseChange() {
    lastChanged = 'dose';
    calcWater = Math.round(calcDose * (calcRatioDen / calcRatioNum) * 10) / 10;
  }
  function onWaterChange() {
    lastChanged = 'water';
    calcDose = Math.round(calcWater / (calcRatioDen / calcRatioNum) * 10) / 10;
  }
  function onRatioChange() {
    lastChanged = 'ratio';
    // Keep dose fixed, adjust water
    calcWater = Math.round(calcDose * (calcRatioDen / calcRatioNum) * 10) / 10;
  }

  // My Recipes editor
  function createNewRecipe() {
    editingRecipe = {
      id: 'my-' + Date.now(),
      author: 'You',
      bean: '',
      brewMethod: 'Pour Over',
      grindSize: '',
      waterTemp: 96,
      ratio: '1:16',
      brewTime: '',
      rating: 0,
      reviews: 0,
      saves: 0,
      description: '',
      tags: [],
      dose_g: 15,
      water_g: 240,
      steps: [{ time: '0:00', instruction: '' }],
      tips: [''],
    };
    showEditor = true;
  }

  function cloneToMyRecipes(recipe: Recipe) {
    const clone: Recipe = {
      ...JSON.parse(JSON.stringify(recipe)),
      id: 'my-' + Date.now(),
      author: 'You (from @' + recipe.author + ')',
      rating: 0,
      reviews: 0,
      saves: 0,
    };
    editingRecipe = clone;
    showEditor = true;
  }

  function editMyRecipe(recipe: Recipe) {
    editingRecipe = JSON.parse(JSON.stringify(recipe));
    showEditor = true;
  }

  function saveRecipe() {
    if (!editingRecipe) return;
    // Update ratio string
    editingRecipe.ratio = `${calcRatioNum}:${calcRatioDen}`;
    editingRecipe.dose_g = calcDose;
    editingRecipe.water_g = calcWater;
    // Remove empty steps/tips
    editingRecipe.steps = editingRecipe.steps.filter(s => s.instruction.trim());
    editingRecipe.tips = editingRecipe.tips.filter(t => t.trim());

    const idx = myRecipes.findIndex(r => r.id === editingRecipe!.id);
    if (idx >= 0) {
      myRecipes = myRecipes.map((r, i) => i === idx ? editingRecipe! : r);
    } else {
      myRecipes = [editingRecipe, ...myRecipes];
    }
    showEditor = false;
    editingRecipe = null;
    activeTab = 'mine';
  }

  function deleteMyRecipe(id: string) {
    myRecipes = myRecipes.filter(r => r.id !== id);
  }

  function addStep() {
    if (!editingRecipe) return;
    editingRecipe.steps = [...editingRecipe.steps, { time: '', instruction: '' }];
  }
  function removeStep(i: number) {
    if (!editingRecipe) return;
    editingRecipe.steps = editingRecipe.steps.filter((_, idx) => idx !== i);
  }
  function addTip() {
    if (!editingRecipe) return;
    editingRecipe.tips = [...editingRecipe.tips, ''];
  }

  const communityRecipes: Recipe[] = [
    {
      id: '1', author: 'JamesHoffmann', bean: 'Ethiopian Yirgacheffe (Light Roast)',
      brewMethod: 'V60 Pour Over', grindSize: 'Medium-Fine (650μm)', waterTemp: 96,
      ratio: '1:16', brewTime: '3:30', rating: 4.8, reviews: 124, saves: 89,
      dose_g: 15, water_g: 250,
      description: 'James Hoffmann\'s ultimate V60 technique — a single-pour method that produces a clean, sweet cup highlighting floral and fruit-forward notes.',
      tags: ['Floral', 'Bright', 'Beginner-Friendly'],
      steps: [
        { time: '0:00', instruction: 'Place V60 with rinsed filter on server. Add 15g medium-fine grounds. Create a small well in the center.' },
        { time: '0:00', instruction: 'Start timer. Pour 50g water in a spiral from center outward. This is the bloom.' },
        { time: '0:45', instruction: 'At 45 seconds, begin your main pour. Pour in steady, slow circles from center outward.' },
        { time: '1:15', instruction: 'Continue pouring slowly until you reach 250g total water. Avoid pouring on the filter walls.' },
        { time: '1:30', instruction: 'Give the V60 a gentle swirl to flatten the coffee bed. Let it drain completely.' },
        { time: '3:00–3:30', instruction: 'Drawdown should finish around 3:00–3:30. If faster, grind finer. If slower, grind coarser.' },
      ],
      tips: ['Use water just off the boil (96°C / 205°F) for light roasts', 'The swirl at the end creates a flat bed for even extraction', 'If the cup is sour, grind finer. If bitter, grind coarser.'],
    },
    {
      id: '2', author: 'BaristaBob', bean: 'Colombian Supremo (Medium Roast)',
      brewMethod: 'French Press', grindSize: 'Coarse (800μm)', waterTemp: 93,
      ratio: '1:15', brewTime: '4:00', rating: 4.6, reviews: 87, saves: 56,
      dose_g: 30, water_g: 450,
      description: 'Classic French press immersion brew that highlights chocolate and nutty notes. The key is the 4-minute steep and gentle plunge.',
      tags: ['Chocolate', 'Full-Body', 'Easy'],
      steps: [
        { time: '0:00', instruction: 'Preheat French press with hot water, then discard. Add 30g coarse-ground coffee.' },
        { time: '0:00', instruction: 'Start timer. Pour 450g water at 93°C evenly over the grounds.' },
        { time: '0:30', instruction: 'Stir gently 3–4 times to ensure all grounds are saturated. Place lid on (plunger up).' },
        { time: '4:00', instruction: 'At 4 minutes, press the plunger down slowly and steadily.' },
        { time: '4:15', instruction: 'Pour immediately into cups or a thermal carafe.' },
      ],
      tips: ['Grind MUST be coarse — fine grinds will make the press hard to plunge', 'Preheating the press improves temperature stability', 'For a cleaner cup, skim the foam off the top before plunging'],
    },
    {
      id: '3', author: 'EspressoExpert', bean: 'Italian Roast Blend (Dark)',
      brewMethod: 'Espresso', grindSize: 'Fine (380μm)', waterTemp: 94,
      ratio: '1:2', brewTime: '0:28', rating: 4.9, reviews: 203, saves: 145,
      dose_g: 18, water_g: 36,
      description: 'Competition-style espresso recipe. Dial in carefully for a thick, syrupy shot with notes of dark chocolate and caramel.',
      tags: ['Bold', 'Creamy', 'Advanced'],
      steps: [
        { time: 'Prep', instruction: 'Dose 18g into the portafilter. Distribute evenly with WDT tool.' },
        { time: 'Prep', instruction: 'Tamp firmly and levelly with ~15kg of pressure.' },
        { time: '0:00', instruction: 'Lock portafilter and start extraction. First drops at 5–8 seconds.' },
        { time: '0:08', instruction: 'Stream should look like warm honey — thin, steady, golden-brown.' },
        { time: '0:25–0:30', instruction: 'Stop at 36g output (1:2 ratio). Total 25–30 seconds.' },
      ],
      tips: ['If shot runs too fast (< 22s), grind finer. Too slow (> 35s), grind coarser.', 'Flush the group head before locking in the portafilter', 'Puck should be firm and dry after extraction'],
    },
    {
      id: '4', author: 'AlanAdler', bean: 'Guatemala Antigua (Medium Roast)',
      brewMethod: 'AeroPress (Inverted)', grindSize: 'Medium-Fine (600μm)', waterTemp: 85,
      ratio: '1:14', brewTime: '2:30', rating: 4.7, reviews: 156, saves: 112,
      dose_g: 17, water_g: 240,
      description: 'Inverted AeroPress method for a smooth, sweet, full-bodied cup. Lower water temp reduces bitterness.',
      tags: ['Sweet', 'Smooth', 'Versatile'],
      steps: [
        { time: 'Prep', instruction: 'Set up AeroPress in inverted position. Rinse paper filter and set cap aside.' },
        { time: '0:00', instruction: 'Add 17g medium-fine coffee. Pour 50g water at 85°C for bloom.' },
        { time: '0:30', instruction: 'Stir gently 5 times. Pour remaining water to 240g total.' },
        { time: '1:00', instruction: 'Place rinsed filter cap on top. Let steep until 2:00.' },
        { time: '2:00', instruction: 'Carefully flip onto mug. Press down slowly for 30 seconds.' },
        { time: '2:30', instruction: 'Stop pressing when you hear a hiss.' },
      ],
      tips: ['Lower temperature (80–85°C) is key for avoiding bitterness', 'Be careful when flipping — hold the mug tight', 'Experiment with steep times: longer = stronger'],
    },
    {
      id: '5', author: 'ScottRao', bean: 'Kenyan AA (Light-Medium Roast)',
      brewMethod: 'Chemex', grindSize: 'Medium-Coarse (750μm)', waterTemp: 96,
      ratio: '1:16', brewTime: '4:30', rating: 4.5, reviews: 98, saves: 74,
      dose_g: 25, water_g: 400,
      description: 'A clean, bright Chemex recipe. The thick filter removes oils for a tea-like body with citrus and berry notes.',
      tags: ['Clean', 'Citrus', 'Bright'],
      steps: [
        { time: 'Prep', instruction: 'Place Chemex filter (3 layers toward spout). Rinse with hot water.' },
        { time: '0:00', instruction: 'Add 25g medium-coarse grounds. Pour 50g water for bloom.' },
        { time: '0:45', instruction: 'Begin main pour in slow circles. Target 200g by 1:30.' },
        { time: '1:30', instruction: 'Continue pouring in pulses of 50–75g until 400g.' },
        { time: '2:30', instruction: 'Final pour gentle. Allow complete drawdown.' },
        { time: '4:00–4:30', instruction: 'Total brew 4:00–4:30. Adjust grind if needed.' },
      ],
      tips: ['Use Chemex-specific bonded filters for best results', 'Pour slowly — the thick filter means longer drawdown', 'Kenyan coffees shine with this method'],
    },
  ];

  let displayed = $derived(() => {
    if (activeTab === 'mine') return [];
    let list = activeTab === 'top'
      ? [...communityRecipes].sort((a, b) => b.rating - a.rating)
      : activeTab === 'saved'
      ? communityRecipes.filter(r => savedIds.has(r.id))
      : communityRecipes;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(r =>
        r.bean.toLowerCase().includes(q) ||
        r.brewMethod.toLowerCase().includes(q) ||
        r.description.toLowerCase().includes(q) ||
        r.tags.some(t => t.toLowerCase().includes(q))
      );
    }
    return list;
  });
</script>

<PageLayout title="Community Recipes">
  <div class="space-y-4">
    <!-- Search -->
    <div class="relative">
      <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
      <input
        bind:value={searchQuery}
        placeholder="Search recipes, beans, methods..."
        class="w-full pl-10 border border-neutral-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-amber-500"
      />
    </div>

    <!-- Stats Banner -->
    <div class="p-4 bg-gradient-to-r from-amber-700 to-amber-600 text-white rounded-lg">
      <div class="flex items-center justify-between">
        <div>
          <div class="flex items-center gap-2 mb-1">
            <Users class="w-5 h-5" />
            <span class="font-semibold">Community Stats</span>
          </div>
          <p class="text-sm text-amber-50">Join 2,453 coffee enthusiasts sharing recipes</p>
        </div>
        <div class="text-right">
          <div class="text-2xl font-semibold">847</div>
          <div class="text-xs text-amber-50">Recipes</div>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="grid grid-cols-4 bg-neutral-100 rounded-lg p-1 gap-1">
      {#each [['trending', TrendingUp, 'Trending'], ['top', Star, 'Top'], ['saved', Bookmark, 'Saved'], ['mine', BookOpen, 'Mine']] as [tab, Icon, label]}
        <button
          onclick={() => (activeTab = tab)}
          class="flex items-center justify-center gap-1 py-1.5 text-xs rounded-md transition-colors {activeTab === tab ? 'bg-white text-neutral-900 shadow-sm' : 'text-neutral-600 hover:text-neutral-900'}"
        >
          <svelte:component this={Icon} class="w-3.5 h-3.5" />{label}
          {#if tab === 'saved' && savedIds.size > 0}
            <span class="bg-amber-100 text-amber-800 text-xs w-4 h-4 rounded-full flex items-center justify-center font-bold" style="font-size:10px">{savedIds.size}</span>
          {/if}
          {#if tab === 'mine' && myRecipes.length > 0}
            <span class="bg-green-100 text-green-800 text-xs w-4 h-4 rounded-full flex items-center justify-center font-bold" style="font-size:10px">{myRecipes.length}</span>
          {/if}
        </button>
      {/each}
    </div>

    <!-- ═══ MY RECIPES TAB ═══ -->
    {#if activeTab === 'mine'}
      <button onclick={createNewRecipe}
        class="w-full flex items-center justify-center gap-2 bg-amber-700 hover:bg-amber-800 text-white py-2.5 px-4 rounded-lg font-medium transition-colors">
        <Plus class="w-4 h-4" /> Create New Recipe
      </button>

      {#if myRecipes.length === 0}
        <div class="text-center py-12">
          <BookOpen class="w-12 h-12 text-neutral-300 mx-auto mb-3" />
          <p class="text-neutral-600 mb-1">No recipes yet</p>
          <p class="text-sm text-neutral-500">Create your own or clone a community recipe</p>
        </div>
      {:else}
        <div class="space-y-3">
          {#each myRecipes as recipe (recipe.id)}
            <div class="bg-white border border-neutral-200 rounded-lg overflow-hidden">
              <div class="p-4 space-y-2">
                <div class="flex items-start justify-between">
                  <div>
                    <span class="text-xs text-green-600 font-medium">My Recipe</span>
                    <h4 class="font-semibold text-amber-900">{recipe.bean || 'Untitled Recipe'}</h4>
                    <span class="text-xs border border-amber-200 text-amber-800 bg-amber-50 px-2 py-0.5 rounded-full">{recipe.brewMethod}</span>
                  </div>
                  <div class="flex gap-1">
                    <button onclick={() => editMyRecipe(recipe)} class="p-1.5 text-neutral-400 hover:text-amber-700"><Pencil class="w-4 h-4" /></button>
                    <button onclick={() => deleteMyRecipe(recipe.id)} class="p-1.5 text-neutral-400 hover:text-red-500"><Trash2 class="w-4 h-4" /></button>
                  </div>
                </div>
                {#if recipe.description}
                  <p class="text-sm text-neutral-600 line-clamp-2">{recipe.description}</p>
                {/if}
                <div class="grid grid-cols-2 gap-2 text-xs">
                  <div class="flex items-center gap-1.5 text-neutral-600"><Scale class="w-3.5 h-3.5" /><span>{recipe.dose_g}g → {recipe.water_g}g</span></div>
                  <div class="flex items-center gap-1.5 text-neutral-600"><Coffee class="w-3.5 h-3.5" /><span>{recipe.ratio} ratio</span></div>
                  {#if recipe.grindSize}
                    <div class="flex items-center gap-1.5 text-neutral-600"><Droplets class="w-3.5 h-3.5" /><span>{recipe.grindSize}</span></div>
                  {/if}
                  <div class="flex items-center gap-1.5 text-neutral-600"><Thermometer class="w-3.5 h-3.5" /><span>{displayTemp(recipe.waterTemp)}</span></div>
                </div>
                <button
                  onclick={() => { expandedId = expandedId === recipe.id ? null : recipe.id; if (expandedId === recipe.id) initCalc(recipe); }}
                  class="w-full flex items-center justify-center gap-1 bg-neutral-100 hover:bg-neutral-200 text-neutral-700 py-1.5 rounded-lg text-xs font-medium transition-colors mt-1"
                >
                  {expandedId === recipe.id ? 'Hide Details' : 'View & Adjust'}
                  <ChevronDown class="w-3 h-3 transition-transform {expandedId === recipe.id ? 'rotate-180' : ''}" />
                </button>
              </div>

              {#if expandedId === recipe.id}
                <div class="border-t border-neutral-200 bg-amber-50/50 p-4 space-y-4">
                  <!-- Ratio calculator -->
                  <div>
                    <h5 class="text-sm font-semibold text-amber-900 mb-2 flex items-center gap-1.5">
                      <Scale class="w-4 h-4" /> Ratio Calculator
                    </h5>
                    <div class="grid grid-cols-3 gap-2">
                      <div class="bg-white p-3 rounded-lg border border-neutral-200">
                        <label class="text-xs text-neutral-500 block mb-1">Dose (g)</label>
                        <input type="number" class="w-full text-lg font-semibold text-amber-900 bg-transparent outline-none" step="0.1"
                          bind:value={calcDose} oninput={onDoseChange} />
                      </div>
                      <div class="bg-white p-3 rounded-lg border border-neutral-200">
                        <label class="text-xs text-neutral-500 block mb-1">Ratio</label>
                        <div class="flex items-center gap-1">
                          <input type="number" class="w-8 text-lg font-semibold text-amber-900 bg-transparent outline-none text-center" min="1"
                            bind:value={calcRatioNum} oninput={onRatioChange} />
                          <span class="text-neutral-400 font-bold">:</span>
                          <input type="number" class="w-10 text-lg font-semibold text-amber-900 bg-transparent outline-none text-center" min="1"
                            bind:value={calcRatioDen} oninput={onRatioChange} />
                        </div>
                      </div>
                      <div class="bg-white p-3 rounded-lg border border-neutral-200">
                        <label class="text-xs text-neutral-500 block mb-1">Water (g)</label>
                        <input type="number" class="w-full text-lg font-semibold text-amber-900 bg-transparent outline-none" step="0.1"
                          bind:value={calcWater} oninput={onWaterChange} />
                      </div>
                    </div>
                    <p class="text-xs text-neutral-500 mt-1.5 text-center">Adjust any value — the others update automatically</p>
                  </div>
                  {#if recipe.steps.length}
                    <div>
                      <h5 class="text-sm font-semibold text-amber-900 mb-2"><Clock class="w-4 h-4 inline" /> Steps</h5>
                      <div class="space-y-2">
                        {#each recipe.steps as step, i}
                          <div class="flex gap-3 items-start">
                            <div class="flex-shrink-0 w-6 h-6 bg-amber-700 text-white rounded-full flex items-center justify-center text-xs font-bold">{i+1}</div>
                            <div><span class="text-xs font-mono text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded">{step.time}</span>
                              <p class="text-sm text-neutral-700 mt-1">{step.instruction}</p></div>
                          </div>
                        {/each}
                      </div>
                    </div>
                  {/if}
                  {#if recipe.tips.length}
                    <div>
                      <h5 class="text-sm font-semibold text-amber-900 mb-2">💡 Tips</h5>
                      <ul class="space-y-1">{#each recipe.tips as tip}<li class="text-sm text-neutral-600 flex gap-2"><span class="text-amber-500">•</span><span>{tip}</span></li>{/each}</ul>
                    </div>
                  {/if}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    {/if}

    <!-- ═══ COMMUNITY RECIPE LIST ═══ -->
    {#if activeTab !== 'mine'}
      <div class="space-y-3">
        {#each displayed() as recipe (recipe.id)}
          <div class="bg-white border border-neutral-200 rounded-lg hover:border-amber-300 transition-colors overflow-hidden">
            <div class="p-4 space-y-3">
              <div class="flex items-start justify-between">
                <div>
                  <div class="flex items-center gap-2 mb-1">
                    <span class="text-xs text-neutral-500">@{recipe.author}</span>
                    <span class="text-xs border border-amber-200 text-amber-800 bg-amber-50 px-2 py-0.5 rounded-full">{recipe.brewMethod}</span>
                  </div>
                  <h4 class="font-semibold text-amber-900">{recipe.bean}</h4>
                </div>
                <button
                  onclick={() => toggleSave(recipe.id)}
                  class="p-2 {savedIds.has(recipe.id) ? 'text-amber-700' : 'text-neutral-400'} hover:text-amber-600 transition-colors"
                >
                  <Bookmark class="w-4 h-4 {savedIds.has(recipe.id) ? 'fill-current' : ''}" />
                </button>
              </div>
              <p class="text-sm text-neutral-600 line-clamp-2">{recipe.description}</p>
              <div class="grid grid-cols-2 gap-2 text-xs">
                <div class="flex items-center gap-1.5 text-neutral-600"><Droplets class="w-3.5 h-3.5" /><span>{recipe.grindSize}</span></div>
                <div class="flex items-center gap-1.5 text-neutral-600"><Thermometer class="w-3.5 h-3.5" /><span>{displayTemp(recipe.waterTemp)}</span></div>
                <div class="flex items-center gap-1.5 text-neutral-600"><Coffee class="w-3.5 h-3.5" /><span>{recipe.ratio} ratio</span></div>
                <div class="flex items-center gap-1.5 text-neutral-600"><Scale class="w-3.5 h-3.5" /><span>{recipe.dose_g}g → {recipe.water_g}g</span></div>
              </div>
              <div class="flex flex-wrap gap-1.5">
                {#each recipe.tags as tag}
                  <span class="text-xs border border-neutral-200 text-neutral-600 px-2 py-0.5 rounded-full">{tag}</span>
                {/each}
              </div>
              <div class="flex items-center justify-between pt-2 border-t border-neutral-100">
                <div class="flex items-center gap-4 text-sm text-neutral-600">
                  <div class="flex items-center gap-1"><Star class="w-3.5 h-3.5 fill-amber-400 text-amber-400" /><span class="font-semibold">{recipe.rating}</span></div>
                  <div class="flex items-center gap-1"><MessageCircle class="w-3.5 h-3.5" /><span>{recipe.reviews}</span></div>
                  <div class="flex items-center gap-1"><Bookmark class="w-3.5 h-3.5" /><span>{recipe.saves}</span></div>
                </div>
                <div class="flex gap-1.5">
                  <button
                    onclick={() => cloneToMyRecipes(recipe)}
                    class="flex items-center gap-1 border border-amber-300 text-amber-700 hover:bg-amber-50 py-1.5 px-2.5 rounded-lg text-xs font-medium transition-colors"
                  >
                    <Copy class="w-3 h-3" /> Clone
                  </button>
                  <button
                    onclick={() => { expandedId = expandedId === recipe.id ? null : recipe.id; if (expandedId === recipe.id) initCalc(recipe); }}
                    class="flex items-center gap-1 bg-amber-700 hover:bg-amber-800 text-white py-1.5 px-2.5 rounded-lg text-xs font-medium transition-colors"
                  >
                    {expandedId === recipe.id ? 'Hide' : 'Try Recipe'}
                    <ChevronDown class="w-3 h-3 transition-transform {expandedId === recipe.id ? 'rotate-180' : ''}" />
                  </button>
                </div>
              </div>
            </div>

            {#if expandedId === recipe.id}
              <div class="border-t border-neutral-200 bg-amber-50/50 p-4 space-y-4">
                <!-- Ratio calculator -->
                <div>
                  <h5 class="text-sm font-semibold text-amber-900 mb-2 flex items-center gap-1.5">
                    <Scale class="w-4 h-4" /> Ratio Calculator
                  </h5>
                  <div class="grid grid-cols-3 gap-2">
                    <div class="bg-white p-3 rounded-lg border border-neutral-200">
                      <label class="text-xs text-neutral-500 block mb-1">Dose (g)</label>
                      <input type="number" class="w-full text-lg font-semibold text-amber-900 bg-transparent outline-none" step="0.1"
                        bind:value={calcDose} oninput={onDoseChange} />
                    </div>
                    <div class="bg-white p-3 rounded-lg border border-neutral-200">
                      <label class="text-xs text-neutral-500 block mb-1">Ratio</label>
                      <div class="flex items-center gap-1">
                        <input type="number" class="w-8 text-lg font-semibold text-amber-900 bg-transparent outline-none text-center" min="1"
                          bind:value={calcRatioNum} oninput={onRatioChange} />
                        <span class="text-neutral-400 font-bold">:</span>
                        <input type="number" class="w-10 text-lg font-semibold text-amber-900 bg-transparent outline-none text-center" min="1"
                          bind:value={calcRatioDen} oninput={onRatioChange} />
                      </div>
                    </div>
                    <div class="bg-white p-3 rounded-lg border border-neutral-200">
                      <label class="text-xs text-neutral-500 block mb-1">Water (g)</label>
                      <input type="number" class="w-full text-lg font-semibold text-amber-900 bg-transparent outline-none" step="0.1"
                        bind:value={calcWater} oninput={onWaterChange} />
                    </div>
                  </div>
                  <p class="text-xs text-neutral-500 mt-1.5 text-center">Adjust any value — the others update automatically</p>
                </div>
                <div>
                  <h5 class="text-sm font-semibold text-amber-900 mb-2"><Clock class="w-4 h-4 inline" /> Step-by-Step</h5>
                  <div class="space-y-2">
                    {#each recipe.steps as step, i}
                      <div class="flex gap-3 items-start">
                        <div class="flex-shrink-0 w-6 h-6 bg-amber-700 text-white rounded-full flex items-center justify-center text-xs font-bold">{i+1}</div>
                        <div><span class="text-xs font-mono text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded">{step.time}</span>
                          <p class="text-sm text-neutral-700 mt-1">{step.instruction}</p></div>
                      </div>
                    {/each}
                  </div>
                </div>
                {#if recipe.tips.length}
                  <div>
                    <h5 class="text-sm font-semibold text-amber-900 mb-2">💡 Pro Tips</h5>
                    <ul class="space-y-1.5">{#each recipe.tips as tip}<li class="text-sm text-neutral-600 flex items-start gap-2"><span class="text-amber-500 mt-0.5">•</span><span>{tip}</span></li>{/each}</ul>
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {/each}

        {#if displayed().length === 0}
          <div class="text-center py-12">
            {#if activeTab === 'saved'}
              <Bookmark class="w-12 h-12 text-neutral-300 mx-auto mb-3" />
              <p class="text-neutral-600 mb-1">No saved recipes yet</p>
              <p class="text-sm text-neutral-500">Tap the bookmark icon to save recipes</p>
            {:else}
              <Search class="w-12 h-12 text-neutral-300 mx-auto mb-3" />
              <p class="text-neutral-600 mb-1">No recipes found</p>
              <p class="text-sm text-neutral-500">Try a different search term</p>
            {/if}
          </div>
        {/if}
      </div>
    {/if}
  </div>

  <!-- ═══ RECIPE EDITOR MODAL ═══ -->
  {#if showEditor && editingRecipe}
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="fixed inset-0 bg-black/50 z-50 flex items-end justify-center" onclick={() => { showEditor = false; editingRecipe = null; }}>
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="bg-white rounded-t-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-5 pb-24 space-y-4" onclick={(e) => e.stopPropagation()}>
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-bold text-amber-900">{editingRecipe.id.startsWith('my-') && myRecipes.some(r => r.id === editingRecipe?.id) ? 'Edit' : 'New'} Recipe</h3>
          <button onclick={() => { showEditor = false; editingRecipe = null; }} class="p-1 text-neutral-400 hover:text-neutral-700"><X class="w-5 h-5" /></button>
        </div>

        <div class="space-y-3">
          <div>
            <label class="block text-xs font-medium text-neutral-500 mb-1">Coffee Bean</label>
            <input bind:value={editingRecipe.bean} placeholder="e.g., Ethiopian Yirgacheffe"
              class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-neutral-500 mb-1">Brew Method</label>
              <select bind:value={editingRecipe.brewMethod} class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500">
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
              <input bind:value={editingRecipe.grindSize} placeholder="e.g., Medium-Fine (650μm)"
                class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
            </div>
          </div>

          <!-- Ratio Calculator in Editor -->
          <div class="bg-amber-50 p-3 rounded-lg border border-amber-200">
            <label class="block text-xs font-semibold text-amber-900 mb-2">⚖️ Ratio Calculator</label>
            <div class="grid grid-cols-3 gap-2">
              <div>
                <label class="text-xs text-neutral-500">Dose (g)</label>
                <input type="number" step="0.1" bind:value={editingRecipe.dose_g} class="w-full border border-neutral-200 rounded px-2 py-1.5 text-sm font-semibold focus:ring-2 focus:ring-amber-500"
                  oninput={() => { calcDose = editingRecipe!.dose_g; const [n,d] = parseRatio(editingRecipe!.ratio); editingRecipe!.water_g = Math.round(editingRecipe!.dose_g * d/n * 10)/10; }} />
              </div>
              <div>
                <label class="text-xs text-neutral-500">Ratio</label>
                <input bind:value={editingRecipe.ratio} placeholder="1:16" class="w-full border border-neutral-200 rounded px-2 py-1.5 text-sm font-semibold text-center focus:ring-2 focus:ring-amber-500"
                  oninput={() => { const [n,d] = parseRatio(editingRecipe!.ratio); editingRecipe!.water_g = Math.round(editingRecipe!.dose_g * d/n * 10)/10; }} />
              </div>
              <div>
                <label class="text-xs text-neutral-500">Water (g)</label>
                <input type="number" step="0.1" bind:value={editingRecipe.water_g} class="w-full border border-neutral-200 rounded px-2 py-1.5 text-sm font-semibold focus:ring-2 focus:ring-amber-500"
                  oninput={() => { const [n,d] = parseRatio(editingRecipe!.ratio); editingRecipe!.dose_g = Math.round(editingRecipe!.water_g / (d/n) * 10)/10; }} />
              </div>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-neutral-500 mb-1">Water Temp ({displayTempUnit()})</label>
              <input type="number" bind:value={editingRecipe.waterTemp} class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
            </div>
            <div>
              <label class="block text-xs font-medium text-neutral-500 mb-1">Brew Time</label>
              <input bind:value={editingRecipe.brewTime} placeholder="3:30" class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
            </div>
          </div>

          <div>
            <label class="block text-xs font-medium text-neutral-500 mb-1">Description</label>
            <textarea bind:value={editingRecipe.description} rows={2} placeholder="Describe your recipe..."
              class="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 resize-none"></textarea>
          </div>

          <!-- Steps -->
          <div>
            <div class="flex items-center justify-between mb-1">
              <label class="text-xs font-medium text-neutral-500">Steps</label>
              <button onclick={addStep} class="text-xs text-amber-700 hover:text-amber-900 font-medium">+ Add Step</button>
            </div>
            {#each editingRecipe.steps as step, i}
              <div class="flex gap-2 mb-2 items-start">
                <input bind:value={step.time} placeholder="0:00" class="w-16 border border-neutral-200 rounded px-2 py-1.5 text-xs focus:ring-2 focus:ring-amber-500" />
                <input bind:value={step.instruction} placeholder="What to do..." class="flex-1 border border-neutral-200 rounded px-2 py-1.5 text-xs focus:ring-2 focus:ring-amber-500" />
                {#if editingRecipe.steps.length > 1}
                  <button onclick={() => removeStep(i)} class="text-red-400 hover:text-red-600 p-1"><X class="w-3 h-3" /></button>
                {/if}
              </div>
            {/each}
          </div>

          <!-- Tips -->
          <div>
            <div class="flex items-center justify-between mb-1">
              <label class="text-xs font-medium text-neutral-500">Tips</label>
              <button onclick={addTip} class="text-xs text-amber-700 hover:text-amber-900 font-medium">+ Add Tip</button>
            </div>
            {#each editingRecipe.tips as tip, i}
              <input bind:value={editingRecipe.tips[i]} placeholder="Pro tip..." class="w-full border border-neutral-200 rounded px-2 py-1.5 text-xs mb-2 focus:ring-2 focus:ring-amber-500" />
            {/each}
          </div>
        </div>

        <div class="flex gap-2 pt-2">
          <button onclick={() => { showEditor = false; editingRecipe = null; }}
            class="flex-1 flex items-center justify-center gap-1.5 border border-neutral-300 text-neutral-600 py-2.5 px-3 rounded-lg text-sm font-medium hover:bg-neutral-100 transition-colors">
            <X class="w-4 h-4" /> Cancel
          </button>
          <button onclick={saveRecipe}
            class="flex-1 flex items-center justify-center gap-1.5 bg-amber-700 hover:bg-amber-800 text-white py-2.5 px-3 rounded-lg text-sm font-medium transition-colors">
            <Save class="w-4 h-4" /> Save Recipe
          </button>
        </div>
      </div>
    </div>
  {/if}
</PageLayout>
