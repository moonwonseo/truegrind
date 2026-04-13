<script lang="ts">
  import '../app.css';
  import BottomNav from '$lib/components/BottomNav.svelte';
  import { initTheme } from '$lib/themeStore.svelte';
  import { onMount } from 'svelte';

  let { children } = $props();

  onMount(() => {
    initTheme();
  });
</script>

<div class="min-h-screen pb-20" style="background-color: var(--bg); color: var(--text);">
  {@render children()}
  <BottomNav />
</div>
