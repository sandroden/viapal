<script setup lang="ts">
// Grafica "scontrino": rappresentazione decorativa di una bolletta letta —
// carta crema, mono, riga tratteggiata, bordo inferiore a zig-zag.
//   full → fornitore / periodo / consumo / riferimento + totale + "letto"
//   mini → solo header tipo + totale (miniature nello strip di upload)
import { computed } from 'vue';
import VpIcon from './VpIcon.vue';
import { utility, eur, type ScontrinoData } from './format';

const props = withDefaults(
  defineProps<{
    bolletta: ScontrinoData;
    tilt?: number;
    w?: number;
    read?: boolean;
    mini?: boolean;
  }>(),
  { tilt: 0, w: 150, read: true, mini: false },
);

const c = computed(() => utility(props.bolletta.tipo));
const teeth = computed(() => (props.mini ? 7 : 14));
const points = computed(() =>
  Array.from({ length: teeth.value })
    .map((_, i) => `${i * 10},0 ${i * 10 + 5},8 ${i * 10 + 10},0`)
    .join(' '),
);
</script>

<template>
  <div
    class="scontrino"
    :style="{
      width: w + 'px',
      transform: `rotate(${tilt}deg)`,
      paddingBottom: (mini ? 6 : 10) + 'px',
    }"
  >
    <div :style="{ padding: mini ? '9px 9px 7px' : '13px 14px 10px' }">
      <div class="row-head" :style="{ marginBottom: (mini ? 5 : 7) + 'px' }">
        <VpIcon :name="c.icon" :size="mini ? 11 : 13" :color="c.fg" />
        <span class="tipo" :style="{ fontSize: (mini ? 9 : 11) + 'px' }">{{
          bolletta.tipo.toUpperCase()
        }}</span>
      </div>

      <div v-if="!mini" class="meta">
        <div class="forn">{{ bolletta.fornitore }}</div>
        <div>Periodo {{ bolletta.periodo }}</div>
        <div>Consumo {{ bolletta.consumo }}</div>
        <div>{{ bolletta.riferimento }}</div>
      </div>

      <div class="rule" :style="{ margin: mini ? '6px 0 5px' : '9px 0 8px' }"></div>

      <div class="total">
        <span v-if="!mini" class="tot-label">TOTALE</span>
        <span class="tot-val" :style="{ fontSize: (mini ? 11 : 15) + 'px', color: c.fg }">{{
          eur(bolletta.importo)
        }}</span>
      </div>

      <div v-if="read && !mini" class="letto">
        <VpIcon name="check" :size="11" :stroke="2.6" color="var(--vp-sage)" /> letto dall'AI
      </div>
    </div>

    <svg
      :width="w"
      :height="mini ? 6 : 8"
      :viewBox="`0 0 ${teeth * 10} 8`"
      preserveAspectRatio="none"
      style="display: block"
    >
      <polygon :points="points" fill="#f6efe2" />
    </svg>
  </div>
</template>

<style scoped>
.scontrino {
  background: #f6efe2;
  border-radius: 4px 4px 0 0;
  box-shadow: var(--vp-shadow-2);
  font-family: var(--vp-font-mono);
  color: #3a2f24;
  position: relative;
}
.row-head {
  display: flex;
  align-items: center;
  gap: 5px;
}
.tipo {
  font-weight: 700;
  letter-spacing: 0.04em;
}
.meta {
  font-size: 9px;
  line-height: 1.7;
  color: #6b5d4a;
}
.meta .forn {
  font-weight: 700;
  color: #3a2f24;
}
.rule {
  border-top: 1.5px dashed #c5b48f;
}
.total {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.tot-label {
  font-size: 9px;
  color: #6b5d4a;
}
.tot-val {
  font-weight: 700;
}
.letto {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  font-size: 8.5px;
  color: var(--vp-sage-deep);
  font-family: var(--vp-font-ui);
}
</style>
