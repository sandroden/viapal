<template>
  <div class="vp-com">
    <div class="vp-com__filtri">
      <q-select
        v-model="filtroTipo"
        :options="opzioniTipo"
        label="Tipo"
        dense
        outlined
        emit-value
        map-options
        class="vp-com__filtro"
      />
      <q-select
        v-model="filtroCanale"
        :options="opzioniCanale"
        label="Canale"
        dense
        outlined
        emit-value
        map-options
        class="vp-com__filtro"
      />
      <q-select
        v-model="filtroEsito"
        :options="opzioniEsito"
        label="Esito"
        dense
        outlined
        emit-value
        map-options
        class="vp-com__filtro"
      />
      <q-input v-model="filtroDa" type="date" label="Dal" dense outlined stack-label
        class="vp-com__filtro" />
      <q-input v-model="filtroA" type="date" label="Al" dense outlined stack-label
        class="vp-com__filtro" />
      <q-space />
      <q-btn
        flat
        color="primary"
        icon="refresh"
        no-caps
        label="Aggiorna"
        :loading="store.loading"
        @click="ricarica"
      />
    </div>

    <q-banner v-if="store.errore" class="vp-banner-error" rounded>
      <template #avatar><q-icon name="error" /></template>
      {{ store.errore }}
    </q-banner>

    <q-table
      flat
      bordered
      :rows="store.righe"
      :columns="colonne"
      row-key="id"
      v-model:pagination="paginazione"
      :loading="store.loading"
      :rows-per-page-options="[10, 25, 50]"
      no-data-label="Nessuna comunicazione inviata"
      class="vp-com__table"
      @request="onRequest"
      @row-click="(_evt, riga) => apriDettaglio(riga as ComunicazioneFE)"
    >
      <template #body-cell-data="props">
        <q-td :props="props">{{ formattaData(props.row.created_at) }}</q-td>
      </template>
      <template #body-cell-tipo="props">
        <q-td :props="props">
          <q-chip dense square color="grey-3" text-color="grey-9">
            {{ props.row.tipo_display }}
          </q-chip>
        </q-td>
      </template>
      <template #body-cell-canale="props">
        <q-td :props="props">
          <q-icon :name="props.row.canale === 'push' ? 'notifications' : 'mail'" size="16px" />
          {{ props.row.canale_display }}
        </q-td>
      </template>
      <template #body-cell-esito="props">
        <q-td :props="props">
          <q-chip
            v-if="props.row.errore"
            dense
            color="negative"
            text-color="white"
            icon="error_outline"
          >
            fallita
            <q-tooltip>{{ props.row.errore }}</q-tooltip>
          </q-chip>
          <q-chip v-else-if="props.row.inviata_at" dense color="green-2" text-color="green-10">
            inviata
          </q-chip>
          <q-chip v-else dense color="grey-3" text-color="grey-8">in attesa</q-chip>
        </q-td>
      </template>
    </q-table>

    <!-- Dettaglio: il corpo può venire da un MessageTemplate editabile in
         admin, quindi l'HTML va in un iframe sandbox, mai in v-html. -->
    <q-dialog v-model="mostraDettaglio">
      <q-card class="vp-com__dialog">
        <q-card-section class="vp-com__dialog-head">
          <div class="vp-com__dialog-titolo">{{ dettaglio?.oggetto }}</div>
          <div class="vp-com__dialog-meta">
            {{ dettaglio?.tipo_display }} · {{ dettaglio?.canale_display }} ·
            {{ dettaglio?.destinatario || '—' }} ·
            {{ formattaData(dettaglio?.inviata_at ?? dettaglio?.created_at) }}
          </div>
          <q-banner v-if="dettaglio?.errore" dense class="vp-com__errore">
            <template #avatar><q-icon name="error_outline" color="negative" /></template>
            {{ dettaglio.errore }}
          </q-banner>
        </q-card-section>
        <q-card-section class="vp-com__dialog-body">
          <iframe
            v-if="dettaglio?.corpo_html"
            class="vp-com__iframe"
            sandbox=""
            :srcdoc="dettaglio.corpo_html"
            title="Testo della comunicazione"
          />
          <pre v-else class="vp-com__testo">{{ dettaglio?.corpo }}</pre>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Chiudi" v-close-popup />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </div>
</template>

<script setup lang="ts">
// Registro delle comunicazioni inviate, riusabile in due punti:
//   - senza `tenantId`: tutto l'immobile (tab "Inviati" di /p/riepilogo);
//   - con `tenantId`: il singolo inquilino (tab della sua scheda).
// Stesso approccio di DocumentiPannello.
//
// Nota: gli avvisi utenze scrivono due righe per lo stesso evento (email +
// push). Non si deduplica: la colonna canale le distingue e il filtro le
// separa.
import { onMounted, ref, watch } from 'vue';
import type { QTableProps } from 'quasar';
import {
  useComunicazioniStore,
  type ComunicazioneFE,
  type ComunicazioneDettaglioFE,
} from 'stores/comunicazioni';
import { useFormatoData } from 'src/composables/useFormatoData';

