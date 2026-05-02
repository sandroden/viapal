<template>
  <q-page padding class="vp-p-rit">
    <header class="vp-p-rit__head">
      <div>
        <div class="vp-eyebrow">Pagamenti scaduti</div>
        <h1 class="vp-display vp-p-rit__titolo">Ritardi</h1>
      </div>
      <q-btn
        flat
        color="primary"
        icon="refresh"
        :loading="store.loadingProprietario"
        @click="ricarica"
        no-caps
        label="Aggiorna"
      />
    </header>

    <q-table
      flat
      bordered
      :rows="ritardi"
      :columns="colonne"
      row-key="rowKey"
      :pagination="paginazione"
      :loading="store.loadingProprietario"
      no-data-label="Nessun pagamento in ritardo"
      class="vp-p-rit__table"
    >
      <template #body-cell-importo="props">
        <q-td :props="props">
          <span class="vp-mono">{{ formattaEuro(props.row.importo) }}</span>
        </q-td>
      </template>
      <template #body-cell-scadenza="props">
        <q-td :props="props">
          {{ formattaData(props.row.scadenza) }}
        </q-td>
      </template>
      <template #body-cell-semaforo="props">
        <q-td :props="props">
          <SemaforoBadge
            :livello="livelloDaGiorni(props.row.giorni_ritardo)"
            :giorni-ritardo="props.row.giorni_ritardo"
          />
        </q-td>
      </template>
      <template #body-cell-azioni="props">
        <q-td :props="props">
          <q-btn
            flat
            dense
            color="primary"
            icon="check"
            no-caps
            label="Conferma"
            :loading="processing[props.row.rowKey]"
            @click="conferma(props.row)"
          />
        </q-td>
      </template>
    </q-table>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive } from 'vue';
import type { QTableProps } from 'quasar';
import { Notify } from 'quasar';
import { useDashboardStore, type ProprietarioRiga } from 'stores/dashboard';
import { usePaymentsStore } from 'stores/payments';
import SemaforoBadge from 'src/components/SemaforoBadge.vue';
import type { SemaforoLivello } from 'src/types/semaforo';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';

interface RigaTabella extends ProprietarioRiga {
  rowKey: string;
}

const store = useDashboardStore();
const payments = usePaymentsStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();
const processing = reactive<Record<string, boolean>>({});

const ritardi = computed<RigaTabella[]>(() =>
  (store.proprietarioData?.ritardi ?? []).map((r) => ({
    ...r,
    rowKey: `${r.tipo}-${r.id}`,
  })),
);

const colonne: QTableProps['columns'] = [
  { name: 'tenant', label: 'Inquilino', field: 'tenant', align: 'left', sortable: true },
  {
    name: 'descrizione',
    label: 'Descrizione',
    field: 'descrizione',
    align: 'left',
    sortable: true,
  },
  {
    name: 'importo',
    label: 'Importo',
    field: 'importo',
    align: 'right',
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
    name: 'giorni_ritardo',
    label: 'Giorni ritardo',
    field: 'giorni_ritardo',
    align: 'right',
    sortable: true,
  },
  { name: 'semaforo', label: 'Stato', field: 'giorni_ritardo', align: 'center' },
  { name: 'azioni', label: 'Azioni', field: 'tipo', align: 'right' },
];

const paginazione = {
  rowsPerPage: 25,
  sortBy: 'giorni_ritardo',
  descending: true,
};

const oggi = new Date();
const annoCorrente = oggi.getFullYear();
const meseCorrente = oggi.getMonth() + 1;

onMounted(() => {
  void store.loadProprietario(annoCorrente, meseCorrente);
});

function ricarica() {
  void store.loadProprietario(annoCorrente, meseCorrente, true);
}

function livelloDaGiorni(g: number): SemaforoLivello {
  if (g > 7) return 'argilla_scuro';
  if (g > 0) return 'argilla_chiaro';
  if (g > -7) return 'miele';
  return 'salvia';
}

async function conferma(row: RigaTabella) {
  processing[row.rowKey] = true;
  try {
    await payments.confermaPagato(row.tipo, row.id, {});
    Notify.create({ type: 'positive', message: 'Pagamento confermato', icon: 'check_circle' });
    await store.loadProprietario(annoCorrente, meseCorrente, true);
  } catch (e: unknown) {
    const msg =
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
      'Conferma non riuscita';
    Notify.create({ type: 'negative', message: msg });
  } finally {
    processing[row.rowKey] = false;
  }
}
</script>

<style scoped>
.vp-p-rit__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: var(--vp-gap-5);
  gap: var(--vp-gap-3);
}
.vp-p-rit__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 0;
}
.vp-p-rit__table {
  background: var(--vp-cream);
  border-color: var(--vp-paper-3) !important;
}
</style>
