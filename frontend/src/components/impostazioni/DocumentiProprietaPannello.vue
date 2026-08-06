<template>
  <CardSezione
    titolo="Altri documenti"
    descrizione="Regolamento, regole di convivenza: le carte della casa che non appartengono a un contratto. Con «visibile agli inquilini» il documento compare anche nella loro pagina «I miei documenti»."
  >
    <template v-if="puoModificare" #azioni>
      <q-btn
        color="primary"
        unelevated
        no-caps
        icon="upload"
        label="Carica documento"
        data-testid="carica-documento"
        @click="sheetAperto = true"
      />
    </template>

    <div v-if="store.loading" class="q-pa-md flex flex-center">
      <q-spinner size="28px" />
    </div>
    <div v-else class="imm-elenco">
      <RigaElenco
        v-for="(d, i) in store.documenti"
        :key="d.id"
        :ultima="i === store.documenti.length - 1"
        data-testid="riga-documento"
      >
        <template #tile><TileIcona :icona="icona(d.tipo)" /></template>
        <template #titolo>{{ d.tipo_display }}</template>
        <template #meta>{{ dettaglio(d) }}</template>
        <template #azioni>
          <button
            v-if="puoModificare"
            type="button"
            class="vp-badge imm-vis"
            :class="d.visibile_inquilini ? 'imm-vis--on' : 'imm-vis--off'"
            :aria-pressed="!!d.visibile_inquilini"
            :aria-label="`Visibilità di ${d.tipo_display}`"
            @click="cambiaVisibilita(d)"
          >
            <VpIcon name="eye" :size="13" />
            {{ d.visibile_inquilini ? 'Inquilini' : 'Solo proprietà' }}
            <q-tooltip>
              {{
                d.visibile_inquilini
                  ? 'Gli inquilini lo vedono — clicca per nasconderlo'
                  : 'Solo la proprietà lo vede — clicca per mostrarlo'
              }}
            </q-tooltip>
          </button>
          <BtnIcona
            icona="open"
            :etichetta="`Apri ${d.tipo_display}`"
            tooltip="Apri"
            @click="apri(d)"
          />
          <BtnIcona
            v-if="puoModificare"
            icona="trash"
            pericolo
            :etichetta="`Elimina ${d.tipo_display}`"
            tooltip="Elimina"
            @click="conferma(d)"
          />
        </template>
      </RigaElenco>
      <div v-if="store.documenti.length === 0" class="imm-vuoto">
        Nessun documento della casa caricato.
      </div>
    </div>
  </CardSezione>

  <CaricaDocumentiSheet v-model="sheetAperto" :store="store" :tipi="tipi" />
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import {
  useDocumentiProprietaStore,
  TIPI_DOCUMENTO_PROPRIETA,
  type DocumentoFE,
} from 'stores/documenti';
import { useFormatoData } from 'src/composables/useFormatoData';
import VpIcon from 'components/utenze/VpIcon.vue';
import CardSezione from './ui/CardSezione.vue';
import RigaElenco from './ui/RigaElenco.vue';
import TileIcona from './ui/TileIcona.vue';
import BtnIcona from './ui/BtnIcona.vue';
import CaricaDocumentiSheet from './CaricaDocumentiSheet.vue';

defineProps<{ puoModificare: boolean }>();

const $q = useQuasar();
const { formattaData } = useFormatoData();
const store = useDocumentiProprietaStore();
const tipi = TIPI_DOCUMENTO_PROPRIETA;

const sheetAperto = ref(false);

onMounted(() => {
  void store.fetch();
});

function icona(tipo: string): string {
  switch (tipo) {
    case 'contratto':
      return 'contract';
    case 'registrazione_contratto':
      return 'receipt';
    case 'regolamento_condominiale':
      return 'home';
    default:
      return 'doc';
  }
}

function dettaglio(d: DocumentoFE): string {
  const parti: string[] = [];
  if (d.descrizione) parti.push(d.descrizione);
  parti.push(`caricato il ${formattaData(d.created_at)}`);
  if (d.data_scadenza) {
    parti.push(`${d.scaduto ? 'scaduto' : 'scade'} il ${formattaData(d.data_scadenza)}`);
  }
  return parti.join(' · ');
}

function apri(d: DocumentoFE) {
  window.open(d.file, '_blank', 'noopener');
}

async function cambiaVisibilita(d: DocumentoFE) {
  const nuova = !d.visibile_inquilini;
  const ok = await store.impostaVisibilita(d.id, nuova);
  if (!ok) {
    $q.notify({ type: 'negative', message: store.errore ?? 'Aggiornamento non riuscito.' });
    return;
  }
  $q.notify({
    type: 'positive',
    message: nuova ? 'Ora è visibile agli inquilini.' : 'Ora lo vede solo la proprietà.',
  });
}

function conferma(d: DocumentoFE) {
  $q.dialog({
    title: 'Eliminare il documento?',
    message: `"${d.tipo_display}" verrà rimosso.`,
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Elimina' },
  }).onOk(() => {
    void (async () => {
      const ok = await store.elimina(d.id);
      $q.notify(
        ok
          ? { type: 'positive', message: 'Documento eliminato.' }
          : { type: 'negative', message: store.errore ?? 'Eliminazione non riuscita.' },
      );
    })();
  });
}
</script>

<style scoped>
.imm-elenco {
  margin-top: 4px;
}
.imm-vuoto {
  font-size: 13px;
  color: var(--vp-ink-3);
  padding: 10px 2px;
}
.imm-vis {
  border: none;
  cursor: pointer;
  gap: 5px;
}
.imm-vis--on {
  background: var(--vp-sage-soft);
  color: var(--vp-sage-deep);
}
.imm-vis--off {
  background: var(--vp-paper-2);
  color: var(--vp-ink-3);
}
.imm-vis:focus-visible {
  outline: 2px solid var(--vp-terra);
  outline-offset: 1px;
}
</style>
