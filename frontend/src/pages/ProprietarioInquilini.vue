<template>
  <q-page padding class="vp-p-inq">
    <header class="vp-p-inq__head">
      <div>
        <div class="vp-eyebrow">Anagrafica</div>
        <h1 class="vp-display vp-p-inq__titolo">Inquilini</h1>
      </div>
      <div class="vp-p-inq__controls">
        <q-btn
          unelevated
          color="primary"
          icon="payments"
          label="Da incassare"
          no-caps
          :to="{ name: 'p-da-incassare' }"
        />
        <div v-if="!mostraTutti" class="vp-p-inq__nav-anno">
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
            class="vp-p-inq__sel"
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
        <q-toggle
          v-model="mostraTutti"
          label="Mostra anche storici"
          left-label
          dense
          color="primary"
        />
      </div>
    </header>

    <q-table
      flat
      bordered
      :rows="righe"
      :columns="colonne"
      row-key="id"
      :loading="caricamento"
      :pagination="paginazione"
      no-data-label="Nessun inquilino"
      class="vp-p-inq__table"
      @row-click="(_, riga: Tenant) => apri(riga)"
    >
      <template #body-cell-azioni="props">
        <q-td :props="props" auto-width>
          <q-btn
            flat
            dense
            icon="visibility"
            color="primary"
            no-caps
            label="Dettaglio"
            @click.stop="apri(props.row)"
          />
        </q-td>
      </template>
    </q-table>
  </q-page>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import type { QTableProps } from 'quasar';
import { useTenantsStore, type Tenant } from 'stores/tenants';

const router = useRouter();
const route = useRoute();
const store = useTenantsStore();

const annoCorrente = new Date().getFullYear();
const annoMin = annoCorrente - 5;

function parseAnno(v: unknown): number {
  const n = Number(Array.isArray(v) ? v[0] : v);
  if (Number.isFinite(n) && n >= annoMin && n <= annoCorrente) return n;
  return annoCorrente;
}

const annoSelezionato = ref<number>(parseAnno(route.query.anno));
const mostraTutti = ref<boolean>(route.query.storici === '1');

const anniDisponibili = computed<number[]>(() => {
  const lista: number[] = [];
  for (let a = annoCorrente; a >= annoMin; a -= 1) lista.push(a);
  return lista;
});
const puoIndietro = computed(() => annoSelezionato.value > annoMin);
const puoAvanti = computed(() => annoSelezionato.value < annoCorrente);

const righe = computed<Tenant[]>(() =>
  mostraTutti.value ? store.tenants : store.tenantsAnno(annoSelezionato.value),
);
const caricamento = computed<boolean>(() =>
  mostraTutti.value
    ? store.loading
    : Boolean(store.loadingAnno[annoSelezionato.value]),
);

const colonne: QTableProps['columns'] = [
  { name: 'nominativo', label: 'Nominativo', field: 'nominativo', align: 'left', sortable: true },
  { name: 'email', label: 'Email', field: 'email', align: 'left', sortable: true },
  { name: 'telefono', label: 'Telefono', field: 'telefono', align: 'left' },
  { name: 'azioni', label: '', field: 'id', align: 'right' },
];

const paginazione = { rowsPerPage: 25, sortBy: 'nominativo' };

function aggiornaQuery(): void {
  const q: Record<string, string> = {};
  if (!mostraTutti.value) q.anno = String(annoSelezionato.value);
  if (mostraTutti.value) q.storici = '1';
  void router.replace({ query: q });
}

function annoPrecedente() {
  if (puoIndietro.value) annoSelezionato.value -= 1;
}
function annoSuccessivo() {
  if (puoAvanti.value) annoSelezionato.value += 1;
}

watch(
  mostraTutti,
  (v) => {
    if (v) void store.fetchTenants(false, true);
    aggiornaQuery();
  },
  { immediate: true },
);

watch(
  annoSelezionato,
  (a) => {
    void store.fetchTenantsAnno(a);
    aggiornaQuery();
  },
  { immediate: true },
);

function apri(t: Tenant) {
  const q: Record<string, string> = {};
  if (!mostraTutti.value) q.anno = String(annoSelezionato.value);
  void router.push({
    name: 'p-inquilino-dettaglio',
    params: { id: t.id },
    query: q,
  });
}
</script>

<style scoped>
.vp-p-inq__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: var(--vp-gap-5);
  gap: var(--vp-gap-3);
  flex-wrap: wrap;
}
.vp-p-inq__controls {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-4);
  flex-wrap: wrap;
}
.vp-p-inq__nav-anno {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-1);
}
.vp-p-inq__sel {
  min-width: 120px;
}
.vp-p-inq__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 0;
}
.vp-p-inq__table {
  background: var(--vp-cream);
  border-color: var(--vp-paper-3) !important;
}
</style>
