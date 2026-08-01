<template>
  <q-dialog
    v-model="aperto"
    :position="$q.screen.lt.sm ? 'bottom' : 'standard'"
    :maximized="false"
    @hide="reset"
  >
    <div class="vp-dadd">
      <div class="vp-dadd__maniglia" />
      <h2 class="vp-display vp-dadd__titolo">{{ titolo }}</h2>
      <p class="vp-dadd__intro">
        Scatta una foto o scegli un file: PDF o immagine, fino a 10 MB.
      </p>

      <div class="vp-eyebrow vp-dadd__label">Che documento è</div>
      <div class="vp-dadd__tipi">
        <button
          v-for="t in tipi"
          :key="t.value"
          class="vp-dadd__tipo"
          :class="{ 'vp-dadd__tipo--on': t.value === tipo }"
          @click="tipo = t.value"
        >
          {{ t.label }}
        </button>
      </div>

      <q-input
        v-if="tipo === 'altro'"
        v-model="descrizioneLibera"
        label="Di che documento si tratta"
        outlined
        dense
        class="vp-dadd__descr"
      />

      <div class="vp-eyebrow vp-dadd__label">
        {{ fronteRetro ? 'Fronte e retro' : 'Immagine o PDF' }}
      </div>
      <div class="vp-dadd__slot-riga" :class="{ 'vp-dadd__slot-riga--due': fronteRetro }">
        <label v-for="slot in slots" :key="slot.chiave" class="vp-dadd__slot">
          <input
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,image/*,application/pdf"
            class="vp-dadd__input"
            @change="scegli(slot, $event)"
          />
          <template v-if="slot.anteprima">
            <img :src="slot.anteprima" alt="" class="vp-dadd__anteprima" />
          </template>
          <template v-else-if="slot.file">
            <q-icon name="picture_as_pdf" size="24px" />
            <span class="vp-dadd__slot-nome">{{ slot.file.name }}</span>
          </template>
          <template v-else>
            <q-icon name="photo_camera" size="24px" />
            <span class="vp-dadd__slot-nome">{{ slot.etichetta }}</span>
            <span class="vp-dadd__slot-hint">foto o file</span>
          </template>
        </label>
      </div>

      <div class="vp-dadd__scadenza">
        <q-icon name="event" size="18px" class="vp-dadd__scadenza-ic" />
        <div class="vp-dadd__scadenza-txt">
          <div>Scadenza</div>
          <div class="vp-dadd__scadenza-nota">
            facoltativa: te la segnaliamo nel fascicolo {{ preavviso }} giorni prima
          </div>
        </div>
        <input v-model="dataScadenza" type="date" class="vp-dadd__data" aria-label="Data di scadenza" />
      </div>

      <q-banner v-if="store.errore" class="text-white bg-red-7 vp-dadd__errore" rounded dense>
        {{ store.errore }}
      </q-banner>

      <button
        class="vp-btn vp-btn--primary vp-dadd__salva"
        :disabled="!puoSalvare || store.uploading"
        @click="salva"
      >
        <q-spinner v-if="store.uploading" size="18px" />
        {{ store.uploading ? 'Caricamento…' : etichettaSalva }}
      </button>
      <p class="vp-dadd__privacy">
        Solo tu e i proprietari della casa vedete questo documento.
      </p>
    </div>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import { useQuasar } from 'quasar';
import type { DocumentiStore, TipoDocumentoOption } from 'stores/documenti';
import { TIPI_FRONTE_RETRO } from 'src/utils/statoDocumento';

interface SlotFile {
  chiave: string;
  etichetta: string;
  /** Descrizione salvata sul documento ("fronte"/"retro"), vuota se pagina unica. */
  descrizione: string;
  file: File | null;
  anteprima: string | null;
}

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    store: DocumentiStore;
    tipi: TipoDocumentoOption[];
    /** Tipo preselezionato all'apertura (es. la voce che l'utente ha toccato). */
    tipoIniziale?: string | null;
    /** Inquilino/immobile su cui caricare (uso lato proprietario). */
    targetId?: number;
    titolo?: string;
    /** Giorni di preavviso mostrati nella nota sulla scadenza. */
    preavviso?: number;
  }>(),
  { tipoIniziale: null, titolo: 'Aggiungi un documento', preavviso: 60 },
);

