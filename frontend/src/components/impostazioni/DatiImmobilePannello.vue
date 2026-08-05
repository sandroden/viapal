<template>
  <q-card flat bordered class="vp-card q-mb-md" style="max-width: 720px">
    <q-card-section>
      <div class="vp-section-title">Dati</div>
      <q-form class="q-gutter-md q-mt-sm" @submit.prevent="salvaDati">
        <q-input
          v-model="formNome"
          label="Nome"
          outlined
          dense
          :readonly="!puoModificare"
          :rules="[(v) => !!v?.trim() || 'Il nome è obbligatorio']"
        />
        <q-input
          v-model="formIndirizzo"
          label="Indirizzo"
          outlined
          dense
          :readonly="!puoModificare"
          hint="Come compare nelle email e nella galleria pubblica"
        />

        <!-- Le caselle del quadro "FABBRICATO" della comunicazione di
             cessione: separate dall'indirizzo qui sopra, che resta
             testo libero e non viene ricavato da queste. -->
        <div class="vp-section-title q-mt-md">Indirizzo strutturato</div>
        <div class="vp-hint">
          Serve ai documenti generati (comunicazione di cessione di
          fabbricato), che hanno una casella per ciascun dato.
        </div>
        <div class="row q-col-gutter-sm">
          <div v-for="c in CAMPI_INDIRIZZO" :key="c.campo" class="col-6 col-md-4">
            <q-input
              :ref="(el) => registraCampo(c.campo, el)"
              v-model="formIndirizzoStrutturato[c.campo]"
              :label="c.label"
              outlined
              dense
              :readonly="!puoModificare"
              :data-testid="`immobile-${c.campo}`"
            />
          </div>
        </div>

        <!-- Conto su cui gli inquilini versano: è il conto che finisce
             nel QR di pagamento e che l'app propone quando si registra
             un incasso. Le opzioni sono i conti dei membri. -->
        <q-select
          v-model="formContoUtenze"
          :options="opzioniConto"
          label="Conto per incassi e utenze"
          outlined
          dense
          emit-value
          map-options
          clearable
          :readonly="!puoModificare"
          hint="Dove gli inquilini versano affitto e utenze"
          data-testid="immobile-bank_account_utenze"
        />

        <q-select
          v-model="formFirmatario"
          :options="opzioniFirmatario"
          label="Firma come cedente"
          outlined
          dense
          emit-value
          map-options
          clearable
          :readonly="!puoModificare"
          hint="Il modulo di cessione prevede un dichiarante solo"
          data-testid="immobile-owner_firmatario"
        />

        <q-btn
          v-if="puoModificare"
          type="submit"
          color="primary"
          dense
          label="Salva"
          :loading="savingDati"
          data-testid="salva-dati"
        />
      </q-form>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import { useQuasar, type QInput } from 'quasar';
import { messaggioErrore } from 'src/utils/apiErrors';
import { useOwnerBankAccountsStore } from 'stores/ownerBankAccounts';
import {
  CAMPI_INDIRIZZO,
  usePropertiesStore,
  type IndirizzoStrutturato,
  type PropertyDettaglio,
  type Quota,
} from 'stores/properties';

const props = defineProps<{
  dettaglio: PropertyDettaglio;
  quoteCorrenti: Quota[];
  puoModificare: boolean;
}>();

const emit = defineEmits<{
  (e: 'aggiornato', dettaglio: PropertyDettaglio): void;
}>();

const $q = useQuasar();
const propStore = usePropertiesStore();
const contiStore = useOwnerBankAccountsStore();

const formNome = ref('');
const formIndirizzo = ref('');
const formIndirizzoStrutturato = ref<IndirizzoStrutturato>(indirizzoVuoto());
const formFirmatario = ref<number | null>(null);
const formContoUtenze = ref<number | null>(null);
const savingDati = ref(false);

/** Riferimenti ai campi, per portare il fuoco dove il link dei "dati
 *  mancanti" dice di andare (`?campo=<nome>`). */
const campiIndirizzo = new Map<string, QInput>();

function indirizzoVuoto(): IndirizzoStrutturato {
  return {
    via: '',
    civico: '',
    cap: '',
    comune: '',
    provincia: '',
    piano: '',
    scala: '',
    interno: '',
    vani: '',
    accessori: '',
    ingressi: '',
  };
}

function registraCampo(campo: string, el: unknown) {
  if (el) campiIndirizzo.set(campo, el as QInput);
  else campiIndirizzo.delete(campo);
}

/** Chi può firmare come cedente: i proprietari con quota attiva, cioè la
 *  stessa fonte da cui il generatore ricava la parte locatrice. */
const opzioniFirmatario = computed(() =>
  props.quoteCorrenti.map((q) => ({ label: q.owner_nominativo, value: q.owner })),
);
/** I conti dei membri dell'immobile: l'endpoint è già scopato sull'immobile
 *  attivo, quindi non compaiono conti di estranei. */
const opzioniConto = computed(() =>
  contiStore.accounts.map((c) => ({
    label: `${c.intestatario} — ${c.banca}`,
    value: c.id,
  })),
);

function riempiForm(dati: PropertyDettaglio) {
  formNome.value = dati.nome;
  formIndirizzo.value = dati.indirizzo;
  formFirmatario.value = dati.owner_firmatario;
  formContoUtenze.value = dati.bank_account_utenze;
  const strutturato = indirizzoVuoto();
  for (const c of CAMPI_INDIRIZZO) strutturato[c.campo] = dati[c.campo] ?? '';
  formIndirizzoStrutturato.value = strutturato;
}

watch(() => props.dettaglio, riempiForm, { immediate: true });

/** Porta il fuoco sul campo indicato dal link dei "dati mancanti":
 *  la lettura della query resta alla pagina, qui solo il focus. */
async function focusCampo(nome: string) {
  await nextTick();
  const campo = campiIndirizzo.get(nome);
  campo?.focus();
  campo?.$el?.scrollIntoView({ block: 'center', behavior: 'smooth' });
}

defineExpose({ focusCampo });

async function salvaDati() {
  savingDati.value = true;
  try {
    const aggiornato = await propStore.aggiornaProperty(props.dettaglio.id, {
      nome: formNome.value.trim(),
      indirizzo: formIndirizzo.value.trim(),
      owner_firmatario: formFirmatario.value,
      bank_account_utenze: formContoUtenze.value,
      ...formIndirizzoStrutturato.value,
    });
    emit('aggiornato', aggiornato);
    $q.notify({ type: 'positive', message: 'Dati immobile salvati.' });
  } catch (e: unknown) {
    $q.notify({ type: 'negative', message: messaggioErrore(e, 'Salvataggio non riuscito.') });
  } finally {
    savingDati.value = false;
  }
}
</script>

<style scoped>
.vp-section-title {
  font-weight: 600;
  font-size: 16px;
  color: var(--vp-ink-1);
}
.vp-hint {
  color: var(--vp-ink-3);
  font-size: 13px;
}
</style>
