<script lang="ts">
  import PageLayout from '$lib/components/PageLayout.svelte';
  import { Search, TrendingUp, Star, MessageCircle, Bookmark, Coffee, Droplets, Thermometer, Users } from 'lucide-svelte';

  interface Recipe {
    id: string; author: string; bean: string; brewMethod: string; grindSize: string;
    waterTemp: number; ratio: string; brewTime: string; rating: number;
    reviews: number; saves: number; description: string; tags: string[];
  }

  let searchQuery = $state('');
  let activeTab = $state('trending');
  let savedIds = $state<Set<string>>(new Set());

  const recipes: Recipe[] = [
    { id: '1', author: 'CoffeeNerd42', bean: 'Ethiopian Yirgacheffe', brewMethod: 'Pour Over', grindSize: 'Medium-Fine (650μm)', waterTemp: 96, ratio: '1:16', brewTime: '3:30', rating: 4.8, reviews: 124, saves: 89, description: 'Perfect pour over recipe for bright, floral Ethiopian beans. The key is the bloom phase.', tags: ['Floral', 'Bright', 'Beginner-Friendly'] },
    { id: '2', author: 'BaristaBob', bean: 'Colombian Supremo', brewMethod: 'French Press', grindSize: 'Coarse (800μm)', waterTemp: 93, ratio: '1:15', brewTime: '4:00', rating: 4.6, reviews: 87, saves: 56, description: "Classic French press method that highlights the chocolatey notes. Don't skip the pre-warm step!", tags: ['Chocolate', 'Full-Body', 'Easy'] },
    { id: '3', author: 'EspressoExpert', bean: 'Italian Roast Blend', brewMethod: 'Espresso', grindSize: 'Fine (380μm)', waterTemp: 94, ratio: '1:2', brewTime: '0:28', rating: 4.9, reviews: 203, saves: 145, description: 'Competition-style espresso shot. Dial in your grinder carefully.', tags: ['Bold', 'Creamy', 'Advanced'] },
    { id: '4', author: 'HomeBrewHero', bean: 'Guatemala Antigua', brewMethod: 'AeroPress', grindSize: 'Medium-Fine (600μm)', waterTemp: 85, ratio: '1:14', brewTime: '2:30', rating: 4.7, reviews: 156, saves: 112, description: 'Inverted method for a smooth, sweet cup. Lower temp brings out the caramel sweetness.', tags: ['Sweet', 'Smooth', 'Versatile'] },
  ];

  let displayed = $derived(
    activeTab === 'top' ? [...recipes].sort((a, b) => b.rating - a.rating) : recipes
  );
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
    <div class="grid grid-cols-3 bg-neutral-100 rounded-lg p-1 gap-1">
      {#each [['trending', TrendingUp, 'Trending'], ['top', Star, 'Top Rated'], ['saved', Bookmark, 'Saved']] as [tab, Icon, label]}
        <button
          onclick={() => (activeTab = tab)}
          class="flex items-center justify-center gap-1.5 py-1.5 text-sm rounded-md transition-colors {activeTab === tab ? 'bg-white text-neutral-900 shadow-sm' : 'text-neutral-600 hover:text-neutral-900'}"
        >
          <svelte:component this={Icon} class="w-3.5 h-3.5" />{label}
        </button>
      {/each}
    </div>

    <!-- Recipe List -->
    {#if activeTab === 'saved'}
      <div class="text-center py-12">
        <Bookmark class="w-12 h-12 text-neutral-300 mx-auto mb-3" />
        <p class="text-neutral-600 mb-1">No saved recipes yet</p>
        <p class="text-sm text-neutral-500">Bookmark recipes to find them here</p>
      </div>
    {:else}
      <div class="space-y-3">
        {#each displayed as recipe (recipe.id)}
          <div class="p-4 bg-white border border-neutral-200 rounded-lg hover:border-amber-300 transition-colors space-y-3">
            <div class="flex items-start justify-between">
              <div>
                <div class="flex items-center gap-2 mb-1">
                  <span class="text-xs text-neutral-500">@{recipe.author}</span>
                  <span class="text-xs border border-amber-200 text-amber-800 bg-amber-50 px-2 py-0.5 rounded-full">{recipe.brewMethod}</span>
                </div>
                <h4 class="font-semibold text-amber-900">{recipe.bean}</h4>
              </div>
              <button
                onclick={() => { const s = new Set(savedIds); s.has(recipe.id) ? s.delete(recipe.id) : s.add(recipe.id); savedIds = s; }}
                class="p-2 {savedIds.has(recipe.id) ? 'text-amber-700' : 'text-neutral-400'} hover:text-amber-600 transition-colors"
              >
                <Bookmark class="w-4 h-4 {savedIds.has(recipe.id) ? 'fill-current' : ''}" />
              </button>
            </div>
            <p class="text-sm text-neutral-600 line-clamp-2">{recipe.description}</p>
            <div class="grid grid-cols-2 gap-2 text-xs">
              <div class="flex items-center gap-1.5 text-neutral-600"><Droplets class="w-3.5 h-3.5" /><span>{recipe.grindSize}</span></div>
              <div class="flex items-center gap-1.5 text-neutral-600"><Thermometer class="w-3.5 h-3.5" /><span>{recipe.waterTemp}°C</span></div>
              <div class="flex items-center gap-1.5 text-neutral-600"><Coffee class="w-3.5 h-3.5" /><span>{recipe.ratio} ratio</span></div>
              <div class="flex items-center gap-1.5 text-neutral-600"><span class="font-medium">{recipe.brewTime}</span></div>
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
              <button class="bg-amber-700 hover:bg-amber-800 text-white py-1.5 px-3 rounded-lg text-xs font-medium transition-colors">
                Try Recipe
              </button>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</PageLayout>
