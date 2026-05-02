<template>
  <span class="vp-semaforo" :class="`vp-semaforo--${livello}`">
    <span class="vp-semaforo__dot" />
    <span v-if="testo">{{ testo }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';

export type SemaforoLivello = 'salvia' | 'miele' | 'argilla_chiaro' | 'argilla_scuro';

const props = defineProps<{
  livello: SemaforoLivello;
  label?: string;
  giorniRitardo?: number;
}>();

const defaultLabel: Record<SemaforoLivello, string> = {
  salvia: 'In regola',
  miele: 'In scadenza',
  argilla_chiaro: 'In ritardo',
  argilla_scuro: 'Scaduto',
};

const testo = computed<string>(() => {
  if (props.label !== undefined) return props.label;
  if (typeof props.giorniRitardo === 'number') {
    const g = props.giorniRitardo;
    if (g > 0) return `${g} g di ritardo`;
    if (g === 0) return 'Oggi';
    return `${Math.abs(g)} g alla scadenza`;
  }
  return defaultLabel[props.livello];
});
</script>

<style scoped>
.vp-semaforo {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 24px;
  padding: 0 10px;
  border-radius: var(--vp-r-pill);
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  font-family: var(--vp-font-ui);
}
.vp-semaforo__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  background: currentColor;
  opacity: 0.7;
}
.vp-semaforo--salvia {
  background: var(--vp-status-ok-bg);
  color: var(--vp-status-ok-fg);
}
.vp-semaforo--miele {
  background: var(--vp-status-wait-bg);
  color: var(--vp-status-wait-fg);
}
.vp-semaforo--argilla_chiaro {
  background: oklch(0.92 0.045 35);
  color: oklch(0.45 0.110 30);
}
.vp-semaforo--argilla_scuro {
  background: var(--vp-status-late-bg);
  color: var(--vp-status-late-fg);
}
</style>