const emit = defineEmits<{
  'update:modelValue': [valore: boolean];
  caricato: [];
}>();

const $q = useQuasar();

const aperto = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
});

const tipo = ref(props.tipoIniziale ?? props.tipi[0]?.value ?? 'altro');
const descrizioneLibera = ref('');
const dataScadenza = ref('');
const slots = ref<SlotFile[]>([]);

const fronteRetro = computed(() => TIPI_FRONTE_RETRO.includes(tipo.value));

function creaSlots() {
  liberaAnteprime();
  slots.value = fronteRetro.value
    ? [
        reactive({ chiave: 'fronte', etichetta: 'fronte', descrizione: 'fronte', file: null, anteprima: null }),
        reactive({ chiave: 'retro', etichetta: 'retro', descrizione: 'retro', file: null, anteprima: null }),
      ]
    : [
        reactive({
          chiave: 'unico',
          etichetta: 'documento',
          descrizione: '',
          file: null,
          anteprima: null,
        }),
      ];
}

function liberaAnteprime() {
  for (const s of slots.value) if (s.anteprima) URL.revokeObjectURL(s.anteprima);
}

watch(
  () => props.modelValue,
  (visibile) => {
    if (!visibile) return;
    tipo.value = props.tipoIniziale ?? props.tipi[0]?.value ?? 'altro';
    descrizioneLibera.value = '';
    dataScadenza.value = '';
    creaSlots();
  },
  { immediate: true },
);

watch(tipo, creaSlots);

function scegli(slot: SlotFile, evento: Event) {
  const input = evento.target as HTMLInputElement;
  const file = input.files?.[0] ?? null;
  if (slot.anteprima) URL.revokeObjectURL(slot.anteprima);
  slot.file = file;
  slot.anteprima = file && file.type.startsWith('image/') ? URL.createObjectURL(file) : null;
}

const scelti = computed(() => slots.value.filter((s) => s.file));
const puoSalvare = computed(() => scelti.value.length > 0);
const etichettaSalva = computed(() =>
  scelti.value.length > 1 ? `Salva ${scelti.value.length} pagine` : 'Salva nel fascicolo',
);

function reset() {
  liberaAnteprime();
  slots.value = [];
  // L'errore del caricamento precedente non deve riapparire alla riapertura.
  props.store.$patch({ errore: null });
}

async function salva() {
  if (!puoSalvare.value) return;
  const pagine = scelti.value.map((s) => ({
    file: s.file as File,
    descrizione: tipo.value === 'altro' ? descrizioneLibera.value : s.descrizione,
  }));
  const { ok, falliti } = await props.store.caricaPagine({
    pagine,
    tipo: tipo.value,
    dataScadenza: dataScadenza.value || null,
    ...(props.targetId ? { targetId: props.targetId } : {}),
  });
  if (ok > 0) {
    $q.notify({
      type: 'positive',
      message: ok === 1 ? 'Documento salvato nel fascicolo.' : `${ok} pagine salvate.`,
    });
    emit('caricato');
  }
  if (falliti > 0) {
    $q.notify({
      type: 'negative',
      message:
        falliti === 1 ? 'Un file non è stato caricato.' : `${falliti} file non caricati.`,
    });
    return;
  }
  aperto.value = false;
}
</script>

