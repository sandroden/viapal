<template>
  <q-layout view="hHh Lpr fFf">
    <q-header elevated class="vp-header">
      <q-toolbar>
        <q-toolbar-title class="text-display">Viapal</q-toolbar-title>
        <q-space />
        <q-btn flat dense icon="logout" aria-label="Esci" @click="logout" />
      </q-toolbar>
    </q-header>

    <q-page-container>
      <div class="vp-i-shell" :class="{ 'vp-i-shell--wide': isWide }">
        <router-view />
      </div>
    </q-page-container>

    <q-footer class="vp-bottom-nav">
      <q-tabs
        v-model="activeTab"
        align="justify"
        active-color="primary"
        indicator-color="transparent"
        no-caps
        narrow-indicator
      >
        <q-route-tab name="home" icon="home" label="Home" to="/i/" exact />
        <q-route-tab
          name="situazione"
          icon="account_balance"
          label="Situazione"
          to="/i/situazione"
        />
        <q-route-tab
          name="rendiconto"
          icon="description"
          label="Rendiconto"
          to="/i/rendiconto"
        />
        <q-route-tab name="utenze" icon="bolt" label="Utenze" to="/i/utenze" />
        <q-route-tab name="profilo" icon="person" label="Profilo" to="/i/profilo" />
      </q-tabs>
    </q-footer>
  </q-layout>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from 'stores/auth';

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();
const activeTab = ref<string>('home');

// Pagine "documento" (es. rendiconto): più larghe del cap app-like.
const isWide = computed(() => route.meta.wide === true);

async function logout() {
  await auth.logout();
  await router.replace('/login');
}
</script>

<style scoped>
.vp-i-shell {
  max-width: 760px;
  margin: 0 auto;
  width: 100%;
}
/* Documenti tabellari larghi (rendiconto): stessa leggibilità della vista
   proprietario, senza il cap stretto pensato per le card app-like. */
.vp-i-shell--wide {
  max-width: 960px;
}
.vp-header {
  background: var(--vp-sage-deep);
  color: var(--vp-cream);
}
.vp-bottom-nav {
  background: var(--vp-cream);
  color: var(--vp-ink);
  border-top: 1px solid var(--vp-paper-3);
  box-shadow: 0 -2px 6px oklch(0.30 0.02 50 / 0.06);
}
.vp-bottom-nav :deep(.q-tab) {
  color: var(--vp-ink-3);
  min-height: 56px;
  font-size: 11px;
}
.vp-bottom-nav :deep(.q-tab--active) {
  color: var(--vp-terra-deep);
}
</style>
