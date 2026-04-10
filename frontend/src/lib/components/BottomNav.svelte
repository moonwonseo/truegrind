<script lang="ts">
  import { page } from '$app/stores';
  import { Camera, BookOpen, Users, User } from 'lucide-svelte';

  const navItems = [
    { path: '/', icon: Camera, label: 'Analyze' },
    { path: '/journal', icon: BookOpen, label: 'Journal' },
    { path: '/community', icon: Users, label: 'Community' },
    { path: '/profile', icon: User, label: 'Profile' },
  ];
</script>

<nav class="fixed bottom-0 left-0 right-0 bg-white border-t border-neutral-200 z-50">
  <div class="max-w-md mx-auto flex justify-around items-center h-16">
    {#each navItems as item}
      {@const isActive = $page.url.pathname === item.path}
      <a
        href={item.path}
        class="flex flex-col items-center justify-center flex-1 h-full transition-colors {isActive ? 'text-amber-700' : 'text-neutral-500 hover:text-neutral-700'}"
      >
        <svelte:component this={item.icon} class="w-6 h-6 mb-1" />
        <span class="text-xs">{item.label}</span>
      </a>
    {/each}
  </div>
</nav>
