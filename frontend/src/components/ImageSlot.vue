<template>
  <div
    class="imgslot"
    :class="{ 'imgslot--editable': editable, 'imgslot--empty': !url, 'imgslot--drag': dragOver }"
    :style="rootStyle"
    :tabindex="editable ? 0 : undefined"
    @click="onClick"
    @focus="focused = true"
    @blur="focused = false"
    @mouseenter="hovered = true"
    @mouseleave="hovered = false"
    @dragover="onDragOver"
    @dragleave="dragOver = false"
    @drop="onDrop"
  >
    <img v-if="url" :src="url" :alt="placeholder" class="imgslot-img" />
    <div v-else class="imgslot-ph">
      <q-icon :name="editable ? 'add_photo_alternate' : 'image'" size="26px" />
      <span>{{ placeholder }}</span>
      <span v-if="editable" class="imgslot-hint">Clic, trascina o incolla (Ctrl-V)</span>
    </div>

    <!-- Overlay caricamento -->
    <div v-if="uploading" class="imgslot-loading">
      <q-spinner size="28px" />
    </div>

    <!-- Azioni sola-lettura: espandi (lightbox) -->
    <button
      v-if="url && expandable && !editable"
      type="button"
      class="imgslot-btn imgslot-expand"
      title="Ingrandisci"
      @click.stop="$emit('expand', url)"
    >
      <q-icon name="open_in_full" size="16px" />
    </button>

    <!-- Azioni admin: cambia + rimuovi -->
    <template v-if="editable">
      <button
        v-if="url"
        type="button"
        class="imgslot-btn imgslot-remove"
        title="Rimuovi"
        @click.stop="$emit('remove')"
      >
        <q-icon name="close" size="16px" />
      </button>
    </template>

    <input
      ref="fileInput"
      type="file"
      accept="image/*"
      :multiple="multiple"
      class="imgslot-file"
      @change="onFileChange"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue';

const props = withDefaults(
  defineProps<{
    url?: string | null;
    placeholder?: string;
    editable?: boolean;
    expandable?: boolean;
    uploading?: boolean;
    radius?: number;
    multiple?: boolean;
  }>(),
  {
    url: null,
    placeholder: 'Foto',
    editable: false,
    expandable: false,
    uploading: false,
    radius: 14,
    multiple: false,
  },
);

const emit = defineEmits<{
  (e: 'upload', file: File): void;
  (e: 'upload-many', files: File[]): void;
  (e: 'remove'): void;
  (e: 'expand', url: string): void;
}>();

const fileInput = ref<HTMLInputElement | null>(null);
const dragOver = ref(false);
const hovered = ref(false);
const focused = ref(false);

const rootStyle = computed(() => ({ borderRadius: `${props.radius}px` }));

// Smista i file selezionati (input/drop/paste) verso l'evento giusto:
// `upload-many` in modalità multipla, `upload` singolo altrimenti.
function handleFiles(files: File[]) {
  const imgs = files.filter((f) => f.type.startsWith('image/'));
  if (!imgs.length) return;
  if (props.multiple) emit('upload-many', imgs);
  else if (imgs[0]) emit('upload', imgs[0]);
}

function onClick() {
  if (props.editable && !props.uploading) fileInput.value?.click();
}

function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement;
  handleFiles(Array.from(target.files ?? []));
  target.value = '';
}

function onDragOver(e: DragEvent) {
  if (!props.editable) return;
  e.preventDefault();
  dragOver.value = true;
}

function onDrop(e: DragEvent) {
  if (!props.editable) return;
  e.preventDefault();
  dragOver.value = false;
  handleFiles(Array.from(e.dataTransfer?.files ?? []));
}

// Paste a livello di documento: agisce solo se questo slot è sotto il mouse
// o ha il focus. Più robusto del solo @paste sul div (comportamento
// browser-dipendente sugli elementi non editabili).
function onDocPaste(e: ClipboardEvent) {
  if (!props.editable || props.uploading) return;
  if (!hovered.value && !focused.value) return;
  const items = e.clipboardData?.items;
  if (!items) return;
  const files: File[] = [];
  for (const item of items) {
    if (item.kind === 'file' && item.type.startsWith('image/')) {
      const file = item.getAsFile();
      if (file) files.push(file);
    }
  }
  if (files.length) {
    e.preventDefault();
    handleFiles(files);
  }
}

function attachPaste() {
  document.addEventListener('paste', onDocPaste);
}
function detachPaste() {
  document.removeEventListener('paste', onDocPaste);
}

onMounted(() => {
  if (props.editable) attachPaste();
});
onBeforeUnmount(detachPaste);
watch(
  () => props.editable,
  (on) => {
    detachPaste();
    if (on) attachPaste();
  },
);
</script>

<style scoped>
.imgslot {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: var(--vp-paper-2);
  border: 1px solid var(--vp-paper-3);
}
.imgslot-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.imgslot-ph {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px;
  text-align: center;
  color: var(--vp-ink-3);
  font-size: 12.5px;
}
.imgslot-hint {
  font-size: 11px;
  color: var(--vp-ink-4);
}
.imgslot--editable {
  cursor: pointer;
  outline: none;
}
.imgslot--editable.imgslot--empty {
  border-style: dashed;
}
.imgslot--editable:focus {
  border-color: var(--vp-terra);
  box-shadow: 0 0 0 3px var(--vp-terra-soft);
}
.imgslot--drag {
  border-color: var(--vp-terra);
  background: var(--vp-terra-soft);
}
.imgslot-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in oklab, var(--vp-paper) 60%, transparent);
  color: var(--vp-terra);
}
.imgslot-btn {
  position: absolute;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: rgba(20, 15, 10, 0.55);
  backdrop-filter: blur(3px);
  z-index: 5;
}
.imgslot-btn:hover {
  background: rgba(20, 15, 10, 0.75);
}
.imgslot-expand {
  right: 8px;
  bottom: 8px;
}
.imgslot-remove {
  right: 8px;
  top: 8px;
  background: var(--vp-clay);
}
.imgslot-remove:hover {
  background: var(--vp-clay);
  filter: brightness(0.9);
}
.imgslot-file {
  display: none;
}
</style>
