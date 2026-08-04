<template>
  <q-page padding class="vp-page">
    <div class="vp-page-head row items-center q-gutter-sm">
      <h1 class="vp-h1">Immobile</h1>
      <q-chip v-if="dettaglio" dense outline data-testid="chip-ruolo">
        {{ etichettaRuolo(dettaglio.mio_ruolo) }}
      </q-chip>
      <q-space />
      <q-btn
        dense
        flat
        color="primary"
        icon="add_home"
        label="Nuova proprietà"
        to="/p/proprieta/nuova"
        data-testid="nuova-proprieta"
      />
    </div>

    <div v-if="loading" class="q-pa-lg flex flex-center">
      <q-spinner size="32px" />
    </div>

    <template v-else-if="dettaglio">
      <!-- Dati immobile -->
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

      <!-- Membri -->
      <q-card flat bordered class="vp-card q-mb-md" style="max-width: 720px">
        <q-card-section>
          <div class="row items-center">
            <div class="vp-section-title">Membri</div>
            <q-space />
            <q-btn
              v-if="sonoProprietario"
              dense
              color="primary"
              icon="person_add"
              label="Invita"
              @click="dialogInvito = true"
              data-testid="apri-invito"
            />
          </div>

          <q-list separator class="q-mt-sm">
            <q-item v-for="m in membri" :key="m.id" data-testid="riga-membro">
              <q-item-section>
                <q-item-label>{{ m.nominativo }}</q-item-label>
                <q-item-label caption>{{ m.email || m.username }}</q-item-label>
              </q-item-section>
              <q-item-section side>
                <div class="row items-center q-gutter-sm">
                  <q-select
                    v-if="sonoProprietario"
                    :model-value="m.ruolo"
                    :options="opzioniRuolo"
                    dense
                    outlined
                    emit-value
                    map-options
                    style="min-width: 150px"
                    @update:model-value="(r: RuoloProperty) => cambiaRuolo(m, r)"
                  />
                  <q-chip v-else dense outline>{{ etichettaRuolo(m.ruolo) }}</q-chip>
                  <q-btn
                    v-if="sonoProprietario"
                    flat
                    dense
                    round
                    icon="delete_outline"
                    color="negative"
                    :aria-label="`Rimuovi ${m.nominativo}`"
                    @click="rimuovi(m)"
                  />
                </div>
              </q-item-section>
            </q-item>
          </q-list>
        </q-card-section>
      </q-card>

      <!-- Conti bancari dei membri -->
      <q-card flat bordered class="vp-card q-mb-md" style="max-width: 720px">
        <q-card-section>
          <div class="row items-center">
            <div class="vp-section-title">Conti bancari</div>
            <q-space />
            <q-btn
              dense
              color="primary"
              icon="add"
              label="Nuovo conto"
              data-testid="nuovo-conto"
              @click="apriDialogConto(null)"
            />
          </div>
          <div class="vp-hint q-mt-xs">
            I conti dei membri: da qui si sceglie quello su cui gli inquilini
            versano. Ognuno può modificare solo i propri.
          </div>
          <q-list separator class="q-mt-sm">
            <q-item v-for="c in conti" :key="c.id" data-testid="riga-conto">
              <q-item-section>
                <q-item-label>
                  {{ c.intestatario }} — {{ c.banca }}
                  <q-chip
                    v-if="c.id === dettaglio.bank_account_utenze"
                    dense
                    outline
                    class="q-ml-xs"
                  >
                    incassi e utenze
                  </q-chip>
                </q-item-label>
                <q-item-label caption>
                  {{ c.iban }}
                  <template v-if="!c.attivo"> · non attivo</template>
                </q-item-label>
              </q-item-section>
              <q-item-section side>
                <div class="row items-center q-gutter-xs">
                  <q-btn
                    v-if="c.owner === mioOwnerProfileId || sonoSuperuser"
                    flat
                    dense
                    round
                    icon="edit"
                    :aria-label="`Modifica conto ${c.banca}`"
                    @click="apriDialogConto(c)"
                  />
                  <q-btn
                    v-if="c.owner === mioOwnerProfileId || sonoSuperuser"
                    flat
                    dense
                    round
                    icon="delete_outline"
                    color="negative"
                    :aria-label="`Elimina conto ${c.banca}`"
                    @click="eliminaConto(c)"
                  />
                </div>
              </q-item-section>
            </q-item>
            <q-item v-if="conti.length === 0">
              <q-item-section class="text-grey">
                Nessun conto registrato: senza, gli inquilini non hanno un
                IBAN su cui versare.
              </q-item-section>
            </q-item>
          </q-list>
        </q-card-section>
      </q-card>

      <!-- Quote -->
      <q-card flat bordered class="vp-card q-mb-md" style="max-width: 720px">
        <q-card-section>
          <div class="row items-center">
            <div class="vp-section-title">Quote di proprietà</div>
            <q-space />
            <q-btn
              v-if="sonoProprietario"
              dense
              flat
              color="primary"
              icon="edit"
              label="Nuovo assetto"
              @click="apriDialogQuote"
              data-testid="apri-quote"
            />
          </div>
          <q-list separator class="q-mt-sm">
            <q-item v-for="q in quoteCorrenti" :key="q.id">
              <q-item-section>
                <q-item-label>{{ q.owner_nominativo }}</q-item-label>
                <q-item-label caption>dal {{ q.valid_from }}</q-item-label>
              </q-item-section>
              <q-item-section side>
                <q-chip dense>{{ percentuale(q.quota) }}</q-chip>
              </q-item-section>
            </q-item>
            <q-item v-if="quoteCorrenti.length === 0">
              <q-item-section class="text-grey">
                Nessuna quota attiva configurata.
              </q-item-section>
            </q-item>
          </q-list>
        </q-card-section>
      </q-card>
    </template>

    <!-- Dialog invito -->
    <q-dialog v-model="dialogInvito">
      <q-card style="min-width: 380px">
        <q-card-section>
          <div class="vp-section-title">Invita un membro</div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input
            v-model="invitoEmail"
            label="Email"
            type="email"
            outlined
            dense
            autofocus
            data-testid="invito-email"
          />
          <q-input
            v-model="invitoNominativo"
            label="Nome e cognome (facoltativo)"
            outlined
            dense
            data-testid="invito-nominativo"
          />
          <q-select
            v-model="invitoRuolo"
            :options="opzioniRuolo"
            label="Ruolo"
            outlined
            dense
            emit-value
            map-options
          />
          <q-banner v-if="invitoErrore" class="vp-banner-errore" rounded dense>
            {{ invitoErrore }}
          </q-banner>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn v-close-popup flat label="Annulla" />
          <q-btn
            color="primary"
            label="Invia invito"
            :loading="invitoSaving"
            @click="invia"
            data-testid="invito-invia"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Dialog conto bancario -->
    <q-dialog v-model="dialogConto">
      <q-card style="min-width: 420px">
        <q-card-section>
          <div class="vp-section-title">
            {{ contoInModifica ? 'Modifica conto' : 'Nuovo conto' }}
          </div>
          <div class="vp-hint">
            {{
              sonoSuperuser
                ? 'Da superuser puoi gestire i conti di tutti i membri.'
                : 'Il conto è tuo: gli altri membri lo vedono ma non lo modificano.'
            }}
          </div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-select
            v-if="sonoSuperuser && !contoInModifica"
            v-model="formContoOwner"
            :options="opzioniIntestatario"
            label="Membro intestatario"
            outlined
            dense
            emit-value
            map-options
            data-testid="conto-owner"
            @update:model-value="precompilaIntestatario"
          />
          <q-input
            v-model="formConto.banca"
            label="Banca"
            outlined
            dense
            autofocus
            data-testid="conto-banca"
          />
          <q-input
            v-model="formConto.intestatario"
            label="Intestatario"
            outlined
            dense
            data-testid="conto-intestatario"
          />
          <q-input
            v-model="formConto.iban"
            label="IBAN"
            outlined
            dense
            data-testid="conto-iban"
          />
          <q-toggle v-model="formConto.attivo" label="Attivo" />
          <q-banner v-if="erroreConto" class="vp-banner-errore" rounded dense>
            {{ erroreConto }}
          </q-banner>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn v-close-popup flat label="Annulla" />
          <q-btn
            color="primary"
            label="Salva"
            :loading="savingConto"
            data-testid="salva-conto"
            @click="salvaConto"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Dialog nuovo assetto quote -->
    <q-dialog v-model="dialogQuote">
      <q-card style="min-width: 420px">
        <q-card-section>
          <div class="vp-section-title">Nuovo assetto quote</div>
          <div class="vp-hint">
            La somma deve fare 100%. Valido dal giorno indicato; le quote
            precedenti vengono chiuse a quella data.
          </div>
        </q-card-section>
        <q-card-section class="q-gutter-sm">
          <q-input
            v-model="quoteValidFrom"
            label="Valido dal"
            type="date"
            outlined
            dense
          />
          <div
            v-for="riga in quoteForm"
            :key="riga.user"
            class="row items-center q-gutter-sm"
          >
            <div class="col">{{ riga.nominativo }}</div>
            <q-input
              v-model="riga.percento"
              type="number"
              dense
              outlined
              suffix="%"
              style="width: 110px"
              min="0"
              max="100"
              step="0.01"
            />
          </div>
          <div class="vp-hint">Totale: {{ totalePercento.toFixed(2) }}%</div>
          <q-banner v-if="quoteErrore" class="vp-banner-errore" rounded dense>
            {{ quoteErrore }}
          </q-banner>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn v-close-popup flat label="Annulla" />
          <q-btn
            color="primary"
            label="Salva assetto"
            :loading="quoteSaving"
            @click="salvaAssetto"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue';
