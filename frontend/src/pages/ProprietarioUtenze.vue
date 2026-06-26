<template>
  <q-page class="vp-utenze">
    <q-banner v-if="store.errore" class="vp-banner-error" rounded>
      <template #avatar><q-icon name="error" /></template>
      {{ store.errore }}
    </q-banner>

    <!-- Tab selector: Conguaglio / Andamento -->
    <div class="vp-screen-tabs">
      <button :class="['vp-screen-tab', { active: tab === 'conguaglio' }]" @click="tab = 'conguaglio'">
        <q-icon name="receipt_long" size="16px" />
        Conguaglio
      </button>
      <button :class="['vp-screen-tab', { active: tab === 'andamento' }]" @click="onTabAndamento">
        <q-icon name="bar_chart" size="16px" />
        Andamento
      </button>
    </div>

    <UtenzeAndamento v-if="tab === 'andamento'" />

    <ConguaglioBollette
      v-else-if="periodoCorrenteView"
      :periodo="periodoCorrenteView"
      :periodi="statiPeriodi"
      :anno="anno"
      :mese="mese"
      :criterio="criterio"
      :step="step"
      :bollette="bolletteView"
      :voci="vociView"
      :totale="totaleView"
      :quote="quoteView"
      :mancanti-tipi="mancantiTipi"
      :escludi="escludi"
      :pagata-da="pagataDa"
      :n-inquilini="quoteView.length"
      :has-nuovo-ingresso="hasNuovoIngresso"
      :ingresso-nota="ingressoNota"
      :needs-emetti="needsEmetti"
      :gia-inviato-at="store.period?.avvisi_inviati_at ?? null"
      @cambia-periodo="onCambiaPeriodo"
      @update:criterio="(c) => (criterio = c)"
      @update:step="onStep"
      @upload="apriUpload"
      @emetti="onEmetti"
      @invia="confermaInvio"
      @toggle-invio="onToggleInvio"
      @view-pdf="apriPdf"
    />

    <div v-else-if="tab === 'conguaglio'" class="vp-vuoto">
      <q-spinner-dots v-if="store.loading" size="32px" color="primary" />
      <span v-else>Nessun periodo disponibile.</span>
    </div>

    <PdfDialog
      v-model="mostraPdf"
      :url="pdfCorrente?.url ?? null"
      :title="pdfCorrente?.title ?? null"
    />

    <!-- Dialog: carica bollette -->
    <q-dialog v-model="mostraUpload">
      <q-card class="vp-dialog">
        <q-card-section class="vp-dialog__title">
          <q-icon name="cloud_upload" />
          Carica bollette<span v-if="uploadTipoHint"> · {{ uploadTipoHint }}</span>
        </q-card-section>
        <q-card-section class="column q-gutter-md">
          <q-select
            v-model="ownerId"
            :options="ownerOptions"
            label="Pagata da"
            emit-value
            map-options
            outlined
            dense
          />
          <q-file
            v-model="filePdf"
            label="Seleziona uno o più PDF (luce, gas…)"
            accept=".pdf"
            multiple
            append
            use-chips
            outlined
            dense
          >
            <template #prepend><q-icon name="attach_file" /></template>
          </q-file>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Annulla" @click="mostraUpload = false" />
          <q-btn
            color="primary"
            icon="cloud_upload"
            :label="filePdf.length > 1 ? `Carica ${filePdf.length}` : 'Carica'"
            :disable="!filePdf.length || !ownerId"
            :loading="store.loading"
            @click="onUpload"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useUtenzeStore } from 'stores/utenze';
import ConguaglioBollette from 'src/components/utenze/ConguaglioBollette.vue';
import UtenzeAndamento from 'src/components/utenze/UtenzeAndamento.vue';
import PdfDialog from 'src/components/PdfDialog.vue';
import {
  prodottoToTipo,
  voceToTipo,
  rangePeriodo,
  meseDa,
  meseCapitalize,
  annoDa,
  avatarHue,
  mediaPath,
  fmtConsumo,
  type Criterio,
  type PeriodoView,
  type BollettaView,
  type VoceView,
  type QuotaView,
} from 'src/components/utenze/format';
import type { MeseStato } from 'src/components/utenze/PeriodSelector.vue';

