<template>
  <q-page padding class="vp-p-spese">
    <header class="vp-p-spese__head">
      <div>
        <div class="vp-eyebrow">Uscite</div>
        <h1 class="vp-display vp-p-spese__titolo">Spese</h1>
        <div class="vp-p-spese__sub">
          {{ store.expenses.length }} righe registrate · totale
          {{ formattaEuro(totaleGenerale) }}
        </div>
      </div>
      <div class="vp-p-spese__azioni">
        <q-btn
          flat
          color="primary"
          icon="refresh"
          no-caps
          label="Aggiorna"
          :loading="store.loading"
          @click="ricarica"
        />
        <q-btn
          unelevated
          color="primary"
          icon="add"
          label="Aggiungi"
          no-caps
          @click="dialogAperto = true"
        />
      </div>
    </header>

    <!-- Andamento storico: grafico + tabella sintesi affiancati -->
    <section class="vp-p-spese__storico" v-if="anniDisponibili.length">
      <div class="vp-eyebrow vp-p-spese__storico-title">Andamento per anno</div>
      <div class="vp-p-spese__storico-grid">
        <div class="vp-p-spese__storico-chart">
          <BarChartAnni :righe="datiGrafico" :height="200" />
        </div>
        <q-table
          flat
          dense
          bordered
          :rows="storicoRows"
          :columns="storicoColumns"
          row-key="categoria"
          :pagination="{ rowsPerPage: 0 }"
          hide-bottom
          class="vp-p-spese__storico-table"
        />
      </div>
    </section>

    <!-- Tab per anno con frecce -->
    <div class="vp-p-spese__tabs-wrapper">
      <q-btn
        flat
        round
        dense
        icon="chevron_left"
        aria-label="Anno precedente"
        :disable="!puoIndietroAnno"
        @click="cambiaAnno(-1)"
      />
      <q-tabs
        v-model="annoSelezionato"
        align="left"
        dense
        indicator-color="primary"
        class="vp-p-spese__tabs"
      >
        <q-tab v-for="a in anniDisponibili" :key="a" :name="a" :label="String(a)" />
      </q-tabs>
      <q-btn
        flat
        round
        dense
        icon="chevron_right"
        aria-label="Anno successivo"
        :disable="!puoAvantiAnno"
        @click="cambiaAnno(1)"
      />
    </div>

    <q-tab-panels v-model="annoSelezionato" animated class="vp-p-spese__panels">
      <q-tab-panel v-for="a in anniDisponibili" :key="a" :name="a" class="q-pa-none">
        <div class="vp-p-spese__filtri">
          <div class="vp-p-spese__filtri-gruppi">
            <q-btn-toggle
              v-model="filtroCategoria"
              :options="filtroOptions"
              no-caps
              unelevated
              toggle-color="primary"
            />
            <q-btn-toggle
              v-if="filtroCategoria === 'Utenze'"
              v-model="filtroProdotto"
              :options="filtroProdottoOptions"
              no-caps
              unelevated
              dense
              toggle-color="secondary"
              class="vp-p-spese__filtro-prodotto"
            />
          </div>
          <div class="vp-p-spese__totali">
            <span class="vp-mono">{{ formattaEuro(totaleAnnoFiltrato(a)) }}</span>
            <span class="vp-p-spese__totali-label">
              {{ righeFiltrate(a).length }} righe
            </span>
          </div>
        </div>

        <q-table
          flat
          bordered
          :rows="righeFiltrate(a)"
          :columns="colonne"
          row-key="id"
          :loading="store.loading"
          :pagination="paginazione"
          no-data-label="Nessuna spesa per questo periodo / categoria"
          class="vp-p-spese__table"
        >
          <template #body-cell-data="props">
            <q-td :props="props">{{ formattaData(props.row.data) }}</q-td>
          </template>
          <template #body-cell-pdf="props">
            <q-td :props="props" class="text-center">
              <PdfIconButton
                v-if="props.row.file_pdf"
                :title="props.row.bolletta_numero || props.row.descrizione"
                @click="apriPdf(props.row)"
              />
            </q-td>
          </template>
          <template #body-cell-importo="props">
            <q-td :props="props" class="text-right">
              <span class="vp-mono">{{ formattaEuro(toNumber(props.row.importo)) }}</span>
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>
    </q-tab-panels>

    <PdfDialog
      v-model="pdfDialogOpen"
      :url="pdfCorrente?.url ?? null"
      :title="pdfCorrente?.title ?? null"
    />

    <!-- Dialog aggiungi spesa -->
    <q-dialog v-model="dialogAperto" persistent>
      <q-card class="vp-p-spese__dialog">
        <q-card-section>
          <div class="vp-eyebrow">Nuova spesa</div>
          <h2 class="vp-display vp-p-spese__dialog-titolo">Aggiungi spesa</h2>
        </q-card-section>
        <q-card-section>
          <q-form class="q-gutter-md" @submit.prevent="salva">
            <q-input
              v-model="form.data"
              type="date"
              outlined
              label="Data"
              :error="!!errorOf('data')"
              :error-message="errorOf('data')"
            />
            <q-input
              v-model="form.descrizione"
              outlined
              label="Descrizione"
              :error="!!errorOf('descrizione')"
              :error-message="errorOf('descrizione')"
            />
            <q-input
              v-model.number="form.importo"
              type="number"
              step="0.01"
              outlined
              label="Importo (€)"
              :error="!!errorOf('importo')"
              :error-message="errorOf('importo')"
            />
            <q-select
              v-model="form.category"
              :options="opzioniCategoria"
              option-label="nome"
              option-value="id"
              emit-value
              map-options
              outlined
              label="Categoria"
              :error="!!errorOf('category')"
              :error-message="errorOf('category')"
            />
            <q-input v-model="form.note" outlined type="textarea" label="Note" autogrow />

            <q-separator />
            <div class="vp-p-spese__bt-sezione">
              <q-toggle
                v-model="form.crea_bank_transaction"
                label="Crea anche movimento banca"
              />
              <div
                v-if="form.crea_bank_transaction && contiUtente.length > 0"
                class="vp-p-spese__bt-campi"
              >
                <q-select
                  v-model="form.bt_owner_account"
                  :options="opzioniContiBT"
                  option-label="label"
                  option-value="value"
                  emit-value
                  map-options
                  outlined
                  dense
                  label="Conto da cui esce"
                  :error="!!errorOf('bt_owner_account')"
                  :error-message="errorOf('bt_owner_account')"
                />
                <q-input
                  v-model="form.bt_data"
                  type="date"
                  outlined
                  dense
                  label="Data movimento"
                />
                <q-input
                  v-model="form.bt_descrizione"
                  outlined
                  dense
                  label="Descrizione movimento (opzionale)"
                  :placeholder="form.descrizione"
                />
              </div>
              <q-banner
                v-if="form.crea_bank_transaction && contiUtente.length === 0"
                class="bg-amber-1 text-amber-9"
                rounded
              >
                Nessun conto bancario configurato: impossibile creare il movimento.
              </q-banner>
            </div>

            <q-banner v-if="globalError" class="bg-red-1 text-red-9" rounded>{{ globalError }}</q-banner>
          </q-form>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat color="primary" label="Annulla" no-caps @click="annulla" />
          <q-btn
            unelevated
            color="primary"
            label="Salva spesa"
            no-caps
            :loading="loadingSalva"
            @click="salva"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import type { QTableProps } from 'quasar';
