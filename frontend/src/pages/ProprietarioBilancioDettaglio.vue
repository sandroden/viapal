<template>
  <q-page padding class="vp-p-bd">
    <q-btn
      flat
      icon="arrow_back"
      no-caps
      label="Torna alla dashboard"
      to="/p"
      class="vp-p-bd__back"
    />

    <header class="vp-p-bd__head">
      <div>
        <div class="vp-eyebrow">{{ tipoLabel }} — anno {{ anno }}</div>
        <h1 class="vp-display vp-p-bd__titolo">
          {{ dati?.owner_nominativo ?? 'Dettaglio bilancio' }}
        </h1>
        <p class="vp-p-bd__sub">
          {{ righeOrdinate.length }}
          {{ righeOrdinate.length === 1 ? 'voce' : 'voci' }} —
          totale <strong>{{ formattaEuro(totaleFiltrato) }}</strong>
          <span v-if="filtriAttivi" class="vp-p-bd__sub-extra">
            (totale senza filtri {{ formattaEuro(dati?.totale ?? 0) }})
          </span>
        </p>
      </div>
    </header>

    <div v-if="store.loadingBilancioDettaglio && !dati" class="vp-p-bd__loader">
      <q-spinner color="primary" size="32px" />
    </div>

    <template v-else-if="dati">
      <div v-if="tipo === 'entrate'" class="vp-p-bd__filtri">
        <div class="vp-p-bd__filtro-gruppo">
          <span class="vp-eyebrow">Causale</span>
          <q-btn-toggle
            v-model="causaleFiltro"
            no-caps
            unelevated
            dense
            :options="opzioniCausale"
            color="paper-3"
            text-color="ink"
            toggle-color="primary"
            toggle-text-color="white"
            class="vp-p-bd__toggle"
          />
        </div>
        <q-chip
          v-if="tenantFiltro"
          removable
          icon="person"
          class="vp-p-bd__chip"
          @remove="tenantFiltro = null"
        >
          {{ tenantFiltro }}
        </q-chip>
      </div>

      <EmptyState
        v-if="righe.length === 0"
        icon="inbox"
        :title="`Nessuna ${tipo === 'entrate' ? 'entrata' : 'uscita'} registrata`"
        :message="`Per l'anno ${anno} non risultano voci.`"
      />

      <EmptyState
        v-else-if="righeOrdinate.length === 0"
        icon="filter_alt_off"
        title="Nessun risultato"
        message="Prova a rimuovere uno o più filtri."
      />

      <q-table
        v-else-if="tipo === 'entrate'"
        v-model:pagination="paginazione"
        flat
        bordered
        :rows="righeOrdinateEntrate"
        :columns="colonneEntrate"
        row-key="id"
        :sort-method="passthroughSort"
        hide-pagination
        class="vp-p-bd__tabella"
      >
        <template #body="props">
          <q-tr
            v-if="mostraSeparatoreMese(props.rowIndex)"
            :key="`mese-${props.rowIndex}`"
            class="vp-p-bd__sep-mese"
          >
            <q-td :colspan="colonneEntrate.length">
              {{ etichettaMese(props.row.data_pagamento) }}
            </q-td>
          </q-tr>
          <q-tr :props="props">
            <q-td key="data_pagamento" :props="props">
              {{ props.row.data_pagamento ? formattaData(props.row.data_pagamento) : '—' }}
            </q-td>
            <q-td key="causale_label" :props="props">
              {{ props.row.causale_label }}
            </q-td>
            <q-td key="tenant" :props="props">
              <button
                type="button"
                class="vp-p-bd__cella-tenant"
                :class="{ 'is-active': tenantFiltro === props.row.tenant }"
                @click="filtraTenant(props.row.tenant)"
                :title="tenantFiltro === props.row.tenant
                  ? 'Rimuovi filtro inquilino'
                  : `Filtra per ${props.row.tenant}`"
              >
                {{ props.row.tenant }}
              </button>
            </q-td>
            <q-td key="descrizione" :props="props">
              {{ props.row.descrizione }}
            </q-td>
            <q-td key="scadenza" :props="props">
              {{ props.row.scadenza ? formattaData(props.row.scadenza) : '—' }}
            </q-td>
            <q-td key="importo_pagato" :props="props" class="text-right vp-mono">
              {{ formattaEuro(props.row.importo_pagato) }}
            </q-td>
            <q-td key="importo_dovuto" :props="props" class="text-right vp-mono">
              {{ formattaEuro(props.row.importo_dovuto) }}
            </q-td>
          </q-tr>
        </template>
        <template #bottom-row>
          <q-tr class="vp-p-bd__totale">
            <q-td colspan="5" class="text-right text-bold">
              Totale{{ filtriAttivi ? ' filtrato' : '' }}
            </q-td>
            <q-td class="text-right text-bold vp-mono">
              {{ formattaEuro(totaleFiltrato) }}
            </q-td>
            <q-td />
          </q-tr>
        </template>
      </q-table>

      <q-table
        v-else-if="tipo === 'uscite'"
        v-model:pagination="paginazione"
        flat
        bordered
        :rows="righeOrdinateUscite"
        :columns="colonneUscite"
        row-key="id"
        :sort-method="passthroughSort"
        hide-pagination
        class="vp-p-bd__tabella"
      >
        <template #body="props">
          <q-tr
            v-if="mostraSeparatoreMese(props.rowIndex)"
            :key="`mese-${props.rowIndex}`"
            class="vp-p-bd__sep-mese"
          >
            <q-td :colspan="colonneUscite.length">
              {{ etichettaMese(props.row.data) }}
            </q-td>
          </q-tr>
          <q-tr :props="props">
            <q-td key="data" :props="props">{{ formattaData(props.row.data) }}</q-td>
            <q-td key="categoria" :props="props">{{ props.row.categoria }}</q-td>
            <q-td key="supplier" :props="props">{{ props.row.supplier ?? '—' }}</q-td>
            <q-td key="descrizione" :props="props">
              <a
                v-if="props.row.file_pdf"
                :href="props.row.file_pdf"
                target="_blank"
                rel="noopener"
                class="vp-p-bd__pdf-link"
              >
                <q-icon name="picture_as_pdf" size="18px" class="q-mr-xs" />{{ props.row.descrizione }}
              </a>
              <span v-else>{{ props.row.descrizione }}</span>
            </q-td>
            <q-td key="importo" :props="props" class="text-right vp-mono">
              {{ formattaEuro(props.row.importo) }}
            </q-td>
          </q-tr>
        </template>
        <template #bottom-row>
          <q-tr class="vp-p-bd__totale">
            <q-td colspan="4" class="text-right text-bold">Totale</q-td>
            <q-td class="text-right text-bold vp-mono">
              {{ formattaEuro(totaleFiltrato) }}
            </q-td>
          </q-tr>
        </template>
      </q-table>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import type { QTableProps } from 'quasar';
