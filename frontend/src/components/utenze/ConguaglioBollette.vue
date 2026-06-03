<script setup lang="ts">
/*
  ConguaglioBollette — contenitore wizard della feature "bollette".
  Shell PRESENTAZIONALE: tutti i numeri arrivano come props dallo store.
  Possiede solo lo stato UI: passo corrente (v-model:step) e — dentro
  InvioStep — quale anteprima è espansa.
*/
import { computed, watch } from 'vue';
import VpIcon from './VpIcon.vue';
import PeriodSelector from './PeriodSelector.vue';
import BollettaStep from './BollettaStep.vue';
import RipartizioneStep from './RipartizioneStep.vue';
import InvioStep from './InvioStep.vue';
import BloccatoState from './BloccatoState.vue';
import { eur } from './format';
import type { Criterio, PeriodoView, BollettaView, VoceView, QuotaView } from './format';
import type { MeseStato } from './PeriodSelector.vue';

const props = defineProps<{
  periodo: PeriodoView;
  periodi: MeseStato[];
  anno: number;
  mese: number;
  criterio: Criterio;
  step: number;
  bollette: BollettaView[];
  voci: VoceView[];
  totale: number;
  quote: QuotaView[];
  mancantiTipi: string[];
  escludi: number[];
  pagataDa?: string;
  nInquilini?: number;
  hasNuovoIngresso?: boolean;
  ingressoNota?: string;
  needsEmetti: boolean;
  giaInviatoAt?: string | null;
}>();

const emit = defineEmits<{
  'cambia-periodo': [v: { anno: number; mese: number }];
  'update:criterio': [c: Criterio];
  'update:step': [n: number];
  upload: [tipo?: string];
  invia: [];
  emetti: [];
  'toggle-invio': [receivableId: number];
  'view-pdf': [v: { url: string; title: string }];
}>();

const STEPS = ['Bolletta', 'Ripartizione', 'Invio'];

const per = computed<PeriodoView>(() => props.periodo);
const incompleto = computed(() => per.value?.stato === 'incompleto');
const mancanti = computed(() => props.mancantiTipi.length);
// Avvisi che verranno effettivamente inviati: non usciti e non esclusi a mano.
const daInviare = computed(() =>
  props.quote.filter(
    (q) => q.notificare !== false && !props.escludi.includes(Number(q.receivableId)),
  ),
);

// Cambiando periodo si torna al passo 1.
watch(
  () => [props.anno, props.mese],
  () => emit('update:step', 1),
);

function goStep(n: number): void {
  if (incompleto.value && n > 1) return;
  emit('update:step', n);
}
function setStep(n: number): void {
  emit('update:step', n);
}
</script>

