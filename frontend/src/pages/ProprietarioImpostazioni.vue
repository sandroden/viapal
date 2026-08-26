<template>
  <q-page padding class="vp-page vp-immobile">
    <!-- La testata dice il nome della casa, non «Immobile»: quello lo dice
         già il menu, e in multiproprietà sapere quale casa si sta guardando
         conta più del nome della sezione. -->
    <header class="vp-immobile__head">
      <div class="vp-immobile__intesta">
        <div class="vp-eyebrow">Immobile</div>
        <div class="vp-immobile__titolo">
          <h1 class="vp-immobile__nome">{{ dettaglio?.nome || 'Immobile' }}</h1>
          <span v-if="dettaglio?.indirizzo" class="vp-immobile__indirizzo">
            {{ dettaglio.indirizzo }}
          </span>
        </div>
      </div>
      <div class="vp-immobile__head-azioni">
        <EtichettaStato v-if="propStore.mioRuolo" tono="off" data-testid="chip-ruolo">
          {{ etichettaRuolo(propStore.mioRuolo) }}
        </EtichettaStato>
        <q-btn
          dense
          flat
          no-caps
          color="primary"
          icon="add_home"
          label="Nuova proprietà"
          to="/p/proprieta/nuova"
          data-testid="nuova-proprieta"
        />
      </div>
    </header>

    <!-- Quattro schede raggruppate per «di cosa parla»: la casa, le sue
         carte, i suoi soldi, le sue persone. -->
    <nav class="vp-immobile__tabs" data-testid="tabs-immobile">
      <button
        v-for="t in TABS"
        :key="t.id"
        type="button"
        class="imm-tab"
        :data-on="t.id === tabAttivo ? '' : null"
        :data-testid="`tab-${t.id}`"
        :aria-current="t.id === tabAttivo ? 'page' : undefined"
        @click="tabAttivo = t.id"
      >
        <VpIcon :name="t.icona" :size="16" />{{ t.label }}
      </button>
    </nav>

    <q-tab-panels v-model="tabAttivo" animated keep-alive class="vp-immobile__panels">
      <!-- DATI: anagrafica, indirizzo strutturato, stanze, ruoli operativi -->
      <q-tab-panel name="dati" class="vp-immobile__panel">
        <div v-if="!dettaglio" class="q-pa-lg flex flex-center">
          <q-spinner size="32px" />
        </div>
        <div v-else class="vp-immobile__colonne">
          <div class="vp-immobile__principale">
            <DatiImmobilePannello
              ref="datiPannello"
              :dettaglio="dettaglio"
              :quote-correnti="quoteCorrenti"
              :puo-modificare="puoModificare"
              @aggiornato="dettaglio = $event"
            />
          </div>
          <div class="vp-immobile__servizio">
            <StanzePannello :puo-modificare="puoModificare" />
          </div>
        </div>
      </q-tab-panel>

      <!-- CONTRATTI E DOCUMENTI: le carte della casa -->
      <q-tab-panel name="contratti" class="vp-immobile__panel">
        <div class="vp-immobile__pila">
          <ContrattiPannello ref="contrattiPannello" :puo-modificare="puoModificare" />
          <DocumentiProprietaPannello :puo-modificare="puoModificare" />
          <CopieLetturaPannello :puo-modificare="puoModificare" />
          <LinkLetturaPannello :puo-modificare="puoModificare" />
          <ModelliDocumentoPannello :puo-modificare="puoModificare" />
        </div>
      </q-tab-panel>

      <!-- SPESE: utenze, quote, costi annuali; a destra la configurazione -->
      <q-tab-panel name="spese" class="vp-immobile__panel">
        <div class="vp-immobile__colonne">
          <div class="vp-immobile__principale">
            <UtenzeCasaPannello :puo-modificare="puoModificare" />
            <QuoteCondominioPannello :puo-modificare="puoModificare" />
            <CostiAnnualiPannello :puo-modificare="puoModificare" />
          </div>
          <div class="vp-immobile__servizio">
            <CategorieSpesaPannello :puo-modificare="puoModificare" />
            <FornitoriPannello :puo-modificare="puoModificare" />
          </div>
        </div>
      </q-tab-panel>

      <!-- PROPRIETÀ: le persone, con ruolo, quota e conti -->
      <q-tab-panel name="proprieta" class="vp-immobile__panel">
        <div v-if="loadingGovernance" class="q-pa-lg flex flex-center">
          <q-spinner size="32px" />
        </div>
        <div v-else class="vp-immobile__pila">
          <MembriPannello
            v-if="propertyId"
            ref="membriPannello"
            :property-id="propertyId"
            :membri="membri"
            :quote="quote"
            :sono-proprietario="sonoProprietario"
            @aggiornati="membri = $event"
            @aggiornate="quote = $event"
          />
          <ContiBancariPannello
            :conto-utenze-id="dettaglio?.bank_account_utenze ?? null"
            :membri="membri"
          />
        </div>
      </q-tab-panel>
    </q-tab-panels>
  </q-page>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  etichettaRuolo,
  usePropertiesStore,
  type Membro,
  type PropertyDettaglio,
  type Quota,
} from 'stores/properties';
import { useOwnerBankAccountsStore } from 'stores/ownerBankAccounts';
import VpIcon from 'components/utenze/VpIcon.vue';
import EtichettaStato from 'components/impostazioni/ui/EtichettaStato.vue';
import DatiImmobilePannello from 'components/impostazioni/DatiImmobilePannello.vue';
import StanzePannello from 'components/impostazioni/StanzePannello.vue';
import ContrattiPannello from 'components/impostazioni/ContrattiPannello.vue';
import DocumentiProprietaPannello from 'components/impostazioni/DocumentiProprietaPannello.vue';
import CopieLetturaPannello from 'components/impostazioni/CopieLetturaPannello.vue';
import LinkLetturaPannello from 'components/impostazioni/LinkLetturaPannello.vue';
import ModelliDocumentoPannello from 'components/documenti/ModelliDocumentoPannello.vue';
import UtenzeCasaPannello from 'components/impostazioni/UtenzeCasaPannello.vue';
import QuoteCondominioPannello from 'components/impostazioni/QuoteCondominioPannello.vue';
import CostiAnnualiPannello from 'components/impostazioni/CostiAnnualiPannello.vue';
import CategorieSpesaPannello from 'components/impostazioni/CategorieSpesaPannello.vue';
import FornitoriPannello from 'components/impostazioni/FornitoriPannello.vue';
import MembriPannello from 'components/impostazioni/MembriPannello.vue';
import ContiBancariPannello from 'components/impostazioni/ContiBancariPannello.vue';