const props = defineProps<{
  /** Limita al singolo inquilino; senza, elenca tutto l'immobile. */
  tenantId?: number;
}>();

const store = useComunicazioniStore();
const { formattaData } = useFormatoData();

const filtroTipo = ref<string | null>(null);
const filtroCanale = ref<string | null>(null);
const filtroEsito = ref<string | null>(null);
const filtroDa = ref<string>('');
const filtroA = ref<string>('');

const opzioniTipo = [
  { label: 'Tutti', value: null },
  { label: 'Riepilogo addebiti', value: 'riepilogo_addebiti' },
  { label: 'Avviso utenze', value: 'avviso_utenze' },
  { label: 'Invito inquilino', value: 'invito_inquilino' },
];
const opzioniCanale = [
  { label: 'Tutti', value: null },
  { label: 'Email', value: 'email' },
  { label: 'Push', value: 'push' },
];
const opzioniEsito = [
  { label: 'Tutti', value: null },
  { label: 'Inviate', value: 'inviato' },
  { label: 'Fallite', value: 'errore' },
];

const colonne: QTableProps['columns'] = [
  { name: 'data', label: 'Data', field: 'created_at', align: 'left', sortable: false },
  ...(props.tenantId
    ? []
    : ([
        {
          name: 'inquilino',
          label: 'Inquilino',
          field: 'tenant_nominativo',
          align: 'left' as const,
        },
      ] as NonNullable<QTableProps['columns']>)),
  { name: 'tipo', label: 'Tipo', field: 'tipo_display', align: 'left' },
  { name: 'canale', label: 'Canale', field: 'canale_display', align: 'left' },
  { name: 'destinatario', label: 'Destinatario', field: 'destinatario', align: 'left' },
  { name: 'esito', label: 'Esito', field: 'errore', align: 'left' },
];

const paginazione = ref({
  page: 1,
  rowsPerPage: 25,
  rowsNumber: 0,
});

const mostraDettaglio = ref(false);
const dettaglio = ref<ComunicazioneDettaglioFE | null>(null);

function filtriCorrenti(page = paginazione.value.page, perPage = paginazione.value.rowsPerPage) {
  return {
    tenant: props.tenantId ?? null,
    tipo: filtroTipo.value,
    canale: filtroCanale.value,
    esito: filtroEsito.value,
    da: filtroDa.value || null,
    a: filtroA.value || null,
    limit: perPage,
    offset: (page - 1) * perPage,
  };
}

async function carica(page = 1, perPage = paginazione.value.rowsPerPage): Promise<void> {
  await store.lista(filtriCorrenti(page, perPage));
  paginazione.value = { page, rowsPerPage: perPage, rowsNumber: store.totale };
}

function onRequest(req: Parameters<NonNullable<QTableProps['onRequest']>>[0]): void {
  void carica(req.pagination.page, req.pagination.rowsPerPage);
}

function ricarica(): void {
  void carica(1);
}

async function apriDettaglio(riga: ComunicazioneFE): Promise<void> {
  dettaglio.value = await store.dettaglio(riga.id);
  mostraDettaglio.value = !!dettaglio.value;
}

watch([filtroTipo, filtroCanale, filtroEsito, filtroDa, filtroA], () => {
  void carica(1);
});

onMounted(() => {
  void carica(1);
});
</script>

<style scoped>
.vp-com__filtri {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.vp-com__filtro {
  min-width: 150px;
}
.vp-com__table {
  border-color: var(--vp-paper-3) !important;
}
.vp-com__table :deep(tbody tr) {
  cursor: pointer;
}
.vp-com__dialog {
  width: 720px;
  max-width: 92vw;
}
.vp-com__dialog-head {
  border-bottom: 1px solid var(--vp-paper-3);
}
.vp-com__dialog-titolo {
  font-family: var(--vp-font-display);
  font-size: 18px;
  color: var(--vp-ink);
}
.vp-com__dialog-meta {
  font-size: 12px;
  color: var(--vp-ink-3);
  margin-top: 4px;
}
.vp-com__errore {
  margin-top: 10px;
  background: var(--vp-clay-soft);
  font-size: 13px;
}
.vp-com__dialog-body {
  padding: 0;
}
.vp-com__iframe {
  width: 100%;
  height: 55vh;
  border: none;
  background: #fff;
}
.vp-com__testo {
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 13px;
  margin: 0;
  padding: 18px 20px;
  color: var(--vp-ink-2);
}
</style>