import { Notify } from 'quasar';
import { useExpensesStore, type Expense, type NuovaSpesa } from 'stores/expenses';
import { useAuthStore } from 'stores/auth';
import { useOwnerBankAccountsStore } from 'stores/ownerBankAccounts';
import { useExpenseCategoriesStore } from 'stores/expenseCategories';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';
import { useFormErrors } from 'src/composables/useFormErrors';
import BarChartAnni from 'src/components/BarChartAnni.vue';
import PdfDialog from 'src/components/PdfDialog.vue';
import PdfIconButton from 'src/components/PdfIconButton.vue';

const store = useExpensesStore();
const auth = useAuthStore();
const contiStore = useOwnerBankAccountsStore();
const categoriesStore = useExpenseCategoriesStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();
const { globalError, captureError, reset: resetErrors, errorOf } = useFormErrors();

const dialogAperto = ref(false);
const loadingSalva = ref(false);

const opzioniCategoria = computed(() => categoriesStore.categories);

const contiUtente = computed(() =>
  contiStore.accounts.length > 0
    ? contiStore.accounts
    : (auth.user?.bank_accounts ?? []),
);
const opzioniContiBT = computed(() =>
  contiUtente.value.map((a) => ({
    value: a.id,
    label: `${a.banca} — ${a.intestatario} (…${a.iban.slice(-4)})`,
  })),
);
const contoDefaultBT = computed(
  () => auth.user?.bank_accounts?.[0]?.id ?? contiUtente.value[0]?.id ?? null,
);