const route = useRoute();
const router = useRouter();
const propStore = usePropertiesStore();
const contiStore = useOwnerBankAccountsStore();

const TABS = [
  { id: 'dati', label: 'Dati', icona: 'home' },
  { id: 'contratti', label: 'Contratti e documenti', icona: 'contract' },
  { id: 'spese', label: 'Spese', icona: 'euro' },
  { id: 'proprieta', label: 'Proprietà', icona: 'users' },
] as const;
type Tab = (typeof TABS)[number]['id'];

/** Le dieci schede di prima restano indirizzi validi: i link dei "dati
 *  mancanti" generati dal backend (`?tab=modelli`, `?tab=membri`, …) e i
 *  segnalibri di chi usa l'app puntano ancora lì. */
const ALIAS: Record<string, Tab> = {
  dati: 'dati',
  stanze: 'dati',
  contratti: 'contratti',
  documenti: 'contratti',
  modelli: 'contratti',
  spese: 'spese',
  tari: 'spese',
  proprieta: 'proprieta',
  membri: 'proprieta',
  conti: 'proprieta',
  quote: 'proprieta',
};

function primo(v: unknown): string | null {
  const s = Array.isArray(v) ? v[0] : v;
  return typeof s === 'string' && s ? s : null;
}

/** Il tab arriva dalla query string: i "dati mancanti" della generazione
 *  documenti linkano direttamente al punto in cui si compilano. */
function tabDaRotta(): Tab {
  const nome = primo(route.query.tab);
  return (nome && ALIAS[nome]) || 'dati';
}

const tabAttivo = ref<Tab>(tabDaRotta());

const puoModificare = computed(
  () => propStore.mioRuolo === 'proprietario' || propStore.mioRuolo === 'gestore',
);
const sonoProprietario = computed(() => propStore.isProprietarioAttivo);

// ---------------------------------------------------------------------------
// Dati immobile, membri, quote di proprietà: lo stato vive nella pagina
// perché serve a più pannelli (i membri anche ai conti bancari, le quote
// anche al firmatario nel tab Dati).
// ---------------------------------------------------------------------------

const propertyId = computed(() => propStore.activePropertyId);
const dettaglio = ref<PropertyDettaglio | null>(null);
const membri = ref<Membro[]>([]);
const quote = ref<Quota[]>([]);
const loadingGovernance = ref(true);
const datiPannello = ref<InstanceType<typeof DatiImmobilePannello> | null>(null);
const membriPannello = ref<InstanceType<typeof MembriPannello> | null>(null);
const contrattiPannello = ref<InstanceType<typeof ContrattiPannello> | null>(null);

const quoteCorrenti = computed(() => quote.value.filter((q) => q.valid_to === null));

async function caricaGovernance() {
  const id = propertyId.value;
  if (!id) {
    loadingGovernance.value = false;
    return;
  }
  loadingGovernance.value = true;
  try {
    dettaglio.value = await propStore.caricaDettaglio(id);
    await contiStore.ensureLoaded(true);
    membri.value = await propStore.caricaMembri(id);
    quote.value = await propStore.caricaQuote(id);
  } finally {
    loadingGovernance.value = false;
  }
}

