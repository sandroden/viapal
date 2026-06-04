<template>
  <q-page class="vp-iu">
    <header class="vp-iu__head">
      <div class="vp-eyebrow">Le tue spese</div>
      <h1 class="vp-display vp-iu__titolo">Utenze</h1>
    </header>

    <div v-if="store.loading && !dettaglio" class="vp-iu__loader">
      <q-spinner color="primary" size="32px" />
    </div>

    <EmptyState
      v-else-if="!periodi.length"
      icon="bolt"
      title="Nessuna utenza"
      message="Qui vedrai i conteggi delle utenze una volta inviati dai proprietari."
    />

    <template v-else-if="periodoView">
      <!-- Selettore periodo: frecce tra i mesi inviati -->
      <div class="vp-iu__sel">
        <button
          class="vp-iu__arrow"
          :disabled="idx >= periodi.length - 1"
          aria-label="Mese precedente"
          @click="vai(idx + 1)"
        >
          <VpIcon name="back" :size="18" />
        </button>
        <div class="vp-iu__sel-label">
          <div class="vp-iu__sel-mese">{{ periodoView.label }}</div>
          <div class="vp-iu__sel-range">{{ periodoView.range }}</div>
        </div>
        <button
          class="vp-iu__arrow"
          :disabled="idx <= 0"
          aria-label="Mese successivo"
          @click="vai(idx - 1)"
        >
          <VpIcon name="chevron" :size="18" />
        </button>
      </div>

      <!-- Stepper a 2 passi -->
      <div class="vp-iu__stepper">
        <button
          v-for="(label, i) in STEPS"
          :key="label"
          class="vp-iu__chip"
          :class="{ active: step === i + 1, done: i + 1 < step }"
          @click="step = i + 1"
        >
          <span class="vp-iu__num">
            <VpIcon v-if="i + 1 < step" name="check" :size="13" :stroke="3" color="#fff" />
            <template v-else>{{ i + 1 }}</template>
          </span>
          {{ label }}
        </button>
      </div>

      <!-- Corpo -->
      <div class="vp-iu__body">
        <BollettaStep
          v-if="step === 1"
          :periodo="periodoView"
          :bollette="bolletteView"
          :voci="vociView"
          :totale="totaleView"
          :mancanti-tipi="[]"
          readonly
          @view-pdf="apriPdf"
        />
        <RipartizioneStep
          v-else
          criterio="giorni"
          :quote="quoteView"
          :voci="vociView"
          :totale="totaleView"
          readonly
        />
      </div>

      <div class="vp-iu__foot">
        <button class="vp-btn vp-btn--ghost" :disabled="step === 1" @click="step = 1">
          <VpIcon name="back" :size="16" /> Bolletta
        </button>
        <button v-if="step === 1" class="vp-btn vp-btn--primary" @click="step = 2">
          Vedi la tua quota <VpIcon name="arrow" :size="16" color="#fff" />
        </button>
        <div v-else class="vp-iu__miaquota">
          <span class="vp-eyebrow">La tua quota</span>
          <span class="vp-mono vp-iu__miaquota-val">{{ eur(miaQuota) }}</span>
        </div>
      </div>
    </template>

    <PdfDialog
      v-model="mostraPdf"
      :url="pdfCorrente?.url ?? null"
      :title="pdfCorrente?.title ?? null"
    />
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useUtenzeInquilinoStore } from 'stores/utenzeInquilino';
import BollettaStep from 'src/components/utenze/BollettaStep.vue';
import RipartizioneStep from 'src/components/utenze/RipartizioneStep.vue';
import VpIcon from 'src/components/utenze/VpIcon.vue';
import PdfDialog from 'src/components/PdfDialog.vue';
import EmptyState from 'src/components/EmptyState.vue';
import {
  prodottoToTipo,
  voceToTipo,
  rangePeriodo,
  meseDa,
  meseCapitalize,
  annoDa,
  avatarHue,
  mediaPath,
  eur,
  type PeriodoView,
  type BollettaView,
  type VoceView,
  type QuotaView,
} from 'src/components/utenze/format';
import { useRefreshOnResume } from 'src/composables/useRefreshOnResume';

const store = useUtenzeInquilinoStore();

const STEPS = ['Bolletta', 'Ripartizione'];
const step = ref(1);
const selectedId = ref<number | null>(null);

const mostraPdf = ref(false);
const pdfCorrente = ref<{ url: string; title: string } | null>(null);
function apriPdf(v: { url: string; title: string }): void {
  pdfCorrente.value = v;
  mostraPdf.value = true;
}

const periodi = computed(() => store.periodi);
const dettaglio = computed(() => store.dettaglio);
const idx = computed(() => periodi.value.findIndex((p) => p.id === selectedId.value));

function num(v: number | string | null | undefined): number {
  const n = typeof v === 'string' ? parseFloat(v) : (v ?? 0);
  return Number.isFinite(n) ? n : 0;
}

function vai(nuovoIdx: number): void {
  const p = periodi.value[nuovoIdx];
  if (p) selectedId.value = p.id;
}

const periodoView = computed<PeriodoView | null>(() => {
  const p = dettaglio.value?.period;
  if (!p) return null;
  return {
    id: String(p.id),
    mese: meseDa(p.periodo_da),
    label: `${meseCapitalize(meseDa(p.periodo_da))} ${annoDa(p.periodo_da)}`,
    range: rangePeriodo(p.periodo_da, p.periodo_a),
    stato: 'inviato',
    presenti: 3,
    attese: 3,
  };
});

