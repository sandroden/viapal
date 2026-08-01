<template>
  <div class="vp-dbar" role="img" :aria-label="descrizione">
    <div
      v-for="voce in voci"
      :key="voce.tipo"
      class="vp-dbar__seg"
      :style="{
        background: STILI_STATO[voce.stato].dot,
        opacity: voce.stato === 'attesa' ? 0.45 : voce.stato === 'mancante' ? 1 : 0.85,
      }"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { VoceFascicolo } from 'stores/fascicolo';
import { STILI_STATO } from 'src/utils/statoDocumento';

const props = defineProps<{ voci: VoceFascicolo[] }>();

const descrizione = computed(() =>
  props.voci.map((v) => `${v.tipo_display}: ${v.stato_display}`).join(', '),
);
</script>

<style scoped>
.vp-dbar {
  display: flex;
  gap: var(--vp-gap-1);
}
.vp-dbar__seg {
  flex: 1;
  height: 6px;
  border-radius: 3px;
}
</style>
