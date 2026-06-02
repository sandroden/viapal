<script setup lang="ts">
// Pillola di stato del periodo.
//   inviato     → verde "inviato"
//   da-inviare  → miele "da inviare"
//   incompleto  → argilla "N mancanti"
import VpIcon from './VpIcon.vue';

withDefaults(
  defineProps<{
    stato: string;
    mancanti?: number;
    compact?: boolean;
  }>(),
  { mancanti: 0, compact: false },
);
</script>

<template>
  <span v-if="stato === 'inviato'" class="vp-badge vp-badge--ok">
    <VpIcon name="check" :size="12" :stroke="2.6" />
    <span v-if="!compact">inviato</span>
  </span>

  <span v-else-if="stato === 'da-inviare'" class="vp-badge vp-badge--wait"> da inviare </span>

  <span v-else class="vp-badge vp-badge--late">
    <VpIcon name="alert" :size="12" /> {{ mancanti }} mancanti
  </span>
</template>
