<template>
  <div class="vp-docs">
    <!-- Form di caricamento -->
    <q-card v-if="!soloLettura" class="vp-docs__card">
      <q-card-section>
        <div class="vp-docs__card-titolo">Carica un documento</div>
        <q-form ref="uploadForm" @submit.prevent="invia" class="q-gutter-md q-mt-sm">
          <q-select
            v-model="tipo"
            :options="tipi"
            label="Tipo di documento"
            outlined
            dense
            emit-value
            map-options
            :rules="[(v) => !!v || 'Seleziona il tipo']"
          />
          <q-file
            v-model="file"
            label="File (PDF o immagine, max 10 MB)"
            hint="Puoi selezionare più file (es. fronte e retro)"
            outlined
            dense
            multiple
            append
            accept=".pdf,.jpg,.jpeg,.png"
            :rules="[(v) => (Array.isArray(v) && v.length > 0) || 'Seleziona almeno un file']"
          >
            <template #prepend>
              <q-icon name="attach_file" />
            </template>
            <template #append>
              <q-icon
                v-if="file && file.length"
                name="close"
                class="cursor-pointer"
                @click.stop="file = []"
              />
            </template>
          </q-file>
          <q-input
            v-model="descrizione"
            label="Descrizione (facoltativa: applicata a tutti i file)"
            outlined
            dense
          />
          <q-input
            v-model="dataScadenza"
            type="date"
            label="Data di scadenza (facoltativa)"
            outlined
            dense
            stack-label
          />
          <q-toggle
            v-if="conVisibilita"
            v-model="visibileInquilini"
            label="Visibile agli inquilini"
            dense
          />
          <q-banner v-if="store.errore" class="text-white bg-red-7" rounded dense>
            {{ store.errore }}
          </q-banner>
          <q-btn
            type="submit"
            :label="file && file.length > 1 ? `Carica ${file.length} file` : 'Carica documento'"
            color="primary"
            icon="upload"
            unelevated
            no-caps
            :loading="store.uploading"
          />
        </q-form>
      </q-card-section>
    </q-card>

    <!-- Elenco -->
    <div v-if="!soloLettura" class="vp-docs__sezione">Documenti caricati</div>

    <q-inner-loading :showing="store.loading" />

    <q-card v-if="!store.loading && !store.documenti.length" class="vp-docs__vuoto">
      <q-card-section class="text-center text-grey-7">
        {{ testoVuoto ?? 'Nessun documento caricato.' }}
      </q-card-section>
    </q-card>

    <q-card v-else-if="store.documenti.length" class="vp-docs__card">
      <q-list separator>
        <q-item v-for="doc in store.documenti" :key="doc.id">
          <q-item-section avatar>
            <q-icon :name="iconaTipo(doc.tipo)" color="primary" size="28px" />
          </q-item-section>
          <q-item-section>
            <q-item-label>{{ doc.tipo_display }}</q-item-label>
            <q-item-label caption>
              <span v-if="doc.descrizione">{{ doc.descrizione }} · </span>
              caricato il {{ formattaData(doc.created_at) }}
            </q-item-label>
            <q-item-label v-if="doc.data_scadenza" caption>
              <q-badge
                :color="doc.scaduto ? 'negative' : 'grey-6'"
                :label="
                  (doc.scaduto ? 'Scaduto il ' : 'Scade il ') +
                  formattaData(doc.data_scadenza)
                "
              />
            </q-item-label>
          </q-item-section>
          <q-item-section side>
            <div class="row items-center no-wrap">
              <q-toggle
                v-if="conVisibilita"
                :model-value="!!doc.visibile_inquilini"
                dense
                size="sm"
                checked-icon="visibility"
                unchecked-icon="visibility_off"
                aria-label="Visibile agli inquilini"
                @update:model-value="(v: boolean) => cambiaVisibilita(doc, v)"
              >
                <q-tooltip>
                  {{ doc.visibile_inquilini ? 'Visibile agli inquilini' : 'Non visibile agli inquilini' }}
                </q-tooltip>
              </q-toggle>
              <q-btn
                flat
                round
                dense
                icon="open_in_new"
                color="primary"
                :href="doc.file"
                target="_blank"
                aria-label="Apri documento"
              />
              <q-btn
                v-if="!soloLettura"
                flat
                round
                dense
                icon="delete"
                color="negative"
                aria-label="Elimina documento"
                @click="conferma(doc)"
              />
            </div>
          </q-item-section>
        </q-item>
      </q-list>
    </q-card>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue';
import { useQuasar, type QForm } from 'quasar';
import type { DocumentiStore, DocumentoFE, TipoDocumentoOption } from 'stores/documenti';
import { useFormatoData } from 'src/composables/useFormatoData';

