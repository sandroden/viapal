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

    <div class="vp-p-rit__filtri">
      <!-- Due toggle con entrambi una voce "Tutti": senza etichetta si
           leggerebbero come un unico gruppo contraddittorio. -->
      <span class="vp-p-rit__filtro-label">Inquilini</span>
      <q-btn-toggle
        v-model="filtroPresenza"
        :options="filtroPresenzaOptions"
        no-caps
        unelevated
        toggle-color="primary"
        data-testid="filtro-presenza"
      >
        <q-tooltip>
          Gli ex inquilini portano gli scoperti storici, spesso ancora da
          ricostruire: di default restano fuori.
        </q-tooltip>
      </q-btn-toggle>
      <span class="vp-p-rit__filtro-label">Stato</span>
      <q-btn-toggle
        v-model="filtroStato"
        :options="filtroStatoOptions"
        no-caps
        unelevated
        toggle-color="primary"
      />
      <q-select
        v-model="filtroInquilino"
        :options="filtroInquilinoOptions"
        label="Inquilino"
        dense
        outlined
        emit-value
        map-options
        class="vp-p-rit__filtro-inq"
      />
      <q-space />
      <span class="vp-p-rit__totali-label">
        {{ ritardiFiltrati.length }} di {{ ritardi.length }}
      </span>
    </div>

    <q-table
      flat
      bordered
      :rows="ritardiFiltrati"
      :columns="colonne"
      row-key="rowKey"
      :pagination="paginazione"
      :loading="store.loadingProprietario"
      no-data-label="Nessun pagamento in ritardo"
      class="vp-p-rit__table"
    >
      <template #body-cell-tenant="props">
        <q-td :props="props">
          <a
            href="#"
            class="vp-p-rit__tenant-link"
            @click.prevent="filtraInquilino(props.row.tenant)"
          >
            {{ props.row.tenant }}
          </a>
          <q-chip
            v-if="!props.row.tenant_attivo"
            dense
            outline
            color="blue-grey-6"
            class="vp-p-rit__chip-uscito"
          >
            uscito
          </q-chip>
        </q-td>
      </template>
      <template #body-cell-importo="props">
        <q-td :props="props">
          <span class="vp-mono">{{ formattaEuro(props.row.residuo) }}</span>
          <!-- Su un parziale il dovuto pieno da solo inganna: 46,21 € letto
               come "non ha pagato" quando ne mancano 2,89. -->
          <div v-if="props.row.parziale" class="vp-p-rit__parziale">
            di {{ formattaEuro(props.row.importo_dovuto) }} ·
            {{ formattaEuro(props.row.importo_pagato) }} già versati
          </div>
        </q-td>
      </template>
      <template #body-cell-scadenza="props">
        <q-td :props="props">
          {{ formattaData(props.row.scadenza) }}
        </q-td>
      </template>
      <template #body-cell-giorni_ritardo="props">
        <q-td :props="props">
          <SemaforoBadge
            :livello="livelloDaGiorni(props.row.giorni_ritardo)"
            :giorni-ritardo="props.row.giorni_ritardo"
          />
        </q-td>
      </template>
      <template #body-cell-stato="props">
        <q-td :props="props">
          <q-chip
            dense
            :color="coloreStato(props.row.stato)"
            :text-color="textColorStato(props.row.stato)"
            :icon="iconaStato(props.row.stato)"
          >
            {{ labelStato(props.row.stato) }}
          </q-chip>
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
          <q-btn
            v-if="props.row.stato === 'dichiarato'"
            flat
            dense
            color="blue-grey-8"
            icon="undo"
            no-caps
            label="Rifiuta"
            :loading="processing[props.row.rowKey]"
            @click="rifiuta(props.row)"
          >
            <q-tooltip>
              Rimbalza la dichiarazione: l'addebito torna da pagare con il residuo reale
            </q-tooltip>
          </q-btn>
        </q-td>
      </template>
    </q-table>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import type { QTableProps } from 'quasar';
import { Notify } from 'quasar';
import { useDashboardStore, type ProprietarioRiga } from 'stores/dashboard';
import { usePaymentsStore } from 'stores/payments';
import SemaforoBadge from 'src/components/SemaforoBadge.vue';
import type { SemaforoLivello } from 'src/types/semaforo';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';
import { messaggioErrore } from 'src/utils/apiErrors';

interface RigaTabella extends ProprietarioRiga {
  rowKey: string;
}

const store = useDashboardStore();
const payments = usePaymentsStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();
const processing = reactive<Record<string, boolean>>({});

const filtroStato = ref<string>('tutti');
const filtroInquilino = ref<string>('tutti');
// Default: solo chi è in casa adesso. Gli scoperti degli usciti sono in
// buona parte dati storici ancora da ricostruire e non sono azionabili.
const filtroPresenza = ref<'attivi' | 'usciti' | 'tutti'>('attivi');

const filtroStatoOptions = [
  { label: 'Tutti', value: 'tutti' },
  { label: 'Atteso', value: 'atteso' },
  { label: 'Dichiarato', value: 'dichiarato' },
  { label: 'In ritardo', value: 'in_ritardo' },
];

const filtroPresenzaOptions = [
  { label: 'Attivi', value: 'attivi' },
  { label: 'Usciti', value: 'usciti' },
  { label: 'Tutti', value: 'tutti' },
];