import { useQuasar, type QInput } from 'quasar';
import { useRoute } from 'vue-router';
import { api } from 'boot/axios';
import { messaggioErrore } from 'src/utils/apiErrors';
import { useAuthStore, type RuoloProperty } from 'stores/auth';
import { useOwnerBankAccountsStore } from 'stores/ownerBankAccounts';
import {
  CAMPI_INDIRIZZO,
  usePropertiesStore,
  type IndirizzoStrutturato,
  type Membro,
  type PropertyDettaglio,
  type Quota,
} from 'stores/properties';

const $q = useQuasar();
const route = useRoute();
const propStore = usePropertiesStore();
const auth = useAuthStore();
const contiStore = useOwnerBankAccountsStore();

interface ContoBancario {
  id: number;
  owner: number;
  owner_nominativo: string;
  banca: string;
  intestatario: string;
  iban: string;
  attivo: boolean;
}

const loading = ref(true);
const dettaglio = ref<PropertyDettaglio | null>(null);
const membri = ref<Membro[]>([]);
const quote = ref<Quota[]>([]);

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

const dialogInvito = ref(false);
const invitoEmail = ref('');
const invitoNominativo = ref('');
const invitoRuolo = ref<RuoloProperty>('proprietario');
const invitoSaving = ref(false);
const invitoErrore = ref('');

