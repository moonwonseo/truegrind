<script lang="ts">
  import { getTheme, toggleTheme } from '$lib/themeStore.svelte';
  import { Sun, Moon } from 'lucide-svelte';

  let { children, title = '' }: { children: any; title?: string } = $props();
  let theme = $derived(getTheme());
</script>

{#if title}
  <header style="background-color: var(--surface); border-bottom: 1px solid var(--border);" class="sticky top-0 z-40">
    <div class="max-w-md mx-auto px-4 py-4 flex items-center justify-between">
      <h1 style="color: var(--text-secondary);" class="font-semibold">{title}</h1>
      <button onclick={toggleTheme} class="p-2 rounded-lg transition-colors" style="color: var(--text-muted); background: var(--surface2);" aria-label="Toggle theme">
        {#if theme === 'dark'}
          <Sun class="w-4 h-4" />
        {:else}
          <Moon class="w-4 h-4" />
        {/if}
      </button>
    </div>
  </header>
{/if}
<main class="max-w-md mx-auto px-4 py-6">
  {@render children()}
</main>