import {
  useDashboardStore,
  type BilancioDettaglioEntrata,
  type BilancioDettaglioUscita,
  type TipoBilancio,
} from 'stores/dashboard';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';
import EmptyState from 'src/components/EmptyState.vue';

const route = useRoute();
const store = useDashboardStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

const ownerId = computed(() => Number(route.params.ownerId));
const tipo = computed<TipoBilancio>(() =>
  route.query.tipo === 'uscite' ? 'uscite' : 'entrate',
);
const anno = computed(() =>
  Number(route.query.anno ?? new Date().getFullYear()),
);

const tipoLabel = computed(() => (tipo.value === 'entrate' ? 'Entrate' : 'Uscite'));

const datiKey = computed(() => `${ownerId.value}-${anno.value}-${tipo.value}`);
const dati = computed(() => store.bilancioDettaglio[datiKey.value] ?? null);
const righe = computed(() => dati.value?.righe ?? []);

type CausaleFiltro = 'tutti' | 'affitto' | 'utenze' | 'extra';
const causaleFiltro = ref<CausaleFiltro>('tutti');
const tenantFiltro = ref<string | null>(null);

const opzioniCausale = [
  { label: 'Tutti', value: 'tutti' },
  { label: 'Affitto', value: 'affitto' },
  { label: 'Utenze', value: 'utenze' },
  { label: 'Extra', value: 'extra' },
];

const filtriAttivi = computed(
  () => causaleFiltro.value !== 'tutti' || tenantFiltro.value !== null,
);

function filtraTenant(t: string) {
  tenantFiltro.value = tenantFiltro.value === t ? null : t;
}

