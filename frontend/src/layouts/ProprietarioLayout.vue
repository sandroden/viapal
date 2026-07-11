<template>
  <q-layout view="hHh LpR fFf">
    <q-header elevated class="vp-header">
      <q-toolbar>
        <q-btn flat dense round icon="menu" aria-label="Menu" @click="toggleDrawer" />
        <img
          v-if="!drawerOpen"
          src="/viapal.png"
          alt="Viapal"
          class="vp-header__logo"
        />
        <q-toolbar-title class="text-display">
          Viapal — area proprietari
        </q-toolbar-title>
        <q-space />

        <!-- Switcher immobile: visibile solo con più di un immobile.
             Con un immobile solo l'app resta identica a prima. -->
        <q-btn-dropdown
          v-if="propStore.hasMultiple"
          flat
          dense
          no-caps
          icon="home_work"
          :label="propStore.activeProperty?.nome ?? 'Immobile'"
          class="vp-property-switcher"
          data-testid="property-switcher"
        >
          <q-list>
            <q-item
              v-for="p in propStore.properties"
              :key="p.id"
              v-close-popup
              clickable
              :active="p.id === propStore.activePropertyId"
              @click="propStore.cambia(p.id)"
            >
              <q-item-section avatar>
                <q-icon :name="p.id === propStore.activePropertyId ? 'radio_button_checked' : 'radio_button_unchecked'" />
              </q-item-section>
              <q-item-section>
                <q-item-label>{{ p.nome }}</q-item-label>
                <q-item-label caption>{{ etichettaRuolo(p.ruolo) }}</q-item-label>
              </q-item-section>
            </q-item>
            <q-separator />
            <q-item v-close-popup clickable to="/p/proprieta/nuova">
              <q-item-section avatar><q-icon name="add_home" /></q-item-section>
              <q-item-section>Nuova proprietà…</q-item-section>
            </q-item>
          </q-list>
        </q-btn-dropdown>
        <q-chip
          v-if="propStore.mioRuolo && propStore.mioRuolo !== 'proprietario'"
          dense
          outline
          class="vp-user-chip"
          data-testid="ruolo-badge"
        >
          {{ etichettaRuolo(propStore.mioRuolo) }}
        </q-chip>

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
      <div class="vp-drawer__brand">
        <img src="/viapal.png" alt="Viapal" class="vp-drawer__brand-img" />
      </div>

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
import { useAuthStore, type RuoloProperty } from 'stores/auth';
import { usePropertiesStore } from 'stores/properties';

const auth = useAuthStore();
const propStore = usePropertiesStore();
const router = useRouter();
const drawerOpen = ref(true);

function etichettaRuolo(ruolo: RuoloProperty | null): string {
  if (ruolo === 'proprietario') return 'Proprietario';
  if (ruolo === 'gestore') return 'Gestore';
  if (ruolo === 'sola_lettura') return 'Sola lettura';
  return '';
}

const vociMenu = [
  { to: '/p/', label: 'Dashboard', icon: 'dashboard' },
  { to: '/p/ritardi', label: 'Ritardi', icon: 'warning_amber' },
  { to: '/p/inquilini', label: 'Inquilini', icon: 'group' },
  { to: '/p/quadro-annuale', label: 'Quadro annuale', icon: 'table_view' },
  { to: '/p/spese', label: 'Spese', icon: 'shopping_cart' },
  { to: '/p/utenze', label: 'Utenze', icon: 'bolt' },
  { to: '/p/riconciliazione', label: 'Riconciliazione', icon: 'compare_arrows' },
  { to: '/p/saldi-fratelli', label: 'Saldi fratelli', icon: 'account_balance' },
  { to: '/p/conto-economico', label: 'Conto economico', icon: 'assessment' },
  { to: '/p/quick-add', label: 'Aggiungi rapida', icon: 'add_circle' },
  { to: '/p/impostazioni/proprieta', label: 'Immobile', icon: 'home_work' },
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
.vp-header__logo {
  height: 32px;
  width: auto;
  margin-left: var(--vp-gap-2);
  border-radius: var(--vp-r-sm);
  background: var(--vp-cream);
  padding: 2px;
}
.vp-user-chip {
  color: var(--vp-cream);
  border-color: var(--vp-cream);
}
.vp-property-switcher {
  color: var(--vp-cream);
  margin-right: var(--vp-gap-2);
}
.vp-drawer {
  background: var(--vp-paper-2);
  border-right: 1px solid var(--vp-paper-3);
}
.vp-drawer__brand {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: var(--vp-gap-4) var(--vp-gap-3);
  border-bottom: 1px solid var(--vp-paper-3);
}
.vp-drawer__brand-img {
  width: 100%;
  max-width: 180px;
  height: auto;
  display: block;
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
