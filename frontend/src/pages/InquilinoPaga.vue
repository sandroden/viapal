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
        <div class="vp-i-paga__importo-wrap">
          <div class="vp-eyebrow">{{ item.parziale ? 'Resto da saldare' : 'Importo' }}</div>
          <div class="vp-i-paga__importo vp-display">{{ formattaEuro(item.residuo) }}</div>
        </div>
      </div>
      <div v-if="item.parziale" class="vp-i-paga__versato">
        Già versato <span class="vp-mono">{{ formattaEuro(item.importo_pagato) }}</span>
        di <span class="vp-mono">{{ formattaEuro(item.importo_dovuto) }}</span>
      </div>
    </q-card>

    <q-card v-if="item?.pagamento" class="vp-i-paga__bonifico q-mb-md">
      <div class="vp-eyebrow">Paga con bonifico</div>
      <p class="vp-i-paga__bonifico-hint">
        Inquadra il QR con l'app della tua banca: il bonifico si precompila con importo e causale.
      </p>

      <div class="vp-i-paga__qr-wrap">
        <img v-if="qrDataUrl" :src="qrDataUrl" alt="QR bonifico" class="vp-i-paga__qr" />
      </div>

      <div class="vp-i-paga__dati">
        <div class="vp-i-paga__dato">
          <span class="vp-i-paga__dato-lbl">Beneficiario</span>
          <span>{{ item.pagamento.beneficiario }}</span>
        </div>
        <div class="vp-i-paga__dato">
          <span class="vp-i-paga__dato-lbl">IBAN</span>
          <span class="vp-mono vp-i-paga__iban">{{ item.pagamento.iban }}</span>
        </div>
        <div class="vp-i-paga__dato">
          <span class="vp-i-paga__dato-lbl">Causale</span>
          <span>{{ item.pagamento.causale }}</span>
        </div>
      </div>

      <div class="vp-i-paga__copia">
        <q-btn
          flat
          dense
          no-caps
          color="primary"
          icon="content_copy"
          label="Copia IBAN"
          @click="copia(item.pagamento.iban, 'IBAN copiato')"
        />
        <q-btn
          flat
          dense
          no-caps
          color="primary"
          icon="content_copy"
          label="Copia causale"
          @click="copia(item.pagamento.causale, 'Causale copiata')"
        />
      </div>
    </q-card>

    <q-banner v-else-if="item" class="vp-i-paga__no-conto q-mb-md" rounded>
      <template #avatar><q-icon name="info" color="grey-7" /></template>
      Per questo pagamento chiedi i dati del bonifico al proprietario.
    </q-banner>

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
import { useEpcQr, type EpcDati } from 'src/composables/useEpcQr';
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

// QR EPC reattivo: l'importo segue il campo del form (default = residuo).
const epcDati = computed<EpcDati | null>(() => {
  const p = item.value?.pagamento;
  if (!p) return null;
  return {
    beneficiario: p.beneficiario,
    iban: p.iban,
    causale: p.causale,
    importo: importo.value || 0,
  };
});
const { dataUrl: qrDataUrl } = useEpcQr(epcDati);

async function copia(testo: string, msg: string) {
  try {
    await navigator.clipboard.writeText(testo);
    Notify.create({ type: 'positive', message: msg, icon: 'check' });
  } catch {
    Notify.create({ type: 'warning', message: 'Copia non riuscita' });
  }
}

const dataPagamento = ref<string>(new Date().toISOString().slice(0, 10));
const metodo = ref<string>('bonifico');
const riferimento = ref<string>('');
const note = ref<string>('');
const loading = ref(false);
const errore = ref<string>('');

onMounted(async () => {
  if (!dashboard.inquilinoData) await dashboard.loadInquilino();
  if (item.value) importo.value = item.value.residuo;
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
.vp-i-paga__importo-wrap {
  text-align: right;
}
.vp-i-paga__importo {
  font-size: var(--vp-text-2xl);
  color: var(--vp-terra-deep);
  font-variant-numeric: tabular-nums;
}
.vp-i-paga__versato {
  margin-top: var(--vp-gap-3);
  padding-top: var(--vp-gap-3);
  border-top: 1px solid var(--vp-paper-3);
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-3);
}
.vp-i-paga__bonifico {
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  padding: var(--vp-gap-4);
}
.vp-i-paga__bonifico-hint {
  margin: var(--vp-gap-1) 0 var(--vp-gap-3);
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-3);
}
.vp-i-paga__qr-wrap {
  display: flex;
  justify-content: center;
  margin-bottom: var(--vp-gap-3);
}
.vp-i-paga__qr {
  width: 200px;
  height: 200px;
  border-radius: var(--vp-r-md);
  background: #fff;
  padding: var(--vp-gap-2);
  box-shadow: var(--vp-shadow-1);
}
.vp-i-paga__dati {
  display: flex;
  flex-direction: column;
  gap: var(--vp-gap-2);
  margin-bottom: var(--vp-gap-3);
}
.vp-i-paga__dato {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.vp-i-paga__dato-lbl {
  font-size: var(--vp-text-xs);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--vp-ink-3);
}
.vp-i-paga__iban {
  word-break: break-all;
}
.vp-i-paga__copia {
  display: flex;
  gap: var(--vp-gap-2);
  flex-wrap: wrap;
}
.vp-i-paga__no-conto {
  background: var(--vp-paper-2, #f0ebe2);
  color: var(--vp-ink-2);
  font-size: var(--vp-text-sm);
}
.vp-i-paga__azioni {
  display: flex;
  justify-content: flex-end;
  gap: var(--vp-gap-2);
}
</style>
