<template>
  <q-dialog
    :model-value="modelValue"
    full-width
    full-height
    @update:model-value="(v) => emit('update:modelValue', v)"
  >
    <q-card class="vp-pdf-dialog">
      <q-toolbar class="vp-pdf-dialog__toolbar">
        <q-icon name="picture_as_pdf" size="22px" class="q-mr-sm" />
        <q-toolbar-title class="vp-pdf-dialog__title">
          {{ title || 'Bolletta' }}
        </q-toolbar-title>
        <q-btn
          v-if="url"
          flat
          dense
          no-caps
          icon="open_in_new"
          label="Apri in nuova scheda"
          :href="url"
          target="_blank"
          rel="noopener"
        />
        <q-btn
          v-close-popup
          flat
          dense
          round
          icon="close"
          aria-label="Chiudi"
        />
      </q-toolbar>
      <q-card-section class="q-pa-none vp-pdf-dialog__body">
        <iframe
          v-if="url"
          :src="url"
          class="vp-pdf-dialog__iframe"
          title="Anteprima bolletta PDF"
        />
        <div v-else class="vp-pdf-dialog__empty">PDF non disponibile</div>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: boolean;
  url: string | null;
  title?: string | null;
}>();
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void;
}>();
</script>

<style scoped>
.vp-pdf-dialog {
  display: flex;
  flex-direction: column;
  background: var(--vp-cream);
}
.vp-pdf-dialog__toolbar {
  background: var(--vp-paper-2);
  color: var(--vp-ink);
  border-bottom: 1px solid var(--vp-paper-3);
  min-height: 52px;
}
.vp-pdf-dialog__title {
  font-family: var(--vp-font-display);
  font-size: var(--vp-text-base);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.vp-pdf-dialog__body {
  flex: 1;
  display: flex;
}
.vp-pdf-dialog__iframe {
  flex: 1;
  width: 100%;
  height: 100%;
  border: 0;
  background: #525659;
}
.vp-pdf-dialog__empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--vp-ink-3);
  font-style: italic;
}
</style>