const bolletteView = computed<BollettaView[]>(() => {
  const d = dettaglio.value;
  if (!d) return [];
  const cards: BollettaView[] = d.bollette.map((b) => ({
    tipo: String(prodottoToTipo(b.prodotto)),
    fornitore: b.supplier_nome || '—',
    importo: num(b.importo_totale),
    periodo: rangePeriodo(b.periodo_da, b.periodo_a),
    consumo: b.consumo || '—',
    riferimento: b.numero_fattura || '—',
    pdfUrl: mediaPath(b.file_pdf),
    letto: true,
  }));
  const tari = num(d.totali_per_voce?.tari);
  if (tari > 0 && !cards.some((c) => c.tipo === 'TARI')) {
    cards.push({
      tipo: 'TARI',
      fornitore: 'Comune (TARI)',
      importo: tari,
      periodo: periodoView.value?.range ?? '',
      consumo: '—',
      riferimento: 'costo annuale ripartito',
      pdfUrl: null,
      letto: false,
    });
  }
  return cards;
});

const ORDINE_VOCI = ['luce', 'gas', 'tari', 'altro'];
const vociView = computed<VoceView[]>(() => {
  const tpv = dettaglio.value?.totali_per_voce ?? {};
  return ORDINE_VOCI.filter((k) => k in tpv && num(tpv[k]) > 0).map((k) => ({
    tipo: String(voceToTipo(k)),
    importo: num(tpv[k]),
  }));
});

const totaleView = computed(() => num(dettaglio.value?.totale_periodo));

const quoteView = computed<QuotaView[]>(() => {
  const quote = dettaglio.value?.quote ?? [];
  return quote.map((q) => ({
    id: q.assignment_id,
    nome: q.tenant_nominativo,
    stanza: '',
    email: '',
    mq: 0,
    giorni: q.giorni_presenza,
    avatarHue: avatarHue(q.tenant_nominativo),
    per: {
      Luce: num(q.dettaglio?.luce),
      Gas: num(q.dettaglio?.gas),
      TARI: num(q.dettaglio?.tari),
    },
    quota: num(q.quota),
    mine: q.is_me,
  }));
});

const miaQuota = computed(() => quoteView.value.find((q) => q.mine)?.quota ?? 0);

watch(selectedId, (id) => {
  step.value = 1;
  if (id != null) void store.fetchDettaglio(id);
});

onMounted(async () => {
  const lista = await store.fetchPeriodi();
  const primo = lista[0]; // il più recente (lista in ordine desc)
  if (primo) selectedId.value = primo.id;
});

// Refresh al rientro nell'app: lista periodi + dettaglio selezionato.
useRefreshOnResume(() => {
  void store.fetchPeriodi();
  if (selectedId.value != null) void store.fetchDettaglio(selectedId.value);
});
</script>

<style scoped>
.vp-iu {
  background: var(--vp-paper);
  padding: 6px 18px 40px;
}
.vp-iu__head {
  padding: 0 0 12px;
}
.vp-iu__titolo {
  font-size: 25px;
  margin: 4px 0 0;
  color: var(--vp-ink);
}
.vp-iu__loader {
  display: flex;
  justify-content: center;
  padding: var(--vp-gap-6);
}
.vp-iu__sel {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--vp-paper-2);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  padding: 8px 10px;
  margin-bottom: 16px;
}
.vp-iu__arrow {
  width: 38px;
  height: 38px;
  border-radius: var(--vp-r-md);
  border: none;
  background: var(--vp-cream);
  color: var(--vp-ink-2);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}
.vp-iu__arrow:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.vp-iu__sel-label {
  flex: 1;
  text-align: center;
}
.vp-iu__sel-mese {
  font-size: 16px;
  font-weight: 600;
  color: var(--vp-ink);
}
.vp-iu__sel-range {
  font-size: 12px;
  color: var(--vp-ink-3);
}
.vp-iu__stepper {
  display: flex;
  gap: 10px;
  margin-bottom: 18px;
}
.vp-iu__chip {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  padding: 11px 14px;
  border-radius: 12px;
  cursor: pointer;
  background: var(--vp-paper-2);
  border: 1.5px solid transparent;
  font-family: inherit;
  font-size: 14px;
  font-weight: 500;
  color: var(--vp-ink-3);
}
.vp-iu__chip.active {
  background: var(--vp-cream);
  border-color: var(--vp-terra);
  color: var(--vp-ink);
}
.vp-iu__chip.done {
  background: var(--vp-sage-soft);
  color: var(--vp-sage-deep);
}
.vp-iu__num {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--vp-paper-3);
  color: var(--vp-ink-3);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}
.vp-iu__chip.active .vp-iu__num {
  background: var(--vp-terra);
  color: #fff;
}
.vp-iu__chip.done .vp-iu__num {
  background: var(--vp-sage);
  color: #fff;
}
.vp-iu__body {
  margin-bottom: 18px;
}
.vp-iu__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-top: 1px solid var(--vp-paper-3);
  padding-top: 14px;
}
.vp-iu__miaquota {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.vp-iu__miaquota-val {
  font-size: 22px;
  font-weight: 600;
  color: var(--vp-terra-deep);
}
@media (min-width: 1024px) {
  /* Sfonda il container stretto del layout inquilino per la torta affiancata. */
  .vp-iu {
    width: 100vw;
    margin-left: calc(50% - 50vw);
    padding-left: max(28px, calc(50vw - 520px));
    padding-right: max(28px, calc(50vw - 520px));
  }
  .vp-iu__titolo {
    font-size: 30px;
  }
}
</style>
