<template>
  <q-page padding class="vp-i-cong">
    <q-btn flat icon="arrow_back" label="Indietro" no-caps color="primary" @click="indietro" />

    <div class="vp-eyebrow q-mt-md">Utenze</div>
    <h1 class="vp-display vp-i-cong__titolo">Dettaglio utenze</h1>

    <div v-if="loading" class="vp-i-cong__loader">
      <q-spinner color="primary" size="32px" />
    </div>

    <q-card v-else-if="charge" class="vp-i-cong__card">
      <div class="vp-i-cong__riga">
        <span class="vp-eyebrow">Importo totale</span>
        <span class="vp-display vp-i-cong__importo">
          {{ formattaEuro(toNumber(charge.importo_totale)) }}
        </span>
      </div>

      <q-separator class="q-my-md" />

      <div class="vp-i-cong__griglia">
        <div>
          <div class="vp-eyebrow">Scadenza</div>
          <div>{{ formattaData(charge.scadenza) }}</div>
        </div>
        <div>
          <div class="vp-eyebrow">Stato</div>
          <div>{{ charge.stato }}</div>
        </div>
        <div v-if="charge.giorni_presenza !== undefined">
          <div class="vp-eyebrow">Giorni presenza</div>
          <div>{{ charge.giorni_presenza }}</div>
        </div>
        <div v-if="charge.importo_pagato">
          <div class="vp-eyebrow">Importo pagato</div>
          <div>{{ formattaEuro(toNumber(charge.importo_pagato)) }}</div>
        </div>
        <div v-if="charge.data_pagamento">
          <div class="vp-eyebrow">Data pagamento</div>
          <div>{{ formattaData(charge.data_pagamento) }}</div>
        </div>
      </div>

      <div v-if="charge.stato !== 'pagato'" class="vp-i-cong__azioni">
        <q-btn
          unelevated
          color="primary"
          icon-right="check"
          :to="`/i/paga/utility_charge/${charge.id}`"
          label="Ho pagato"
          no-caps
        />
      </div>
    </q-card>

    <EmptyState
      v-else
      icon="error_outline"
      title="Utenze non trovate"
      message="Il dettaglio richiesto non è disponibile."
    />
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { usePaymentsStore, type UtilityCharge } from 'stores/payments';
import EmptyState from 'src/components/EmptyState.vue';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';

const route = useRoute();
const router = useRouter();
const payments = usePaymentsStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

const id = computed(() => Number(route.params.id));
const charge = ref<UtilityCharge | null>(null);
const loading = ref(false);

onMounted(async () => {
  loading.value = true;
  try {
    charge.value = await payments.fetchUtilityCharge(id.value);
  } catch {
    charge.value = null;
  } finally {
    loading.value = false;
  }
});

function toNumber(v: string | number | null | undefined): number {
  if (v === null || v === undefined) return 0;
  return typeof v === 'string' ? Number(v) : v;
}

function indietro() {
  router.back();
}
</script>

<style scoped>
.vp-i-cong {
  max-width: 640px;
  margin: 0 auto;
}
.vp-i-cong__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 var(--vp-gap-4);
}
.vp-i-cong__card {
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  padding: var(--vp-gap-5);
  box-shadow: var(--vp-shadow-1);
}
.vp-i-cong__riga {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--vp-gap-3);
}
.vp-i-cong__importo {
  font-size: var(--vp-text-3xl);
  color: var(--vp-terra-deep);
  font-variant-numeric: tabular-nums;
}
.vp-i-cong__griglia {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--vp-gap-4);
}
.vp-i-cong__azioni {
  margin-top: var(--vp-gap-5);
  display: flex;
  justify-content: flex-end;
}
.vp-i-cong__loader {
  display: flex;
  justify-content: center;
  padding: var(--vp-gap-6);
}
</style>
