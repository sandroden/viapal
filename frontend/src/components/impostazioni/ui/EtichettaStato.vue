<template>
  <span class="vp-badge" :class="`imm-badge--${tono}`">
    <slot />
  </span>
</template>

<script setup lang="ts">
// Badge della scheda Immobile. Quattro toni, nessun colore inventato riga
// per riga: ok = in vigore/attivo, off = archivio, line = attributo
// neutro, terra = "è questo" (il conto degli incassi, la quota personale).
withDefaults(
  defineProps<{
    tono?: 'ok' | 'off' | 'line' | 'terra';
  }>(),
  { tono: 'off' },
);
</script>

<style scoped>
.imm-badge--ok {
  background: var(--vp-sage-soft);
  color: var(--vp-sage-deep);
}
.imm-badge--off {
  background: var(--vp-paper-3);
  color: var(--vp-ink-2);
}
.imm-badge--line {
  background: transparent;
  color: var(--vp-ink-2);
  border: 1px solid var(--vp-paper-3);
}
.imm-badge--terra {
  background: var(--vp-terra-soft);
  color: var(--vp-terra-deep);
}
</style>
