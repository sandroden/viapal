<template>
  <button
    type="button"
    class="vp-btn imm-btn"
    :class="variante === 'ghost' ? 'vp-btn--ghost' : 'vp-btn--soft'"
    :disabled="disabilitato"
  >
    <VpIcon v-if="icona" :name="icona" :size="14" />
    {{ etichetta }}
  </button>
</template>

<script setup lang="ts">
import VpIcon from 'components/utenze/VpIcon.vue';

// Un solo bottone pieno per vista (q-btn color=primary): le aggiunte sono
// bottoni tenui col «+», le azioni secondarie sono ghost.
withDefaults(
  defineProps<{
    etichetta: string;
    icona?: string;
    variante?: 'soft' | 'ghost';
    disabilitato?: boolean;
  }>(),
  { icona: 'plus', variante: 'soft', disabilitato: false },
);
</script>

<style scoped>
.imm-btn {
  height: 32px;
  padding: 0 13px;
  font-size: 13px;
  gap: 6px;
  flex-shrink: 0;
}
.imm-btn:disabled {
  opacity: 0.5;
  cursor: default;
}
.imm-btn:focus-visible {
  outline: 2px solid var(--vp-terra);
  outline-offset: 1px;
}
</style>
