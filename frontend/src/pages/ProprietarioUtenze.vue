<template>
  <q-page class="vp-page">
    <div class="vp-page__head">
      <h1 class="vp-display vp-page__title">Utenze — emissione</h1>
      <q-btn
        flat
        dense
        icon="refresh"
        label="Ricomincia"
        @click="ricomincia"
      />
    </div>

    <q-banner v-if="store.errore" class="vp-banner-error" rounded>
      <template #avatar><q-icon name="error" /></template>
      {{ store.errore }}
    </q-banner>

    <!-- 1. Carica bolletta -->
    <q-card flat bordered class="vp-card">
      <q-card-section class="vp-card__title">
        <q-icon name="upload_file" /> 1 · Carica bolletta (PDF)
      </q-card-section>
      <q-card-section class="vp-row">
        <q-select
          v-model="ownerId"
          :options="ownerOptions"
          label="Pagata da"
          emit-value
          map-options
          outlined
          dense
          class="vp-field"
        />
        <q-file
          v-model="filePdf"
          label="Seleziona uno o più PDF (gas, luce…)"
          accept=".pdf"
          multiple
          append
          use-chips
          outlined
          dense
          class="vp-field vp-field--grow"
        >
          <template #prepend><q-icon name="attach_file" /></template>
        </q-file>
        <q-btn
          color="primary"
          icon="cloud_upload"
          :label="filePdf.length > 1 ? `Carica ${filePdf.length}` : 'Carica'"
          :disable="!filePdf.length || !ownerId"
          :loading="store.loading"
          @click="onUpload"
        />
      </q-card-section>
      <q-card-section v-if="store.caricati.length" class="vp-upload-ok">
        <div v-for="b in store.caricati" :key="b.id" class="vp-upload-row">
          <q-icon name="check_circle" color="positive" />
          <strong>{{ b.prodotto }}</strong>
          {{ b.importo_totale }}€ ·
          {{ b.periodo_da }} → {{ b.periodo_a }}
          <span v-if="b.consumo">· {{ b.consumo }}</span>
        </div>
      </q-card-section>
    </q-card>

    <!-- 2. Periodo del mese -->
    <q-card flat bordered class="vp-card">
      <q-card-section class="vp-card__title">
        <q-icon name="event" /> 2 · Periodo del mese
      </q-card-section>
      <q-card-section class="vp-row">
        <q-select
          v-model="mese"
          :options="meseOptions"
          label="Mese"
          emit-value
          map-options
          outlined
          dense
          class="vp-field"
        />
        <q-select
          v-model="anno"
          :options="annoOptions"
          label="Anno"
          outlined
          dense
          class="vp-field"
        />
        <q-btn
          color="primary"
          icon="search"
          label="Trova periodo"
          :loading="store.loading"
          @click="onPerMese"
        />
      </q-card-section>

      <q-card-section v-if="store.period" class="vp-period">
        <div class="vp-period__info">
          <q-chip square :color="statoColor" text-color="white" dense>
            {{ store.period.stato_display }}
          </q-chip>
          <span class="vp-period__range">
            {{ store.period.periodo_da }} → {{ store.period.periodo_a }}
          </span>
        </div>
        <div v-if="store.completezza" class="vp-completezza">
          <q-chip
            v-for="voce in vociCompletezza"
            :key="voce.key"
            :icon="store.completezza[voce.key] ? 'check_circle' : 'cancel'"
            :color="store.completezza[voce.key] ? 'positive' : 'grey-5'"
            text-color="white"
            dense
          >
            {{ voce.label }}
          </q-chip>
        </div>
        <div v-if="store.completezza && !store.completezza.completo" class="vp-hint">
          Servono almeno una bolletta <strong>luce</strong> e una
          <strong>gas</strong> prima di calcolare.
        </div>
      </q-card-section>
    </q-card>

    <!-- 3. Anteprima conto -->
    <q-card v-if="store.period" flat bordered class="vp-card">
      <q-card-section class="vp-card__title">
        <q-icon name="calculate" /> 3 · Conto per inquilino
        <q-space />
        <q-btn
          color="primary"
          outline
          icon="calculate"
          label="Calcola"
          :disable="!store.completezza?.completo"
          :loading="store.loading"
          @click="store.calcolaAnteprima()"
        />
      </q-card-section>

      <template v-if="store.anteprima">
        <!-- Le tre voci del periodo: luce, gas, TARI -> totale -> per persona -->
        <q-card-section>
          <div class="vp-sub">Di cosa si compone</div>
          <q-markup-table flat dense wrap-cells class="vp-tbl">
            <thead>
              <tr>
                <th class="text-left">Voce</th>
                <th class="text-right">Importo</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="v in vociPeriodo" :key="v.key">
                <td class="text-left">
                  <q-badge :color="voceColor(v.key)" :label="v.label" />
                </td>
                <td class="text-right">{{ euro(v.importo) }}</td>
              </tr>
            </tbody>
            <tfoot>
              <tr class="vp-tot">
                <td class="text-left text-weight-bold">Totale periodo</td>
                <td class="text-right text-weight-bold">
                  {{ euro(store.anteprima.totale_periodo) }}
                </td>
              </tr>
            </tfoot>
          </q-markup-table>
        </q-card-section>

        <!-- Quote per inquilino: solo nome, giorni, quota -->
        <q-card-section>
          <div class="vp-sub">Quota per inquilino</div>
          <q-markup-table flat dense wrap-cells class="vp-tbl">
            <thead>
              <tr>
                <th class="text-left">Inquilino</th>
                <th class="text-right">Giorni</th>
                <th class="text-right">Quota</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="q in store.anteprima.quote" :key="q.assignment_id">
                <td class="text-left">{{ q.tenant_nominativo }}</td>
                <td class="text-right">{{ q.giorni_presenza }}</td>
                <td class="text-right text-weight-bold">{{ euro(q.quota) }}</td>
              </tr>
            </tbody>
          </q-markup-table>
        </q-card-section>
      </template>

      <q-card-actions v-if="store.anteprima && store.anteprima.quote.length" align="right">
        <q-chip
          v-if="store.period.stato === 'inviato'"
          icon="check"
          color="positive"
          text-color="white"
        >
          Addebiti creati
        </q-chip>
        <q-btn
          v-else
          color="primary"
          icon="task_alt"
          label="Crea addebiti"
          :loading="store.loading"
          @click="onEmetti"
        />
      </q-card-actions>
    </q-card>

    <!-- 4. Avvisi -->
    <q-card v-if="store.period?.stato === 'inviato'" flat bordered class="vp-card">
      <q-card-section class="vp-card__title">
        <q-icon name="mail" /> 4 · Avvisi agli inquilini
        <q-space />
        <q-btn
          color="primary"
          outline
          icon="visibility"
          label="Anteprima avvisi"
          :loading="store.loading"
          @click="store.inviaAvvisi(true)"
        />
      </q-card-section>

      <q-card-section v-if="store.invio">
        <div class="vp-invio-summary">
          <q-chip dense color="grey-3">{{ store.invio.totale }} destinatari</q-chip>
          <q-chip v-if="store.invio.dry_run" dense color="amber-3">anteprima</q-chip>
          <q-chip v-else dense color="positive" text-color="white">
            {{ store.invio.inviati }} inviati
          </q-chip>
          <q-chip v-if="store.invio.errori" dense color="negative" text-color="white">
            {{ store.invio.errori }} errori
          </q-chip>
          <q-chip
            v-if="store.invio.senza_email.length"
            dense
            color="orange"
            text-color="white"
          >
            senza email: {{ store.invio.senza_email.join(', ') }}
          </q-chip>
        </div>

        <q-list bordered separator class="vp-avvisi">
          <q-expansion-item
            v-for="a in store.invio.avvisi"
            :key="a.receivable_id"
            :label="a.tenant_nominativo"
            :caption="a.email || 'nessuna email'"
          >
            <template #header>
              <q-item-section>
                <q-item-label>{{ a.tenant_nominativo }}</q-item-label>
                <q-item-label caption>{{ a.email || 'nessuna email' }}</q-item-label>
              </q-item-section>
              <q-item-section side>
                <q-chip dense :color="esitoColor(a.esito)" text-color="white">
                  {{ a.esito }}
                </q-chip>
              </q-item-section>
            </template>
            <q-card>
              <q-card-section>
                <div class="vp-mail-oggetto">{{ a.oggetto }}</div>
                <pre class="vp-mail-corpo">{{ a.corpo }}</pre>
              </q-card-section>
            </q-card>
          </q-expansion-item>
        </q-list>
      </q-card-section>

      <q-card-actions v-if="store.invio?.dry_run" align="right">
        <q-btn
          color="primary"
          icon="send"
          label="Invia per davvero"
          :loading="store.loading"
          @click="confermaInvio"
        />
      </q-card-actions>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useUtenzeStore } from 'stores/utenze';

