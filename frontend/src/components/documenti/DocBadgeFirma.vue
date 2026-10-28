<template>
  <span class="vp-dbf" :style="{ background: stile.bg, color: stile.fg }">
    <span class="vp-dbf__dot" :style="{ background: stile.dot }" />
    {{ stile.label }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { StatoFirma } from 'stores/fascicolo';
import { STILI_FIRMA } from 'src/utils/statoDocumento';

/** A che punto è la firma di una versione: stessa forma del badge di stato,
 *  colori suoi, così le due cose non si confondono sulla stessa riga. */
const props = defineProps<{ stato: StatoFirma }>();

const stile = computed(() => STILI_FIRMA[props.stato] ?? STILI_FIRMA['']);
</script>

<style scoped>
.vp-dbf {
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
.vp-dbf__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
</style>
