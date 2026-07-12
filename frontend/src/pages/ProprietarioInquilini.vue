<template>
  <q-page padding class="vp-p-inq">
    <header class="vp-p-inq__head">
      <div>
        <div class="vp-eyebrow">Anagrafica</div>
        <h1 class="vp-display vp-p-inq__titolo">Inquilini</h1>
      </div>
      <div class="vp-p-inq__controls">
        <q-btn
          v-if="puoModificare"
          unelevated
          color="primary"
          icon="person_add"
          label="Nuovo inquilino"
          no-caps
          data-testid="nuovo-inquilino"
          @click="apriDialogNuovoInquilino"
        />
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
      :visible-columns="colonneVisibili"
      row-key="id"
      :loading="caricamento"
      :pagination="paginazione"
      no-data-label="Nessun inquilino"
      class="vp-p-inq__table"
      @row-click="(_, riga: Tenant) => apri(riga)"
    >
      <template #body-cell-saldo="props">
        <q-td :props="props" class="vp-mono vp-p-inq__saldo" :class="classeSaldo(props.row.saldo)">
          {{ props.row.saldo === null || props.row.saldo === undefined ? '—' : formattaEuro(props.row.saldo) }}
        </q-td>
      </template>
      <template #body-cell-saldo_totale="props">
        <q-td
          :props="props"
          class="vp-mono vp-p-inq__saldo"
          :class="classeSaldo(props.row.saldo_totale)"
        >
          {{
            props.row.saldo_totale === null || props.row.saldo_totale === undefined
              ? '—'
              : formattaEuro(props.row.saldo_totale)
          }}
        </q-td>
      </template>
      <template #body-cell-azioni="props">
        <q-td :props="props" auto-width class="vp-p-inq__azioni">
          <q-btn
            flat
            round
            dense
            icon="theater_comedy"
            color="primary"
            :loading="impersonandoId === props.row.id"
            aria-label="Vedi come questo inquilino"
            @click.stop="impersona(props.row)"
          >
            <q-tooltip>Vedi come {{ props.row.nominativo }}</q-tooltip>
          </q-btn>
        </q-td>
      </template>
    </q-table>

    <!-- Dialog nuovo inquilino -->
    <q-dialog v-model="dialogNuovo">
      <q-card style="min-width: 420px">
        <q-card-section>
          <div class="vp-p-inq__dialog-titolo">Nuovo inquilino</div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input
            v-model="formNuovo.nominativo"
            label="Nominativo"
            outlined
            dense
            autofocus
            data-testid="nuovo-inquilino-nominativo"
          />
          <q-input
            v-model="formNuovo.email"
            label="Email (facoltativa, serve per l'invito)"
            type="email"
            outlined
            dense
            data-testid="nuovo-inquilino-email"
          />
          <q-input
            v-model="formNuovo.telefono"
            label="Telefono"
            outlined
            dense
          />
          <q-input
            v-model="formNuovo.giorno_pagamento_affitto"
            label="Giorno pagamento affitto (1-28)"
            type="number"
            min="1"
            max="28"
            outlined
            dense
            data-testid="nuovo-inquilino-giorno"
          />
          <q-select
            v-model="formNuovo.frequenza_conguagli"
            :options="opzioniFrequenzaConguagli"
            label="Frequenza conguagli utenze"
            outlined
            dense
            emit-value
            map-options
          />
          <q-banner v-if="erroreNuovo" class="vp-p-inq__banner-errore" rounded dense>
            {{ erroreNuovo }}
          </q-banner>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn v-close-popup flat label="Annulla" />
          <q-btn
            color="primary"
            label="Crea inquilino"
            :loading="salvandoNuovo"
            data-testid="nuovo-inquilino-salva"
            @click="creaInquilino"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { isAxiosError } from 'axios';
import { useQuasar, type QTableProps } from 'quasar';
import { api } from 'boot/axios';
import { useTenantsStore, type Tenant } from 'stores/tenants';
import { useAuthStore } from 'stores/auth';
import { usePropertiesStore } from 'stores/properties';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';

const { formattaEuro } = useFormatoEuro();

const router = useRouter();
const route = useRoute();
const store = useTenantsStore();
const auth = useAuthStore();
const propStore = usePropertiesStore();
const $q = useQuasar();

const puoModificare = computed(
  () => propStore.mioRuolo === 'proprietario' || propStore.mioRuolo === 'gestore',
);

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

const colonne = computed<QTableProps['columns']>(() => [
  { name: 'nominativo', label: 'Nominativo', field: 'nominativo', align: 'left', sortable: true },
  { name: 'email', label: 'Email', field: 'email', align: 'left', sortable: true },
  { name: 'telefono', label: 'Telefono', field: 'telefono', align: 'left' },
  {
    name: 'saldo',
    label: `Saldo ${annoSelezionato.value}`,
    field: 'saldo',
    align: 'right',
    sortable: true,
    sort: (a: number | null, b: number | null) => (a ?? 0) - (b ?? 0),
  },
  {
    name: 'saldo_totale',
    label: 'Saldo totale',
    field: 'saldo_totale',
    align: 'right',
    sortable: true,
    sort: (a: number | null, b: number | null) => (a ?? 0) - (b ?? 0),
  },
  { name: 'azioni', label: '', field: 'id', align: 'right' },
]);

const colonneVisibili = computed<string[]>(() => {
  const v = ['nominativo', 'email', 'telefono'];
  if (!mostraTutti.value) v.push('saldo');
  v.push('saldo_totale', 'azioni');
  return v;
});

