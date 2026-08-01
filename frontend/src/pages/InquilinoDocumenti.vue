<template>
  <q-page class="vp-idoc">
    <header class="vp-idoc__header">
      <div class="vp-eyebrow">Profilo</div>
      <h1 class="vp-display vp-idoc__titolo">I miei documenti</h1>
    </header>

    <!-- Stato del fascicolo: cosa manca e cosa scade, in una riga -->
    <section class="vp-card vp-idoc__stato">
      <q-inner-loading :showing="fascicoloStore.loading" />
      <FascicoloBarra v-if="voci.length" :voci="voci" />
      <p class="vp-idoc__riassunto">
        <span v-if="mancanti" class="vp-idoc__forte">
          {{ mancanti === 1 ? 'Manca 1 documento' : `Mancano ${mancanti} documenti` }}
        </span>
        <span v-if="mancanti && daRinnovare"> · </span>
        <span v-if="daRinnovare">{{ daRinnovare }} da rinnovare</span>
        <span v-if="!mancanti && !daRinnovare" class="vp-idoc__forte">
          Fascicolo in ordine
        </span>
        <br v-if="nostri" />
        <span v-if="nostri" class="vp-idoc__nota">
          {{ nostri === 1 ? '1 documento lo carichiamo noi' : `${nostri} documenti li carichiamo noi` }}
        </span>
      </p>
      <button class="vp-btn vp-btn--primary vp-idoc__aggiungi" @click="apriAggiungi()">
        <q-icon name="photo_camera" size="16px" />
        Aggiungi documento
      </button>
    </section>

    <!-- Il fascicolo: checklist, non elenco di file -->
    <div class="vp-eyebrow vp-idoc__sezione">Il tuo fascicolo</div>
    <div class="vp-card vp-idoc__lista">
      <FascicoloVoce
        v-for="voce in voci"
        :key="voce.tipo"
        :voce="voce"
        @apri="apriVisore"
        @aggiungi="apriAggiungi"
      />
      <div v-if="!voci.length && !fascicoloStore.loading" class="vp-idoc__vuoto">
        Nessun documento richiesto al momento.
      </div>
    </div>

    <!-- Documenti caricati fuori checklist -->
    <template v-if="altri.length">
      <div class="vp-eyebrow vp-idoc__sezione">Altri documenti</div>
      <div class="vp-card vp-idoc__lista">
        <FascicoloVoce v-for="(voce, i) in altri" :key="i" :voce="voce" @apri="apriVisore" />
      </div>
    </template>

    <!-- Documenti della casa: sola lettura -->
    <div class="vp-idoc__sezione vp-idoc__sezione--riga">
      <span class="vp-eyebrow">Documenti della casa</span>
      <span class="vp-idoc__nota">· in sola lettura</span>
    </div>
    <div class="vp-card vp-idoc__lista vp-idoc__lista--casa">
      <div
        v-for="doc in documentiCasa"
        :key="doc.id"
        class="vp-idoc__casa"
        role="button"
        tabindex="0"
        @click="apriVisore(voceDaDocumento(doc), true)"
        @keydown.enter="apriVisore(voceDaDocumento(doc), true)"
      >
        <div class="vp-idoc__casa-ic">
          <q-icon :name="iconaCasa(doc.tipo)" size="17px" />
        </div>
        <div class="vp-idoc__casa-txt">
          <div class="vp-idoc__casa-nome">{{ doc.tipo_display }}</div>
          <div class="vp-idoc__casa-nota">{{ doc.descrizione || formattaData(doc.created_at) }}</div>
        </div>
        <q-icon name="chevron_right" size="18px" class="vp-idoc__chevron" />
      </div>
      <div v-if="!documentiCasa.length && !storeCasa.loading" class="vp-idoc__vuoto">
        I proprietari non hanno ancora condiviso documenti.
      </div>
    </div>

    <p class="vp-idoc__privacy">
      I documenti sono visibili solo a te e ai proprietari:
      <router-link to="/i/privacy">informativa privacy</router-link>.
    </p>

    <div class="vp-idoc__back">
      <q-btn flat color="primary" icon="arrow_back" label="Torna al profilo" no-caps to="/i/profilo" />
    </div>

    <DocVisoreDialog
      v-model="visoreAperto"
      :voce="voceAperta"
      :solo-lettura="visoreSoloLettura"
      @sostituisci="sostituisci"
      @elimina="elimina"
    />

    <DocAggiungiSheet
      v-model="aggiungiAperto"
      :store="store"
      :tipi="tipiCaricabili"
      :tipo-iniziale="tipoIniziale"
      :preavviso="preavviso"
      @caricato="ricarica"
    />
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import FascicoloBarra from 'components/documenti/FascicoloBarra.vue';
import FascicoloVoce from 'components/documenti/FascicoloVoce.vue';
import DocVisoreDialog from 'components/documenti/DocVisoreDialog.vue';
import DocAggiungiSheet from 'components/documenti/DocAggiungiSheet.vue';
import {
  useDocumentiStore,
  useDocumentiProprietaStore,
  TIPI_DOCUMENTO_INQUILINO,
} from 'stores/documenti';
import { useFascicoloStore, type VoceFascicolo } from 'stores/fascicolo';
import { voceDaDocumento } from 'src/utils/statoDocumento';
import { useFormatoData } from 'src/composables/useFormatoData';

const $q = useQuasar();
const { formattaData } = useFormatoData();

