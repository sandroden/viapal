<template>
  <div class="vp-fasc">
    <!-- Colonna elenco -->
    <div class="vp-fasc__elenco">
      <!-- Banner solo quando c'è qualcosa da segnalare: nessun documento è
           dovuto, quindi "tutto a posto" non è una notizia. -->
      <div v-if="daSegnalare.length" class="vp-banner vp-banner--late">
        <q-icon name="error_outline" size="19px" class="vp-fasc__banner-ic" />
        <div class="vp-fasc__banner-txt">
          <div v-html="riepilogoHtml" />
        </div>
      </div>

      <div class="vp-fasc__intestazione">
        <span class="vp-eyebrow">Fascicolo personale</span>
        <div class="vp-fasc__riga" />
        <!-- Generare è un'azione, non una casella vuota nell'elenco: alcuni
             documenti non servono affatto, e il fascicolo non deve chiederli.
             Resta però la strada secondaria: il gesto abituale è caricare.
             I due bottoni stanno insieme, così su schermo stretto vanno a
             capo in blocco invece di sparpagliarsi. -->
        <div v-if="!soloLettura" class="vp-fasc__azioni-testa">
          <button class="vp-btn vp-btn--ghost vp-fasc__azione" @click="generaAperto = true">
            <q-icon name="auto_awesome" size="15px" />
            Genera
          </button>
          <button class="vp-btn vp-btn--soft vp-fasc__azione" @click="aggiungi()">
            <q-icon name="upload" size="15px" />
            Carica documento
          </button>
        </div>
      </div>

      <div class="vp-card vp-fasc__lista">
        <q-inner-loading :showing="fascicoloStore.loading" />
        <!-- Nessun documento è dovuto: il vuoto va spiegato, non riempito
             di caselle da compilare. -->
        <div v-if="senzaDocumenti" class="vp-fasc__nessuno">
          Nessun documento, per ora.<template v-if="!soloLettura">
            Carica le copie che servono, o genera l'atto di subentro e la
            cessione di fabbricato.</template>
        </div>
        <FascicoloVoce
          v-for="voce in voci"
          :key="voce.tipo"
          :voce="voce"
          :selezionata="!compatto && voce.tipo === tipoSelezionato"
          badge-con-data
          :larghezza="38"
          :altezza="48"
          @apri="seleziona"
        >
          <template #azioni>
            <a
              :href="voce.pagine[0]?.file"
              :download="voce.pagine[0]?.nome_file"
              class="vp-fasc__scarica"
              aria-label="Scarica"
              @click.stop
            >
              <q-icon name="download" size="17px" />
            </a>
            <!-- Su un PDF che abbiamo prodotto noi la scorciatoia è rifarlo. -->
            <button
              v-if="voce.generabile && !soloLettura"
              class="vp-fasc__scarica"
              aria-label="Rigenera"
              @click.stop="apriGenerazione(voce.generabile, voce.tipo_display)"
            >
              <q-icon name="autorenew" size="17px" />
            </button>
          </template>
        </FascicoloVoce>
      </div>

      <template v-if="altri.length">
        <div class="vp-eyebrow vp-fasc__sezione">Altri documenti</div>
        <div class="vp-card vp-fasc__lista">
          <FascicoloVoce
            v-for="(voce, i) in altri"
            :key="i"
            :voce="voce"
            :selezionata="!compatto && voce.pagine[0]?.id === paginaSelezionataId"
            :larghezza="38"
            :altezza="48"
            @apri="seleziona"
          />
        </div>
      </template>
    </div>

    <!-- Visore affiancato: il documento si apre qui, non in una nuova scheda -->
    <aside v-if="!compatto" class="vp-fasc__visore">
      <template v-if="selezionata">
        <header class="vp-fasc__vtesta">
          <div class="vp-fasc__vtitolo">
            <div class="vp-fasc__vnome">{{ selezionata.titolo ?? selezionata.tipo_display }}</div>
            <div class="vp-fasc__vmeta">{{ metaSelezionata }}</div>
          </div>
          <DocBadgeStato :stato="selezionata.stato" />
        </header>

        <div class="vp-fasc__vcorpo">
          <DocPagina v-if="paginaCorrente" :key="paginaCorrente.id" :pagina="paginaCorrente" />
        </div>

        <div v-if="selezionata.pagine.length > 1" class="vp-fasc__vpagine">
          <button
            v-for="(p, i) in selezionata.pagine"
            :key="p.id"
            class="vp-fasc__vtab"
            :class="{ 'vp-fasc__vtab--on': i === indicePagina }"
            @click="indicePagina = i"
          >
            {{ p.etichetta }}
          </button>
        </div>

        <footer v-if="paginaCorrente" class="vp-fasc__vazioni">
          <button class="vp-btn vp-btn--ghost vp-fasc__vazione" @click="ingrandisci">
            <q-icon name="zoom_out_map" size="15px" />
            Ingrandisci
          </button>
          <a
            class="vp-btn vp-btn--ghost vp-fasc__vazione"
            :href="paginaCorrente.file"
            :download="paginaCorrente.nome_file"
          >
            <q-icon name="download" size="15px" />
            Scarica
          </a>
          <button
            v-if="!soloLettura"
            class="vp-btn vp-btn--ghost vp-fasc__vcestino"
            aria-label="Elimina"
            @click="confermaElimina(paginaCorrente)"
          >
            <q-icon name="delete_outline" size="16px" />
          </button>
        </footer>
      </template>

      <div v-else class="vp-fasc__vvuoto vp-fasc__vvuoto--nessuno">
        {{
          senzaDocumenti
            ? 'Qui compaiono i documenti dell’inquilino, quando ce ne sono.'
            : 'Scegli un documento a sinistra per vederlo qui.'
        }}
      </div>
    </aside>

    <DocVisoreDialog
      v-model="visoreAperto"
      :voce="selezionata"
      :solo-lettura="soloLettura"
      @sostituisci="aggiungi"
      @elimina="elimina"
    />

    <DocAggiungiSheet
      v-model="aggiungiAperto"
      :store="store"
      :tipi="tipi"
      :tipo-iniziale="tipoIniziale"
      :target-id="tenantId"
      :preavviso="preavviso"
      titolo="Carica un documento"
      @caricato="ricarica"
    />

    <GeneraDocumentiSheet
      v-model="generaAperto"
      :tenant-id="tenantId"
      @scelto="(d) => apriGenerazione(d.codice, d.titolo)"
    />

    <GeneraDocumentoDialog
      v-model="dialogGenerazione"
      :tenant-id="tenantId"
      :documento="documentoDaGenerare"
      :titolo-atteso="titoloDaGenerare"
      @generato="ricarica"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useQuasar } from 'quasar';
