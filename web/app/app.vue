<template>
  <div class="shell">
    <header>
      <NuxtLink
        to="/"
        class="brand"
      >
        PostCall
      </NuxtLink>
      <nav :aria-label="$t('nav.main')">
        <NuxtLink to="/">
          {{ $t('nav.calls') }}
        </NuxtLink>
        <NuxtLink to="/profile">
          {{ $t('nav.profile') }}
        </NuxtLink>
        <NuxtLink to="/settings">
          {{ $t('nav.settings') }}
        </NuxtLink>
      </nav>
      <LanguageSwitcher />
    </header>
    <NuxtRouteAnnouncer />
    <main>
      <NuxtPage />
    </main>
    <footer>
      <NuxtLink to="/notices">
        {{ $t('nav.notices') }}
      </NuxtLink>
    </footer>
  </div>
</template>