<style scoped>
.vp-dadd {
  width: 100%;
  max-width: 560px;
  padding: var(--vp-gap-2) var(--vp-gap-4) var(--vp-gap-5);
  background: var(--vp-paper);
  border-radius: var(--vp-r-xl) var(--vp-r-xl) 0 0;
}
@media (min-width: 600px) {
  .vp-dadd {
    border-radius: var(--vp-r-lg);
    padding: var(--vp-gap-4) var(--vp-gap-5) var(--vp-gap-5);
  }
  .vp-dadd__maniglia {
    display: none;
  }
}
.vp-dadd__maniglia {
  width: 40px;
  height: 4px;
  border-radius: 2px;
  background: var(--vp-paper-3);
  margin: 0 auto var(--vp-gap-4);
}
.vp-dadd__titolo {
  font-size: var(--vp-text-xl);
  margin: 0 0 var(--vp-gap-1);
}
.vp-dadd__intro {
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-3);
  margin: 0 0 var(--vp-gap-4);
}
.vp-dadd__label {
  margin-bottom: var(--vp-gap-2);
}
.vp-dadd__tipi {
  display: flex;
  flex-wrap: wrap;
  gap: var(--vp-gap-2);
  margin-bottom: var(--vp-gap-4);
}
.vp-dadd__tipo {
  height: 34px;
  padding: 0 12px;
  border-radius: var(--vp-r-pill);
  border: 1px solid var(--vp-paper-3);
  background: var(--vp-cream);
  color: var(--vp-ink-2);
  font-family: var(--vp-font-ui);
  font-size: var(--vp-text-sm);
  cursor: pointer;
}
.vp-dadd__tipo--on {
  border-color: var(--vp-terra);
  background: var(--vp-terra-soft);
  color: var(--vp-terra-deep);
}
.vp-dadd__descr {
  margin-bottom: var(--vp-gap-4);
}
.vp-dadd__slot-riga {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--vp-gap-3);
  margin-bottom: var(--vp-gap-4);
  /* Un riquadro solo non si allarga a tutta la finestra: resta una "carta". */
  justify-items: center;
}
.vp-dadd__slot-riga > * {
  width: 100%;
  max-width: 300px;
}
.vp-dadd__slot-riga--due {
  grid-template-columns: 1fr 1fr;
}
.vp-dadd__slot {
  position: relative;
  overflow: hidden;
  min-height: 104px;
  padding: var(--vp-gap-3) var(--vp-gap-2);
  border: 1.5px dashed var(--vp-terra);
  border-radius: 14px;
  background: var(--vp-cream);
  color: var(--vp-terra-deep);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  text-align: center;
}
.vp-dadd__input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}
.vp-dadd__anteprima {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: var(--vp-paper-2);
}
.vp-dadd__slot-nome {
  font-size: var(--vp-text-sm);
  font-weight: 500;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.vp-dadd__slot-hint {
  font-size: 11.5px;
  color: var(--vp-ink-3);
}
.vp-dadd__scadenza {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-3);
  padding: var(--vp-gap-3) var(--vp-gap-4);
  margin-bottom: var(--vp-gap-4);
  background: var(--vp-paper-2);
  border-radius: var(--vp-r-md);
}
.vp-dadd__scadenza-ic {
  color: var(--vp-ink-3);
}
.vp-dadd__scadenza-txt {
  flex: 1;
  font-size: var(--vp-text-sm);
}
.vp-dadd__scadenza-nota {
  font-size: var(--vp-text-xs);
  color: var(--vp-ink-3);
}
.vp-dadd__data {
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-sm);
  background: var(--vp-cream);
  color: var(--vp-ink-2);
  font-family: var(--vp-font-ui);
  font-size: var(--vp-text-sm);
  padding: 6px 8px;
}
.vp-dadd__errore {
  margin-bottom: var(--vp-gap-3);
}
.vp-dadd__salva {
  width: 100%;
  height: 46px;
  font-size: var(--vp-text-md);
}
.vp-dadd__salva:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.vp-dadd__privacy {
  text-align: center;
  font-size: var(--vp-text-xs);
  color: var(--vp-ink-3);
  margin: var(--vp-gap-3) 0 0;
}
</style>