const conti = ref<ContoBancario[]>([]);
const dialogConto = ref(false);
const contoInModifica = ref<ContoBancario | null>(null);
const formConto = ref({ banca: '', intestatario: '', iban: '', attivo: true });
/** Solo superuser: profilo proprietario per cui si crea il conto. */
const formContoOwner = ref<number | null>(null);
const savingConto = ref(false);
const erroreConto = ref('');

const dialogQuote = ref(false);
const quoteValidFrom = ref(new Date().toISOString().slice(0, 10));
const quoteForm = ref<Array<{ user: number; nominativo: string; percento: string }>>([]);
const quoteSaving = ref(false);
const quoteErrore = ref('');

const opzioniRuolo = [
  { label: 'Proprietario', value: 'proprietario' },
  { label: 'Gestore', value: 'gestore' },
  { label: 'Sola lettura', value: 'sola_lettura' },
];

const mioOwnerProfileId = computed(() => auth.user?.owner_profile_id ?? null);
const sonoSuperuser = computed(() => !!auth.user?.is_superuser);
const sonoProprietario = computed(() => dettaglio.value?.mio_ruolo === 'proprietario');
const puoModificare = computed(
  () => dettaglio.value?.mio_ruolo === 'proprietario' || dettaglio.value?.mio_ruolo === 'gestore',
);
const quoteCorrenti = computed(() => quote.value.filter((q) => q.valid_to === null));
/** Chi può firmare come cedente: i proprietari con quota attiva, cioè la
 *  stessa fonte da cui il generatore ricava la parte locatrice. */