const ritardi = computed<RigaTabella[]>(() =>
  (store.proprietarioData?.ritardi ?? []).map((r) => ({
    ...r,
    rowKey: `${r.tipo}-${r.id}`,
  })),
);

// Il filtro presenza viene prima di tutto: nomi nel select e totali
// devono parlare della popolazione che si sta guardando.
const ritardiPresenza = computed<RigaTabella[]>(() => {
  if (filtroPresenza.value === 'attivi') return ritardi.value.filter((r) => r.tenant_attivo);
  if (filtroPresenza.value === 'usciti') return ritardi.value.filter((r) => !r.tenant_attivo);
  return ritardi.value;
});

const filtroInquilinoOptions = computed(() => {
  const nomi = Array.from(new Set(ritardiPresenza.value.map((r) => r.tenant))).sort();
  return [
    { label: 'Tutti', value: 'tutti' },
    ...nomi.map((n) => ({ label: n, value: n })),
  ];
});

// Cambiando popolazione l'inquilino selezionato può sparire: senza questo
// la tabella resterebbe vuota senza spiegazione.
watch(filtroInquilinoOptions, (opzioni) => {
  if (
    filtroInquilino.value !== 'tutti' &&
    !opzioni.some((o) => o.value === filtroInquilino.value)
  ) {
    filtroInquilino.value = 'tutti';
  }
});

const ritardiFiltrati = computed<RigaTabella[]>(() => {
  let righe = ritardiPresenza.value;
  if (filtroStato.value !== 'tutti') {
    righe = righe.filter((r) => r.stato === filtroStato.value);
  }
  if (filtroInquilino.value !== 'tutti') {
    righe = righe.filter((r) => r.tenant === filtroInquilino.value);
  }
  return righe;
});

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
    label: 'Da saldare',
    field: 'residuo',
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
  { name: 'stato', label: 'Stato', field: 'stato', align: 'center', sortable: true },
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

function handleEsc(e: KeyboardEvent) {
  if (e.key === 'Escape' && filtroInquilino.value !== 'tutti') {
    filtroInquilino.value = 'tutti';
  }
}

onMounted(() => {
  void store.loadProprietario(annoCorrente, meseCorrente);
  window.addEventListener('keydown', handleEsc);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleEsc);
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

function labelStato(stato: string): string {
  if (stato === 'dichiarato') return 'Da confermare';
  if (stato === 'in_ritardo') return 'In ritardo';
  if (stato === 'atteso') return 'Atteso';
  return stato;
}

function coloreStato(stato: string): string {
  if (stato === 'dichiarato') return 'blue-grey-1';
  if (stato === 'in_ritardo') return 'red-1';
  return 'grey-3';
}

function textColorStato(stato: string): string {
  if (stato === 'dichiarato') return 'blue-grey-9';
  if (stato === 'in_ritardo') return 'red-9';
  return 'grey-9';
}

function iconaStato(stato: string): string {
  if (stato === 'dichiarato') return 'hourglass_top';
  if (stato === 'in_ritardo') return 'priority_high';
  return 'schedule';
}

function filtraInquilino(nome: string) {
  filtroInquilino.value = nome;
}

async function conferma(row: RigaTabella) {
  processing[row.rowKey] = true;
  try {
    await payments.confermaPagato(row.tipo, row.id, {});
    Notify.create({ type: 'positive', message: 'Pagamento confermato', icon: 'check_circle' });
    await store.loadProprietario(annoCorrente, meseCorrente, true);
  } catch (e: unknown) {
    Notify.create({ type: 'negative', message: messaggioErrore(e, 'Conferma non riuscita') });
  } finally {
    processing[row.rowKey] = false;
  }
}

async function rifiuta(row: RigaTabella) {
  processing[row.rowKey] = true;
  try {
    await payments.rifiutaPagato(row.tipo, row.id);
    Notify.create({
      type: 'info',
      message: 'Dichiarazione rifiutata: l\'addebito torna da pagare',
      icon: 'undo',
    });
    await store.loadProprietario(annoCorrente, meseCorrente, true);
  } catch (e: unknown) {
    Notify.create({ type: 'negative', message: messaggioErrore(e, 'Rifiuto non riuscito') });
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
.vp-p-rit__filtri {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-3);
  margin-bottom: var(--vp-gap-3);
  flex-wrap: wrap;
}
.vp-p-rit__filtro-label {
  color: var(--vp-ink-3);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.vp-p-rit__filtro-inq {
  min-width: 220px;
}
.vp-p-rit__totali-label {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm);
}
.vp-p-rit__parziale {
  color: var(--vp-ink-3);
  font-size: 11px;
  white-space: nowrap;
}
.vp-p-rit__table {
  background: var(--vp-cream);
  border-color: var(--vp-paper-3) !important;
}
.vp-p-rit__chip-uscito {
  font-size: 10px;
  margin-left: var(--vp-gap-2);
  vertical-align: middle;
}
.vp-p-rit__tenant-link {
  color: var(--vp-terra-deep);
  text-decoration: none;
  border-bottom: 1px dotted var(--vp-paper-3);
  cursor: pointer;
}
.vp-p-rit__tenant-link:hover {
  border-bottom-color: var(--vp-terra-deep);
}
</style>
