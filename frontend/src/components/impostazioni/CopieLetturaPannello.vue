<template>
  <CardSezione
    titolo="Copie per la lettura"
    descrizione="Le versioni oscurate dei documenti, da mandare a chi deve ancora firmare. Si caricano una volta e si riusano per ogni destinatario: non compaiono fra le carte del contratto, né in «Altri documenti», né nella pagina degli inquilini."
  >
    <template v-if="puoModificare" #azioni>
      <BtnSoft
        etichetta="Copia per la lettura"
        data-testid="nuova-copia-lettura"
        @click="apriCaricamento(null)"
      />
    </template>

    <div v-if="store.loading" class="q-pa-md flex flex-center">
      <q-spinner size="28px" />
    </div>
    <div v-else class="cl-elenco">
      <RigaElenco
        v-for="(d, i) in copie"
        :key="d.id"
        :ultima="i === copie.length - 1"
        data-testid="riga-copia-lettura"
      >
        <template #tile><TileIcona icona="doc" /></template>
        <template #titolo>{{ titoloDi(d) }}</template>
        <template #badge>
          <EtichettaStato :tono="d.esponibile ? 'ok' : 'off'">
            {{ etichettaUso(d) }}
          </EtichettaStato>
        </template>
        <template #meta>copia di: {{ origineDi(d) }}</template>
        <template #azioni>
          <!-- La spunta è la revoca a grana fine: tolta, i link già mandati
               smettono di servire questo file. -->
          <button
            v-if="puoModificare"
            type="button"
            class="vp-badge cl-esp"
            :class="d.esponibile ? 'cl-esp--on' : 'cl-esp--off'"
            :aria-pressed="!!d.esponibile"
            :aria-label="`Esponibilità di ${titoloDi(d)}`"
            :data-testid="`esponibile-${d.id}`"
            @click="cambiaEsponibile(d)"
          >
            <VpIcon name="eye" :size="13" />
            {{ d.esponibile ? 'Esponibile' : 'Sospesa' }}
            <q-tooltip>
              {{
                d.esponibile
                  ? 'I link la servono — clicca per sospenderla ovunque'
                  : 'Nessun link la serve — clicca per riattivarla'
              }}
            </q-tooltip>
          </button>
          <BtnIcona
            icona="open"
            :etichetta="`Apri ${titoloDi(d)}`"
            tooltip="Apri"
            @click="apri(d)"
          />
          <BtnIcona
            v-if="puoModificare"
            icona="edit"
            :etichetta="`Modifica ${titoloDi(d)}`"
            tooltip="Modifica descrizione"
            @click="modifica(d)"
          />
          <BtnIcona
            v-if="puoModificare"
            icona="trash"
            pericolo
            :etichetta="`Elimina ${titoloDi(d)}`"
            tooltip="Elimina"
            @click="conferma(d)"
          />
        </template>
      </RigaElenco>
      <div v-if="copie.length === 0" class="cl-vuoto">
        Nessuna copia caricata. Il contratto oscurato si carica una volta e
        vale per tutti i destinatari.
      </div>
    </div>
  </CardSezione>

  <CopiaLetturaDialog v-model="dialogAperto" :originale="originaleScelto" />

  <ModificaDocumentoDialog
    v-model="modificaAperta"
    :store="store"
    :documento="inModifica"
    :tipi="TIPI_DOCUMENTO_PROPRIETA"
    :contratti="contratti"
  />
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { api } from 'boot/axios';
import {
  useDocumentiProprietaStore,
  TIPI_DOCUMENTO_PROPRIETA,
  type DocumentoFE,
} from 'stores/documenti';
import VpIcon from 'components/utenze/VpIcon.vue';
import CardSezione from './ui/CardSezione.vue';
import RigaElenco from './ui/RigaElenco.vue';
import TileIcona from './ui/TileIcona.vue';
import EtichettaStato from './ui/EtichettaStato.vue';
import BtnIcona from './ui/BtnIcona.vue';
import BtnSoft from './ui/BtnSoft.vue';
import CopiaLetturaDialog from './CopiaLetturaDialog.vue';
import ModificaDocumentoDialog from './ModificaDocumentoDialog.vue';