const opzioniFirmatario = computed(() =>
  quoteCorrenti.value.map((q) => ({ label: q.owner_nominativo, value: q.owner })),
);
/** I conti dei membri dell'immobile: l'endpoint è già scopato sull'immobile
 *  attivo, quindi non compaiono conti di estranei. */
const opzioniConto = computed(() =>
  contiStore.accounts.map((c) => ({
    label: `${c.intestatario} — ${c.banca}`,
    value: c.id,
  })),
);
const totalePercento = computed(() =>
  quoteForm.value.reduce((tot, r) => tot + (Number(r.percento) || 0), 0),
);
/** I membri con profilo proprietario: gli intestatari possibili quando il
 *  superuser crea un conto a nome altrui. */
const opzioniIntestatario = computed(() =>
  membri.value
    .filter((m) => m.owner_profile !== null)
    .map((m) => ({ label: m.nominativo, value: m.owner_profile as number })),
);

function etichettaRuolo(ruolo: RuoloProperty | null): string {
  const opzione = opzioniRuolo.find((o) => o.value === ruolo);
  return opzione?.label ?? '';
}

function percentuale(quota: string): string {
  return `${(Number(quota) * 100).toFixed(2).replace(/\.00$/, '')}%`;
}

async function carica() {
  const id = propStore.activePropertyId;
  if (!id) return;
  loading.value = true;
  try {
    dettaglio.value = await propStore.caricaDettaglio(id);
    riempiForm(dettaglio.value);
    await contiStore.ensureLoaded(true);
    membri.value = await propStore.caricaMembri(id);
    await caricaConti();
    quote.value = await propStore.caricaQuote(id);
  } finally {
    loading.value = false;
  }
  await focusCampoDaRotta();
}

function riempiForm(dati: PropertyDettaglio) {
  formNome.value = dati.nome;
  formIndirizzo.value = dati.indirizzo;
  formFirmatario.value = dati.owner_firmatario;
  formContoUtenze.value = dati.bank_account_utenze;
  const strutturato = indirizzoVuoto();
  for (const c of CAMPI_INDIRIZZO) strutturato[c.campo] = dati[c.campo] ?? '';
  formIndirizzoStrutturato.value = strutturato;
}

/** Deep link `?campo=<nome>`: il link dei dati mancanti deve atterrare sul
 *  campo, non genericamente sulla pagina. */
async function focusCampoDaRotta() {
  const q = route.query.campo;
  const nome = Array.isArray(q) ? q[0] : q;
  if (!nome) return;
  await nextTick();
  const campo = campiIndirizzo.get(nome);
  campo?.focus();
  campo?.$el?.scrollIntoView({ block: 'center', behavior: 'smooth' });
}

async function salvaDati() {
  if (!dettaglio.value) return;
  savingDati.value = true;
  try {
    dettaglio.value = await propStore.aggiornaProperty(dettaglio.value.id, {
      nome: formNome.value.trim(),
      indirizzo: formIndirizzo.value.trim(),
      owner_firmatario: formFirmatario.value,
      bank_account_utenze: formContoUtenze.value,
      ...formIndirizzoStrutturato.value,
    });
    riempiForm(dettaglio.value);
    $q.notify({ type: 'positive', message: 'Dati immobile salvati.' });
  } catch (e: unknown) {
    $q.notify({ type: 'negative', message: messaggioErrore(e, 'Salvataggio non riuscito.') });
  } finally {
    savingDati.value = false;
  }
}