interface FormSpesa extends NuovaSpesa {
  crea_bank_transaction: boolean;
  bt_owner_account: number | null;
  bt_data: string;
  bt_descrizione: string;
}

const form = reactive<FormSpesa>({
  data: new Date().toISOString().slice(0, 10),
  descrizione: '',
  importo: 0,
  category: null,
  note: '',
  crea_bank_transaction: true,
  bt_owner_account: contoDefaultBT.value,
  bt_data: new Date().toISOString().slice(0, 10),
  bt_descrizione: '',
});

watch(contoDefaultBT, (id) => {
  if (form.bt_owner_account == null) form.bt_owner_account = id;
});
watch(
  () => form.data,
  (d) => {
    if (d) form.bt_data = d;
  },
);

const colonne: QTableProps['columns'] = [
  { name: 'data', label: 'Data', field: 'data', align: 'left', sortable: true },
  { name: 'descrizione', label: 'Descrizione', field: 'descrizione', align: 'left', sortable: true },
  { name: 'category', label: 'Categoria', field: 'category_nome', align: 'left', sortable: true },
  { name: 'prodotto', label: 'Tipo', field: 'bolletta_prodotto', align: 'left' },
  { name: 'anticipata_da', label: 'Anticipata da', field: 'anticipata_da_nominativo', align: 'left' },
  { name: 'pdf', label: 'PDF', field: 'file_pdf', align: 'center' },
  { name: 'importo', label: 'Importo', field: 'importo', align: 'right', sortable: true },
];

type FiltroProdotto = 'tutti' | 'gas' | 'luce' | 'acqua';
const filtroProdotto = ref<FiltroProdotto>('tutti');
const filtroProdottoOptions = [
  { label: 'Tutti', value: 'tutti' as FiltroProdotto },
  { label: 'Gas', value: 'gas' as FiltroProdotto },
  { label: 'Luce', value: 'luce' as FiltroProdotto },
  { label: 'Acqua', value: 'acqua' as FiltroProdotto },
];

const pdfDialogOpen = ref(false);
const pdfCorrente = ref<{ url: string; title: string } | null>(null);
function apriPdf(row: Expense) {
  if (!row.file_pdf) return;
  pdfCorrente.value = {
    url: row.file_pdf,
    title: row.bolletta_numero || row.descrizione || 'Bolletta',
  };
  pdfDialogOpen.value = true;
}

const paginazione = { rowsPerPage: 25, sortBy: 'data', descending: true };

function toNumber(v: string | number | null | undefined): number {
  if (v == null) return 0;
  return typeof v === 'string' ? Number(v) : v;
}

function categoriaOf(e: Expense): string {
  return e.category_nome || 'Altro';
}

const annoSelezionato = ref<number>(new Date().getFullYear());

const anniDisponibili = computed<number[]>(() => {
  const set = new Set<number>();
  for (const e of store.expenses) {
    set.add(new Date(e.data).getFullYear());
  }
  return [...set].sort((a, b) => b - a);
});

watch(anniDisponibili, (anni) => {
  if (anni.length && !anni.includes(annoSelezionato.value)) {
    annoSelezionato.value = anni[0]!;
  }
});

const puoIndietroAnno = computed(() => {
  const anni = anniDisponibili.value;
  const i = anni.indexOf(annoSelezionato.value);
  return i >= 0 && i < anni.length - 1;
});

const puoAvantiAnno = computed(() => {
  const anni = anniDisponibili.value;
  const i = anni.indexOf(annoSelezionato.value);
  return i > 0;
});

function cambiaAnno(delta: number) {
  // anniDisponibili è ordinato decrescente: indice + 1 = anno precedente
  const anni = anniDisponibili.value;
  const i = anni.indexOf(annoSelezionato.value);
  if (i < 0) return;
  const nuovoIndex = delta > 0 ? i - 1 : i + 1;
  if (nuovoIndex < 0 || nuovoIndex >= anni.length) return;
  annoSelezionato.value = anni[nuovoIndex]!;
}