function classeSaldo(s: number | null | undefined): string {
  if (s === null || s === undefined) return '';
  if (s < -0.005) return 'vp-p-inq__saldo--neg';
  if (s > 0.005) return 'vp-p-inq__saldo--pos';
  return 'vp-p-inq__saldo--zero';
}

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
    // force=true: rientrando in pagina dopo aver registrato pagamenti o
    // ribilanciato riconciliazioni vogliamo vedere subito i saldi nuovi.
    void store.fetchTenantsAnno(a, true);
    aggiornaQuery();
  },
  { immediate: true },
);

function apri(t: Tenant, tab: 'pagamenti' | 'profilo' = 'pagamenti') {
  const q: Record<string, string> = { tab };
  if (!mostraTutti.value) q.anno = String(annoSelezionato.value);
  void router.push({
    name: 'p-inquilino-dettaglio',
    params: { id: t.id },
    query: q,
  });
}

// --- Nuovo inquilino (dialog additivo) -------------------------------------

const dialogNuovo = ref(false);
const salvandoNuovo = ref(false);
const erroreNuovo = ref('');
interface FormNuovoInquilino {
  nominativo: string;
  email: string;
  telefono: string;
  giorno_pagamento_affitto: string;
  frequenza_conguagli: 'mensile' | 'bimestrale';
}

const formNuovo = ref<FormNuovoInquilino>({
  nominativo: '',
  email: '',
  telefono: '',
  giorno_pagamento_affitto: '5',
  frequenza_conguagli: 'mensile',
});

const opzioniFrequenzaConguagli = [
  { label: 'Mensile', value: 'mensile' },
  { label: 'Bimestrale', value: 'bimestrale' },
];

function messaggioErrore(e: unknown, fallback: string): string {
  if (isAxiosError(e)) {
    const data = e.response?.data as Record<string, unknown> | undefined;
    if (data && typeof data === 'object') {
      if (typeof data.detail === 'string') return data.detail;
      for (const valore of Object.values(data)) {
        if (typeof valore === 'string') return valore;
        if (Array.isArray(valore) && typeof valore[0] === 'string') return valore[0];
      }
    }
  }
  return fallback;
}

function apriDialogNuovoInquilino() {
  erroreNuovo.value = '';
  formNuovo.value = {
    nominativo: '',
    email: '',
    telefono: '',
    giorno_pagamento_affitto: '5',
    frequenza_conguagli: 'mensile',
  };
  dialogNuovo.value = true;
}

async function creaInquilino() {
  erroreNuovo.value = '';
  const f = formNuovo.value;
  if (!f.nominativo.trim()) {
    erroreNuovo.value = 'Il nominativo è obbligatorio.';
    return;
  }
  const giorno = Number(f.giorno_pagamento_affitto);
  if (!Number.isInteger(giorno) || giorno < 1 || giorno > 28) {
    erroreNuovo.value = 'Il giorno di pagamento deve essere tra 1 e 28.';
    return;
  }
  salvandoNuovo.value = true;
  try {
    const { data: creato } = await api.post<Tenant>('/api/v1/tenants/', {
      nominativo: f.nominativo.trim(),
      email: f.email.trim(),
      telefono: f.telefono.trim(),
      giorno_pagamento_affitto: giorno,
      frequenza_conguagli: f.frequenza_conguagli,
    });
    dialogNuovo.value = false;
    $q.notify({ type: 'positive', message: `Inquilino ${creato.nominativo} creato.` });
    // Ricarica le liste correnti (la vista attiva e l'eventuale "tutti").
    void store.fetchTenantsAnno(annoSelezionato.value, true);
    if (mostraTutti.value) void store.fetchTenants(false, true);
    if (f.email.trim()) proponiInvito(creato);
  } catch (e: unknown) {
    erroreNuovo.value = messaggioErrore(e, 'Creazione non riuscita.');
  } finally {
    salvandoNuovo.value = false;
  }
}

function proponiInvito(t: Tenant) {
  $q.dialog({
    title: 'Inviare l\'invito?',
    message: `Inviare a ${t.nominativo} l'email di primo accesso (${t.email ?? ''})?`,
    cancel: { flat: true, label: 'Più tardi' },
    ok: { color: 'primary', label: 'Invia invito' },
  }).onOk(() => {
    void (async () => {
      try {
        const { data } = await api.post<{ esito: string; email: string; errore?: string }>(
          `/api/v1/tenants/${t.id}/invita/`,
        );
        $q.notify({ type: 'positive', message: `Invito inviato a ${data.email}.` });
      } catch (e: unknown) {
        $q.notify({
          type: 'negative',
          message: messaggioErrore(e, 'Invio dell\'invito non riuscito.'),
        });
      }
    })();
  });
}

// Impersonation diretta dalla lista ("vedi come questo inquilino").
const impersonandoId = ref<number | null>(null);
async function impersona(t: Tenant) {
  impersonandoId.value = t.id;
  try {
    // impersonate() fa hard reload verso /i/: in caso di successo la pagina si
    // ricarica e questa funzione non prosegue oltre.
    await auth.impersonate(t.id);
  } catch {
    $q.notify({ type: 'negative', message: 'Impossibile impersonare questo inquilino.' });
    impersonandoId.value = null;
  }
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
.vp-p-inq__saldo--neg {
  color: var(--vp-terra, #b56a3b);
  font-weight: 600;
}
.vp-p-inq__saldo--pos {
  color: var(--vp-salvia, #4f6e3f);
}
.vp-p-inq__saldo--zero {
  color: var(--vp-ink-3);
}
.vp-p-inq__azioni {
  white-space: nowrap;
}
.vp-mono {
  font-variant-numeric: tabular-nums;
}
.vp-p-inq__dialog-titolo {
  font-weight: 600;
  font-size: 16px;
  color: var(--vp-ink-1);
}
.vp-p-inq__banner-errore {
  background: var(--vp-clay-soft, #fbeae5);
  color: var(--vp-clay-deep, #8c3b21);
}
</style>
