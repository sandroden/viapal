<template>
  <span class="vp-dbs" :style="{ background: stile.bg, color: stile.fg }">
    <span class="vp-dbs__dot" :style="{ background: stile.dot }" />
    {{ testo ?? stile.label }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { StatoDocumento } from 'stores/fascicolo';
import { STILI_STATO } from 'src/utils/statoDocumento';

const props = defineProps<{
  stato: StatoDocumento;
  /** Testo alternativo all'etichetta di default (es. "scade il 14/10/2026"). */
  testo?: string | undefined;
}>();

const stile = computed(() => STILI_STATO[props.stato]);
</script>

<style scoped>
.vp-dbs {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 21px;
  padding: 0 8px;
  border-radius: var(--vp-r-pill);
  font-size: 11.5px;
  font-weight: 500;
  white-space: nowrap;
}
.vp-dbs__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
</style>
