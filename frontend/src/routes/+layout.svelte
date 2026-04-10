<script lang="ts">
  import '../app.css';
  import BottomNav from '$lib/components/BottomNav.svelte';

  let { children } = $props();
</script>

<div class="min-h-screen bg-neutral-50 pb-20">
  {@render children()}
  <BottomNav />
</div>