const store = useUtenzeStore();
const $q = useQuasar();

const oggi = new Date();
const mese = ref(oggi.getMonth() + 1);
const anno = ref(oggi.getFullYear());
const ownerId = ref<number | null>(null);
const filePdf = ref<File[]>([]);

const meseNomi = [
  'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
  'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre',
];
const meseOptions = meseNomi.map((label, i) => ({ label, value: i + 1 }));
const annoOptions = [oggi.getFullYear() + 1, oggi.getFullYear(), oggi.getFullYear() - 1, oggi.getFullYear() - 2];

const vociCompletezza = [
  { key: 'luce' as const, label: 'Luce' },
  { key: 'gas' as const, label: 'Gas' },
  { key: 'tari' as const, label: 'TARI' },
];

const ownerOptions = computed(() =>
  store.owners.map((o) => ({ label: o.nominativo, value: o.id })),
);

const statoColor = computed(() =>
  store.period?.stato === 'inviato' ? 'positive' : 'grey-6',
);

const VOCI_LABEL: Record<string, string> = {
  luce: 'Luce',
  gas: 'Gas',
  tari: 'TARI',
  altro: 'Altro',
};
const VOCI_ORDINE = ['luce', 'gas', 'tari', 'altro'];

const vociPeriodo = computed(() => {
  const tpv = store.anteprima?.totali_per_voce ?? {};
  return VOCI_ORDINE.filter((k) => k in tpv).map((k) => ({
    key: k,
    label: VOCI_LABEL[k] ?? k,
    importo: tpv[k],
  }));
});