// ---------------------------------------------------------------------------
// Deep link: la lettura della query resta qui, l'azione ai pannelli.
// ---------------------------------------------------------------------------

/** Riscrive la query con il solo tab attivo: i param one-shot dei deep
 *  link (`contratto`, `campo`) vengono consumati. */
function aggiornaQuery(): void {
  void router.replace({ query: { tab: tabAttivo.value } });
}

/** `?tab=contratti&contratto=<id>`: apre il dialog del contratto indicato. */
function apriContrattoDaId(id: number | null) {
  if (!id) return;
  void nextTick().then(() => contrattiPannello.value?.apriContratto(id));
}

/** `?tab=dati&campo=<nome>`: fuoco sul campo da compilare. */
function focusCampoDati(campo: string | null) {
  if (!campo) return;
  void nextTick().then(() => datiPannello.value?.focusCampo(campo));
}

/** `?tab=membri&modifica=anagrafica&owner=<id>&campo=<nome>`: apre il dialog
 *  anagrafica del membro indicato (dati mancanti dei documenti generati). */
function apriAnagraficaMembro(
  modifica: string | null,
  ownerId: number | null,
  campo: string | null,
) {
  if (tabAttivo.value !== 'proprieta' || modifica !== 'anagrafica' || !ownerId) return;
  void nextTick().then(() => membriPannello.value?.apriAnagrafica(ownerId, campo));
}

onMounted(() => {
  // Catturati prima di aggiornaQuery(), che riscrive la query e li consuma.
  const campo = primo(route.query.campo);
  const contrattoId = Number(primo(route.query.contratto)) || null;
  const modifica = primo(route.query.modifica);
  const ownerId = Number(primo(route.query.owner)) || null;

  apriContrattoDaId(contrattoId);
  void caricaGovernance().then(() => {
    if (tabAttivo.value === 'dati') focusCampoDati(campo);
    apriAnagraficaMembro(modifica, ownerId, campo);
  });
  aggiornaQuery();
});

watch(tabAttivo, aggiornaQuery);

// I link dei "dati mancanti" possono puntare a questa stessa pagina: la
// rotta non cambia, il componente non si rimonta, e senza questo watch la
// query cambierebbe senza che succeda nulla.
watch(
  () => route.query,
  (q) => {
    const tab = tabDaRotta();
    if (tab !== tabAttivo.value) tabAttivo.value = tab;
    apriContrattoDaId(Number(primo(q.contratto)) || null);
    if (tab === 'dati') focusCampoDati(primo(q.campo));
    apriAnagraficaMembro(primo(q.modifica), Number(primo(q.owner)) || null, primo(q.campo));
  },
);
</script>

<style scoped>
.vp-immobile {
  max-width: 1060px;
  margin: 0 auto;
}
.vp-immobile__head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: var(--vp-gap-3);
}
.vp-immobile__titolo {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
}
.vp-immobile__nome {
  font-family: var(--vp-font-display);
  font-size: 30px;
  font-weight: 500;
  line-height: 1.1;
  margin: 4px 0 0;
}
.vp-immobile__indirizzo {
  font-size: 14px;
  color: var(--vp-ink-3);
}
.vp-immobile__head-azioni {
  display: flex;
  align-items: center;
  gap: 10px;
}

.vp-immobile__tabs {
  display: flex;
  gap: 4px;
  margin: 0 0 var(--vp-gap-3);
  flex-wrap: wrap;
}
.imm-tab {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 36px;
  padding: 0 15px;
  border-radius: var(--vp-r-pill);
  border: none;
  background: transparent;
  font-family: var(--vp-font-ui);
  font-size: 13.5px;
  font-weight: 500;
  color: var(--vp-ink-2);
  cursor: pointer;
  transition:
    background 0.12s,
    color 0.12s;
}
.imm-tab:hover {
  background: var(--vp-paper-2);
  color: var(--vp-ink);
}
.imm-tab[data-on] {
  background: var(--vp-terra-soft);
  color: var(--vp-terra-deep);
}
.imm-tab:focus-visible {
  outline: 2px solid var(--vp-terra);
  outline-offset: 1px;
}

.vp-immobile__panels {
  background: transparent;
}
.vp-immobile__panel {
  padding: 0;
}

/* Colonna principale e colonna di servizio: le stanze accanto ai dati, la
   configurazione delle spese accanto alle spese. */
.vp-immobile__colonne {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: var(--vp-gap-3);
  align-items: start;
}
.vp-immobile__principale,
.vp-immobile__servizio,
.vp-immobile__pila {
  display: flex;
  flex-direction: column;
  gap: var(--vp-gap-3);
}
@media (max-width: 1023px) {
  .vp-immobile__colonne {
    grid-template-columns: 1fr;
  }
}
</style>
