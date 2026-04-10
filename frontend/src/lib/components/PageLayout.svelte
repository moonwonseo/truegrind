<script lang="ts">
  let { children, title = '' }: { children: any; title?: string } = $props();
</script>

{#if title}
  <header class="bg-white border-b border-neutral-200 sticky top-0 z-40">
    <div class="max-w-md mx-auto px-4 py-4">
      <h1 class="text-amber-900 font-semibold">{title}</h1>
    </div>
  </header>
{/if}
<main class="max-w-md mx-auto px-4 py-6">
  {@render children()}
</main>