import FascicoloVoce from './FascicoloVoce.vue';
import DocBadgeStato from './DocBadgeStato.vue';
import DocPagina from './DocPagina.vue';
import DocVisoreDialog from './DocVisoreDialog.vue';
import DocAggiungiSheet from './DocAggiungiSheet.vue';
import GeneraDocumentiSheet from './GeneraDocumentiSheet.vue';
import GeneraDocumentoDialog from './GeneraDocumentoDialog.vue';
import { useDocumentiStore, TIPI_DOCUMENTO_INQUILINO } from 'stores/documenti';
import { useFascicoloStore, type VoceFascicolo } from 'stores/fascicolo';
import { useFormatoData } from 'src/composables/useFormatoData';

const props = defineProps<{
  tenantId: number;
  /** Ruolo in sola lettura: nessun caricamento né eliminazione. */
  soloLettura?: boolean;
}>();

const $q = useQuasar();
const { formattaData } = useFormatoData();

const store = useDocumentiStore();
const fascicoloStore = useFascicoloStore();

const tipoSelezionato = ref<string | null>(null);
const paginaSelezionataId = ref<number | null>(null);
const indicePagina = ref(0);
const visoreAperto = ref(false);
const aggiungiAperto = ref(false);
const tipoIniziale = ref<string | null>(null);
/** Elenco dei documenti producibili (l'azione "Genera"). */
const generaAperto = ref(false);
/** Anteprima/generazione del documento scelto. */
const dialogGenerazione = ref(false);
const documentoDaGenerare = ref<string | null>(null);
const titoloDaGenerare = ref('');

const tipi = TIPI_DOCUMENTO_INQUILINO;
const voci = computed(() => fascicoloStore.voci);
const altri = computed(() => fascicoloStore.altri);
const senzaDocumenti = computed(
  () => !fascicoloStore.loading && !voci.value.length && !altri.value.length,
);
const preavviso = computed(() => fascicoloStore.fascicolo?.giorni_preavviso_scadenza ?? 60);
/** Sotto i 1024px il visore affiancato non ci sta: si apre a schermo intero. */
const compatto = computed(() => $q.screen.lt.md);