const props = defineProps<{
  /** Store documenti (inquilino o proprietà, stessa forma). */
  store: DocumentiStore;
  /** Opzioni del select "tipo di documento". */
  tipi: TipoDocumentoOption[];
  /** Target esplicito (id inquilino/immobile) — uso lato proprietario;
   *  l'inquilino non lo passa e opera sui propri. */
  targetId?: number;
  /** Solo consultazione: niente upload né eliminazione (es. documenti
   *  della casa visti dall'inquilino). */
  soloLettura?: boolean;
  /** Mostra il controllo "visibile agli inquilini" (documenti proprietà,
   *  lato gestione). */
  conVisibilita?: boolean;
  /** Messaggio quando l'elenco è vuoto. */
  testoVuoto?: string;
}>();

const $q = useQuasar();
const { formattaData } = useFormatoData();

const uploadForm = ref<QForm | null>(null);
const tipo = ref<string | null>(null);
const file = ref<File[]>([]);
const descrizione = ref('');
const dataScadenza = ref('');
const visibileInquilini = ref(false);

function iconaTipo(t: string): string {
  switch (t) {
    case 'carta_identita':
      return 'badge';
    case 'codice_fiscale':
      return 'credit_card';
    case 'passaporto':
      return 'menu_book';
    case 'permesso_soggiorno':
      return 'verified_user';
    case 'contratto_lavoro':
      return 'work';
    case 'ricevuta_registrazione':
      return 'receipt_long';
    case 'atto_subentro':
      return 'history_edu';
    case 'contratto':
      return 'gavel';
    case 'side_letter':
      return 'drive_file_rename_outline';
    case 'registrazione_contratto':
      return 'approval';
    case 'regolamento_condominiale':
      return 'apartment';
    default:
      return 'description';
  }
}

onMounted(() => {
  void props.store.fetch(props.targetId);
});
watch(
  () => props.targetId,
  (id) => {
    void props.store.fetch(id);
  },
);

async function invia() {
  if (!tipo.value || !file.value.length) return;
  const { ok, falliti } = await props.store.caricaMulti({
    files: file.value,
    tipo: tipo.value,
    descrizione: descrizione.value,
    dataScadenza: dataScadenza.value || null,
    ...(props.conVisibilita ? { visibileInquilini: visibileInquilini.value } : {}),
    ...(props.targetId ? { targetId: props.targetId } : {}),
  });
  if (ok > 0) {
    tipo.value = null;
    file.value = [];
    descrizione.value = '';
    dataScadenza.value = '';
    visibileInquilini.value = false;
    // Svuotare i campi rifà scattare le regole "obbligatorio": azzeriamo la
    // validazione così non restano errori dopo un caricamento riuscito.
    void nextTick(() => uploadForm.value?.resetValidation());
    $q.notify({
      type: 'positive',
      message: ok === 1 ? 'Documento caricato.' : `${ok} documenti caricati.`,
    });
  }
  if (falliti > 0) {
    $q.notify({
      type: 'negative',
      message:
        falliti === 1
          ? 'Un file non è stato caricato.'
          : `${falliti} file non sono stati caricati.`,
    });
  }
}

function conferma(doc: DocumentoFE) {
  $q.dialog({
    title: 'Elimina documento',
    message: `Eliminare "${doc.tipo_display}"? L'operazione non è reversibile.`,
    cancel: { label: 'Annulla', flat: true, noCaps: true },
    ok: { label: 'Elimina', color: 'negative', unelevated: true, noCaps: true },
  }).onOk(() => {
    void elimina(doc.id);
  });
}

async function cambiaVisibilita(doc: DocumentoFE, visibile: boolean) {
  const ok = await props.store.impostaVisibilita(doc.id, visibile);
  if (!ok) {
    $q.notify({
      type: 'negative',
      message: props.store.errore ?? 'Errore aggiornamento visibilità.',
    });
    return;
  }
  $q.notify({
    type: 'positive',
    message: visibile
      ? 'Documento ora visibile agli inquilini.'
      : 'Documento non più visibile agli inquilini.',
  });
}

async function elimina(id: number) {
  const ok = await props.store.elimina(id);
  $q.notify(
    ok
      ? { type: 'positive', message: 'Documento eliminato.' }
      : { type: 'negative', message: props.store.errore ?? 'Errore eliminazione.' },
  );
}
</script>

<style scoped>
.vp-docs__card {
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  overflow: hidden;
}
.vp-docs__card-titolo {
  font-weight: 600;
  color: var(--vp-ink);
}
.vp-docs__sezione {
  font-weight: 600;
  color: var(--vp-ink);
  margin: var(--vp-gap-5) 0 var(--vp-gap-2);
}
.vp-docs__vuoto {
  background: var(--vp-cream);
  border: 1px dashed var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
}
</style>
