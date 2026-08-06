<template>
  <button
    type="button"
    class="imm-ib"
    :class="{ 'imm-ib--danger': pericolo }"
    :aria-label="etichetta"
    :disabled="disabilitato"
  >
    <VpIcon :name="icona" :size="16" />
    <q-tooltip v-if="tooltip">{{ tooltip }}</q-tooltip>
  </button>
</template>

<script setup lang="ts">
import VpIcon from 'components/utenze/VpIcon.vue';

// Matita e cestino discreti e identici ovunque: oggi cambiano colore da
// tab a tab. Il rosso compare solo al passaggio del mouse sul cestino.
withDefaults(
  defineProps<{
    icona: string;
    /** Testo per screen reader (finisce in aria-label). */
    etichetta: string;
    tooltip?: string;
    pericolo?: boolean;
    disabilitato?: boolean;
  }>(),
  { tooltip: '', pericolo: false, disabilitato: false },
);
</script>

<style scoped>
.imm-ib {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--vp-ink-3);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition:
    background 0.12s,
    color 0.12s;
}
.imm-ib:hover:not(:disabled) {
  background: var(--vp-paper-2);
  color: var(--vp-ink);
}
.imm-ib--danger:hover:not(:disabled) {
  background: var(--vp-clay-soft);
  color: var(--vp-clay);
}
.imm-ib:disabled {
  opacity: 0.4;
  cursor: default;
}
.imm-ib:focus-visible {
  outline: 2px solid var(--vp-terra);
  outline-offset: 1px;
}
</style>
