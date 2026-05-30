<template>
  <q-page padding class="vp-i-home">
    <header class="vp-i-home__hero">
      <div class="vp-eyebrow">La tua casa</div>
      <h1 class="vp-display vp-i-home__titolo">
        Ciao, {{ saluto }}
      </h1>
      <p v-if="stanzaCorrente" class="vp-i-home__sottotitolo">
        Stanza «{{ stanzaCorrente.nome }}» — canone
        {{ formattaEuro(stanzaCorrente.canone_mensile) }}/mese
      </p>
      <p v-else class="vp-i-home__sottotitolo">
        Nessuna stanza assegnata in questo momento.
      </p>
    </header>

    <section class="vp-i-home__section">
      <div class="vp-i-home__section-head">
        <div>
          <div class="vp-eyebrow">Da pagare</div>
          <h2 class="vp-display vp-i-home__h2">
            {{ daPagare.length }}
            {{ daPagare.length === 1 ? 'pagamento' : 'pagamenti' }} aperti
          </h2>
          <p v-if="numParziali > 0" class="vp-i-home__nota-parziali">
            di cui {{ numParziali }} {{ numParziali === 1 ? 'già pagato' : 'già pagati' }} in parte
          </p>
        </div>
        <q-btn
          flat
          icon="refresh"
          color="primary"
          :loading="store.loadingInquilino"
          @click="ricarica"
          aria-label="Ricarica"
        />
      </div>

      <div v-if="store.loadingInquilino && daPagare.length === 0" class="vp-i-home__loader">
        <q-spinner color="primary" size="32px" />
      </div>

      <div v-else-if="daPagare.length === 0">
        <EmptyState
          icon="check_circle"
          title="Tutto in regola"
          message="Quando ci sarà un affitto o un'utenza da saldare, lo vedrai qui."
        />
      </div>

      <div v-else class="vp-i-home__lista">
        <PagamentoCard v-for="item in daPagare" :key="`${item.tipo}-${item.id}`" :item="item" />
      </div>
    </section>

    <section class="vp-i-home__section">
      <div class="vp-i-home__section-head">
        <div>
          <div class="vp-eyebrow">Da ricevere</div>
          <h2 class="vp-display vp-i-home__h2">Ultimi pagamenti</h2>
        </div>
        <q-btn flat color="primary" label="Storico" to="/i/pagamenti" no-caps />
      </div>

      <div v-if="ultimiPagamenti.length === 0">
        <EmptyState
          icon="history"
          title="Nessun pagamento registrato"
          message="Quando dichiarerai un pagamento, comparirà qui."
        />
      </div>

      <q-list v-else class="vp-i-home__storico" bordered separator>
        <q-item v-for="p in ultimiPagamenti" :key="`${p.tipo}-${p.id}`">
          <q-item-section>
            <q-item-label>{{ p.descrizione }}</q-item-label>
            <q-item-label caption>
              {{ formattaData(p.data_pagamento) }} ·
              <span class="vp-mono">{{ formattaEuro(p.importo) }}</span>
            </q-item-label>
          </q-item-section>
          <q-item-section side>
            <SemaforoBadge livello="salvia" label="Pagato" />
          </q-item-section>
        </q-item>
      </q-list>
    </section>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useAuthStore } from 'stores/auth';
import { useDashboardStore } from 'stores/dashboard';
import PagamentoCard from 'src/components/PagamentoCard.vue';
import SemaforoBadge from 'src/components/SemaforoBadge.vue';
import EmptyState from 'src/components/EmptyState.vue';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';

const auth = useAuthStore();
const store = useDashboardStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

const saluto = computed(() =>
  auth.user?.first_name?.trim() || auth.user?.username || 'Inquilino',
);
const daPagare = computed(() => store.inquilinoData?.da_pagare ?? []);
const numParziali = computed(() => daPagare.value.filter((x) => x.parziale).length);
const ultimiPagamenti = computed(() => store.inquilinoData?.ultimi_pagamenti ?? []);
const stanzaCorrente = computed(() => store.inquilinoData?.stanza_corrente ?? null);

onMounted(() => {
  void store.loadInquilino();
});

function ricarica() {
  void store.loadInquilino(true);
}
</script>

<style scoped>
.vp-i-home {
  background: var(--vp-paper);
  min-height: 100%;
}
.vp-i-home__hero {
  margin-bottom: var(--vp-gap-5);
}
.vp-i-home__titolo {
  font-size: var(--vp-text-3xl);
  margin: var(--vp-gap-2) 0 var(--vp-gap-1);
  color: var(--vp-ink);
}
.vp-i-home__sottotitolo {
  color: var(--vp-ink-2);
  font-size: var(--vp-text-md);
  margin: 0;
}
.vp-i-home__section {
  margin-bottom: var(--vp-gap-6);
}
.vp-i-home__section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--vp-gap-3);
  gap: var(--vp-gap-3);
}
.vp-i-home__h2 {
  margin: 4px 0 0;
  font-size: var(--vp-text-xl);
  color: var(--vp-ink);
}
.vp-i-home__nota-parziali {
  margin: 2px 0 0;
  font-size: var(--vp-text-sm);
  color: var(--vp-sage-deep);
}
.vp-i-home__lista {
  display: grid;
  gap: var(--vp-gap-3);
}
.vp-i-home__storico {
  background: var(--vp-cream);
  border-radius: var(--vp-r-lg);
  border-color: var(--vp-paper-3) !important;
  overflow: hidden;
}
.vp-i-home__loader {
  display: flex;
  justify-content: center;
  padding: var(--vp-gap-6);
}
</style>