const sortDefault = computed(() =>
  tipo.value === 'entrate' ? 'data_pagamento' : 'data',
);

const paginazione = ref({
  sortBy: sortDefault.value,
  descending: true,
  rowsPerPage: 0,
});

watch(tipo, () => {
  paginazione.value = {
    sortBy: sortDefault.value,
    descending: true,
    rowsPerPage: 0,
  };
  causaleFiltro.value = 'tutti';
  tenantFiltro.value = null;
});

const ordinamentoTemporale = computed(
  () => paginazione.value.sortBy === sortDefault.value,
);

// Disattiva il sort interno di Quasar: ordiniamo noi nel computed sotto
// per poter intercalare separatori mese.
const passthroughSort: QTableProps['sortMethod'] = (rows) => rows;

const righeFiltrateEntrate = computed<BilancioDettaglioEntrata[]>(() => {
  if (tipo.value !== 'entrate') return [];
  let arr = righe.value as BilancioDettaglioEntrata[];
  if (causaleFiltro.value !== 'tutti') {
    arr = arr.filter((r) => r.causale === causaleFiltro.value);
  }
  if (tenantFiltro.value) {
    arr = arr.filter((r) => r.tenant === tenantFiltro.value);
  }
  return arr;
});

const righeFiltrateUscite = computed<BilancioDettaglioUscita[]>(() => {
  if (tipo.value !== 'uscite') return [];
  return righe.value as BilancioDettaglioUscita[];
});

type Ordinabile = string | number | null | undefined;
function ordinaPer<T>(arr: T[], sortBy: string, descending: boolean): T[] {
  const out = [...arr];
  out.sort((a, b) => {
    const av = (a as Record<string, Ordinabile>)[sortBy];
    const bv = (b as Record<string, Ordinabile>)[sortBy];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === 'number' && typeof bv === 'number') return av - bv;
    return String(av).localeCompare(String(bv));
  });
  if (descending) out.reverse();
  return out;
}

const righeOrdinateEntrate = computed<BilancioDettaglioEntrata[]>(() =>
  ordinaPer(
    righeFiltrateEntrate.value,
    paginazione.value.sortBy ?? 'data_pagamento',
    paginazione.value.descending ?? true,
  ),
);

const righeOrdinateUscite = computed<BilancioDettaglioUscita[]>(() =>
  ordinaPer(
    righeFiltrateUscite.value,
    paginazione.value.sortBy ?? 'data',
    paginazione.value.descending ?? true,
  ),
);

const righeOrdinate = computed<
  BilancioDettaglioEntrata[] | BilancioDettaglioUscita[]
>(() =>
  tipo.value === 'entrate' ? righeOrdinateEntrate.value : righeOrdinateUscite.value,
);

const totaleFiltrato = computed(() => {
  if (tipo.value === 'entrate') {
    return righeOrdinateEntrate.value.reduce(
      (s, r) => s + (r.importo_pagato || 0),
      0,
    );
  }
  return righeOrdinateUscite.value.reduce((s, r) => s + (r.importo || 0), 0);
});

function meseChiave(dataIso: string | null | undefined): string {
  return dataIso ? dataIso.substring(0, 7) : '';
}

function mostraSeparatoreMese(idx: number): boolean {
  if (!ordinamentoTemporale.value) return false;
  const arr = righeOrdinate.value;
  const cur = arr[idx];
  if (!cur) return false;
  const curKey = meseChiave(getDataRiga(cur));
  if (!curKey) return false;
  if (idx === 0) return true;
  const prev = arr[idx - 1];
  if (!prev) return true;
  return meseChiave(getDataRiga(prev)) !== curKey;
}

function getDataRiga(
  r: BilancioDettaglioEntrata | BilancioDettaglioUscita,
): string | null {
  if (tipo.value === 'entrate') {
    return (r as BilancioDettaglioEntrata).data_pagamento;
  }
  return (r as BilancioDettaglioUscita).data;
}

function etichettaMese(dataIso: string | null | undefined): string {
  if (!dataIso) return '—';
  const [y, m] = dataIso.split('-');
  const d = new Date(Number(y), Number(m) - 1, 1);
  const s = d.toLocaleString('it-IT', { month: 'long', year: 'numeric' });
  return s.charAt(0).toUpperCase() + s.slice(1);
}

