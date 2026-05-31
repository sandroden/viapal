<template>
  <div class="th-donut" :style="{ width: `${size}px`, height: `${size}px` }">
    <svg :width="size" :height="size" class="th-donut__svg">
      <circle
        :cx="size / 2" :cy="size / 2" :r="r" fill="none"
        stroke="var(--vp-paper-3)" :stroke-width="stroke"
      />
      <circle
        :cx="size / 2" :cy="size / 2" :r="r" fill="none"
        stroke="var(--vp-sage)" :stroke-width="stroke"
        :stroke-dasharray="c" :stroke-dashoffset="off" stroke-linecap="round"
      />
    </svg>
    <div class="th-donut__pct" :style="{ fontSize: `${Math.round(size * 0.27)}px` }">{{ pct }}%</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(defineProps<{ pct: number; size?: number; stroke?: number }>(), {
  size: 46,
  stroke: 5,
});

const r = computed(() => (props.size - props.stroke) / 2);
const c = computed(() => 2 * Math.PI * r.value);
const off = computed(() => c.value * (1 - props.pct / 100));
</script>

<style scoped>
.th-donut {
  position: relative;
  flex-shrink: 0;
}
.th-donut__svg {
  transform: rotate(-90deg);
}
.th-donut__pct {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: var(--vp-sage-deep);
  font-family: var(--vp-font-ui);
  font-variant-numeric: tabular-nums;
}
</style>
