<template>
  <q-page padding class="vp-p-spese">
    <header class="vp-p-spese__head">
      <div>
        <div class="vp-eyebrow">Uscite</div>
        <h1 class="vp-display vp-p-spese__titolo">Spese</h1>
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

    <q-table
      flat
      bordered
      :rows="store.expenses"
      :columns="colonne"
      row-key="id"
      :loading="store.loading"
      :pagination="paginazione"
      no-data-label="Nessuna spesa registrata"
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
              :rules="[(v) => !!v || 'Inserisci la data']"
            />
            <q-input
              v-model="form.descrizione"
              outlined
              label="Descrizione"
              :rules="[(v) => !!v || 'Inserisci la descrizione']"
            />
            <q-input
              v-model.number="form.importo"
              type="number"
              step="0.01"
              outlined
              label="Importo (€)"
              :rules="[(v) => (v != null && v > 0) || 'Importo non valido']"
            />
            <q-input v-model="form.categoria" outlined label="Categoria" />
            <q-input v-model="form.fornitore" outlined label="Fornitore" />
            <q-input v-model="form.note" outlined type="textarea" label="Note" autogrow />

            <q-banner v-if="errore" class="bg-red-1 text-red-9" rounded>
              {{ errore }}
            </q-banner>
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
import { onMounted, reactive, ref } from 'vue';
import type { QTableProps } from 'quasar';
import { Notify } from 'quasar';
import { useExpensesStore, type NuovaSpesa } from 'stores/expenses';
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
  {
    name: 'descrizione',
    label: 'Descrizione',
    field: 'descrizione',
    align: 'left',
    sortable: true,
  },
  { name: 'categoria', label: 'Categoria', field: 'categoria', align: 'left' },
  { name: 'fornitore', label: 'Fornitore', field: 'fornitore', align: 'left' },
  { name: 'importo', label: 'Importo', field: 'importo', align: 'right', sortable: true },
];

const paginazione = { rowsPerPage: 25, sortBy: 'data', descending: true };

onMounted(() => {
  void store.fetchExpenses();
});

function ricarica() {
  void store.fetchExpenses(true);
}

function toNumber(v: string | number): number {
  return typeof v === 'string' ? Number(v) : v;
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
</style>