defineProps<{ puoModificare: boolean }>();

const $q = useQuasar();
const store = useDocumentiProprietaStore();

type ContrattoBreve = { id: number; nome: string; data_decorrenza: string };
const contratti = ref<ContrattoBreve[]>([]);

onMounted(() => {
  void caricaContratti();
});

async function caricaContratti() {
  try {
    const { data } = await api.get<ContrattoBreve[] | { results: ContrattoBreve[] }>(
      '/api/v1/contracts/',
    );
    contratti.value = Array.isArray(data) ? data : (data.results ?? []);
  } catch {
    // Senza elenco la sezione resta usabile: la copia eredita il contratto
    // dell'originale, cambiarlo è l'eccezione.
  }
}

const dialogAperto = ref(false);
const originaleScelto = ref<DocumentoFE | null>(null);
const modificaAperta = ref(false);
const inModifica = ref<DocumentoFE | null>(null);

/** La sezione è definita dal campo, non da una convenzione sul tipo. */
const copie = computed(() => store.documenti.filter((d) => d.copia_di));

function titoloDi(d: DocumentoFE): string {
  return d.titolo || d.descrizione || d.tipo_display;
}

function origineDi(d: DocumentoFE): string {
  const nome = d.copia_di_titolo || '—';
  return d.contract_nome ? `${nome} · ${d.contract_nome}` : nome;
}

function etichettaUso(d: DocumentoFE): string {
  if (!d.esponibile) return 'Sospesa';
  const n = d.link_in_uso ?? 0;
  if (n === 0) return 'In nessun link';
  return n === 1 ? 'In 1 link' : `In ${n} link`;
}

function apri(d: DocumentoFE) {
  window.open(d.file, '_blank', 'noopener');
}

function apriCaricamento(originale: DocumentoFE | null) {
  originaleScelto.value = originale;
  dialogAperto.value = true;
}

function modifica(d: DocumentoFE) {
  inModifica.value = d;
  modificaAperta.value = true;
}

async function cambiaEsponibile(d: DocumentoFE) {
  const nuova = !d.esponibile;
  const ok = await store.impostaEsponibile(d.id, nuova);
  if (!ok) {
    $q.notify({ type: 'negative', message: store.errore ?? 'Aggiornamento non riuscito.' });
    return;
  }
  $q.notify({
    type: 'positive',
    message: nuova
      ? 'Di nuovo servita dai link che la contengono.'
      : 'Sospesa: i link che la contengono non la servono più.',
  });
}

function conferma(d: DocumentoFE) {
  $q.dialog({
    title: 'Eliminare la copia?',
    message: `"${titoloDi(d)}" verrà rimossa. Se è in un link di lettura, l'eliminazione viene rifiutata.`,
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Elimina' },
  }).onOk(() => {
    void (async () => {
      const ok = await store.elimina(d.id);
      $q.notify(
        ok
          ? { type: 'positive', message: 'Copia eliminata.' }
          : { type: 'negative', message: store.errore ?? 'Eliminazione non riuscita.' },
      );
    })();
  });
}

defineExpose({ apriCaricamento });
</script>

<style scoped>
.cl-elenco {
  margin-top: 4px;
}
.cl-vuoto {
  font-size: 13px;
  color: var(--vp-ink-3);
  padding: 10px 2px;
  line-height: 1.5;
}
.cl-esp {
  border: none;
  cursor: pointer;
  gap: 5px;
}
.cl-esp--on {
  background: var(--vp-sage-soft);
  color: var(--vp-sage-deep);
}
.cl-esp--off {
  background: var(--vp-paper-2);
  color: var(--vp-ink-3);
}
.cl-esp:focus-visible {
  outline: 2px solid var(--vp-terra);
  outline-offset: 1px;
}
</style>
