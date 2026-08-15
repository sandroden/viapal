<template>
  <div>
    <CardSezione titolo="Modelli dei documenti generati">
      <template #descrizione>
        Il testo dei documenti generati è un dato di questa casa, non del
        programma: si carica qui, come file HTML. Parti dall'esempio, adattalo
        e ricaricalo; i segnaposto <code v-text="'{{chiave}}'" /> vengono
        sostituiti alla generazione.
      </template>

      <div class="imm-elenco">
        <RigaElenco
          v-for="(doc, i) in CODICI_DOCUMENTO"
          :key="doc.codice"
          :ultima="i === CODICI_DOCUMENTO.length - 1"
          :data-testid="`modello-${doc.codice}`"
        >
          <template #tile><TileIcona icona="doc" colore="var(--vp-wood)" /></template>
          <template #titolo>{{ doc.label }}</template>
          <template #badge>
            <EtichettaStato :tono="store.perCodice(doc.codice) ? 'ok' : 'off'">
              {{ store.perCodice(doc.codice) ? 'Caricato' : 'Non caricato' }}
            </EtichettaStato>
          </template>
          <template #meta>
            <template v-if="store.perCodice(doc.codice)">
              aggiornato il {{ formattaData(store.perCodice(doc.codice)!.updated_at) }}
            </template>
            <template v-else>Finché manca, il documento non si può generare.</template>
          </template>
          <template #azioni>
            <q-btn
              v-if="puoModificare"
              flat
              dense
              no-caps
              size="sm"
              icon="upload_file"
              :label="store.perCodice(doc.codice) ? 'Sostituisci' : 'Carica HTML'"
              :data-testid="`carica-${doc.codice}`"
              @click="scegliFile(doc.codice)"
            />
            <q-btn
              flat
              dense
              no-caps
              size="sm"
              icon="download"
              label="Esempio"
              @click="scaricaEsempio(doc.codice)"
            />
            <q-btn
              v-if="store.perCodice(doc.codice)"
              flat
              dense
              no-caps
              size="sm"
              icon="file_download"
              label="Il tuo"
              @click="scaricaProprio(doc.codice)"
            />
            <q-btn
              flat
              dense
              no-caps
              size="sm"
              icon="list"
              label="Segnaposto"
              @click="apriSegnaposto(doc.codice)"
            />
            <BtnIcona
              v-if="puoModificare && store.perCodice(doc.codice)"
              icona="trash"
              pericolo
              :etichetta="`Elimina il modello ${doc.label}`"
              tooltip="Elimina"
              @click="confermaElimina(doc.codice, doc.label)"
            />
          </template>
        </RigaElenco>
      </div>
    </CardSezione>

    <input
      ref="inputFile"
      type="file"
      accept=".html,text/html"
      class="hidden"
      @change="caricaFile"
    />

    <!-- Segnaposto disponibili: derivati dal generatore, non riscritti a mano -->
    <q-dialog v-model="dialogSegnaposto">
      <q-card style="width: 460px; max-width: min(640px, 92vw)">
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
import CardSezione from 'components/impostazioni/ui/CardSezione.vue';
import RigaElenco from 'components/impostazioni/ui/RigaElenco.vue';
import TileIcona from 'components/impostazioni/ui/TileIcona.vue';
import EtichettaStato from 'components/impostazioni/ui/EtichettaStato.vue';
import BtnIcona from 'components/impostazioni/ui/BtnIcona.vue';

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

<style scoped>
.imm-elenco {
  margin-top: 4px;
}
</style>
