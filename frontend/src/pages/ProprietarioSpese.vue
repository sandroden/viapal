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

    <!-- Andamento storico -->
    <section class="vp-p-spese__storico" v-if="anniDisponibili.length">
      <div class="vp-eyebrow">Andamento per anno</div>
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
    </section>

    <!-- Tab per anno -->
    <q-tabs
      v-model="annoSelezionato"
      align="left"
      dense
      indicator-color="primary"
      class="vp-p-spese__tabs"
    >
      <q-tab v-for="a in anniDisponibili" :key="a" :name="a" :label="String(a)" />
    </q-tabs>

    <q-tab-panels v-model="annoSelezionato" animated class="vp-p-spese__panels">
      <q-tab-panel v-for="a in anniDisponibili" :key="a" :name="a" class="q-pa-none">
        <div class="vp-p-spese__filtri">
          <q-btn-toggle
            v-model="filtroCategoria"
            :options="filtroOptions"
            no-caps
            unelevated
            toggle-color="primary"
          />
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
          <template #body-cell-importo="props">
            <q-td :props="props" class="text-right">
              <span class="vp-mono">{{ formattaEuro(toNumber(props.row.importo)) }}</span>
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>
    </q-tab-panels>

    <!-- Dialog aggiungi spesa -->
    <q-dialog v-model="dialogAperto" persistent>
      <q-card class="vp-p-spese__dialog">
        <q-card-section>
          <div class="vp-eyebrow">Nuova spesa</div>
          <h2 class="vp-display vp-p-spese__dialog-titolo">Aggiungi spesa</h2>
        </q-card-section>
        <q-card-section>
          <q-form class="q-gutter-md" @submit.prevent="salva">
            <q-input v-model="form.data" type="date" outlined label="Data" />
            <q-input v-model="form.descrizione" outlined label="Descrizione" />
            <q-input
              v-model.number="form.importo"
              type="number"
              step="0.01"
              outlined
              label="Importo (€)"
            />
            <q-input v-model="form.categoria" outlined label="Categoria" />
            <q-input v-model="form.fornitore" outlined label="Fornitore" />
            <q-input v-model="form.note" outlined type="textarea" label="Note" autogrow />
            <q-banner v-if="errore" class="bg-red-1 text-red-9" rounded>{{ errore }}</q-banner>
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
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';

const store = useExpensesStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

const dialogAperto = ref(false);
const loadingSalva = ref(false);
const errore = ref('');

const form = reactive<NuovaSpesa>({
  data: new Date().toISOString().slice(0, 10),
  descrizione: '',
  importo: 0,
  categoria: '',
  fornitore: '',
  note: '',
});

const colonne: QTableProps['columns'] = [
  { name: 'data', label: 'Data', field: 'data', align: 'left', sortable: true },
  { name: 'descrizione', label: 'Descrizione', field: 'descrizione', align: 'left', sortable: true },
  { name: 'category', label: 'Categoria', field: 'category_nome', align: 'left', sortable: true },
  { name: 'anticipata_da', label: 'Anticipata da', field: 'anticipata_da_nominativo', align: 'left' },
  { name: 'importo', label: 'Importo', field: 'importo', align: 'right', sortable: true },
];

const paginazione = { rowsPerPage: 25, sortBy: 'data', descending: true };

function toNumber(v: string | number | null | undefined): number {
  if (v == null) return 0;
  return typeof v === 'string' ? Number(v) : v;
}

function categoriaOf(e: Expense): string {
  return e.category_nome || e.categoria || 'Altro';
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
  const righe = righeAnno(a);
  if (filtroCategoria.value === 'Tutte') return righe;
  return righe.filter((e) => categoriaOf(e) === filtroCategoria.value);
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
});

function ricarica() {
  void store.fetchExpenses(true);
}

function annulla() {
  dialogAperto.value = false;
  errore.value = '';
}

async function salva() {
  errore.value = '';
  if (!form.descrizione || !form.data || !form.importo || form.importo <= 0) {
    errore.value = 'Compila i campi obbligatori';
    return;
  }
  loadingSalva.value = true;
  try {
    await store.creaSpesa({
      data: form.data,
      descrizione: form.descrizione,
      importo: form.importo,
      categoria: form.categoria || undefined,
      fornitore: form.fornitore || undefined,
      note: form.note || undefined,
    });
    Notify.create({ type: 'positive', message: 'Spesa salvata', icon: 'check_circle' });
    dialogAperto.value = false;
    Object.assign(form, {
      data: new Date().toISOString().slice(0, 10),
      descrizione: '',
      importo: 0,
      categoria: '',
      fornitore: '',
      note: '',
    });
  } catch (e: unknown) {
    const msg =
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
      'Salvataggio non riuscito';
    errore.value = msg;
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
.vp-p-spese__storico-table {
  margin-top: var(--vp-gap-2);
}
.vp-p-spese__tabs {
  background: var(--vp-paper-2);
  border-radius: var(--vp-r-md) var(--vp-r-md) 0 0;
  margin-top: var(--vp-gap-2);
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
.vp-mono {
  font-variant-numeric: tabular-nums;
}
</style>