const store = useUtenzeStore();
const $q = useQuasar();

const tab = ref<'conguaglio' | 'andamento'>('conguaglio');

async function onTabAndamento(): Promise<void> {
  tab.value = 'andamento';
  if (!store.statistiche.length) {
    await store.fetchStatistiche();
  }
}

const criterio = ref<Criterio>('giorni');
const step = ref(1);
const escludi = ref<number[]>([]);

const ownerId = ref<number | null>(null);
const filePdf = ref<File[]>([]);
const mostraUpload = ref(false);
const uploadTipoHint = ref<string | null>(null);

const mostraPdf = ref(false);
const pdfCorrente = ref<{ url: string; title: string } | null>(null);
function apriPdf(v: { url: string; title: string }): void {
  pdfCorrente.value = v;
  mostraPdf.value = true;
}

const ownerOptions = computed(() =>
  store.owners.map((o) => ({ label: o.nominativo, value: o.id })),
);

function num(v: number | string | null | undefined): number {
  const n = typeof v === 'string' ? parseFloat(v) : (v ?? 0);
  return Number.isFinite(n) ? n : 0;
}

// ── Anno/mese correnti (dal periodo selezionato) ──────────────────────
const anno = computed(() =>
  store.period ? Number(annoDa(store.period.periodo_da)) : new Date().getFullYear(),
);
const mese = computed(() =>
  store.period ? Number(store.period.periodo_da.slice(5, 7)) : new Date().getMonth() + 1,
);

const needsEmetti = computed(() => store.period?.stato !== 'inviato');
const incompletoCorrente = computed(() => !!store.completezza && !store.completezza.completo);

// "inviato" (badge verde) = avvisi REALMENTE spediti (avvisi_inviati_at), non
// il semplice stato='inviato' del periodo (= solo addebiti creati). Periodi
// passati con addebiti ma senza invio email restano "da-inviare".
const statiPeriodi = computed<MeseStato[]>(() =>
  store.periodi.map((p) => ({
    anno: Number(annoDa(p.periodo_da)),
    mese: Number(p.periodo_da.slice(5, 7)),
    stato: p.avvisi_inviati_at ? 'inviato' : 'da-inviare',
  })),
);

const mancantiTipi = computed<string[]>(() => {
  const c = store.completezza;
  if (!c) return [];
  const out: string[] = [];
  if (!c.luce) out.push('Luce');
  if (!c.gas) out.push('Gas');
  if (!c.tari) out.push('TARI');
  return out;
});

const periodoCorrenteView = computed<PeriodoView | null>(() => {
  const p = store.period;
  if (!p) return null;
  const presentiCount = store.completezza
    ? [store.completezza.luce, store.completezza.gas, store.completezza.tari].filter(Boolean).length
    : 3;
  return {
    id: String(p.id),
    mese: meseDa(p.periodo_da),
    label: `${meseCapitalize(meseDa(p.periodo_da))} ${annoDa(p.periodo_da)}`,
    range: rangePeriodo(p.periodo_da, p.periodo_a),
    stato: incompletoCorrente.value ? 'incompleto' : p.avvisi_inviati_at ? 'inviato' : 'da-inviare',
    presenti: presentiCount,
    attese: 3,
  };
});

// ── Bollette del periodo (card di dettaglio) ──────────────────────────
const bolletteView = computed<BollettaView[]>(() => {
  const cards: BollettaView[] = store.bollettePeriodo.map((b) => ({
    tipo: String(prodottoToTipo(b.prodotto)),
    fornitore: b.supplier_nome || b.pagata_da_nominativo || '—',
    importo: num(b.importo_totale),
    periodo: rangePeriodo(b.periodo_da, b.periodo_a),
    consumo: fmtConsumo(b.consumo),
    riferimento: b.numero_fattura || '—',
    pdfUrl: mediaPath(b.file_pdf),
    letto: true,
  }));
  const tari = num(store.anteprima?.totali_per_voce?.tari);
  const haTariCard = cards.some((c) => c.tipo === 'TARI');
  if (tari > 0 && !haTariCard && store.period) {
    cards.push({
      tipo: 'TARI',
      fornitore: 'Comune (TARI)',
      importo: tari,
      periodo: rangePeriodo(store.period.periodo_da, store.period.periodo_a),
      consumo: '—',
      riferimento: 'costo annuale ripartito',
      pdfUrl: null,
      letto: false,
    });
  }
  return cards;
});