function euro(v: number | string | null | undefined): string {
  const n = typeof v === 'string' ? parseFloat(v) : v ?? 0;
  if (!n) return '—';
  return new Intl.NumberFormat('it-IT', {
    style: 'currency',
    currency: 'EUR',
  }).format(n);
}

function voceColor(tipo: string): string {
  if (tipo === 'luce') return 'amber-7';
  if (tipo === 'gas') return 'blue-grey-6';
  if (tipo === 'tari') return 'green-7';
  return 'grey-6';
}

function esitoColor(esito?: string): string {
  if (esito === 'inviato') return 'positive';
  if (esito === 'errore') return 'negative';
  if (esito === 'senza_email') return 'orange';
  return 'grey-6';
}

async function onUpload(): Promise<void> {
  if (!filePdf.value.length || !ownerId.value) return;
  let ok = 0;
  const errori: string[] = [];
  // Caricamento in sequenza: l'endpoint accetta un PDF per volta.
  for (const file of filePdf.value) {
    const res = await store.caricaBolletta(file, ownerId.value);
    if (res) {
      ok += 1;
    } else {
      errori.push(`${file.name}: ${store.errore ?? 'errore'}`);
    }
  }
  filePdf.value = [];
  if (ok) {
    $q.notify({ type: 'positive', message: `${ok} bolletta/e caricate` });
    // Rinfresca la completezza del periodo: i chip Luce/Gas/TARI si
    // accendono subito senza dover ricaricare la pagina.
    if (store.period) {
      await store.perMese(anno.value, mese.value);
    }
  }
  if (errori.length) {
    $q.notify({ type: 'negative', message: errori.join(' · '), timeout: 6000 });
  }
}

