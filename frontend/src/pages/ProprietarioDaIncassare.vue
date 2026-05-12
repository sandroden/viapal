<template>
  <q-page padding class="vp-p-di">
    <header class="vp-p-di__head">
      <div>
        <div class="vp-eyebrow">Pagamenti attesi</div>
        <h1 class="vp-display vp-p-di__titolo">Da incassare</h1>
        <div class="vp-p-di__sub">
          {{ righe.length }} righe ·
          totale residuo
          <span class="vp-mono">{{ formattaEuro(totaleResiduo) }}</span>
        </div>
      </div>
      <div class="vp-p-di__filtri">
        <div class="vp-p-di__nav-anno">
          <q-btn
            flat
            round
            dense
            icon="chevron_left"
            aria-label="Anno precedente"
            :disable="!puoIndietro"
            @click="annoPrecedente"
          />
          <q-select
            v-model="annoSelezionato"
            :options="anniDisponibili"
            dense
            outlined
            label="Anno"
            class="vp-p-di__sel-anno"
          />
          <q-btn
            flat
            round
            dense
            icon="chevron_right"
            aria-label="Anno successivo"
            :disable="!puoAvanti"
            @click="annoSuccessivo"
          />
        </div>
        <q-input
          v-model="dataDa"
          dense
          outlined
          type="date"
          label="Scadenza dal"
          clearable
          class="vp-p-di__sel"
        />
        <q-input
          v-model="dataA"
          dense
          outlined
          type="date"
          label="Scadenza al"
          clearable
          class="vp-p-di__sel"
        />
        <q-btn flat dense icon="refresh" no-caps label="Aggiorna" @click="ricarica" />
      </div>
    </header>

    <q-table
      v-if="righe.length"
      flat
      bordered
      :rows="righe"
      :columns="colonne"
      row-key="id"
      :pagination="paginazione"
      :loading="caricamento"
      class="vp-p-di__table"
    >
      <template #body-cell-tipo="props">
        <q-td :props="props">
          <q-icon
            :name="iconaPerCausale(props.row.causale)"
            size="18px"
            class="vp-p-di__tipo-icon"
            :class="`vp-p-di__chip--c-${props.row.causale}`"
          />
          {{ etichettaPerCausale(props.row.causale) }}
        </q-td>
      </template>
      <template #body-cell-inquilino="props">
        <q-td :props="props">
          <router-link
            :to="{ name: 'p-inquilino-dettaglio', params: { id: props.row.tenant_id } }"
            class="vp-p-di__link-inq"
          >
            {{ props.row.tenant_nominativo }}
          </router-link>
        </q-td>
      </template>
      <template #body-cell-importo_dovuto="props">
        <q-td :props="props" class="vp-mono">{{ formattaEuro(props.row.importo_dovuto) }}</q-td>
      </template>
      <template #body-cell-residuo="props">
        <q-td :props="props" class="vp-mono">{{ formattaEuro(props.row.residuo) }}</q-td>
      </template>
      <template #body-cell-scadenza="props">
        <q-td :props="props">
          {{ props.row.scadenza ? formattaData(props.row.scadenza) : '—' }}
        </q-td>
      </template>
      <template #body-cell-stato="props">
        <q-td :props="props">
          <span
            class="vp-p-di__stato-click"
            @click="aprireRegistraPagamento(props.row)"
          >
            <SemaforoBadge
              :livello="livelloStato(props.row.stato, props.row.scadenza)"
              :label="props.row.stato_display || props.row.stato"
            />
            <q-icon name="payments" size="14px" class="vp-p-di__stato-icon" />
            <q-tooltip>Registra pagamento</q-tooltip>
          </span>
        </q-td>
      </template>
    </q-table>

    <EmptyState
      v-else-if="!caricamento"
      icon="celebration"
      title="Tutto incassato"
      message="Nessun pagamento atteso nei filtri selezionati."
    />

    <RegistraPagamentoDialog
      v-if="receivableSelezionato"
      v-model="dialogPagamento"
      :receivable="receivableSelezionato"
      :owner-accounts="contiUtente"
      :default-owner-account-id="contoDiDefaultUtente"
      @saved="dopoSalvataggio"
    />
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import type { QTableProps } from 'quasar';
import { api } from 'boot/axios';
import SemaforoBadge from 'src/components/SemaforoBadge.vue';
import EmptyState from 'src/components/EmptyState.vue';
import RegistraPagamentoDialog from 'src/components/RegistraPagamentoDialog.vue';
import type { SemaforoLivello } from 'src/types/semaforo';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';
import { useAuthStore } from 'stores/auth';
import { useOwnerBankAccountsStore } from 'stores/ownerBankAccounts';

type CausaleReceivable = 'affitto' | 'utenze' | 'extra' | 'caparra';

