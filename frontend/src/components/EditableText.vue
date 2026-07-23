<template>
  <span v-if="!editable" class="editable"><slot /></span>
  <span v-else class="editable editable--on" role="button" tabindex="0">
    <slot />
    <q-icon name="edit" size="13px" class="editable-ic" />
    <q-popup-edit
      v-model="draft"
      :title="title"
      buttons
      label-set="Salva"
      label-cancel="Annulla"
      auto-save
      v-slot="scope"
      @save="onSave"
    >
      <q-input
        v-if="textarea"
        v-model="scope.value"
        type="textarea"
        autofocus
        dense
        autogrow
        @keyup.enter.ctrl="scope.set"
      />
      <q-input
        v-else
        v-model="scope.value"
        :type="inputType"
        autofocus
        dense
        @keyup.enter="scope.set"
      />
    </q-popup-edit>
  </span>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';

const props = withDefaults(
  defineProps<{
    value?: string;
    editable?: boolean;
    textarea?: boolean;
    inputType?: 'text' | 'number' | 'date';
    title?: string;
  }>(),
  {
    value: '',
    editable: false,
    textarea: false,
    inputType: 'text',
    title: 'Modifica',
  },
);

const emit = defineEmits<{ (e: 'save', value: string): void }>();

const draft = ref(props.value);
watch(
  () => props.value,
  (v) => {
    draft.value = v;
  },
);

function onSave(value: string) {
  emit('save', value ?? '');
}
</script>

<style scoped>
.editable--on {
  cursor: pointer;
  border-bottom: 1px dashed currentColor;
  position: relative;
}
.editable-ic { margin-left: 4px; opacity: 0.6; vertical-align: middle; }
</style>
