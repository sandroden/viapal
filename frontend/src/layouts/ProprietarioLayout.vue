<template>
  <q-layout view="hHh LpR fFf">
    <q-header elevated class="vp-header">
      <q-toolbar>
        <q-btn flat dense round icon="menu" aria-label="Menu" @click="toggleDrawer" />
        <q-toolbar-title class="text-display">
          Viapal — area proprietari
        </q-toolbar-title>
        <q-space />
        <q-chip dense outline class="vp-user-chip">
          {{ auth.user?.first_name || auth.user?.username }}
        </q-chip>
        <q-btn flat dense icon="logout" aria-label="Esci" @click="logout" />
      </q-toolbar>
    </q-header>

    <q-drawer
      v-model="drawerOpen"
      show-if-above
      :width="240"
      :breakpoint="900"
      class="vp-drawer"
    >
      <q-list padding>
        <q-item-label header class="vp-drawer__header">Navigazione</q-item-label>

        <q-item
          v-for="voce in vociMenu"
          :key="voce.to"
          v-ripple
          clickable
          :to="voce.to"
          exact
          class="vp-drawer__item"
        >
          <q-item-section avatar>
            <q-icon :name="voce.icon" />
          </q-item-section>
          <q-item-section>{{ voce.label }}</q-item-section>
        </q-item>
      </q-list>
    </q-drawer>

    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from 'stores/auth';

const auth = useAuthStore();
const router = useRouter();
const drawerOpen = ref(true);

const vociMenu = [
  { to: '/p/', label: 'Dashboard', icon: 'dashboard' },
  { to: '/p/ritardi', label: 'Ritardi', icon: 'warning_amber' },
  { to: '/p/inquilini', label: 'Inquilini', icon: 'group' },
  { to: '/p/quadro-annuale', label: 'Quadro annuale', icon: 'table_view' },
  { to: '/p/spese', label: 'Spese', icon: 'shopping_cart' },
  { to: '/p/quick-add', label: 'Aggiungi rapida', icon: 'add_circle' },
];

function toggleDrawer() {
  drawerOpen.value = !drawerOpen.value;
}

async function logout() {
  await auth.logout();
  await router.replace('/login');
}
</script>

<style scoped>
.vp-header {
  background: var(--vp-terra-deep);
  color: var(--vp-cream);
}
.vp-user-chip {
  color: var(--vp-cream);
  border-color: var(--vp-cream);
}
.vp-drawer {
  background: var(--vp-paper-2);
  border-right: 1px solid var(--vp-paper-3);
}
.vp-drawer__header {
  color: var(--vp-ink-3);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.vp-drawer__item {
  border-radius: var(--vp-r-md);
  margin: 2px 8px;
  color: var(--vp-ink-2);
  min-height: 44px;
}
.vp-drawer__item.q-router-link--exact-active {
  background: var(--vp-terra-soft);
  color: var(--vp-terra-deep);
  font-weight: 500;
}
</style>