const store = useDocumentiStore();
const storeCasa = useDocumentiProprietaStore();
const fascicoloStore = useFascicoloStore();

const visoreAperto = ref(false);
const voceAperta = ref<VoceFascicolo | null>(null);
/** I documenti della casa si consultano soltanto: niente sostituisci/elimina. */
const visoreSoloLettura = ref(false);
const aggiungiAperto = ref(false);
const tipoIniziale = ref<string | null>(null);

const voci = computed(() => fascicoloStore.voci);
const altri = computed(() => fascicoloStore.altri);
const documentiCasa = computed(() => storeCasa.documenti);
const preavviso = computed(() => fascicoloStore.fascicolo?.giorni_preavviso_scadenza ?? 60);

const mancanti = computed(() => fascicoloStore.fascicolo?.riepilogo.mancante ?? 0);
const daRinnovare = computed(() => fascicoloStore.fascicolo?.riepilogo.da_sistemare ?? 0);
const nostri = computed(() => fascicoloStore.fascicolo?.riepilogo.attesa ?? 0);

/** L'atto di subentro lo carica la proprietà: non è tra le scelte dell'inquilino. */
const tipiCaricabili = TIPI_DOCUMENTO_INQUILINO.filter((t) => t.value !== 'atto_subentro');

function iconaCasa(tipo: string): string {
  switch (tipo) {
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

function apriVisore(voce: VoceFascicolo, soloLettura = false) {
  voceAperta.value = voce;
  visoreSoloLettura.value = soloLettura;
  visoreAperto.value = true;
}

function apriAggiungi(voce?: VoceFascicolo) {
  tipoIniziale.value = voce?.tipo ?? null;
  aggiungiAperto.value = true;
}

function sostituisci(voce: VoceFascicolo) {
  visoreAperto.value = false;
  apriAggiungi(voce);
}

async function elimina(id: number) {
  const ok = await store.elimina(id);
  if (!ok) {
    $q.notify({ type: 'negative', message: store.errore ?? 'Errore eliminazione.' });
    return;
  }
  $q.notify({ type: 'positive', message: 'Documento eliminato.' });
  visoreAperto.value = false;
  await ricarica();
}

async function ricarica() {
  await fascicoloStore.fetch();
  // Riallinea la voce aperta (es. dopo aver aggiunto il retro).
  if (voceAperta.value) {
    const aggiornata = fascicoloStore.voci.find((v) => v.tipo === voceAperta.value?.tipo);
    voceAperta.value = aggiornata ?? null;
    if (!aggiornata) visoreAperto.value = false;
  }
}

onMounted(async () => {
  // Lo store dei propri documenti serve solo per caricare/eliminare: l'elenco
  // mostrato è il fascicolo, che arriva già raggruppato dal backend.
  await Promise.all([fascicoloStore.fetch(), storeCasa.fetch()]);
});
</script>

<style scoped>
.vp-idoc {
  max-width: 640px;
  margin: 0 auto;
  padding: var(--vp-gap-4) var(--vp-gap-4) var(--vp-gap-6);
}
.vp-idoc__header {
  margin-bottom: var(--vp-gap-4);
}
.vp-idoc__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 0;
}
.vp-idoc__stato {
  position: relative;
  padding: var(--vp-gap-4);
  margin-bottom: var(--vp-gap-5);
}
.vp-idoc__riassunto {
  margin: var(--vp-gap-3) 0 var(--vp-gap-3);
  font-size: 14px;
  line-height: 1.45;
  color: var(--vp-ink-2);
}
.vp-idoc__forte {
  color: var(--vp-ink);
  font-weight: 500;
}
.vp-idoc__nota {
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-3);
}
.vp-idoc__aggiungi {
  width: 100%;
}
.vp-idoc__sezione {
  margin-bottom: var(--vp-gap-2);
}
.vp-idoc__sezione--riga {
  display: flex;
  align-items: baseline;
  gap: var(--vp-gap-2);
}
.vp-idoc__lista {
  overflow: hidden;
  margin-bottom: var(--vp-gap-5);
}
.vp-idoc__lista--casa {
  background: var(--vp-paper-2);
}
.vp-idoc__vuoto {
  padding: var(--vp-gap-5) var(--vp-gap-4);
  text-align: center;
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm);
}
.vp-idoc__casa {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-3);
  padding: var(--vp-gap-3) var(--vp-gap-4);
  border-bottom: 1px solid var(--vp-paper-3);
  cursor: pointer;
}
.vp-idoc__casa:last-child {
  border-bottom: none;
}
.vp-idoc__casa:hover {
  background: var(--vp-paper-3);
}
.vp-idoc__casa-ic {
  flex: none;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: var(--vp-terra-soft);
  color: var(--vp-terra-deep);
  display: flex;
  align-items: center;
  justify-content: center;
}
.vp-idoc__casa-txt {
  flex: 1;
  min-width: 0;
}
.vp-idoc__casa-nome {
  font-size: 14.5px;
  font-weight: 500;
}
.vp-idoc__casa-nota {
  font-size: 12.5px;
  color: var(--vp-ink-3);
}
.vp-idoc__chevron {
  color: var(--vp-ink-4);
}
.vp-idoc__privacy {
  font-size: var(--vp-text-xs);
  color: var(--vp-ink-3);
  text-align: center;
  margin: 0;
}
.vp-idoc__back {
  margin-top: var(--vp-gap-4);
  display: flex;
  justify-content: center;
}
</style>
