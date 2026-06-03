<script setup lang="ts">
// STEP 1 · BOLLETTA
// Strip di upload multiplo + card di dettaglio per utenza + composizione.
// Quando il periodo è incompleto mostra le card presenti, gli slot "carica"
// tratteggiati per le mancanti e un avviso argilla al posto della composizione.
import { computed } from 'vue';
import VpIcon from './VpIcon.vue';
import VpScontrino from './VpScontrino.vue';
import PdfIconButton from 'src/components/PdfIconButton.vue';
import { utility, eur } from './format';
import type { PeriodoView, BollettaView, VoceView } from './format';

const props = withDefaults(
  defineProps<{
    periodo: PeriodoView;
    bollette: BollettaView[]; // solo le PRESENTI (PDF letti)
    voci: VoceView[]; // composizione del periodo (totali per voce)
    totale: number;
    mancantiTipi: string[]; // tipi ancora da caricare
    readonly?: boolean; // vista inquilino: niente upload
  }>(),
  { readonly: false },
);
const emit = defineEmits<{
  upload: [tipo?: string];
  'view-pdf': [v: { url: string; title: string }];
}>();

const incompleto = computed(() => props.periodo.stato === 'incompleto');
const mancanti = computed(() => props.mancantiTipi.length);
</script>

<template>
  <div>
    <!-- Strip di upload (multiplo) -->
    <div class="strip" :class="{ warn: incompleto }">
      <div class="thumbs">
        <div
          v-for="(b, i) in bollette"
          :key="b.tipo"
          :style="{ marginLeft: i ? '-16px' : 0, marginTop: i * 3 + 'px', zIndex: i }"
        >
          <VpScontrino :bolletta="b" :tilt="-6 + i * 7" :w="52" mini />
        </div>
      </div>
      <div class="strip-text">
        <div
          class="strip-title"
          :style="{ color: incompleto ? 'oklch(0.40 0.11 28)' : 'var(--vp-terra-deep)' }"
        >
          <template v-if="incompleto"
            >{{ periodo.presenti }} di {{ periodo.attese }} bollette · mancano
            {{ mancantiTipi.join(' e ') }}</template
          >
          <template v-else
            >{{ bollette.length }} bollette lette ·
            {{ bollette.map((b) => b.fornitore).join(', ') }}</template
          >
        </div>
        <div class="strip-sub">
          <template v-if="readonly">Bollette del periodo, lette dall'AI.</template>
          <template v-else
            >Importo e periodo riconosciuti dall'AI. Trascina altri PDF per aggiungerne — l'upload è
            multiplo.</template
          >
        </div>
      </div>
      <button
        v-if="!readonly"
        class="vp-btn vp-btn--ghost"
        style="flex-shrink: 0"
        @click="emit('upload')"
      >
        <VpIcon name="upload" :size="15" /> Aggiungi
      </button>
    </div>

    <div class="sec-head">
      <div class="vp-display" style="font-size: 21px">Dettaglio delle utenze</div>
      <div class="muted">importo, periodo e consumo di ogni bolletta</div>
    </div>

    <!-- Card di dettaglio + slot mancanti -->
    <div class="grid3">
      <div v-for="b in bollette" :key="b.tipo" class="vp-card card">
        <div
          class="card-head"
          :style="{ background: utility(b.tipo).soft, color: utility(b.tipo).fg }"
        >
          <div class="card-icon">
            <VpIcon :name="utility(b.tipo).icon" :size="18" :color="utility(b.tipo).fg" />
          </div>
          <div>
            <div class="card-tipo">{{ b.tipo }}</div>
            <div class="card-forn">{{ b.fornitore }}</div>
          </div>
        </div>
        <div class="card-body">
          <div class="kv"><span>Periodo</span><span>{{ b.periodo }}</span></div>
          <div class="kv"><span>Consumo</span><span>{{ b.consumo }}</span></div>
          <div class="kv">
            <span>Riferimento</span><span class="vp-mono ref">{{ b.riferimento }}</span>
          </div>
          <div class="dashed"></div>
          <div class="imp">
            <span class="muted">Importo</span>
            <span class="vp-mono imp-val" :style="{ color: utility(b.tipo).fg }">{{
              eur(b.importo)
            }}</span>
          </div>
        </div>
        <div class="card-foot">
          <span v-if="b.letto !== false" class="card-foot-ok">
            <VpIcon name="check" :size="13" :stroke="2.4" color="var(--vp-sage)" /> PDF letto
            correttamente
          </span>
          <span v-else class="card-foot-info">Costo annuale, senza bolletta PDF</span>
          <PdfIconButton
            v-if="b.pdfUrl"
            title="Apri / scarica la bolletta"
            @click="emit('view-pdf', { url: b.pdfUrl ?? '', title: `${b.tipo} — ${b.fornitore}` })"
          />
        </div>
      </div>

      <button
        v-for="t in mancantiTipi"
        v-show="!readonly"
        :key="'m' + t"
        class="slot"
        @click="emit('upload', t)"
      >
        <div class="slot-icon" :style="{ background: utility(t).soft }">
          <VpIcon :name="utility(t).icon" :size="20" :color="utility(t).fg" />
        </div>
        <div class="slot-tipo">{{ t }} mancante</div>
        <div class="slot-cta">
          <VpIcon name="upload" :size="14" color="var(--vp-terra-deep)" /> Carica la bolletta
        </div>
      </button>
    </div>

    <!-- Composizione OPPURE avviso di incompletezza -->
    <div v-if="incompleto" class="vp-banner vp-banner--late">
      <VpIcon name="alert" :size="18" color="var(--vp-clay)" style="margin-top: 2px" />
      <div style="flex: 1">
        <b>Totale non ancora completo.</b>
        <span class="muted">
          Finora {{ eur(totale) }} su {{ periodo.presenti }} di {{ periodo.attese }} bollette.
          Carica le {{ mancanti }} mancanti per sbloccare ripartizione e invio.</span
        >
      </div>
    </div>

    <div v-else-if="voci.length" class="vp-card comp">
      <div class="sec-head" style="margin-bottom: 18px">
        <div class="vp-display" style="font-size: 20px">Di cosa si compone</div>
        <div class="muted">Somma delle utenze del periodo</div>
      </div>
      <div class="bar">
        <div
          v-for="v in voci"
          :key="v.tipo"
          :title="v.tipo"
          :style="{ width: (v.importo / totale) * 100 + '%', background: utility(v.tipo).bar }"
        ></div>
      </div>
      <div class="legend">
        <div v-for="v in voci" :key="v.tipo" class="leg">
          <span class="swatch" :style="{ background: utility(v.tipo).bar }"></span>
          <div>
            <div class="leg-tipo">
              {{ v.tipo }} <span class="leg-pct">· {{ Math.round((v.importo / totale) * 100) }}%</span>
            </div>
            <div class="vp-mono leg-val">{{ eur(v.importo) }}</div>
          </div>
        </div>
        <div class="leg-total">
          <div class="vp-eyebrow">Totale periodo</div>
          <div class="vp-mono total-val">{{ eur(totale) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.muted {
  font-size: 13px;
  color: var(--vp-ink-3);
}
.strip {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px 12px 12px;
  margin-bottom: 18px;
  border: 1.5px dashed var(--vp-terra);
  border-radius: 14px;
  background: var(--vp-terra-soft);
}
.strip.warn {
  border-color: var(--vp-clay);
  background: var(--vp-clay-soft);
}
.thumbs {
  display: flex;
  align-items: flex-start;
  flex-shrink: 0;
}
.strip-text {
  flex: 1;
}
.strip-title {
  font-size: 15px;
  font-weight: 600;
}
.strip-sub {
  font-size: 13px;
  color: var(--vp-ink-2);
  margin-top: 2px;
}

.sec-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 14px;
}
.grid3 {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
  margin-bottom: 18px;
}

.card {
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.card-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
}
.card-icon {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: var(--vp-cream);
  display: flex;
  align-items: center;
  justify-content: center;
}
.card-tipo {
  font-size: 16px;
  font-weight: 600;
}
.card-forn {
  font-size: 12px;
  opacity: 0.8;
}
.card-body {
  padding: 16px 18px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.kv {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 13px;
}
.kv > span:first-child {
  color: var(--vp-ink-3);
}
.kv > span:last-child {
  color: var(--vp-ink);
  font-weight: 500;
}
.kv .ref {
  font-weight: 400;
  font-size: 12px;
}
.dashed {
  border-top: 1px dashed var(--vp-paper-3);
  margin: 4px 0;
}
.imp {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.imp-val {
  font-size: 22px;
  font-family: var(--vp-font-display);
}
.card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 6px 12px 6px 18px;
  border-top: 1px solid var(--vp-paper-3);
  font-size: 12px;
  color: var(--vp-sage-deep);
}
.card-foot-ok {
  display: flex;
  align-items: center;
  gap: 6px;
}
.card-foot-info {
  color: var(--vp-ink-3);
}

.slot {
  border: 1.5px dashed var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  background: var(--vp-paper-2);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 24px;
  cursor: pointer;
  font-family: inherit;
  color: var(--vp-ink-3);
  min-height: 200px;
}
.slot-icon {
  width: 40px;
  height: 40px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.slot-tipo {
  font-size: 15px;
  font-weight: 600;
  color: var(--vp-ink-2);
}
.slot-cta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--vp-terra-deep);
  font-weight: 500;
}

.comp {
  padding: 22px 26px;
}
.bar {
  display: flex;
  height: 18px;
  border-radius: var(--vp-r-pill);
  overflow: hidden;
  margin-bottom: 18px;
}
.legend {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr auto;
  gap: 20px;
  align-items: center;
}
.leg {
  display: flex;
  align-items: center;
  gap: 11px;
}
.swatch {
  width: 12px;
  height: 12px;
  border-radius: 4px;
  flex-shrink: 0;
}
.leg-tipo {
  font-size: 13px;
  color: var(--vp-ink-2);
}
.leg-pct {
  color: var(--vp-ink-4);
}
.leg-val {
  font-size: 18px;
  font-weight: 500;
}
.leg-total {
  text-align: right;
  padding-left: 18px;
  border-left: 1px solid var(--vp-paper-3);
}
.total-val {
  font-size: 30px;
  font-family: var(--vp-font-display);
  margin-top: 2px;
}

@media (max-width: 720px) {
  .grid3 {
    grid-template-columns: 1fr;
  }
  .legend {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