<template>
  <div class="cg">
    <!-- Header -->
    <div class="head">
      <div class="crumbs">
        <span>Utenze</span>
        <VpIcon name="chevron" :size="12" />
        <span class="ink">{{ per?.label }}</span>
      </div>

      <div class="title-row">
        <div>
          <h1 class="vp-display title">
            Utenze, <span class="title-mese">{{ per?.mese }}</span>
          </h1>
          <div class="title-sub">
            Periodo {{ per?.range }} · {{ nInquilini }} inquilini<span v-if="pagataDa">
              · pagata da {{ pagataDa }}</span
            >
          </div>
        </div>

        <PeriodSelector
          :anno="anno"
          :mese="mese"
          :stato="per.stato"
          :mancanti="per.attese - per.presenti"
          :periodi="periodi"
          @cambia="(v) => emit('cambia-periodo', v)"
        />
      </div>

      <!-- Stepper -->
      <div class="stepper">
        <button
          v-for="(label, i) in STEPS"
          :key="label"
          class="chip"
          :class="{ active: step === i + 1, done: i + 1 < step, locked: incompleto && i + 1 > 1 }"
          :disabled="incompleto && i + 1 > 1"
          @click="goStep(i + 1)"
        >
          <span class="num">
            <VpIcon v-if="i + 1 < step" name="check" :size="13" :stroke="3" color="#fff" />
            <VpIcon
              v-else-if="incompleto && i + 1 > 1"
              name="lock"
              :size="12"
              color="var(--vp-ink-3)"
            />
            <template v-else>{{ i + 1 }}</template>
          </span>
          <span class="chip-text">
            <span class="chip-eyebrow">Passo {{ i + 1 }}</span>
            <span class="chip-label">{{ label }}</span>
          </span>
        </button>
      </div>
    </div>

    <!-- Body -->
    <div class="body vp-scroll">
      <BollettaStep
        v-if="step === 1 && per"
        :periodo="per"
        :bollette="bollette"
        :voci="voci"
        :totale="totale"
        :mancanti-tipi="mancantiTipi"
        @upload="(t) => emit('upload', t)"
        @view-pdf="(v) => emit('view-pdf', v)"
      />
      <template v-else-if="step === 2">
        <BloccatoState v-if="incompleto" :mancanti="mancanti" @torna="setStep(1)" />
        <RipartizioneStep
          v-else
          :criterio="criterio"
          :quote="quote"
          :voci="voci"
          :totale="totale"
          :has-nuovo-ingresso="hasNuovoIngresso ?? false"
          :ingresso-nota="ingressoNota ?? ''"
          @update:criterio="(v) => emit('update:criterio', v)"
        />
      </template>
      <template v-else-if="per">
        <BloccatoState v-if="incompleto" :mancanti="mancanti" @torna="setStep(1)" />
        <InvioStep
          v-else
          :periodo="per"
          :quote="quote"
          :criterio="criterio"
          :needs-emetti="needsEmetti"
          :gia-inviato-at="giaInviatoAt ?? null"
          :escludi="escludi"
          @invia="emit('invia')"
          @emetti="emit('emetti')"
          @toggle="(id) => emit('toggle-invio', id)"
        />
      </template>
    </div>

    <!-- Footer nav -->
    <div class="foot">
      <button
        class="vp-btn vp-btn--ghost"
        :disabled="step === 1"
        :style="{ opacity: step === 1 ? 0.4 : 1 }"
        @click="setStep(Math.max(1, step - 1))"
      >
        <VpIcon name="back" :size="16" /> Indietro
      </button>

      <div class="foot-status">
        <template v-if="incompleto"
          >Mancano {{ mancanti }} bollette per chiudere {{ per?.label }}</template
        >
        <template v-else-if="step === 1"
          >{{ bollette.length }} bollette lette · totale {{ eur(totale) }}</template
        >
        <template v-else-if="step === 2 && needsEmetti"
          >Somma quote {{ eur(quote.reduce((s, q) => s + q.quota, 0)) }} — crea gli addebiti per
          procedere</template
        >
        <template v-else-if="step === 2"
          >Addebiti già creati · {{ eur(quote.reduce((s, q) => s + q.quota, 0)) }}</template
        >
        <template v-else-if="needsEmetti">Crea gli addebiti per preparare gli avvisi</template>
        <template v-else
          >{{ daInviare.length }} avvisi pronti all'invio<span
            v-if="quote.length > daInviare.length"
          >
            · {{ quote.length - daInviare.length }} esclusi</span
          ></template
        >
      </div>

      <!-- Step 1 incompleto: carica le mancanti -->
      <button v-if="incompleto" class="vp-btn vp-btn--primary" @click="emit('upload')">
        <VpIcon name="upload" :size="16" color="#fff" /> Carica le {{ mancanti }} mancanti
      </button>
      <!-- Step 1: avanti alla ripartizione -->
      <button v-else-if="step === 1" class="vp-btn vp-btn--primary" @click="setStep(2)">
        Vai alla ripartizione <VpIcon name="arrow" :size="16" color="#fff" />
      </button>
      <!-- Step 2: creazione addebiti ESPLICITA, poi invio -->
      <button
        v-else-if="step === 2 && needsEmetti"
        class="vp-btn vp-btn--primary"
        @click="emit('emetti')"
      >
        <VpIcon name="check" :size="16" :stroke="2.4" color="#fff" /> Crea addebiti
      </button>
      <button v-else-if="step === 2" class="vp-btn vp-btn--primary" @click="setStep(3)">
        Vai all'invio <VpIcon name="arrow" :size="16" color="#fff" />
      </button>
      <!-- Step 3: invio (fallback crea addebiti se si è saltati qui) -->
      <button
        v-else-if="needsEmetti"
        class="vp-btn vp-btn--primary"
        @click="emit('emetti')"
      >
        <VpIcon name="check" :size="16" :stroke="2.4" color="#fff" /> Crea addebiti
      </button>
      <button
        v-else
        class="vp-btn vp-btn--primary"
        :disabled="!daInviare.length"
        :style="{ opacity: daInviare.length ? 1 : 0.5 }"
        @click="emit('invia')"
      >
        <VpIcon name="message" :size="16" color="#fff" />
        {{ giaInviatoAt ? 'Invia di nuovo' : `Invia ${daInviare.length} avvisi` }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.cg {
  width: 100%;
  display: flex;
  flex-direction: column;
  background: var(--vp-paper);
  color: var(--vp-ink);
  font-family: var(--vp-font-ui);
  min-height: calc(100vh - 50px);
}
.ink {
  color: var(--vp-ink);
}

.head {
  padding: 18px 36px 0;
  flex-shrink: 0;
  position: sticky;
  top: 0;
  z-index: 5;
  background: var(--vp-paper);
}
.crumbs {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--vp-ink-3);
}
.title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin: 8px 0 16px;
  flex-wrap: wrap;
  gap: 12px;
}
.title {
  font-size: 30px;
  margin: 0;
}
.title-mese {
  color: var(--vp-ink-2);
  font-style: italic;
}
.title-sub {
  color: var(--vp-ink-2);
  font-size: 14px;
  margin-top: 4px;
}

