<template>
  <div style="max-width: 720px">
    <div class="vp-hint q-mb-md">
      Il testo dei documenti generati è un dato di questa casa, non del
      programma: si carica qui, come file HTML. Parti dall'esempio, adattalo e
      ricaricalo. I segnaposto <code v-text="'{{chiave}}'" /> vengono
      sostituiti alla generazione.
    </div>

    <q-card
      v-for="doc in CODICI_DOCUMENTO"
      :key="doc.codice"
      flat
      bordered
      class="vp-card q-mb-md"
      :data-testid="`modello-${doc.codice}`"
    >
      <q-card-section>
        <div class="row items-center q-gutter-sm">
          <div class="vp-section-title col">{{ doc.label }}</div>
          <q-chip
            dense
            :color="store.perCodice(doc.codice) ? 'positive' : 'grey-5'"
            text-color="white"
            :label="store.perCodice(doc.codice) ? 'caricato' : 'non caricato'"
          />
        </div>

        <div v-if="store.perCodice(doc.codice)" class="vp-hint q-mt-xs">
          Aggiornato il {{ formattaData(store.perCodice(doc.codice)!.updated_at) }}
        </div>
        <div v-else class="vp-hint q-mt-xs">
          Finché manca, il documento non si può generare.
        </div>

        <div class="row items-center q-gutter-sm q-mt-md">
          <q-btn
            v-if="puoModificare"
            dense
            no-caps
            color="primary"
            icon="upload_file"
            :label="store.perCodice(doc.codice) ? 'Sostituisci' : 'Carica HTML'"
            :data-testid="`carica-${doc.codice}`"
            @click="scegliFile(doc.codice)"
          />
          <q-btn
            dense
            flat
            no-caps
            icon="download"
            label="Scarica l'esempio"
            @click="scaricaEsempio(doc.codice)"
          />
          <q-btn
            v-if="store.perCodice(doc.codice)"
            dense
            flat
            no-caps
            icon="file_download"
            label="Scarica il tuo"
            @click="scaricaProprio(doc.codice)"
          />
          <q-btn
            dense
            flat
            no-caps
            icon="list"
            label="Segnaposto"
            @click="apriSegnaposto(doc.codice)"
          />
          <q-btn
            v-if="puoModificare && store.perCodice(doc.codice)"
            dense
            flat
            round
            icon="delete_outline"
            color="negative"
            :aria-label="`Elimina il modello ${doc.label}`"
            @click="confermaElimina(doc.codice, doc.label)"
          />
        </div>
      </q-card-section>
    </q-card>

    <input
      ref="inputFile"
      type="file"
      accept=".html,text/html"
      class="hidden"
      @change="caricaFile"
    />

    <!-- Segnaposto disponibili: derivati dal generatore, non riscritti a mano -->
    <q-dialog v-model="dialogSegnaposto">
      <q-card style="min-width: 460px; max-width: 640px">
        <q-card-section>
          <div class="vp-section-title">Segnaposto disponibili</div>
          <div class="vp-hint">{{ titoloSegnaposto }}</div>
        </q-card-section>
        <q-card-section style="max-height: 60vh; overflow-y: auto">
          <q-list dense separator>
            <q-item v-for="s in segnaposto" :key="s.chiave">
              <q-item-section>
                <q-item-label>
                  <span class="vp-mono">{{ segnapostoTesto(s.chiave) }}</span>
                </q-item-label>
                <q-item-label caption>{{ s.etichetta }}</q-item-label>
              </q-item-section>
              <q-item-section v-if="s.derivato || !s.obbligatorio" side>
                <q-chip dense outline :label="s.derivato ? 'composto' : 'facoltativo'" />
              </q-item-section>
            </q-item>
          </q-list>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn v-close-popup flat no-caps label="Chiudi" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import {
  CODICI_DOCUMENTO,
  useModelliDocumentoStore,
  type Segnaposto,
} from 'stores/modelliDocumento';
import { useFormatoData } from 'src/composables/useFormatoData';
import { messaggioErrore } from 'src/utils/apiErrors';

defineProps<{ puoModificare?: boolean }>();

const $q = useQuasar();
const { formattaData } = useFormatoData();
const store = useModelliDocumentoStore();

const inputFile = ref<HTMLInputElement | null>(null);
const codiceInCaricamento = ref<string | null>(null);
const dialogSegnaposto = ref(false);
const segnaposto = ref<Segnaposto[]>([]);
const titoloSegnaposto = ref('');

/** Le doppie graffe non si possono scrivere in un'interpolazione Vue:
 *  si compongono qui e si stampano con `v-text`. */
function segnapostoTesto(chiave: string): string {
  return `{${'{'}${chiave}}}`;
}

function scegliFile(codice: string) {
  codiceInCaricamento.value = codice;
  inputFile.value?.click();
}

async function caricaFile(evento: Event) {
  const input = evento.target as HTMLInputElement;
  const file = input.files?.[0];
  const codice = codiceInCaricamento.value;
  input.value = '';
  if (!file || !codice) return;
  const corpo = await file.text();
  const ok = await store.salva(codice, corpo, file.name.replace(/\.html?$/i, ''));
  $q.notify(
    ok
      ? { type: 'positive', message: 'Modello caricato.' }
      : { type: 'negative', message: store.errore ?? 'Errore nel caricamento.' },
  );
}

function scarica(nome: string, contenuto: string) {
  const url = URL.createObjectURL(new Blob([contenuto], { type: 'text/html' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = nome;
  a.click();
  URL.revokeObjectURL(url);
}

async function scaricaEsempio(codice: string) {
  try {
    scarica(`${codice}-esempio.html`, await store.esempio(codice));
  } catch (e: unknown) {
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, "Impossibile scaricare l'esempio."),
    });
  }
}

function scaricaProprio(codice: string) {
  const modello = store.perCodice(codice);
  if (modello) scarica(`${codice}.html`, modello.corpo_html);
}

async function apriSegnaposto(codice: string) {
  try {
    const dati = await store.segnaposto(codice);
    segnaposto.value = dati.segnaposto;
    titoloSegnaposto.value = dati.titolo;
    dialogSegnaposto.value = true;
  } catch (e: unknown) {
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, "Impossibile leggere l'elenco."),
    });
  }
}

function confermaElimina(codice: string, label: string) {
  const modello = store.perCodice(codice);
  if (!modello) return;
  $q.dialog({
    title: 'Elimina modello',
    message: `Eliminare il modello «${label}»? Senza modello il documento non si genera.`,
    cancel: { label: 'Annulla', flat: true, noCaps: true },
    ok: { label: 'Elimina', color: 'negative', unelevated: true, noCaps: true },
  }).onOk(() => {
    void store.elimina(modello.id);
  });
}

onMounted(() => {
  void store.fetch();
});
</script>
