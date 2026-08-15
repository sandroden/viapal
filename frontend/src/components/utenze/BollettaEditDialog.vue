<template>
  <q-dialog v-model="aperto">
    <q-card class="vp-bill-dlg">
      <q-card-section class="row items-center q-pb-none">
        <div>
          <div class="vp-eyebrow">Bolletta {{ bolletta?.prodotto }}</div>
          <div class="vp-display vp-bill-dlg__titolo">Importo e quota esclusa</div>
          <div class="vp-bill-dlg__sub">
            La quota esclusa resta a carico della proprietà e non viene
            ripartita sugli inquilini.
          </div>
        </div>
        <q-space />
        <q-btn icon="close" flat round dense @click="aperto = false" />
      </q-card-section>

      <q-card-section>
        <q-form class="q-gutter-md" @submit.prevent="salva">
          <q-input
            v-model.number="importoTotale"
            type="number"
            step="0.01"
            min="0"
            outlined
            dense
            label="Importo totale bolletta (€)"
          />
          <q-input
            v-model.number="quotaEsclusa"
            type="number"
            step="0.01"
            min="0"
            outlined
            dense
            label="Quota esclusa dalla ripartizione (€)"
            hint="Voci a carico della proprietà: canone RAI, aumento potenza, allacci…"
            :error="!quotaValida"
            error-message="Deve essere tra 0 e l'importo totale."
          />
          <q-input
            v-model="motivoEsclusione"
            outlined
            dense
            label="Motivo esclusione"
            maxlength="200"
            placeholder="Es. Canone RAI"
          />
          <div v-if="quotaEsclusa > 0 && quotaValida" class="vp-bill-dlg__netto">
            Da ripartire: <span class="vp-mono">{{ eur(importoTotale - quotaEsclusa) }}</span>
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
          :disable="!quotaValida || importoTotale <= 0"
          @click="salva"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { eur } from './format';
import type { BollettaFE } from 'stores/utenze';

const props = defineProps<{
  modelValue: boolean;
  bolletta: BollettaFE | null;
  salvando?: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void;
  (
    e: 'salva',
    v: { id: number; importo_totale: string; quota_esclusa: string; motivo_esclusione: string },
  ): void;
}>();

const aperto = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
});

const importoTotale = ref(0);
const quotaEsclusa = ref(0);
const motivoEsclusione = ref('');

watch(
  () => props.modelValue,
  (apertoNuovo) => {
    if (apertoNuovo && props.bolletta) {
      importoTotale.value = Number(parseFloat(props.bolletta.importo_totale).toFixed(2));
      quotaEsclusa.value = Number(parseFloat(props.bolletta.quota_esclusa || '0').toFixed(2));
      motivoEsclusione.value = props.bolletta.motivo_esclusione || '';
    }
  },
);

const quotaValida = computed(
  () => quotaEsclusa.value >= 0 && quotaEsclusa.value <= importoTotale.value,
);

function salva(): void {
  if (!props.bolletta || !quotaValida.value) return;
  emit('salva', {
    id: props.bolletta.id,
    importo_totale: importoTotale.value.toFixed(2),
    quota_esclusa: quotaEsclusa.value.toFixed(2),
    motivo_esclusione: quotaEsclusa.value > 0 ? motivoEsclusione.value : '',
  });
}
</script>

<style scoped>
.vp-bill-dlg {
  width: 420px;
  max-width: 92vw;
  border-radius: var(--vp-r-lg);
}
.vp-bill-dlg__titolo {
  font-size: var(--vp-text-lg, 1.1rem);
}
.vp-bill-dlg__sub {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm, 0.9rem);
  margin-top: 2px;
  max-width: 340px;
}
.vp-bill-dlg__netto {
  font-size: 13px;
  color: var(--vp-ink-3);
}
</style>
