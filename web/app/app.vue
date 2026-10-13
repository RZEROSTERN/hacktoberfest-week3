<template>
  <div class="shell">
    <header>
      <NuxtLink
        to="/"
        class="brand"
      >
        Scopewise
      </NuxtLink>
      <nav aria-label="Main">
        <NuxtLink to="/">
          Calls
        </NuxtLink>
        <NuxtLink to="/profile">
          Profile
        </NuxtLink>
        <NuxtLink to="/settings">
          Settings
        </NuxtLink>
      </nav>
    </header>
    <NuxtRouteAnnouncer />
    <main>
      <NuxtPage />
    </main>
  </div>
</template>