async function caricaConti() {
  const { data } = await api.get<ContoBancario[] | { results: ContoBancario[] }>(
    '/api/v1/bank-accounts/',
  );
  conti.value = Array.isArray(data) ? data : (data.results ?? []);
}

function apriDialogConto(c: ContoBancario | null) {
  contoInModifica.value = c;
  erroreConto.value = '';
  formConto.value = {
    banca: c?.banca ?? '',
    intestatario: c?.intestatario ?? '',
    iban: c?.iban ?? '',
    attivo: c?.attivo ?? true,
  };
  formContoOwner.value = c?.owner ?? mioOwnerProfileId.value;
  dialogConto.value = true;
}

/** Alla scelta del membro, propone il suo nominativo come intestatario
 *  (se il campo non è già stato compilato a mano). */
function precompilaIntestatario(ownerId: number | null) {
  if (formConto.value.intestatario.trim()) return;
  const scelto = opzioniIntestatario.value.find((o) => o.value === ownerId);
  if (scelto) formConto.value.intestatario = scelto.label;
}

async function salvaConto() {
  erroreConto.value = '';
  const f = formConto.value;
  if (!f.banca.trim() || !f.intestatario.trim() || !f.iban.trim()) {
    erroreConto.value = 'Banca, intestatario e IBAN sono obbligatori.';
    return;
  }
  if (sonoSuperuser.value && !contoInModifica.value && !formContoOwner.value) {
    erroreConto.value = 'Scegli il membro intestatario del conto.';
    return;
  }
  savingConto.value = true;
  const payload: Record<string, unknown> = {
    banca: f.banca.trim(),
    intestatario: f.intestatario.trim(),
    iban: f.iban.replace(/\s+/g, '').toUpperCase(),
    attivo: f.attivo,
  };
  // Il backend accetta l'owner esplicito solo dal superuser; per gli altri
  // il conto è sempre il proprio.
  if (sonoSuperuser.value && !contoInModifica.value) {
    payload.owner = formContoOwner.value;
  }
  try {
    if (contoInModifica.value) {
      await api.patch(`/api/v1/bank-accounts/${contoInModifica.value.id}/`, payload);
    } else {
      await api.post('/api/v1/bank-accounts/', payload);
    }
    dialogConto.value = false;
    await caricaConti();
    // Il select del conto dell'immobile pesca dallo store: va riallineato.
    await contiStore.ensureLoaded(true);
    $q.notify({ type: 'positive', message: 'Conto salvato.' });
  } catch (e: unknown) {
    erroreConto.value = messaggioErrore(e, 'Salvataggio non riuscito.');
  } finally {
    savingConto.value = false;
  }
}

function eliminaConto(c: ContoBancario) {
  $q.dialog({
    title: 'Eliminare il conto?',
    message: `${c.intestatario} — ${c.banca} verrà rimosso.`,
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Elimina' },
  }).onOk(() => {
    void (async () => {
      try {
        await api.delete(`/api/v1/bank-accounts/${c.id}/`);
        await caricaConti();
        await contiStore.ensureLoaded(true);
        $q.notify({ type: 'positive', message: 'Conto eliminato.' });
      } catch (e: unknown) {
        $q.notify({
          type: 'negative',
          message: messaggioErrore(e, 'Eliminazione non riuscita: ha movimenti collegati.'),
        });
      }
    })();
  });
}

