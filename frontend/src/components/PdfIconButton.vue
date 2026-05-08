<template>
  <q-btn
    flat
    round
    dense
    color="primary"
    icon="picture_as_pdf"
    size="sm"
    aria-label="Apri PDF bolletta"
    @click.stop="emit('click')"
  >
    <q-tooltip
      v-if="title"
      anchor="top middle"
      self="bottom middle"
      :offset="[0, 4]"
      class="vp-pdf-tooltip"
    >
      {{ title }}
    </q-tooltip>
  </q-btn>
</template>

<script setup lang="ts">
defineProps<{
  title?: string | null;
}>();
const emit = defineEmits<{
  (e: 'click'): void;
}>();
</script>

<style scoped>
.vp-pdf-tooltip {
  font-size: var(--vp-text-xs, 12px);
  background: var(--vp-ink, #2b2b2b);
  color: var(--vp-cream, #fff);
  padding: 4px 8px;
  border-radius: 4px;
  max-width: 360px;
}
</style>
