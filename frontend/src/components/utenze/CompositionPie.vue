<script setup lang="ts">
// Torta (donut) della composizione spese: un segmento per voce (Luce/Gas/TARI),
// colori dalla mappa UTILITY. Più efficace della barra lineare su desktop.
import { computed } from 'vue';
import { utility, eur } from './format';
import type { VoceView } from './format';

const props = withDefaults(
  defineProps<{
    voci: VoceView[];
    totale: number;
    size?: number;
    stroke?: number;
  }>(),
  { size: 168, stroke: 26 },
);

const r = computed(() => (props.size - props.stroke) / 2);
const circ = computed(() => 2 * Math.PI * r.value);

interface Segmento {
  tipo: string;
  importo: number;
  pct: number;
  dash: number;
  offset: number;
  color: string;
}

const segmenti = computed<Segmento[]>(() => {
  const tot = props.totale || props.voci.reduce((s, v) => s + v.importo, 0) || 1;
  let acc = 0;
  return props.voci.map((v) => {
    const frac = v.importo / tot;
    const dash = frac * circ.value;
    const seg: Segmento = {
      tipo: v.tipo,
      importo: v.importo,
      pct: Math.round(frac * 100),
      dash,
      // offset negativo: i segmenti si concatenano partendo da ore 12
      offset: -acc * circ.value,
      color: utility(v.tipo).bar,
    };
    acc += frac;
    return seg;
  });
});
</script>

<template>
  <div class="pie">
    <div class="pie-wrap" :style="{ width: size + 'px', height: size + 'px' }">
      <svg :width="size" :height="size" class="pie-svg">
        <circle
          :cx="size / 2"
          :cy="size / 2"
          :r="r"
          fill="none"
          stroke="var(--vp-paper-2)"
          :stroke-width="stroke"
        />
        <circle
          v-for="s in segmenti"
          :key="s.tipo"
          :cx="size / 2"
          :cy="size / 2"
          :r="r"
          fill="none"
          :stroke="s.color"
          :stroke-width="stroke"
          :stroke-dasharray="`${s.dash} ${circ - s.dash}`"
          :stroke-dashoffset="s.offset"
        />
      </svg>
      <div class="pie-center">
        <div class="vp-eyebrow">Totale</div>
        <div class="vp-mono pie-tot">{{ eur(totale) }}</div>
      </div>
    </div>

    <div class="pie-legend">
      <div v-for="s in segmenti" :key="s.tipo" class="pie-leg">
        <span class="pie-swatch" :style="{ background: s.color }"></span>
        <span class="pie-tipo">{{ s.tipo }}</span>
        <span class="pie-pct">{{ s.pct }}%</span>
        <span class="vp-mono pie-val">{{ eur(s.importo) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pie {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
}
.pie-wrap {
  position: relative;
  flex-shrink: 0;
}
.pie-svg {
  transform: rotate(-90deg);
}
.pie-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}
.pie-tot {
  font-size: 19px;
  font-weight: 600;
  color: var(--vp-ink);
}
.pie-legend {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.pie-leg {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.pie-swatch {
  width: 12px;
  height: 12px;
  border-radius: 4px;
  flex-shrink: 0;
}
.pie-tipo {
  color: var(--vp-ink-2);
}
.pie-pct {
  color: var(--vp-ink-4);
  margin-left: 2px;
}
.pie-val {
  margin-left: auto;
  font-weight: 500;
  color: var(--vp-ink);
}
</style>