const filtroCategoria = ref<string>('Tutte');

const categorieDisponibili = computed<string[]>(() => {
  const set = new Set<string>();
  for (const e of store.expenses) set.add(categoriaOf(e));
  return [...set].sort();
});

const filtroOptions = computed(() => [
  { label: 'Tutte', value: 'Tutte' },
  ...categorieDisponibili.value.map((c) => ({ label: c, value: c })),
]);

function righeAnno(a: number): Expense[] {
  return store.expenses.filter((e) => new Date(e.data).getFullYear() === a);
}

function righeFiltrate(a: number): Expense[] {
  let righe = righeAnno(a);
  if (filtroCategoria.value !== 'Tutte') {
    righe = righe.filter((e) => categoriaOf(e) === filtroCategoria.value);
  }
  if (filtroCategoria.value === 'Utenze' && filtroProdotto.value !== 'tutti') {
    righe = righe.filter((e) => e.bolletta_prodotto === filtroProdotto.value);
  }
  return righe;
}

function totaleAnnoFiltrato(a: number): number {
  return righeFiltrate(a).reduce((s, e) => s + toNumber(e.importo), 0);
}

const totaleGenerale = computed<number>(() =>
  store.expenses.reduce((s, e) => s + toNumber(e.importo), 0),
);

// Storico: matrice anno x categoria
const storicoColumns = computed<QTableProps['columns']>(() => {
  const cols: QTableProps['columns'] = [
    {
      name: 'categoria',
      label: 'Categoria',
      field: 'categoria',
      align: 'left',
    },
  ];
  for (const a of anniDisponibili.value) {
    cols.push({
      name: `anno-${a}`,
      label: String(a),
      field: `anno_${a}`,
      align: 'right',
      format: (v: number) => formattaEuro(v ?? 0),
    });
  }
  cols.push({
    name: 'totale',
    label: 'Totale',
    field: 'totale',
    align: 'right',
    format: (v: number) => formattaEuro(v ?? 0),
  });
  return cols;
});

interface StoricoRow {
  categoria: string;
  totale: number;
  [k: `anno_${number}`]: number;
}

interface DatoGrafico {
  anno: number;
  perCategoria: Record<string, number>;
}

const datiGrafico = computed<DatoGrafico[]>(() => {
  const map: Record<number, DatoGrafico> = {};
  for (const e of store.expenses) {
    const a = new Date(e.data).getFullYear();
    if (!map[a]) map[a] = { anno: a, perCategoria: {} };
    const cat = categoriaOf(e);
    map[a].perCategoria[cat] = (map[a].perCategoria[cat] ?? 0) + toNumber(e.importo);
  }
  return Object.values(map).sort((a, b) => a.anno - b.anno);
});

const storicoRows = computed<StoricoRow[]>(() => {
  const map: Record<string, StoricoRow> = {};
  for (const e of store.expenses) {
    const cat = categoriaOf(e);
    if (!map[cat]) {
      map[cat] = { categoria: cat, totale: 0 };
    }
    const a = new Date(e.data).getFullYear();
    const k = `anno_${a}` as const;
    map[cat][k] = (map[cat][k] ?? 0) + toNumber(e.importo);
    map[cat].totale += toNumber(e.importo);
  }
  // Riga totali finale
  const totali: StoricoRow = { categoria: 'Totale', totale: 0 };
  for (const r of Object.values(map)) {
    totali.totale += r.totale;
    for (const a of anniDisponibili.value) {
      const k = `anno_${a}` as const;
      totali[k] = (totali[k] ?? 0) + (r[k] ?? 0);
    }
  }
  const arr = Object.values(map).sort((a, b) => b.totale - a.totale);
  arr.push(totali);
  return arr;
});

onMounted(() => {
  void store.fetchExpenses();
  void contiStore.ensureLoaded();
  void categoriesStore.ensureLoaded();
});

function ricarica() {
  void store.fetchExpenses(true);
}

function annulla() {
  dialogAperto.value = false;
  resetErrors();
}

