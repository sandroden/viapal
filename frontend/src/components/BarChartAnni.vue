<template>
  <div class="vp-bca">
    <svg
      :viewBox="`0 0 ${width} ${height}`"
      preserveAspectRatio="xMidYMid meet"
      class="vp-bca__svg"
    >
      <!-- griglia y -->
      <g class="vp-bca__grid">
        <line
          v-for="(_, i) in 5"
          :key="`g-${i}`"
          :x1="margin.left"
          :x2="width - margin.right"
          :y1="margin.top + (innerH * i) / 4"
          :y2="margin.top + (innerH * i) / 4"
        />
      </g>

      <!-- barre per anno (impilate per categoria) -->
      <g v-for="(item, anno_i) in items" :key="item.anno">
        <g
          v-for="(seg, c_i) in item.segments"
          :key="`s-${anno_i}-${c_i}`"
        >
          <rect
            :x="barX(anno_i)"
            :y="seg.y"
            :width="barWidth"
            :height="seg.h"
            :fill="colorCategoria(seg.categoria)"
            :data-cat="seg.categoria"
          >
            <title>
              {{ seg.categoria }}: {{ formattaEuro(seg.importo) }} ({{ item.anno }})
            </title>
          </rect>
        </g>
        <text
          :x="barX(anno_i) + barWidth / 2"
          :y="margin.top + innerH + 18"
          text-anchor="middle"
          class="vp-bca__label-x"
        >
          {{ item.anno }}
        </text>
        <text
          :x="barX(anno_i) + barWidth / 2"
          :y="yScale(item.totale) - 6"
          text-anchor="middle"
          class="vp-bca__label-tot"
        >
          {{ formattaTotale(item.totale) }}
        </text>
      </g>

      <!-- asse y label -->
      <g v-for="(_, i) in 5" :key="`y-${i}`">
        <text
          :x="margin.left - 6"
          :y="margin.top + (innerH * i) / 4 + 4"
          text-anchor="end"
          class="vp-bca__label-y"
        >
          {{ formattaTotale(maxValore - (maxValore * i) / 4) }}
        </text>
      </g>
    </svg>

    <div class="vp-bca__legend">
      <span
        v-for="cat in categorie"
        :key="cat"
        class="vp-bca__legend-item"
      >
        <span
          class="vp-bca__legend-dot"
          :style="{ background: colorCategoria(cat) }"
        />
        {{ cat }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';

interface Riga {
  anno: number;
  perCategoria: Record<string, number>;
}

const props = defineProps<{
  righe: Riga[];
  height?: number;
}>();

const { formattaEuro } = useFormatoEuro();

const width = 760;
const height = computed(() => props.height ?? 280);
const margin = { top: 28, right: 16, bottom: 36, left: 64 };
const innerW = computed(() => width - margin.left - margin.right);
const innerH = computed(() => height.value - margin.top - margin.bottom);

const PALETTE = [
  '#a8542d', // terracotta
  '#7a8b5f', // salvia
  '#c79a4a', // miele
  '#8b5a3c', // legno
  '#5b6c8c', // azzurro polvere
  '#9c4a4a', // argilla scuro
];

const categorie = computed<string[]>(() => {
  const set = new Set<string>();
  for (const r of props.righe) for (const k of Object.keys(r.perCategoria)) set.add(k);
  return [...set].sort();
});

function colorCategoria(cat: string): string {
  const idx = categorie.value.indexOf(cat);
  return PALETTE[idx % PALETTE.length] ?? '#999';
}

const itemsBase = computed(() => {
  const sorted = [...props.righe].sort((a, b) => a.anno - b.anno);
  return sorted.map((r) => {
    const totale = Object.values(r.perCategoria).reduce((s, v) => s + v, 0);
    let cum = 0;
    const segs = categorie.value
      .map((c) => {
        const importo = r.perCategoria[c] ?? 0;
        if (importo === 0) return null;
        const y0 = cum;
        cum += importo;
        return { categoria: c, importo, y0, y1: cum };
      })
      .filter((s): s is { categoria: string; importo: number; y0: number; y1: number } => s !== null);
    return { anno: r.anno, totale, segs };
  });
});

const maxValore = computed(() => {
  let m = 0;
  for (const it of itemsBase.value) m = Math.max(m, it.totale);
  return Math.max(1, Math.ceil(m / 1000) * 1000);
});

function yScale(v: number): number {
  return margin.top + innerH.value - (v / maxValore.value) * innerH.value;
}

const barWidth = computed(() => {
  const n = itemsBase.value.length || 1;
  return Math.min(80, Math.max(24, innerW.value / (n * 1.6)));
});

function barX(i: number): number {
  const n = itemsBase.value.length;
  if (n === 0) return margin.left;
  const step = innerW.value / n;
  return margin.left + step * i + (step - barWidth.value) / 2;
}

const items = computed(() => {
  return itemsBase.value.map((it) => {
    const segments = it.segs.map((s) => {
      const yTop = yScale(s.y1);
      const yBot = yScale(s.y0);
      return { categoria: s.categoria, importo: s.importo, y: yTop, h: Math.max(1, yBot - yTop) };
    });
    return { anno: it.anno, totale: it.totale, segments };
  });
});

function formattaTotale(v: number): string {
  if (v >= 1000) return `${(v / 1000).toFixed(1).replace('.', ',')}k €`;
  return `${Math.round(v)} €`;
}
</script>

<style scoped>
.vp-bca {
  width: 100%;
}
.vp-bca__svg {
  width: 100%;
  height: auto;
  display: block;
}
.vp-bca__grid line {
  stroke: var(--vp-paper-3);
  stroke-dasharray: 2 4;
  stroke-width: 1;
}
.vp-bca__label-x {
  fill: var(--vp-ink-2);
  font-size: 12px;
  font-family: var(--vp-font-ui);
}
.vp-bca__label-y {
  fill: var(--vp-ink-3);
  font-size: 11px;
  font-family: var(--vp-font-ui);
}
.vp-bca__label-tot {
  fill: var(--vp-ink-2);
  font-size: 11px;
  font-family: var(--vp-font-ui);
  font-variant-numeric: tabular-nums;
}
.vp-bca__legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--vp-gap-3);
  margin-top: var(--vp-gap-2);
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-2);
}
.vp-bca__legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.vp-bca__legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  display: inline-block;
}
</style>