.stepper {
  display: flex;
  gap: 10px;
}
.chip {
  flex: 1;
  padding: 11px 16px;
  border-radius: 12px;
  cursor: pointer;
  text-align: left;
  background: var(--vp-paper-2);
  border: 1.5px solid transparent;
  display: flex;
  align-items: center;
  gap: 11px;
  font-family: inherit;
  color: var(--vp-ink-3);
  transition:
    background 0.15s,
    border-color 0.15s;
}
.chip.done {
  background: var(--vp-sage-soft);
  color: var(--vp-sage-deep);
}
.chip.active {
  background: var(--vp-cream);
  border-color: var(--vp-terra);
  color: var(--vp-ink);
}
.chip.locked {
  opacity: 0.5;
  cursor: not-allowed;
}
.num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--vp-paper-3);
  color: var(--vp-ink-3);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
}
.chip.done .num {
  background: var(--vp-sage);
  color: #fff;
}
.chip.active .num {
  background: var(--vp-terra);
  color: #fff;
}
.chip-text {
  display: flex;
  flex-direction: column;
}
.chip-eyebrow {
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  opacity: 0.7;
  font-weight: 500;
}
.chip-label {
  font-size: 15px;
  font-weight: 500;
  margin-top: 1px;
}
.chip.active .chip-label {
  font-weight: 600;
}

.body {
  flex: 1;
  min-height: 0;
  padding: 20px 36px 96px;
}

.foot {
  flex-shrink: 0;
  padding: 14px 36px;
  border-top: 1px solid var(--vp-paper-3);
  background: var(--vp-paper);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  position: sticky;
  bottom: 0;
  z-index: 5;
}
.foot-status {
  font-size: 13px;
  color: var(--vp-ink-3);
}

@media (max-width: 720px) {
  .head {
    padding: 14px 16px 0;
  }
  .body {
    padding: 16px 16px 96px;
  }
  .foot {
    padding: 12px 16px;
  }
  .title {
    font-size: 24px;
  }
  .chip-eyebrow {
    display: none;
  }
}
</style>
