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
        <template v-for="(sezione, i) in sezioniMenu" :key="sezione.label ?? i">
          <!-- Le sezioni senza header (es. Immobile in coda) vanno comunque
               staccate visivamente da quella precedente. -->
          <q-separator v-if="!sezione.label && i > 0" spaced />
          <q-item-label v-if="sezione.label" header class="vp-drawer__header">
            {{ sezione.label }}
          </q-item-label>

          <q-item
            v-for="voce in sezione.voci"
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
        </template>

        <!-- Scorciatoia amministrativa: solo superuser, e fuori dal menu di
             dominio perché porta altrove (Django, non la SPA). -->
        <template v-if="auth.isSuperuser">
          <q-separator class="vp-drawer__sep" />
          <q-item
            v-ripple
            clickable
            type="a"
            href="/admin/"
            class="vp-drawer__item"
            data-testid="link-admin"
          >
            <q-item-section avatar>
              <q-icon name="admin_panel_settings" />
            </q-item-section>
            <q-item-section>Admin Django</q-item-section>
          </q-item>
        </template>
      </q-list>
    </q-drawer>

    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from 'stores/auth';
import { etichettaRuolo, usePropertiesStore } from 'stores/properties';

const auth = useAuthStore();
const propStore = usePropertiesStore();
const router = useRouter();
const drawerOpen = ref(true);
const galleriaSlug = ref<string | null>(null);

interface VoceMenu {
  to: string;
  label: string;
  icon: string;
}

interface SezioneMenu {
  label: string | null;
  voci: VoceMenu[];
}

// Sezioni per ambito contabile: lato inquilini (incassi) e lato
// proprietari (uscite e conti tra loro), più l'immobile.
const sezioniMenu = computed<SezioneMenu[]>(() => {
  // Un'unica pagina a tab per tutto l'immobile: la voce si chiama come la
  // pagina, quindi la sezione non ripete l'header "Immobile".
  const immobile: VoceMenu[] = [
    { to: '/p/impostazioni', label: 'Immobile', icon: 'home_work' },
  ];
  if (galleriaSlug.value) {
    immobile.push({
      to: `/g/${galleriaSlug.value}`,
      label: 'Galleria annuncio',
      icon: 'photo_library',
    });
  }
  return [
    {
      label: null,
      voci: [{ to: '/p/', label: 'Dashboard', icon: 'dashboard' }],
    },
    {
      label: 'Inquilini',
      voci: [
        { to: '/p/inquilini', label: 'Inquilini', icon: 'group' },
        { to: '/p/cerca-inquilini', label: 'Cerca inquilini', icon: 'person_search' },
        { to: '/p/ritardi', label: 'Ritardi', icon: 'warning_amber' },
        { to: '/p/notifiche', label: 'Notifiche addebiti', icon: 'mark_email_read' },
        { to: '/p/utenze', label: 'Utenze', icon: 'bolt' },
        { to: '/p/riconciliazione', label: 'Riconciliazione', icon: 'compare_arrows' },
      ],
    },
    {
      label: 'Proprietari',
      voci: [
        { to: '/p/spese', label: 'Spese', icon: 'shopping_cart' },
        { to: '/p/saldi-proprietari', label: 'Saldi proprietari', icon: 'account_balance' },
        { to: '/p/conto-economico', label: 'Conto economico', icon: 'assessment' },
      ],
    },
    { label: null, voci: immobile },
  ];
});

// Slug della galleria dell'immobile ATTIVO (multiproprietà: mai list[0]).
onMounted(async () => {
  const id = propStore.activePropertyId;
  if (!id) return;
  try {
    const dettaglio = await propStore.caricaDettaglio(id);
    galleriaSlug.value = dettaglio.slug ?? null;
  } catch {
    galleriaSlug.value = null;
  }
});

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
.vp-drawer__sep {
  margin: var(--vp-gap-2) var(--vp-gap-3);
  background: var(--vp-paper-3);
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
