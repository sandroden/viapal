<template>
  <article class="vp-pag-card">
    <header class="vp-pag-card__head">
      <div class="vp-pag-card__tipo">
        <q-icon :name="iconaTipo" size="20px" />
        <span>{{ tipoLabel }}</span>
      </div>
      <SemaforoBadge :livello="item.semaforo" :giorni-ritardo="item.giorni_ritardo" />
    </header>

    <div class="vp-pag-card__descrizione">{{ item.descrizione }}</div>

    <div v-if="item.parziale" class="vp-pag-card__parziale">
      <div class="vp-pag-card__parziale-row">
        <span class="vp-pag-card__quasi">Pagato in parte</span>
        <span class="vp-pag-card__perc">{{ percento }}%</span>
      </div>
      <q-linear-progress
        :value="frazione"
        rounded
        size="8px"
        color="secondary"
        track-color="grey-3"
        class="vp-pag-card__progress"
      />
      <div class="vp-pag-card__versato">
        Versato <span class="vp-mono">{{ formattaEuro(item.importo_pagato) }}</span>
        di <span class="vp-mono">{{ formattaEuro(item.importo_dovuto) }}</span>
      </div>
    </div>

    <div class="vp-pag-card__meta">
      <div>
        <div class="vp-pag-card__importo-label">{{ item.parziale ? 'Resto da saldare' : 'Importo' }}</div>
        <div class="vp-pag-card__importo vp-display">{{ formattaEuro(item.residuo) }}</div>
      </div>
      <div class="vp-pag-card__scadenza">Scadenza: {{ formattaData(item.scadenza) }}</div>
    </div>

    <footer class="vp-pag-card__azioni">
      <q-btn
        v-if="item.stato !== 'dichiarato'"
        unelevated
        color="primary"
        :to="`/i/paga/${item.tipo}/${item.id}`"
        :label="item.parziale ? 'Salda il resto' : 'Ho pagato'"
        icon-right="check"
      />
      <q-chip v-else dense color="amber-2" text-color="amber-9" icon="hourglass_top">
        In attesa di conferma
      </q-chip>
      <q-btn
        v-if="item.tipo === 'utility_charge'"
        flat
        color="primary"
        :to="`/i/utenze/${item.id}`"
        label="Dettaglio"
      />
    </footer>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import SemaforoBadge from 'src/components/SemaforoBadge.vue';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';
import type { DaPagareItem } from 'src/stores/dashboard';

const props = defineProps<{ item: DaPagareItem }>();

const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

const frazione = computed(() => {
  if (!props.item.importo_dovuto) return 0;
  const f = props.item.importo_pagato / props.item.importo_dovuto;
  return Math.max(0, Math.min(1, f));
});
const percento = computed(() => Math.round(frazione.value * 100));

const tipoLabel = computed(() => {
  switch (props.item.tipo) {
    case 'rent':
      return 'Affitto';
    case 'utility_charge':
      return 'Utenze';
    case 'extra':
      return 'Spesa extra';
    default:
      return 'Pagamento';
  }
});

const iconaTipo = computed(() => {
  switch (props.item.tipo) {
    case 'rent':
      return 'home';
    case 'utility_charge':
      return 'bolt';
    case 'extra':
      return 'note_add';
    default:
      return 'payments';
  }
});
</script>

<style scoped>
.vp-pag-card {
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  box-shadow: var(--vp-shadow-1);
  padding: var(--vp-gap-4);
  display: flex;
  flex-direction: column;
  gap: var(--vp-gap-3);
}
.vp-pag-card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--vp-gap-3);
}
.vp-pag-card__tipo {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--vp-ink-2);
  font-size: var(--vp-text-sm);
  font-weight: 500;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}
.vp-pag-card__descrizione {
  font-family: var(--vp-font-display);
  font-size: var(--vp-text-xl);
  color: var(--vp-ink);
  line-height: 1.25;
}
.vp-pag-card__parziale {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: var(--vp-gap-3);
  background: var(--vp-paper);
  border-radius: var(--vp-r-md);
}
.vp-pag-card__parziale-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.vp-pag-card__quasi {
  font-size: var(--vp-text-sm);
  font-weight: 600;
  color: var(--vp-sage-deep);
}
.vp-pag-card__perc {
  font-size: var(--vp-text-sm);
  font-weight: 600;
  color: var(--vp-sage-deep);
  font-variant-numeric: tabular-nums;
}
.vp-pag-card__progress {
  border-radius: var(--vp-r-pill);
}
.vp-pag-card__versato {
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-3);
}
.vp-pag-card__meta {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--vp-gap-3);
  flex-wrap: wrap;
}
.vp-pag-card__importo-label {
  font-size: var(--vp-text-xs);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--vp-ink-3);
  margin-bottom: 2px;
}
.vp-pag-card__importo {
  font-size: var(--vp-text-2xl);
  color: var(--vp-terra-deep);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}
.vp-pag-card__scadenza {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm);
}
.vp-pag-card__azioni {
  display: flex;
  gap: var(--vp-gap-2);
  justify-content: flex-end;
  flex-wrap: wrap;
}
</style>
