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
      <router-view />
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
          name="pagamenti"
          icon="receipt_long"
          label="Pagamenti"
          to="/i/pagamenti"
        />
        <q-route-tab name="profilo" icon="person" label="Profilo" to="/i/profilo" />
      </q-tabs>
    </q-footer>
  </q-layout>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from 'stores/auth';

const auth = useAuthStore();
const router = useRouter();
const activeTab = ref<string>('home');

async function logout() {
  await auth.logout();
  await router.replace('/login');
}
</script>

<style scoped>
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