const colonneEntrate: QTableProps['columns'] = [
  {
    name: 'data_pagamento',
    label: 'Pagato il',
    field: 'data_pagamento',
    align: 'left',
    sortable: true,
  },
  {
    name: 'causale_label',
    label: 'Causale',
    field: 'causale_label',
    align: 'left',
    sortable: true,
  },
  { name: 'tenant', label: 'Inquilino', field: 'tenant', align: 'left', sortable: true },
  {
    name: 'descrizione',
    label: 'Descrizione',
    field: 'descrizione',
    align: 'left',
  },
  {
    name: 'scadenza',
    label: 'Scadenza',
    field: 'scadenza',
    align: 'left',
    sortable: true,
  },
  {
    name: 'importo_pagato',
    label: 'Pagato',
    field: 'importo_pagato',
    align: 'right',
    sortable: true,
  },
  {
    name: 'importo_dovuto',
    label: 'Dovuto',
    field: 'importo_dovuto',
    align: 'right',
    sortable: true,
  },
];

const colonneUscite: QTableProps['columns'] = [
  { name: 'data', label: 'Data', field: 'data', align: 'left', sortable: true },
  { name: 'categoria', label: 'Categoria', field: 'categoria', align: 'left', sortable: true },
  { name: 'supplier', label: 'Fornitore', field: 'supplier', align: 'left' },
  { name: 'descrizione', label: 'Descrizione', field: 'descrizione', align: 'left' },
  { name: 'importo', label: 'Importo', field: 'importo', align: 'right', sortable: true },
];

async function carica() {
  if (!ownerId.value || Number.isNaN(ownerId.value)) return;
  await store.loadDettaglioBilancio(ownerId.value, anno.value, tipo.value);
}

onMounted(() => {
  void carica();
});

watch([ownerId, anno, tipo], () => {
  void carica();
});
</script>

<style scoped>
.vp-p-bd__back {
  margin-bottom: var(--vp-gap-3);
}
.vp-p-bd__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: var(--vp-gap-3);
  flex-wrap: wrap;
  margin-bottom: var(--vp-gap-4);
}
.vp-p-bd__titolo {
  font-size: var(--vp-text-3xl);
  margin: var(--vp-gap-2) 0 var(--vp-gap-1);
}
.vp-p-bd__sub {
  color: var(--vp-ink-2);
  margin: 0;
}
.vp-p-bd__sub-extra {
  margin-left: var(--vp-gap-2);
  font-style: italic;
  color: var(--vp-ink-3);
}
.vp-p-bd__loader {
  display: flex;
  justify-content: center;
  padding: var(--vp-gap-7);
}
.vp-p-bd__filtri {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--vp-gap-3);
  margin-bottom: var(--vp-gap-4);
}
.vp-p-bd__filtro-gruppo {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-2);
}
.vp-p-bd__toggle {
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-md);
  background: var(--vp-cream);
}
.vp-p-bd__chip {
  background: var(--vp-terra-soft, #f0d9c8);
  color: var(--vp-ink, #2a2622);
}
.vp-p-bd__tabella {
  background: var(--vp-cream);
}
.vp-p-bd__totale {
  background: var(--vp-paper-2);
}
.vp-p-bd__sep-mese td {
  background: var(--vp-paper-2, #efe7dc);
  color: var(--vp-ink, #2a2622);
  font-family: var(--vp-font-display);
  font-size: var(--vp-text-sm, 0.9rem);
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: var(--vp-gap-2) var(--vp-gap-3);
  border-top: 2px solid var(--vp-terra, #b56a3b);
}
.vp-p-bd__cella-tenant {
  background: transparent;
  border: 0;
  padding: 0;
  font: inherit;
  color: var(--vp-terra, #b56a3b);
  text-decoration: underline dotted;
  text-underline-offset: 3px;
  cursor: pointer;
  text-align: left;
}
.vp-p-bd__cella-tenant:hover {
  color: var(--vp-ink);
}
.vp-p-bd__cella-tenant.is-active {
  font-weight: 600;
  color: var(--vp-ink);
  text-decoration: none;
}
.vp-mono {
  font-variant-numeric: tabular-nums;
}
</style>