async function invia() {
  if (!dettaglio.value) return;
  invitoSaving.value = true;
  invitoErrore.value = '';
  try {
    await propStore.invitaMembro(dettaglio.value.id, {
      email: invitoEmail.value.trim(),
      ruolo: invitoRuolo.value,
      nominativo: invitoNominativo.value.trim(),
    });
    dialogInvito.value = false;
    invitoEmail.value = '';
    invitoNominativo.value = '';
    $q.notify({ type: 'positive', message: 'Invito inviato via email.' });
    membri.value = await propStore.caricaMembri(dettaglio.value.id);
  } catch (e: unknown) {
    invitoErrore.value = messaggioErrore(e, 'Invito non riuscito.');
  } finally {
    invitoSaving.value = false;
  }
}

async function cambiaRuolo(m: Membro, ruolo: RuoloProperty) {
  if (!dettaglio.value || m.ruolo === ruolo) return;
  try {
    await propStore.cambiaRuoloMembro(dettaglio.value.id, m.id, ruolo);
    m.ruolo = ruolo;
    $q.notify({ type: 'positive', message: `Ruolo di ${m.nominativo} aggiornato.` });
  } catch (e: unknown) {
    $q.notify({ type: 'negative', message: messaggioErrore(e, 'Cambio ruolo non riuscito.') });
    membri.value = await propStore.caricaMembri(dettaglio.value.id);
  }
}

function rimuovi(m: Membro) {
  if (!dettaglio.value) return;
  $q.dialog({
    title: 'Rimuovere il membro?',
    message: `${m.nominativo} non avrà più accesso a questo immobile.`,
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Rimuovi' },
  }).onOk(() => {
    void (async () => {
      try {
        await propStore.rimuoviMembro(dettaglio.value!.id, m.id);
        membri.value = membri.value.filter((x) => x.id !== m.id);
      } catch (e: unknown) {
        $q.notify({
          type: 'negative',
          message: messaggioErrore(e, 'Rimozione non riuscita.'),
        });
      }
    })();
  });
}

function apriDialogQuote() {
  quoteErrore.value = '';
  const proprietari = membri.value.filter((m) => m.ruolo === 'proprietario');
  const attive = new Map(quoteCorrenti.value.map((q) => [q.owner_nominativo, q.quota]));
  quoteForm.value = proprietari.map((m) => ({
    user: m.user,
    nominativo: m.nominativo,
    percento: attive.has(m.nominativo)
      ? String(Number(attive.get(m.nominativo)) * 100)
      : '',
  }));
  dialogQuote.value = true;
}

async function salvaAssetto() {
  if (!dettaglio.value) return;
  quoteErrore.value = '';
  if (Math.abs(totalePercento.value - 100) > 0.1) {
    quoteErrore.value = `La somma è ${totalePercento.value.toFixed(2)}%: deve fare 100%.`;
    return;
  }
  quoteSaving.value = true;
  try {
    await propStore.salvaQuote(dettaglio.value.id, {
      valid_from: quoteValidFrom.value,
      quote: quoteForm.value
        .filter((r) => Number(r.percento) > 0)
        .map((r) => ({
          user: r.user,
          quota: (Number(r.percento) / 100).toFixed(4),
        })),
    });
    dialogQuote.value = false;
    quote.value = await propStore.caricaQuote(dettaglio.value.id);
    $q.notify({ type: 'positive', message: 'Assetto quote salvato.' });
  } catch (e: unknown) {
    quoteErrore.value = messaggioErrore(e, 'Salvataggio quote non riuscito.');
  } finally {
    quoteSaving.value = false;
  }
}

onMounted(carica);
</script>

<style scoped>
.vp-page-head {
  margin-bottom: var(--vp-gap-4);
}
.vp-h1 {
  font-size: 26px;
  line-height: 1.2;
  margin: 0;
}
.vp-section-title {
  font-weight: 600;
  font-size: 16px;
  color: var(--vp-ink-1);
}
.vp-hint {
  color: var(--vp-ink-3);
  font-size: 13px;
}
.vp-banner-errore {
  background: var(--vp-clay-soft, #fbeae5);
  color: var(--vp-clay-deep, #8c3b21);
}
</style>
