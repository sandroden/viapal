<template>
  <q-page padding class="vp-i-pagamenti">
    <div class="vp-eyebrow">Storico</div>
    <h1 class="vp-display vp-i-pagamenti__titolo">I tuoi pagamenti</h1>

    <div v-if="loading" class="vp-i-pagamenti__loader">
      <q-spinner color="primary" size="32px" />
    </div>

    <EmptyState
      v-else-if="pagamenti.length === 0"
      icon="receipt_long"
      title="Storico vuoto"
      message="Non risulta ancora alcun pagamento dichiarato o confermato."
    />

    <q-list v-else bordered separator class="vp-i-pagamenti__lista">
      <q-item v-for="p in pagamenti" :key="`${p.tipo}-${p.id}`">
        <q-item-section avatar>
          <q-icon :name="iconaPer(p.tipo)" color="primary" />
        </q-item-section>
        <q-item-section>
          <q-item-label>{{ p.descrizione }}</q-item-label>
          <q-item-label caption>
            {{ formattaData(p.data_pagamento) }}
          </q-item-label>
        </q-item-section>
        <q-item-section side>
          <div class="vp-mono">{{ formattaEuro(p.importo) }}</div>
          <SemaforoBadge :livello="livelloPer(p.stato)" :label="labelPer(p.stato)" />
        </q-item-section>
      </q-item>
    </q-list>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useDashboardStore } from 'stores/dashboard';
import EmptyState from 'src/components/EmptyState.vue';
import SemaforoBadge, { type SemaforoLivello } from 'src/components/SemaforoBadge.vue';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';

const store = useDashboardStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();
const loading = ref(false);

const pagamenti = computed(() => store.inquilinoData?.ultimi_pagamenti ?? []);

onMounted(async () => {
  loading.value = true;
  try {
    await store.loadInquilino();
  } finally {
    loading.value = false;
  }
});

function iconaPer(tipo: string): string {
  if (tipo === 'rent') return 'home';
  if (tipo === 'utility_charge') return 'bolt';
  return 'note_add';
}

function livelloPer(stato: string): SemaforoLivello {
  if (stato === 'pagato') return 'salvia';
  if (stato === 'dichiarato') return 'miele';
  return 'argilla_chiaro';
}

function labelPer(stato: string): string {
  if (stato === 'pagato') return 'Pagato';
  if (stato === 'dichiarato') return 'Dichiarato';
  return stato;
}
</script>

<style scoped>
.vp-i-pagamenti {
  max-width: 640px;
  margin: 0 auto;
}
.vp-i-pagamenti__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 var(--vp-gap-4);
}
.vp-i-pagamenti__lista {
  background: var(--vp-cream);
  border-radius: var(--vp-r-lg);
  border-color: var(--vp-paper-3) !important;
  overflow: hidden;
}
.vp-i-pagamenti__loader {
  display: flex;
  justify-content: center;
  padding: var(--vp-gap-6);
}
</style>
