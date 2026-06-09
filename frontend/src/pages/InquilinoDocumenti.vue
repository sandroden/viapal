<template>
  <q-page padding class="vp-i-doc">
    <div class="vp-eyebrow">Profilo</div>
    <h1 class="vp-display vp-i-doc__titolo">I miei documenti</h1>
    <p class="vp-i-doc__intro">
      Carica qui i tuoi documenti (carta d'identità, codice fiscale, passaporto,
      permesso di soggiorno, contratto di lavoro). Per i documenti fronte/retro
      carica due file indicando "fronte" e "retro" nella descrizione.
    </p>

    <!-- Form di caricamento -->
    <q-card class="vp-i-doc__card">
      <q-card-section>
        <div class="vp-i-doc__card-titolo">Carica un documento</div>
        <q-form ref="uploadForm" @submit.prevent="invia" class="q-gutter-md q-mt-sm">
          <q-select
            v-model="tipo"
            :options="tipiOptions"
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
    <div class="vp-i-doc__sezione">Documenti caricati</div>

    <q-inner-loading :showing="store.loading" />

    <q-card v-if="!store.loading && !store.documenti.length" class="vp-i-doc__vuoto">
      <q-card-section class="text-center text-grey-7">
        Nessun documento caricato.
      </q-card-section>
    </q-card>

    <q-card v-else-if="store.documenti.length" class="vp-i-doc__card">
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
              <q-btn
                flat
                round
                dense
                icon="visibility"
                color="primary"
                :href="doc.file"
                target="_blank"
                aria-label="Apri documento"
              />
              <q-btn
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

    <div class="vp-i-doc__back">
      <q-btn flat color="primary" icon="arrow_back" label="Torna al profilo" no-caps to="/i/profilo" />
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue';
import { useQuasar, type QForm } from 'quasar';
import { useDocumentiStore, type DocumentoFE, type TipoDocumento } from 'stores/documenti';
import { useFormatoData } from 'src/composables/useFormatoData';

const store = useDocumentiStore();
const $q = useQuasar();
const { formattaData } = useFormatoData();

const tipiOptions = [
  { label: "Carta d'identità", value: 'carta_identita' },
  { label: 'Codice fiscale / Tessera sanitaria', value: 'codice_fiscale' },
  { label: 'Passaporto', value: 'passaporto' },
  { label: 'Permesso di soggiorno', value: 'permesso_soggiorno' },
  { label: 'Contratto di lavoro', value: 'contratto_lavoro' },
  { label: 'Altro', value: 'altro' },
];

const uploadForm = ref<QForm | null>(null);
const tipo = ref<TipoDocumento | null>(null);
const file = ref<File[]>([]);
const descrizione = ref('');
const dataScadenza = ref('');

function iconaTipo(t: TipoDocumento): string {
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
    default:
      return 'description';
  }
}

onMounted(() => {
  void store.fetch();
});

async function invia() {
  if (!tipo.value || !file.value.length) return;
  const { ok, falliti } = await store.caricaMulti({
    files: file.value,
    tipo: tipo.value,
    descrizione: descrizione.value,
    dataScadenza: dataScadenza.value || null,
  });
  if (ok > 0) {
    tipo.value = null;
    file.value = [];
    descrizione.value = '';
    dataScadenza.value = '';
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

async function elimina(id: number) {
  const ok = await store.elimina(id);
  $q.notify(
    ok
      ? { type: 'positive', message: 'Documento eliminato.' }
      : { type: 'negative', message: store.errore ?? 'Errore eliminazione.' },
  );
}
</script>

<style scoped>
.vp-i-doc {
  max-width: 640px;
  margin: 0 auto;
}
.vp-i-doc__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 var(--vp-gap-2);
}
.vp-i-doc__intro {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm);
  margin-bottom: var(--vp-gap-4);
}
.vp-i-doc__card {
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  overflow: hidden;
}
.vp-i-doc__card-titolo {
  font-weight: 600;
  color: var(--vp-ink);
}
.vp-i-doc__sezione {
  font-weight: 600;
  color: var(--vp-ink);
  margin: var(--vp-gap-5) 0 var(--vp-gap-2);
}
.vp-i-doc__vuoto {
  background: var(--vp-cream);
  border: 1px dashed var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
}
.vp-i-doc__back {
  margin-top: var(--vp-gap-5);
  display: flex;
  justify-content: center;
}
</style>
