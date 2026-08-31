<template>
  <q-dialog v-model="aperto">
    <q-card class="vp-tari-dlg">
      <q-card-section class="row items-center q-pb-none">
        <div>
          <div class="vp-eyebrow">TARI · {{ periodoLabel }}</div>
          <div class="vp-display vp-tari-dlg__titolo">Quota a carico della proprietà</div>
          <div class="vp-tari-dlg__sub">
            La parte esclusa non viene ripartita sugli inquilini: è il caso del posto
            rimasto sfitto, la cui TARI non va scaricata su chi c'è.
          </div>
        </div>
        <q-space />
        <q-btn icon="close" flat round dense @click="aperto = false" />
      </q-card-section>

      <q-card-section>
        <q-form class="q-gutter-md" @submit.prevent="salva">
          <div v-if="periodoEmesso" class="vp-tari-dlg__emesso">
            Periodo già emesso: gli addebiti creati non si aggiornano da soli,
            vanno rigenerati.
          </div>
          <div class="vp-tari-dlg__lorda">
            TARI del periodo: <span class="vp-mono">{{ eur(tariLorda) }}</span>
          </div>
          <q-input
            v-model.number="quotaEsclusa"
            type="number"
            step="0.01"
            min="0"
            outlined
            dense
            label="Quota esclusa dalla ripartizione (€)"
            hint="Quanto resta a carico della proprietà per questo periodo."
            :error="!quotaValida"
            error-message="Deve essere tra 0 e la TARI del periodo."
          />
          <q-input
            v-model="motivo"
            outlined
            dense
            label="Motivo esclusione"
            maxlength="200"
            placeholder="Es. Stanza singola sfitta"
          />

          <!-- Aiuto al calcolo: la frazione dei posti scoperti sul totale. -->
          <div class="vp-tari-dlg__calc">
            <div class="vp-tari-dlg__calc-lbl">Aiuto al calcolo</div>
            <div class="vp-tari-dlg__calc-row">
              <q-input
                v-model.number="postiSfitti"
                type="number"
                min="0"
                outlined
                dense
                label="posti sfitti"
                class="vp-tari-dlg__calc-in"
              />
              <span class="vp-tari-dlg__calc-su">su</span>
              <q-input
                v-model.number="postiTotali"
                type="number"
                min="1"
                outlined
                dense
                label="posti totali"
                class="vp-tari-dlg__calc-in"
              />
              <q-btn
                flat
                dense
                no-caps
                color="primary"
                label="Usa"
                :disable="!quotaSuggerita"
                @click="applicaSuggerita"
              />
            </div>
            <div v-if="quotaSuggerita" class="vp-tari-dlg__calc-hint">
              {{ postiSfitti }} su {{ postiTotali }} →
              <span class="vp-mono">{{ eur(quotaSuggerita) }}</span>
            </div>
          </div>

          <div v-if="quotaEsclusa > 0 && quotaValida" class="vp-tari-dlg__netto">
            Da ripartire: <span class="vp-mono">{{ eur(tariLorda - quotaEsclusa) }}</span>
          </div>
        </q-form>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn flat color="primary" label="Annulla" no-caps @click="aperto = false" />
        <q-btn
          unelevated
          color="primary"
          label="Salva"
          no-caps
          :loading="salvando"
          :disable="!quotaValida"
          @click="salva"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { eur } from './format';

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    /** TARI lorda del periodo (prima dell'esclusione). */
    tariLorda: number;
    quotaIniziale?: number;
    motivoIniziale?: string;
    /** Inquilini presenti nel periodo: precompila i posti del calcolatore. */
    presenti?: number;
    periodoLabel?: string;
    /** Periodo già emesso: la modifica è ammessa ma non tocca gli addebiti. */
    periodoEmesso?: boolean;
    salvando?: boolean;
  }>(),
  {
    quotaIniziale: 0,
    motivoIniziale: '',
    presenti: 0,
    periodoLabel: '',
    periodoEmesso: false,
    salvando: false,
  },
);

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void;
  (e: 'salva', v: { quota_esclusa: string; motivo: string }): void;
}>();

const aperto = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
});

const quotaEsclusa = ref(0);
const motivo = ref('');
const postiSfitti = ref(1);
const postiTotali = ref(1);

watch(
  () => props.modelValue,
  (apertoNuovo) => {
    if (!apertoNuovo) return;
    quotaEsclusa.value = Number((props.quotaIniziale || 0).toFixed(2));
    motivo.value = props.motivoIniziale || '';
    postiSfitti.value = 1;
    // Caso tipico: la casa è piena tranne un posto → totale = presenti + 1.
    postiTotali.value = Math.max(1, (props.presenti || 0) + 1);
  },
);

const quotaValida = computed(
  () => quotaEsclusa.value >= 0 && quotaEsclusa.value <= props.tariLorda,
);

const quotaSuggerita = computed(() => {
  const sfitti = Number(postiSfitti.value) || 0;
  const totali = Number(postiTotali.value) || 0;
  if (sfitti <= 0 || totali <= 0 || sfitti > totali) return 0;
  return Math.round(((props.tariLorda * sfitti) / totali) * 100) / 100;
});

function applicaSuggerita(): void {
  if (!quotaSuggerita.value) return;
  quotaEsclusa.value = quotaSuggerita.value;
  if (!motivo.value) {
    motivo.value =
      postiSfitti.value === 1 ? 'Un posto sfitto' : `${postiSfitti.value} posti sfitti`;
  }
}

function salva(): void {
  if (!quotaValida.value) return;
  emit('salva', {
    quota_esclusa: quotaEsclusa.value.toFixed(2),
    motivo: quotaEsclusa.value > 0 ? motivo.value : '',
  });
}
</script>

<style scoped>
.vp-tari-dlg {
  width: 440px;
  max-width: 92vw;
  border-radius: var(--vp-r-lg);
}
.vp-tari-dlg__titolo {
  font-size: var(--vp-text-lg, 1.1rem);
}
.vp-tari-dlg__sub {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm, 0.9rem);
  margin-top: 2px;
  max-width: 360px;
}
.vp-tari-dlg__emesso {
  background: var(--vp-clay-soft, #f6e7dd);
  color: var(--vp-clay-deep, #7a4a2f);
  border-radius: var(--vp-r-md, 10px);
  padding: 8px 10px;
  font-size: 12px;
}
.vp-tari-dlg__lorda {
  font-size: 13px;
  color: var(--vp-ink-3);
}
.vp-tari-dlg__netto {
  font-size: 13px;
  color: var(--vp-ink-3);
}
.vp-tari-dlg__calc {
  border: 1px dashed var(--vp-line, #d9d3c7);
  border-radius: var(--vp-r-md, 10px);
  padding: 10px 12px;
}
.vp-tari-dlg__calc-lbl {
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--vp-ink-3);
  margin-bottom: 6px;
}
.vp-tari-dlg__calc-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.vp-tari-dlg__calc-in {
  width: 96px;
}
.vp-tari-dlg__calc-su {
  color: var(--vp-ink-3);
  font-size: 13px;
}
.vp-tari-dlg__calc-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--vp-ink-3);
}
</style>