// ── Composizione (totali per voce del periodo) ────────────────────────
const ORDINE_VOCI = ['luce', 'gas', 'tari', 'altro'];
const vociView = computed<VoceView[]>(() => {
  const tpv = store.anteprima?.totali_per_voce ?? {};
  return ORDINE_VOCI.filter((k) => k in tpv && num(tpv[k]) > 0).map((k) => ({
    tipo: String(voceToTipo(k)),
    importo: num(tpv[k]),
  }));
});

const totaleView = computed(() => {
  if (store.anteprima) return num(store.anteprima.totale_periodo);
  return store.bollettePeriodo.reduce((s, b) => s + num(b.importo_totale), 0);
});

// ── Quote per inquilino (+ avviso: email/oggetto/corpo/notificare) ────
function avvisoPer(nominativo: string) {
  return store.invio?.avvisi.find((a) => a.tenant_nominativo === nominativo);
}

const quoteView = computed<QuotaView[]>(() => {
  const quote = store.anteprima?.quote ?? [];
  return quote.map((q) => {
    const a = avvisoPer(q.tenant_nominativo);
    return {
      id: q.assignment_id,
      receivableId: a?.receivable_id ?? null,
      nome: q.tenant_nominativo,
      stanza: '',
      email: a?.email ?? '',
      mq: 0,
      giorni: q.giorni_presenza,
      avatarHue: avatarHue(q.tenant_nominativo),
      per: {
        Luce: num(q.dettaglio?.luce),
        Gas: num(q.dettaglio?.gas),
        TARI: num(q.dettaglio?.tari),
      },
      quota: num(q.quota),
      oggetto: a?.oggetto ?? '',
      corpo: a?.corpo ?? '',
      notificare: a ? a.notificare !== false : true,
      bonifico: a?.bonifico
        ? {
            beneficiario: a.bonifico.beneficiario,
            iban: a.bonifico.iban,
            causale: a.bonifico.causale,
            importo: num(a.bonifico.importo),
          }
        : null,
    };
  });
});

const pagataDa = computed(() => {
  const conNome = store.bollettePeriodo.find((b) => b.pagata_da_nominativo);
  return conNome?.pagata_da_nominativo ?? '';
});

const hasNuovoIngresso = computed(() => {
  const g = quoteView.value.map((q) => q.giorni);
  return g.length > 1 && Math.min(...g) < Math.max(...g);
});
const ingressoNota = computed(() =>
  hasNuovoIngresso.value
    ? "Qualcuno è presente solo per una parte del periodo: la sua quota è ridotta in proporzione ai giorni di effettiva presenza."
    : '',
);

// ── Orchestrazione ────────────────────────────────────────────────────
async function caricaDatiPeriodo(): Promise<void> {
  if (!store.period) return;
  escludi.value = [];
  await store.fetchBollettePeriodo(store.period.periodo_da, store.period.periodo_a);
  if (store.completezza?.completo) {
    await store.calcolaAnteprima();
  }
  if (store.period.stato === 'inviato') {
    await store.inviaAvvisi(true);
  }
}

async function onCambiaPeriodo(v: { anno: number; mese: number }): Promise<void> {
  step.value = 1;
  await store.perMese(v.anno, v.mese);
  await caricaDatiPeriodo();
}

async function onStep(n: number): Promise<void> {
  step.value = n;
  if (n === 2 && store.completezza?.completo && !store.anteprima) {
    await store.calcolaAnteprima();
  }
  if (n === 3 && store.period?.stato === 'inviato' && !store.invio) {
    await store.inviaAvvisi(true);
  }
}

function onToggleInvio(receivableId: number): void {
  const i = escludi.value.indexOf(receivableId);
  if (i >= 0) escludi.value.splice(i, 1);
  else escludi.value.push(receivableId);
}