interface ReceivableRiga {
  id: number;
  causale: CausaleReceivable;
  descrizione_estesa: string;
  tenant_id: number;
  tenant_nominativo: string;
  scadenza: string | null;
  importo_dovuto: number;
  importo_allocato: number;
  residuo: number;
  stato: string;
  stato_display: string;
  bank_account_destinazione: number | null;
}

interface ReceivableInput {
  id: number;
  causale: CausaleReceivable;
  importo_dovuto: number;
  importo_pagato: number;
  descrizione: string;
  tenant_nominativo: string;
  scadenza: string;
  bank_account_destinazione_id: number | null;
}

const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();
const auth = useAuthStore();
const contiStore = useOwnerBankAccountsStore();
const router = useRouter();
const route = useRoute();

const annoCorrente = new Date().getFullYear();
const annoMin = annoCorrente - 5;
const annoMax = annoCorrente + 1;

function parseAnno(v: unknown): number {
  const n = Number(Array.isArray(v) ? v[0] : v);
  if (Number.isFinite(n) && n >= annoMin && n <= annoMax) return n;
  return annoCorrente;
}

function inizioAnno(a: number): string {
  return `${a}-01-01`;
}
function fineAnno(a: number): string {
  return `${a}-12-31`;
}

const annoSelezionato = ref<number>(parseAnno(route.query.anno));
const righe = ref<ReceivableRiga[]>([]);
const caricamento = ref(false);
const dataDa = ref<string | null>(
  typeof route.query.dataDa === 'string' && route.query.dataDa
    ? route.query.dataDa
    : inizioAnno(annoSelezionato.value),
);
const dataA = ref<string | null>(
  typeof route.query.dataA === 'string' && route.query.dataA
    ? route.query.dataA
    : fineAnno(annoSelezionato.value),
);

const anniDisponibili = computed<number[]>(() => {
  const lista: number[] = [];
  for (let a = annoMax; a >= annoMin; a -= 1) lista.push(a);
  return lista;
});
const puoIndietro = computed(() => annoSelezionato.value > annoMin);
const puoAvanti = computed(() => annoSelezionato.value < annoMax);

function annoPrecedente(): void {
  if (puoIndietro.value) annoSelezionato.value -= 1;
}
function annoSuccessivo(): void {
  if (puoAvanti.value) annoSelezionato.value += 1;
}

watch(annoSelezionato, (a) => {
  dataDa.value = inizioAnno(a);
  dataA.value = fineAnno(a);
});

const dialogPagamento = ref(false);
const receivableSelezionato = ref<ReceivableInput | null>(null);

const ETICHETTE: Record<CausaleReceivable, string> = {
  affitto: 'Affitto',
  utenze: 'Utenze',
  extra: 'Extra',
  caparra: 'Caparra',
};
const ICONE: Record<CausaleReceivable, string> = {
  affitto: 'home',
  utenze: 'bolt',
  extra: 'receipt',
  caparra: 'savings',
};
function etichettaPerCausale(c: CausaleReceivable): string {
  return ETICHETTE[c] ?? c;
}
function iconaPerCausale(c: CausaleReceivable): string {
  return ICONE[c] ?? 'help';
}

const colonne: QTableProps['columns'] = [
  { name: 'tipo', label: 'Tipo', field: 'causale', align: 'left', sortable: true },
  {
    name: 'inquilino',
    label: 'Inquilino',
    field: 'tenant_nominativo',
    align: 'left',
    sortable: true,
  },
  {
    name: 'descrizione',
    label: 'Descrizione',
    field: 'descrizione_estesa',
    align: 'left',
    sortable: true,
  },
  {
    name: 'scadenza',
    label: 'Scadenza',
    field: 'scadenza',
    align: 'left',
    sortable: true,
  },
  {
    name: 'importo_dovuto',
    label: 'Dovuto',
    field: 'importo_dovuto',
    align: 'right',
    sortable: true,
  },
  {
    name: 'residuo',
    label: 'Residuo',
    field: 'residuo',
    align: 'right',
    sortable: true,
  },
  { name: 'stato', label: 'Stato', field: 'stato', align: 'center' },
];

const paginazione = {
  rowsPerPage: 50,
  sortBy: 'scadenza',
  descending: true,
};

const totaleResiduo = computed(() =>
  righe.value.reduce((s, r) => s + Number(r.residuo || 0), 0),
);

const contiUtente = computed(() =>
  contiStore.accounts.length > 0
    ? contiStore.accounts
    : (auth.user?.bank_accounts ?? []),
);
const contoDiDefaultUtente = computed(
  () => auth.user?.bank_accounts?.[0]?.id ?? null,
);

