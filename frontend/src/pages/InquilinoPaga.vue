<template>
  <q-page padding class="vp-i-paga">
    <q-btn flat icon="arrow_back" label="Indietro" no-caps color="primary" @click="indietro" />

    <div class="vp-eyebrow q-mt-md">Dichiara pagamento</div>
    <h1 class="vp-display vp-i-paga__titolo">Ho pagato</h1>

    <q-card v-if="item" class="vp-i-paga__riepilogo q-mb-md">
      <div class="vp-i-paga__head">
        <div>
          <div class="vp-eyebrow">{{ tipoLabel }}</div>
          <div class="text-h6">{{ item.descrizione }}</div>
          <div class="vp-i-paga__meta">
            Scadenza: {{ formattaData(item.scadenza) }}
          </div>
        </div>
        <div class="vp-i-paga__importo vp-display">{{ formattaEuro(item.importo) }}</div>
      </div>
    </q-card>

    <q-form class="q-gutter-md" @submit.prevent="conferma">
      <q-input
        v-model.number="importo"
        type="number"
        step="0.01"
        outlined
        label="Importo pagato (€)"
        :rules="[(v) => (v != null && v > 0) || 'Inserisci un importo valido']"
      />

      <q-input
        v-model="dataPagamento"
        outlined
        type="date"
        label="Data pagamento"
        :rules="[(v) => !!v || 'Inserisci la data']"
      />

      <q-select
        v-model="metodo"
        outlined
        label="Metodo"
        :options="opzioniMetodo"
        emit-value
        map-options
      />

      <q-input
        v-model="riferimento"
        outlined
        label="Riferimento (opzionale)"
        hint="Es. n. CRO bonifico, ricevuta..."
      />

      <q-input v-model="note" outlined type="textarea" label="Note (opzionale)" autogrow />

      <q-banner v-if="errore" class="bg-red-1 text-red-9" rounded>{{ errore }}</q-banner>

      <div class="vp-i-paga__azioni">
        <q-btn flat color="primary" label="Annulla" no-caps @click="indietro" />
        <q-btn
          unelevated
          color="primary"
          type="submit"
          icon-right="check"
          label="Conferma pagamento"
          :loading="loading"
          no-caps
        />
      </div>
    </q-form>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useDashboardStore, type DaPagareItem, type TipoPagamento } from 'stores/dashboard';
import { usePaymentsStore } from 'stores/payments';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';
import { Notify } from 'quasar';

const route = useRoute();
const router = useRouter();
const dashboard = useDashboardStore();
const payments = usePaymentsStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

const tipo = computed(() => route.params.tipo as TipoPagamento);
const id = computed(() => Number(route.params.id));

const item = computed<DaPagareItem | null>(() => {
  const lista = dashboard.inquilinoData?.da_pagare ?? [];
  return lista.find((x) => x.tipo === tipo.value && x.id === id.value) ?? null;
});

const tipoLabel = computed(() => {
  switch (tipo.value) {
    case 'rent':
      return 'Affitto';
    case 'utility_charge':
      return 'Utenze';
    case 'extra':
      return 'Spesa extra';
    default:
      return 'Pagamento';
  }
});

const opzioniMetodo = [
  { label: 'Bonifico', value: 'bonifico' },
  { label: 'Contanti', value: 'contanti' },
  { label: 'Assegno', value: 'assegno' },
  { label: 'Altro', value: 'altro' },
];

const importo = ref<number>(0);
const dataPagamento = ref<string>(new Date().toISOString().slice(0, 10));
const metodo = ref<string>('bonifico');
const riferimento = ref<string>('');
const note = ref<string>('');
const loading = ref(false);
const errore = ref<string>('');

onMounted(async () => {
  if (!dashboard.inquilinoData) await dashboard.loadInquilino();
  if (item.value) importo.value = item.value.importo;
});

async function conferma() {
  errore.value = '';
  loading.value = true;
  try {
    await payments.dichiaraPagato(tipo.value, id.value, {
      importo_pagato: importo.value,
      data_pagamento: dataPagamento.value,
      metodo_pagamento: metodo.value,
      riferimento: riferimento.value || undefined,
      note: note.value || undefined,
    });
    Notify.create({
      type: 'positive',
      message: 'Pagamento dichiarato. In attesa di conferma del proprietario.',
      icon: 'check_circle',
    });
    await dashboard.loadInquilino(true);
    await router.replace('/i/');
  } catch (e: unknown) {
    const msg =
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
      'Errore durante l\'invio.';
    errore.value = msg;
  } finally {
    loading.value = false;
  }
}

function indietro() {
  router.back();
}
</script>

<style scoped>
.vp-i-paga {
  max-width: 640px;
  margin: 0 auto;
}
.vp-i-paga__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 var(--vp-gap-4);
}
.vp-i-paga__riepilogo {
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  padding: var(--vp-gap-4);
}
.vp-i-paga__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--vp-gap-3);
  flex-wrap: wrap;
}
.vp-i-paga__meta {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm);
  margin-top: 4px;
}
.vp-i-paga__importo {
  font-size: var(--vp-text-2xl);
  color: var(--vp-terra-deep);
  font-variant-numeric: tabular-nums;
}
.vp-i-paga__azioni {
  display: flex;
  justify-content: flex-end;
  gap: var(--vp-gap-2);
}
</style>