// ── Upload ────────────────────────────────────────────────────────────
function apriUpload(tipo?: string): void {
  uploadTipoHint.value = tipo ?? null;
  mostraUpload.value = true;
}

async function onUpload(): Promise<void> {
  if (!filePdf.value.length || !ownerId.value) return;
  let ok = 0;
  const errori: string[] = [];
  for (const file of filePdf.value) {
    const res = await store.caricaBolletta(file, ownerId.value);
    if (res) ok += 1;
    else errori.push(`${file.name}: ${store.errore ?? 'errore'}`);
  }
  filePdf.value = [];
  if (ok) {
    $q.notify({ type: 'positive', message: `${ok} bolletta/e caricate` });
    if (store.period) {
      await store.perMese(anno.value, mese.value);
      await caricaDatiPeriodo();
    }
    mostraUpload.value = false;
  }
  if (errori.length) {
    $q.notify({ type: 'negative', message: errori.join(' · '), timeout: 6000 });
  }
}

// ── Crea addebiti (esplicito) → poi invio ─────────────────────────────
async function onEmetti(): Promise<void> {
  const ok = await store.emetti();
  if (ok) {
    $q.notify({ type: 'positive', message: 'Addebiti utenze creati' });
    await store.fetchPeriodi();
    // Ora esistono i Receivable: carica l'anteprima avvisi e vai all'invio.
    await store.inviaAvvisi(true);
    step.value = 3;
  }
}

function confermaInvio(): void {
  if (store.period?.stato !== 'inviato') {
    // Non ancora emesso: la creazione addebiti è un passo esplicito.
    void onEmetti();
    return;
  }
  const giaInviati = !!store.period?.avvisi_inviati_at;
  const n = quoteView.value.filter(
    (q) => q.notificare !== false && !escludi.value.includes(Number(q.receivableId)),
  ).length;
  $q.dialog({
    title: giaInviati ? 'Reinvio avvisi' : 'Conferma invio',
    message:
      `Invio reale delle email a ${n} inquilini.` +
      (giaInviati ? ' Gli avvisi erano già stati inviati: procedere comunque?' : ' Procedere?'),
    cancel: true,
    persistent: true,
  }).onOk(() => {
    void inviaReale();
  });
}

async function inviaReale(): Promise<void> {
  const res = await store.inviaAvvisi(false, [...escludi.value]);
  if (res) {
    await store.fetchPeriodi();
    $q.notify({
      type: res.errori ? 'warning' : 'positive',
      message: `Inviate ${res.inviati} email${res.errori ? `, ${res.errori} errori` : ''}`,
    });
  }
}

onMounted(async () => {
  await store.fetchOwners();
  if (!ownerId.value && store.owners.length) {
    ownerId.value = store.owners[0]?.id ?? null;
  }
  await store.fetchPeriodi();
  // Default backend: ultimo periodo con avvisi ancora da inviare.
  await store.perMese();
  await caricaDatiPeriodo();
});
</script>

<style scoped>
.vp-utenze {
  background: var(--vp-paper);
}

.vp-screen-tabs {
  display: flex;
  gap: 4px;
  padding: 0 20px;
  border-bottom: 1px solid var(--vp-paper-3);
  background: var(--vp-paper);
  position: sticky;
  top: 0;
  z-index: 10;
}
.vp-screen-tab {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 10px 14px 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-family: var(--vp-font-ui);
  font-size: 14px;
  font-weight: 400;
  color: var(--vp-ink-3);
  position: relative;
  transition: color 0.15s;
}
.vp-screen-tab:hover { color: var(--vp-ink); }
.vp-screen-tab.active {
  color: var(--vp-ink);
  font-weight: 600;
}
.vp-screen-tab.active::after {
  content: '';
  position: absolute;
  left: 8px;
  right: 8px;
  bottom: -1px;
  height: 2.5px;
  border-radius: 2px;
  background: var(--vp-terra);
}
.vp-banner-error {
  background: #fdecea;
  color: #a3261d;
  margin: 12px;
}
.vp-vuoto {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 50vh;
  color: var(--vp-ink-3);
}
.vp-dialog {
  min-width: 360px;
  border-radius: var(--vp-r-lg);
}
.vp-dialog__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: var(--vp-terra-deep);
}
</style>