const selezionata = computed<VoceFascicolo | null>(() => {
  const tutte = [...voci.value, ...altri.value];
  if (paginaSelezionataId.value !== null) {
    const perPagina = tutte.find((v) => v.pagine[0]?.id === paginaSelezionataId.value);
    if (perPagina) return perPagina;
  }
  return tutte.find((v) => v.tipo === tipoSelezionato.value) ?? null;
});

const paginaCorrente = computed(() => selezionata.value?.pagine[indicePagina.value] ?? null);

const metaSelezionata = computed(() => {
  const voce = selezionata.value;
  if (!voce) return '';
  const parti: string[] = [];
  if (voce.caricato_il) parti.push(`caricato il ${formattaData(voce.caricato_il)}`);
  if (voce.data_scadenza) parti.push(`scadenza ${formattaData(voce.data_scadenza)}`);
  return parti.join(' · ');
});

// ── Riepilogo in testa: nomi dei documenti, non solo conteggi ──
const scaduti = computed(() => voci.value.filter((v) => v.stato === 'scaduto'));
const inScadenza = computed(() => voci.value.filter((v) => v.stato === 'scadenza'));
const daSegnalare = computed(() => [...scaduti.value, ...inScadenza.value]);

function frase(voci: VoceFascicolo[], singolare: string, plurale: string): string {
  if (!voci.length) return '';
  const nomi = voci.map((v) => v.tipo_display.toLowerCase()).join(', ');
  const testa = voci.length === 1 ? `<b>1 ${singolare}</b>` : `<b>${voci.length} ${plurale}</b>`;
  return `${testa} (${nomi})`;
}

const riepilogoHtml = computed(() =>
  [
    frase(scaduti.value, 'documento scaduto', 'documenti scaduti'),
    frase(inScadenza.value, 'documento in scadenza', 'documenti in scadenza'),
  ]
    .filter(Boolean)
    .join(' · '),
);

function seleziona(voce: VoceFascicolo) {
  tipoSelezionato.value = voce.tipo;
  paginaSelezionataId.value = voce.pagine[0]?.id ?? null;
  indicePagina.value = 0;
  // Senza visore affiancato (mobile) il documento si apre a schermo intero.
  if (compatto.value) visoreAperto.value = true;
}

function ingrandisci() {
  visoreAperto.value = true;
}

function aggiungi(voce?: VoceFascicolo) {
  tipoIniziale.value = voce?.tipo ?? null;
  visoreAperto.value = false;
  aggiungiAperto.value = true;
}

function apriGenerazione(codice: string, titolo: string) {
  documentoDaGenerare.value = codice;
  titoloDaGenerare.value = titolo;
  visoreAperto.value = false;
  dialogGenerazione.value = true;
}

function confermaElimina(pagina: { id: number; etichetta: string }) {
  const voce = selezionata.value;
  const cosa =
    voce && voce.pagine.length > 1
      ? `la pagina "${pagina.etichetta}"`
      : `"${voce?.tipo_display}"`;
  $q.dialog({
    title: 'Elimina documento',
    message: `Eliminare ${cosa}? L'operazione non è reversibile.`,
    cancel: { label: 'Annulla', flat: true, noCaps: true },
    ok: { label: 'Elimina', color: 'negative', unelevated: true, noCaps: true },
  }).onOk(() => {
    void elimina(pagina.id);
  });
}

async function elimina(id: number) {
  const ok = await store.elimina(id);
  $q.notify(
    ok
      ? { type: 'positive', message: 'Documento eliminato.' }
      : { type: 'negative', message: store.errore ?? 'Errore eliminazione.' },
  );
  if (ok) {
    visoreAperto.value = false;
    await ricarica();
  }
}

async function ricarica() {
  await fascicoloStore.fetch(props.tenantId);
  indicePagina.value = 0;
  if (!selezionata.value) preseleziona();
  paginaSelezionataId.value = selezionata.value?.pagine[0]?.id ?? null;
}

/** Apre da subito il documento che chiede attenzione: il visore vuoto non
 *  dice nulla, e il primo sguardo del proprietario è per ciò che non va. */
function preseleziona() {
  const scelta =
    voci.value.find((v) => v.stato === 'scaduto') ??
    voci.value.find((v) => v.stato === 'scadenza') ??
    voci.value[0] ??
    null;
  tipoSelezionato.value = scelta?.tipo ?? null;
}