async function onPerMese(): Promise<void> {
  await store.perMese(anno.value, mese.value);
}

async function caricaMesePredefinito(): Promise<void> {
  // Default backend: mese successivo all'ultimo periodo con addebiti emessi.
  const res = await store.perMese();
  if (res) {
    anno.value = res.anno;
    mese.value = res.mese;
  }
}

async function onEmetti(): Promise<void> {
  const ok = await store.emetti();
  if (ok) {
    $q.notify({ type: 'positive', message: 'Addebiti utenze creati' });
  }
}

function confermaInvio(): void {
  $q.dialog({
    title: 'Conferma invio',
    message: `Invio reale delle email a ${store.invio?.totale ?? 0} inquilini. Procedere?`,
    cancel: true,
    persistent: true,
  }).onOk(() => {
    void inviaReale();
  });
}

async function inviaReale(): Promise<void> {
  const res = await store.inviaAvvisi(false);
  if (res) {
    $q.notify({
      type: res.errori ? 'warning' : 'positive',
      message: `Inviate ${res.inviati} email${res.errori ? `, ${res.errori} errori` : ''}`,
    });
  }
}

function ricomincia(): void {
  store.reset();
  filePdf.value = [];
}

onMounted(() => {
  void store.fetchOwners().then(() => {
    if (!ownerId.value && store.owners.length) {
      ownerId.value = store.owners[0]?.id ?? null;
    }
  });
  void caricaMesePredefinito();
});
</script>

<style scoped>
.vp-page {
  padding: var(--vp-gap-4, 16px);
  max-width: 900px;
  margin: 0 auto;
}
.vp-page__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--vp-gap-3, 12px);
}
.vp-page__title {
  margin: 0;
  font-size: var(--vp-text-2xl);
}
.vp-card {
  margin-bottom: var(--vp-gap-3, 12px);
  border-radius: var(--vp-r-md, 10px);
}
.vp-card__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: var(--vp-terra-deep, #9b5a3a);
}
.vp-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}
.vp-field {
  min-width: 160px;
}
.vp-field--grow {
  flex: 1 1 240px;
}
.vp-upload-ok {
  color: var(--vp-ink-2, #555);
}
.vp-upload-row {
  padding: 2px 0;
}
.vp-period__info {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.vp-period__range {
  color: var(--vp-ink-2, #555);
}
.vp-completezza {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.vp-hint {
  margin-top: 8px;
  color: var(--vp-ink-3, #888);
  font-size: 13px;
}
.vp-sub {
  font-weight: 600;
  color: var(--vp-ink-2, #555);
  margin-bottom: 6px;
}
.vp-tbl {
  background: transparent;
}
.vp-muted {
  color: var(--vp-ink-3, #888);
  font-size: 13px;
}
.vp-tot td {
  border-top: 2px solid var(--vp-paper-3, #e0d8cf);
}
.vp-banner-error {
  background: #fdecea;
  color: #a3261d;
  margin-bottom: var(--vp-gap-3, 12px);
}
.vp-invio-summary {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.vp-mail-oggetto {
  font-weight: 600;
  margin-bottom: 6px;
}
.vp-mail-corpo {
  white-space: pre-wrap;
  font-family: inherit;
  margin: 0;
  color: var(--vp-ink-2, #555);
}
</style>