function livelloStato(_: string, scadenza: string | null): SemaforoLivello {
  if (!scadenza) return 'salvia';
  const oggi = new Date();
  oggi.setHours(0, 0, 0, 0);
  const s = new Date(scadenza);
  s.setHours(0, 0, 0, 0);
  const giorni = Math.round((oggi.getTime() - s.getTime()) / 86400000);
  if (giorni > 7) return 'argilla_scuro';
  if (giorni > 0) return 'argilla_chiaro';
  if (giorni > -7) return 'miele';
  return 'salvia';
}

interface RispostaReceivables {
  results?: ReceivableRiga[];
}

async function carica(): Promise<void> {
  caricamento.value = true;
  try {
    const params: Record<string, string> = {
      riconciliato: 'false',
      limit: '500',
    };
    if (dataDa.value) params.data_da = dataDa.value;
    if (dataA.value) params.data_a = dataA.value;
    const { data } = await api.get<ReceivableRiga[] | RispostaReceivables>(
      '/api/v1/receivables/',
      { params },
    );
    const items = Array.isArray(data) ? data : (data.results ?? []);
    // Ordina per scadenza decrescente (più recenti / futuri in alto)
    righe.value = items
      .map((r) => ({
        ...r,
        importo_dovuto: Number(r.importo_dovuto),
        importo_allocato: Number(r.importo_allocato),
        residuo: Number(r.residuo),
      }))
      .sort((a, b) => (b.scadenza ?? '').localeCompare(a.scadenza ?? ''));
  } finally {
    caricamento.value = false;
  }
}

function ricarica(): void {
  void carica();
}

watch([dataDa, dataA, annoSelezionato], () => {
  aggiornaQuery();
  void carica();
});

function aggiornaQuery(): void {
  const q: Record<string, string> = { anno: String(annoSelezionato.value) };
  if (dataDa.value && dataDa.value !== inizioAnno(annoSelezionato.value)) {
    q.dataDa = dataDa.value;
  }
  if (dataA.value && dataA.value !== fineAnno(annoSelezionato.value)) {
    q.dataA = dataA.value;
  }
  void router.replace({ query: q });
}

onMounted(() => {
  void carica();
  void contiStore.ensureLoaded();
});

function aprireRegistraPagamento(r: ReceivableRiga): void {
  receivableSelezionato.value = {
    id: r.id,
    causale: r.causale,
    importo_dovuto: Number(r.importo_dovuto),
    importo_pagato: Number(r.importo_allocato),
    descrizione: r.descrizione_estesa,
    tenant_nominativo: r.tenant_nominativo,
    scadenza: r.scadenza ?? new Date().toISOString().slice(0, 10),
    bank_account_destinazione_id: r.bank_account_destinazione,
  };
  dialogPagamento.value = true;
}

async function dopoSalvataggio(): Promise<void> {
  await carica();
}
</script>

<style scoped>
.vp-p-di__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: var(--vp-gap-3);
  flex-wrap: wrap;
  margin-bottom: var(--vp-gap-4);
}
.vp-p-di__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 0;
}
.vp-p-di__sub {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm);
  margin-top: var(--vp-gap-1);
}
.vp-p-di__filtri {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-2);
  flex-wrap: wrap;
}
.vp-p-di__nav-anno {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-1);
}
.vp-p-di__sel-anno {
  min-width: 120px;
}
.vp-p-di__sel {
  min-width: 160px;
}
.vp-p-di__table {
  background: var(--vp-cream);
  border-color: var(--vp-paper-3) !important;
}
.vp-p-di__tipo-icon {
  margin-right: var(--vp-gap-1);
  vertical-align: middle;
}
.vp-p-di__chip--c-affitto {
  color: var(--vp-salvia, #4f6e3f);
}
.vp-p-di__chip--c-utenze {
  color: var(--vp-miele, #b08a1f);
}
.vp-p-di__chip--c-extra {
  color: var(--vp-terra, #b56a3b);
}
.vp-p-di__chip--c-caparra {
  color: var(--vp-ink-3);
}
.vp-p-di__link-inq {
  color: inherit;
  text-decoration: none;
}
.vp-p-di__link-inq:hover {
  text-decoration: underline;
}
.vp-p-di__stato-click {
  display: inline-flex;
  align-items: center;
  gap: var(--vp-gap-1);
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 4px;
  transition: background-color 120ms;
}
.vp-p-di__stato-click:hover {
  background: var(--vp-paper-2, rgba(0, 0, 0, 0.04));
}
.vp-p-di__stato-icon {
  color: var(--vp-ink-3);
  opacity: 0.6;
}
.vp-p-di__stato-click:hover .vp-p-di__stato-icon {
  opacity: 1;
  color: var(--vp-salvia, #4f6e3f);
}
.vp-mono {
  font-variant-numeric: tabular-nums;
}
</style>
