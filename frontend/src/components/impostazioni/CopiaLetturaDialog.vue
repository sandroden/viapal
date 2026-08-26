<template>
  <q-dialog v-model="aperto" @hide="svuota">
    <q-card class="cl-dialog">
      <q-card-section class="cl-dialog__head">
        <div class="cl-dialog__titolo">Copia per la lettura</div>
        <BtnIcona icona="x" etichetta="Chiudi" @click="aperto = false" />
      </q-card-section>

      <q-card-section class="cl-dialog__corpo">
        <div class="cl-dialog__intro">
          La versione priva dei dati di chi ha già firmato, da mandare a chi
          deve ancora decidere. Sta fuori dagli elenchi ufficiali e non
          compare nella pagina degli inquilini.
        </div>

        <!-- Aperta dal chip di un documento l'origine è già decisa; dal
             bottone della sezione si sceglie qui. -->
        <div v-if="originale" class="cl-dialog__origine">
          <TileIcona icona="doc" :size="30" />
          <div>
            <div class="cl-dialog__origine-nome">{{ titoloDi(originale) }}</div>
            <div class="cl-dialog__origine-meta">{{ ambitoDi(originale) }}</div>
          </div>
        </div>
        <q-select
          v-else
          v-model="originaleId"
          :options="opzioniOriginali"
          label="Copia di quale documento"
          outlined
          dense
          emit-value
          map-options
          data-testid="copia-originale"
        />

        <div
          class="cl-drop"
          :class="{ 'cl-drop--sopra': sopra }"
          @dragover.prevent="sopra = true"
          @dragleave="sopra = false"
          @drop.prevent="rilascia"
          @click="inputFile?.click()"
        >
          <VpIcon name="upload" :size="20" />
          <div class="cl-drop__titolo">
            {{ file ? file.name : 'Trascina qui il PDF oscurato' }}
          </div>
          <div class="cl-drop__nota">Un solo file, PDF o immagine, max 10 MB.</div>
          <input
            ref="inputFile"
            type="file"
            accept=".pdf,.jpg,.jpeg,.png"
            class="hidden"
            @change="scegli"
          />
        </div>

        <q-input
          v-model="descrizione"
          label="Descrizione"
          outlined
          dense
          :placeholder="descrizioneProposta"
          hint="Vuota: «… — copia oscurata»"
        />

        <!-- L'avvertenza sta dove si carica il file, non in un documento che
             nessuno rilegge. È il punto in cui l'errore si fa. -->
        <q-banner class="cl-avviso" rounded dense>
          <template #avatar><VpIcon name="alert" :size="18" /></template>
          Il rettangolo nero disegnato sopra un testo <strong>non lo
          cancella</strong>: resta sotto e si recupera con un copia-incolla.
          Copri, poi appiattisci il PDF in immagini. Controlla anche i
          metadati (autore, titolo).
        </q-banner>

        <q-banner v-if="errore" class="vp-banner-errore" rounded dense>{{ errore }}</q-banner>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn v-close-popup flat label="Annulla" />
        <q-btn
          color="primary"
          label="Carica la copia"
          :disable="!file || !idScelto"
          :loading="store.uploading"
          data-testid="salva-copia-lettura"
          @click="salva"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useDocumentiProprietaStore, type DocumentoFE } from 'stores/documenti';
import VpIcon from 'components/utenze/VpIcon.vue';
import BtnIcona from './ui/BtnIcona.vue';
import TileIcona from './ui/TileIcona.vue';

const props = defineProps<{
  /** Il documento di cui si carica la copia. Null: si sceglie nel dialog. */
  originale?: DocumentoFE | null;
}>();

const aperto = defineModel<boolean>({ required: true });

const $q = useQuasar();
const store = useDocumentiProprietaStore();

const inputFile = ref<HTMLInputElement | null>(null);
const file = ref<File | null>(null);
const sopra = ref(false);
const descrizione = ref('');
const originaleId = ref<number | null>(null);
const errore = ref('');

/** Copie di copie non esistono: un livello solo. Fuori anche i documenti
 *  che sono già l'originale di una copia — quella c'è già. */
const opzioniOriginali = computed(() =>
  store.documenti
    .filter((d) => !d.copia_di)
    .map((d) => ({ label: `${titoloDi(d)} · ${ambitoDi(d)}`, value: d.id })),
);

const idScelto = computed(() => props.originale?.id ?? originaleId.value);

const documentoScelto = computed<DocumentoFE | null>(
  () => props.originale ?? store.documenti.find((d) => d.id === originaleId.value) ?? null,
);

const descrizioneProposta = computed(() =>
  documentoScelto.value ? `${titoloDi(documentoScelto.value)} — copia oscurata` : '',
);

function titoloDi(d: DocumentoFE): string {
  return d.titolo || d.descrizione || d.tipo_display;
}

function ambitoDi(d: DocumentoFE): string {
  return d.contract_nome || 'Carta della casa';
}

function scegli(e: Event) {
  const scelti = (e.target as HTMLInputElement).files;
  file.value = scelti?.[0] ?? null;
}

function rilascia(e: DragEvent) {
  sopra.value = false;
  file.value = e.dataTransfer?.files?.[0] ?? null;
}

function svuota() {
  file.value = null;
  descrizione.value = '';
  originaleId.value = null;
  errore.value = '';
}

async function salva() {
  const id = idScelto.value;
  if (!file.value || !id) return;
  errore.value = '';
  const ok = await store.caricaCopiaLettura({
    originaleId: id,
    file: file.value,
    ...(descrizione.value ? { descrizione: descrizione.value } : {}),
  });
  if (!ok) {
    errore.value = store.errore ?? 'Caricamento non riuscito.';
    return;
  }
  $q.notify({ type: 'positive', message: 'Copia per la lettura caricata.' });
  aperto.value = false;
}
</script>

<style scoped>
.cl-dialog {
  width: 520px;
  max-width: 94vw;
}
.cl-dialog__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 4px;
}
.cl-dialog__titolo {
  font-family: var(--vp-serif, Georgia, serif);
  font-size: 18px;
}
.cl-dialog__corpo {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.cl-dialog__intro {
  font-size: 13px;
  color: var(--vp-ink-2);
  line-height: 1.45;
}
.cl-dialog__origine {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 11px;
  background: var(--vp-paper-2);
  border-radius: 8px;
}
.cl-dialog__origine-nome {
  font-size: 13.5px;
}
.cl-dialog__origine-meta {
  font-size: 12px;
  color: var(--vp-ink-3);
}
.cl-drop {
  border: 1px dashed var(--vp-paper-3);
  border-radius: 10px;
  padding: 20px 14px;
  text-align: center;
  cursor: pointer;
  color: var(--vp-ink-2);
  transition: background 0.12s, border-color 0.12s;
}
.cl-drop--sopra {
  border-color: var(--vp-terra);
  background: var(--vp-terra-soft);
}
.cl-drop__titolo {
  font-size: 13.5px;
  margin-top: 6px;
}
.cl-drop__nota {
  font-size: 12px;
  color: var(--vp-ink-3);
  margin-top: 2px;
}
.cl-avviso {
  background: var(--vp-paper-2);
  font-size: 12.5px;
  line-height: 1.45;
  color: var(--vp-ink-2);
}
</style>
