<template>
  <div
    class="fotina"
    :class="{ 'fotina--piena': !!foto, 'fotina--attiva': mirata }"
    :tabindex="0"
    :title="titolo"
    :aria-label="titolo"
    @click="scegliFile"
    @keydown.enter.prevent="scegliFile"
    @focus="focus = true"
    @blur="focus = false"
    @mouseenter="hover = true"
    @mouseleave="hover = false"
    @dragover.prevent="hover = true"
    @dragleave.prevent="hover = false"
    @drop.prevent="onDrop"
  >
    <img v-if="foto" :src="foto" alt="" class="fotina__img" />
    <q-icon v-else :name="lavoro ? 'hourglass_empty' : 'person_add'" size="22px" />

    <button
      v-if="foto"
      type="button"
      class="fotina__togli"
      aria-label="Togli la foto"
      @click.stop="rimuovi"
    >
      <q-icon name="close" size="13px" />
    </button>

    <q-tooltip v-if="!foto" :delay="400">
      Incolla qui la foto del profilo (Ctrl-V), o clicca per sceglierla
    </q-tooltip>

    <input
      ref="input"
      type="file"
      accept="image/*"
      class="fotina__file"
      @change="onFile"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { Notify } from 'quasar';
import { imageToSquareDataUrl } from 'src/utils/image';

const props = defineProps<{ foto: string; nome?: string }>();
const emit = defineEmits<{ (e: 'cambia', foto: string): void }>();

const input = ref<HTMLInputElement | null>(null);
const hover = ref(false);
const focus = ref(false);
const lavoro = ref(false);

/** Il bersaglio dell'incolla: quello sotto il mouse, o quello che ha il
 *  focus. In una lista di card servono entrambi — col mouse si punta senza
 *  cliccare, da tastiera si arriva col tab. */
const mirata = computed(() => hover.value || focus.value);

const titolo = computed(() =>
  props.foto
    ? `Foto di ${props.nome || 'questa persona'} — clicca per cambiarla`
    : 'Incolla o scegli la foto del profilo',
);

function scegliFile() {
  if (!lavoro.value) input.value?.click();
}

function rimuovi() {
  if (props.foto) emit('cambia', '');
}

async function prendi(file: File | null | undefined) {
  if (!file || !file.type.startsWith('image/')) return;
  lavoro.value = true;
  try {
    const dataUrl = await imageToSquareDataUrl(file);
    if (!dataUrl) {
      Notify.create({ type: 'warning', message: 'Questa immagine non si riesce a leggere.' });
      return;
    }
    emit('cambia', dataUrl);
  } finally {
    lavoro.value = false;
  }
}

function onFile(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0];
  void prendi(file);
  if (input.value) input.value.value = '';
}

function onDrop(e: DragEvent) {
  hover.value = false;
  void prendi(e.dataTransfer?.files?.[0]);
}

/** L'incolla si ascolta sul documento e non sull'elemento: un div non
 *  editabile non riceve `paste` in tutti i browser. La guardia `mirata` dice
 *  quale delle fotine in pagina se lo prende, e `defaultPrevented` impedisce
 *  che due la prendano insieme (mouse su una, focus su un'altra). */
function onPaste(e: ClipboardEvent) {
  if (e.defaultPrevented || !mirata.value || lavoro.value) return;
  // Chi sta scrivendo ha la precedenza: il dialogo della nota può stare
  // aperto sopra una card, e l'incolla lì dentro è suo. Si guarda chi ha il
  // fuoco, non il bersaglio dell'evento: quello, se non scrive nessuno, è il
  // documento — che non risponde a `closest`.
  const attivo = document.activeElement;
  if (attivo instanceof HTMLElement && attivo.closest('input, textarea, [contenteditable="true"]')) {
    return;
  }
  for (const item of e.clipboardData?.items ?? []) {
    if (item.kind === 'file' && item.type.startsWith('image/')) {
      e.preventDefault();
      void prendi(item.getAsFile());
      return;
    }
  }
}

onMounted(() => document.addEventListener('paste', onPaste));
onBeforeUnmount(() => document.removeEventListener('paste', onPaste));
</script>

<style scoped>
.fotina {
  position: relative;
  flex-shrink: 0;
  /* 60px: sotto questa misura, su uno schermo 4k la faccia non si riconosce
     più — ed è tutto quello per cui la foto sta lì. */
  width: 60px;
  height: 60px;
  border-radius: var(--vp-r-md);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--vp-paper-2);
  border: 1px dashed var(--vp-ink-4);
  color: var(--vp-ink-3);
  cursor: pointer;
  overflow: visible;
}
.fotina--piena {
  border-style: solid;
  border-color: var(--vp-paper-3);
  background: var(--vp-paper-3);
}
.fotina--attiva {
  border-color: var(--vp-terra);
  color: var(--vp-terra);
}
.fotina:focus-visible {
  outline: 2px solid var(--vp-terra);
  outline-offset: 2px;
}
.fotina__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: calc(var(--vp-r-md) - 1px);
  display: block;
}
.fotina__togli {
  position: absolute;
  top: -7px;
  right: -7px;
  width: 20px;
  height: 20px;
  display: none;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid var(--vp-paper-3);
  border-radius: 50%;
  background: var(--vp-cream);
  color: var(--vp-ink-2);
  cursor: pointer;
}
.fotina:hover .fotina__togli,
.fotina:focus-within .fotina__togli {
  display: inline-flex;
}
.fotina__file {
  display: none;
}
</style>
