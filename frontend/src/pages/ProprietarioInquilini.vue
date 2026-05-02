<template>
  <q-page padding class="vp-p-inq">
    <header class="vp-p-inq__head">
      <div>
        <div class="vp-eyebrow">Anagrafica</div>
        <h1 class="vp-display vp-p-inq__titolo">Inquilini</h1>
      </div>
      <q-btn
        flat
        color="primary"
        icon="refresh"
        no-caps
        label="Aggiorna"
        :loading="store.loading"
        @click="ricarica"
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

    <q-drawer
      v-model="dettaglioAperto"
      side="right"
      :width="380"
      overlay
      bordered
      class="vp-p-inq__drawer"
    >
      <div v-if="selezionato" class="vp-p-inq__drawer-content">
        <div class="vp-eyebrow">Inquilino</div>
        <h2 class="vp-display vp-p-inq__drawer-titolo">{{ selezionato.nominativo }}</h2>

        <q-list separator>
          <q-item v-if="selezionato.email">
            <q-item-section>
              <q-item-label caption>Email</q-item-label>
              <q-item-label>{{ selezionato.email }}</q-item-label>
            </q-item-section>
          </q-item>
          <q-item v-if="selezionato.telefono">
            <q-item-section>
              <q-item-label caption>Telefono</q-item-label>
              <q-item-label>{{ selezionato.telefono }}</q-item-label>
            </q-item-section>
          </q-item>
          <q-item v-if="selezionato.data_nascita">
            <q-item-section>
              <q-item-label caption>Data di nascita</q-item-label>
              <q-item-label>{{ formattaData(selezionato.data_nascita) }}</q-item-label>
            </q-item-section>
          </q-item>
          <q-item v-if="selezionato.documento_numero">
            <q-item-section>
              <q-item-label caption>Documento</q-item-label>
              <q-item-label>
                {{ selezionato.documento_tipo || 'documento' }} ·
                {{ selezionato.documento_numero }}
              </q-item-label>
            </q-item-section>
          </q-item>
          <q-item v-if="selezionato.note">
            <q-item-section>
              <q-item-label caption>Note</q-item-label>
              <q-item-label>{{ selezionato.note }}</q-item-label>
            </q-item-section>
          </q-item>
        </q-list>

        <div class="vp-p-inq__drawer-azioni">
          <q-btn flat color="primary" label="Chiudi" no-caps @click="dettaglioAperto = false" />
        </div>
      </div>
    </q-drawer>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import type { QTableProps } from 'quasar';
import { useTenantsStore, type Tenant } from 'stores/tenants';
import { useFormatoData } from 'src/composables/useFormatoData';

const store = useTenantsStore();
const { formattaData } = useFormatoData();

const dettaglioAperto = ref(false);
const selezionato = ref<Tenant | null>(null);

const colonne: QTableProps['columns'] = [
  { name: 'nominativo', label: 'Nominativo', field: 'nominativo', align: 'left', sortable: true },
  { name: 'email', label: 'Email', field: 'email', align: 'left', sortable: true },
  { name: 'telefono', label: 'Telefono', field: 'telefono', align: 'left' },
  { name: 'azioni', label: '', field: 'id', align: 'right' },
];

const paginazione = { rowsPerPage: 25, sortBy: 'nominativo' };

onMounted(() => {
  void store.fetchTenants();
});

function ricarica() {
  void store.fetchTenants(true);
}

function apri(t: Tenant) {
  selezionato.value = t;
  dettaglioAperto.value = true;
}
</script>

<style scoped>
.vp-p-inq__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: var(--vp-gap-5);
  gap: var(--vp-gap-3);
}
.vp-p-inq__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 0;
}
.vp-p-inq__table {
  background: var(--vp-cream);
  border-color: var(--vp-paper-3) !important;
}
.vp-p-inq__drawer {
  background: var(--vp-cream);
}
.vp-p-inq__drawer-content {
  padding: var(--vp-gap-5);
}
.vp-p-inq__drawer-titolo {
  font-size: var(--vp-text-xl);
  margin: var(--vp-gap-1) 0 var(--vp-gap-4);
}
.vp-p-inq__drawer-azioni {
  margin-top: var(--vp-gap-5);
  display: flex;
  justify-content: flex-end;
}
</style>
