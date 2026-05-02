<template>
  <q-page padding class="vp-p-qa">
    <header class="vp-p-qa__head">
      <div>
        <div class="vp-eyebrow">Conguagli utenze</div>
        <h1 class="vp-display vp-p-qa__titolo">Quadro annuale</h1>
      </div>
      <div class="vp-p-qa__azioni">
        <q-select
          v-model="annoSelezionato"
          :options="anniDisponibili"
          dense
          outlined
          label="Anno"
          class="vp-p-qa__anno"
          @update:model-value="onAnnoChange"
        />
        <q-btn
          flat
          color="primary"
          icon="download"
          no-caps
          label="Esporta CSV"
          :disable="!quadro"
          @click="esportaCsv"
        />
      </div>
    </header>

    <div v-if="store.loading" class="vp-p-qa__loader">
      <q-spinner color="primary" size="32px" />
    </div>

    <EmptyState
      v-else-if="!quadro || quadro.righe.length === 0"
      icon="table_view"
      title="Nessun dato per l'anno selezionato"
      message="Cambia anno o registra dei conguagli per popolare la tabella."
    />

    <div v-else class="vp-p-qa__table-wrap vp-scroll">
      <table class="vp-table">
        <thead>
          <tr>
            <th>Periodo</th>
            <th v-for="t in quadro.tenants" :key="t" class="text-right">{{ t }}</th>
            <th class="text-right">Totale</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="riga in quadro.righe" :key="riga.periodo_id">
            <td>{{ riga.periodo_label }}</td>
            <td
              v-for="t in quadro.tenants"
              :key="t"
              class="text-right vp-mono"
            >
              {{ formattaEuro(riga.per_tenant[t]?.importo ?? 0) }}
            </td>
            <td class="text-right vp-mono">{{ formattaEuro(riga.totale_periodo) }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <th>Totale anno</th>
            <th
              v-for="t in quadro.tenants"
              :key="t"
              class="text-right vp-mono"
            >
              {{ formattaEuro(quadro.totale_anno_per_tenant[t] ?? 0) }}
            </th>
            <th class="text-right vp-mono">{{ formattaEuro(quadro.totale_anno) }}</th>
          </tr>
        </tfoot>
      </table>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useQuadroStore } from 'stores/quadro';
import EmptyState from 'src/components/EmptyState.vue';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { Notify } from 'quasar';

const store = useQuadroStore();
const { formattaEuro } = useFormatoEuro();

const annoCorrente = new Date().getFullYear();
const annoSelezionato = ref<number>(annoCorrente);
const anniDisponibili = computed<number[]>(() => {
  const lista: number[] = [];
  for (let a = annoCorrente; a >= annoCorrente - 5; a -= 1) lista.push(a);
  return lista;
});

const quadro = computed(() => store.byAnno[annoSelezionato.value] ?? null);

onMounted(() => {
  void store.loadAnno(annoSelezionato.value);
});

function onAnnoChange(v: number) {
  void store.loadAnno(v);
}

function esportaCsv() {
  const q = quadro.value;
  if (!q) return;

  const sep = ';';
  const righeCsv: string[] = [];
  const intestazione = ['Periodo', ...q.tenants, 'Totale'];
  righeCsv.push(intestazione.join(sep));

  for (const riga of q.righe) {
    const cells = [
      riga.periodo_label,
      ...q.tenants.map((t) => (riga.per_tenant[t]?.importo ?? 0).toFixed(2).replace('.', ',')),
      riga.totale_periodo.toFixed(2).replace('.', ','),
    ];
    righeCsv.push(cells.join(sep));
  }

  const totali = [
    'Totale anno',
    ...q.tenants.map((t) => (q.totale_anno_per_tenant[t] ?? 0).toFixed(2).replace('.', ',')),
    q.totale_anno.toFixed(2).replace('.', ','),
  ];
  righeCsv.push(totali.join(sep));

  const csv = righeCsv.join('\n');
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `quadro-annuale-${q.anno}.csv`;
  link.click();
  URL.revokeObjectURL(url);

  Notify.create({ type: 'positive', message: 'CSV esportato', icon: 'download' });
}
</script>

<style scoped>
.vp-p-qa__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: var(--vp-gap-5);
  gap: var(--vp-gap-3);
  flex-wrap: wrap;
}
.vp-p-qa__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 0;
}
.vp-p-qa__azioni {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-3);
}
.vp-p-qa__anno {
  min-width: 120px;
}
.vp-p-qa__table-wrap {
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  overflow: auto;
}
.vp-p-qa__loader {
  display: flex;
  justify-content: center;
  padding: var(--vp-gap-7);
}
.vp-table tfoot th {
  background: var(--vp-paper-2);
  border-top: 2px solid var(--vp-paper-3);
}
.text-right {
  text-align: right;
}
</style>