onMounted(() => {
  void ricarica();
});
watch(
  () => props.tenantId,
  () => {
    tipoSelezionato.value = null;
    paginaSelezionataId.value = null;
    void ricarica();
  },
);
</script>

<style scoped>
.vp-fasc {
  display: grid;
  grid-template-columns: 1fr 420px;
  gap: var(--vp-gap-5);
  align-items: start;
}
@media (max-width: 1023px) {
  .vp-fasc {
    grid-template-columns: 1fr;
  }
}
.vp-fasc__banner-ic {
  flex: none;
  margin-top: 1px;
}
.vp-fasc__banner-txt {
  flex: 1;
}
.vp-fasc__intestazione {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-2);
  /* Su schermo stretto i due bottoni vanno a capo invece di schiacciarsi. */
  flex-wrap: wrap;
  margin: var(--vp-gap-5) 0 var(--vp-gap-2);
}
.vp-fasc__riga {
  flex: 1;
  min-width: 16px;
  height: 1px;
  background: var(--vp-paper-3);
}
.vp-fasc__azioni-testa {
  display: flex;
  gap: var(--vp-gap-2);
  margin-left: auto;
}
.vp-fasc__azione {
  height: 32px;
  font-size: var(--vp-text-sm);
  white-space: nowrap;
}
.vp-fasc__sezione {
  margin: var(--vp-gap-5) 0 var(--vp-gap-2);
}
.vp-fasc__lista {
  position: relative;
  overflow: hidden;
  min-height: 60px;
}
.vp-fasc__nessuno {
  padding: var(--vp-gap-4);
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-3);
  line-height: 1.5;
}
.vp-fasc__scarica {
  display: flex;
  align-items: center;
  color: var(--vp-ink-4);
  padding: 4px;
}
.vp-fasc__scarica:hover {
  color: var(--vp-terra);
}

/* ── Visore affiancato ── */
.vp-fasc__visore {
  position: sticky;
  top: var(--vp-gap-4);
  display: flex;
  flex-direction: column;
  /* Altezza piena della finestra: i PDF hanno bisogno di spazio vero. */
  height: calc(100vh - 140px);
  min-height: 520px;
  max-height: 900px;
  background: var(--vp-paper-2);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  overflow: hidden;
}
.vp-fasc__vtesta {
  display: flex;
  align-items: flex-start;
  gap: var(--vp-gap-3);
  padding: var(--vp-gap-4) var(--vp-gap-4) var(--vp-gap-3);
  border-bottom: 1px solid var(--vp-paper-3);
}
.vp-fasc__vtitolo {
  flex: 1;
  min-width: 0;
}
.vp-fasc__vnome {
  font-size: var(--vp-text-lg);
  font-weight: 500;
}
.vp-fasc__vmeta {
  font-size: 12.5px;
  color: var(--vp-ink-3);
  margin-top: 3px;
}
.vp-fasc__vcorpo {
  flex: 1;
  min-height: 0;
  padding: var(--vp-gap-3);
  display: flex;
  align-items: center;
  justify-content: center;
}
.vp-fasc__vvuoto {
  text-align: center;
  max-width: 280px;
}
.vp-fasc__vvuoto--nessuno {
  margin: auto;
  padding: var(--vp-gap-5);
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm);
}
.vp-fasc__vpagine {
  display: flex;
  justify-content: center;
  gap: var(--vp-gap-2);
  padding: 0 0 var(--vp-gap-3);
}
.vp-fasc__vtab {
  height: 28px;
  padding: 0 12px;
  border-radius: var(--vp-r-pill);
  border: 1px solid var(--vp-paper-3);
  background: transparent;
  color: var(--vp-ink-3);
  font-family: var(--vp-font-ui);
  font-size: 12.5px;
  cursor: pointer;
}
.vp-fasc__vtab--on {
  border-color: var(--vp-terra);
  background: var(--vp-cream);
  color: var(--vp-terra-deep);
}
.vp-fasc__vazioni {
  display: flex;
  gap: var(--vp-gap-2);
  padding: var(--vp-gap-3) var(--vp-gap-4);
  border-top: 1px solid var(--vp-paper-3);
  background: var(--vp-paper);
}
.vp-fasc__vazione {
  flex: 1;
  height: 36px;
  font-size: var(--vp-text-sm);
  text-decoration: none;
}
.vp-fasc__vcestino {
  width: 40px;
  height: 36px;
  padding: 0;
  color: var(--vp-clay);
}
</style>