async function salva() {
  resetErrors();
  loadingSalva.value = true;
  try {
    const payload: NuovaSpesa = {
      data: form.data,
      descrizione: form.descrizione,
      importo: form.importo,
      category: form.category,
      note: form.note || undefined,
      crea_bank_transaction: form.crea_bank_transaction,
    };
    if (form.crea_bank_transaction) {
      payload.bt_owner_account = form.bt_owner_account;
      payload.bt_data = form.bt_data || form.data;
      payload.bt_descrizione = form.bt_descrizione || form.descrizione;
    }
    await store.creaSpesa(payload);
    Notify.create({ type: 'positive', message: 'Spesa salvata', icon: 'check_circle' });
    dialogAperto.value = false;
    Object.assign(form, {
      data: new Date().toISOString().slice(0, 10),
      descrizione: '',
      importo: 0,
      category: null,
      note: '',
      crea_bank_transaction: true,
      bt_owner_account: contoDefaultBT.value,
      bt_data: new Date().toISOString().slice(0, 10),
      bt_descrizione: '',
    });
  } catch (e: unknown) {
    captureError(e);
  } finally {
    loadingSalva.value = false;
  }
}
</script>

<style scoped>
.vp-p-spese__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: var(--vp-gap-5);
  gap: var(--vp-gap-3);
  flex-wrap: wrap;
}
.vp-p-spese__azioni {
  display: flex;
  gap: var(--vp-gap-2);
}
.vp-p-spese__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 0;
}
.vp-p-spese__sub {
  color: var(--vp-ink-2);
  font-size: var(--vp-text-sm);
  margin-top: var(--vp-gap-1);
}
.vp-p-spese__storico {
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  padding: var(--vp-gap-4);
  margin-bottom: var(--vp-gap-5);
}
.vp-p-spese__storico-title {
  margin-bottom: var(--vp-gap-2);
}
.vp-p-spese__storico-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.6fr);
  gap: var(--vp-gap-4);
  align-items: start;
}
@media (max-width: 900px) {
  .vp-p-spese__storico-grid {
    grid-template-columns: 1fr;
  }
}
.vp-p-spese__storico-chart {
  display: flex;
  align-items: stretch;
  min-width: 0;
}
.vp-p-spese__storico-chart > * {
  flex: 1;
  min-width: 0;
}
.vp-p-spese__storico-table {
  margin-top: 0;
}
.vp-p-spese__filtri-gruppi {
  display: flex;
  flex-wrap: wrap;
  gap: var(--vp-gap-2);
  align-items: center;
}
.vp-p-spese__filtro-prodotto {
  border-left: 1px solid var(--vp-paper-3);
  padding-left: var(--vp-gap-2);
}
.vp-p-spese__tabs-wrapper {
  display: flex;
  align-items: center;
  background: var(--vp-paper-2);
  border-radius: var(--vp-r-md) var(--vp-r-md) 0 0;
  margin-top: var(--vp-gap-2);
}
.vp-p-spese__tabs {
  flex: 1;
}
.vp-p-spese__panels {
  background: transparent;
}
.vp-p-spese__filtri {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: var(--vp-gap-3) 0;
  flex-wrap: wrap;
  gap: var(--vp-gap-2);
}
.vp-p-spese__totali {
  display: flex;
  align-items: baseline;
  gap: var(--vp-gap-2);
  font-family: var(--vp-font-display);
  font-size: var(--vp-text-xl);
}
.vp-p-spese__totali-label {
  font-family: var(--vp-font-ui);
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-3);
}
.vp-p-spese__table {
  background: var(--vp-cream);
  border-color: var(--vp-paper-3) !important;
}
.vp-p-spese__dialog {
  width: min(560px, 95vw);
  background: var(--vp-cream);
}
.vp-p-spese__dialog-titolo {
  font-size: var(--vp-text-xl);
  margin: var(--vp-gap-1) 0 0;
}
.vp-p-spese__bt-sezione {
  display: flex;
  flex-direction: column;
  gap: var(--vp-gap-2);
}
.vp-p-spese__bt-campi {
  display: flex;
  flex-direction: column;
  gap: var(--vp-gap-2);
  padding-left: var(--vp-gap-3);
  border-left: 2px solid var(--vp-paper-3);
}
.vp-mono {
  font-variant-numeric: tabular-nums;
}
</style>
