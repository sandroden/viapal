<template>
  <q-page padding class="vp-p-inq">
    <header class="vp-p-inq__head">
      <div>
        <div class="vp-eyebrow">Anagrafica</div>
        <h1 class="vp-display vp-p-inq__titolo">Inquilini</h1>
      </div>
      <q-toggle
        v-model="mostraTutti"
        label="Mostra anche storici"
        left-label
        dense
        color="primary"
      />
    </header>

    <q-table
      flat
      bordered
      :rows="store.tenants"
      :columns="colonne"
      row-key="id"
      :loading="store.loading"
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
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import type { QTableProps } from 'quasar';
import { useTenantsStore, type Tenant } from 'stores/tenants';

const router = useRouter();
const store = useTenantsStore();

const mostraTutti = ref(false);

const colonne: QTableProps['columns'] = [
  { name: 'nominativo', label: 'Nominativo', field: 'nominativo', align: 'left', sortable: true },
  { name: 'email', label: 'Email', field: 'email', align: 'left', sortable: true },
  { name: 'telefono', label: 'Telefono', field: 'telefono', align: 'left' },
  { name: 'azioni', label: '', field: 'id', align: 'right' },
];

const paginazione = { rowsPerPage: 25, sortBy: 'nominativo' };

watch(
  mostraTutti,
  (v) => {
    void store.fetchTenants(!v, true);
  },
  { immediate: true },
);

function apri(t: Tenant) {
  void router.push({ name: 'p-inquilino-dettaglio', params: { id: t.id } });
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
.vp-p-inq__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 0;
}
.vp-p-inq__table {
  background: var(--vp-cream);
  border-color: var(--vp-paper-3) !important;
}
</style>
