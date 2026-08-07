<template>
  <CardSezione
    titolo="Conti bancari"
    descrizione="I conti in uso su questo immobile: da qui si sceglie quello su cui gli inquilini versano. Ognuno può modificare solo i propri."
  >
    <template #azioni>
      <BtnSoft
        v-if="puoGestire"
        etichetta="Usa un conto esistente"
        data-testid="usa-conto-esistente"
        @click="apriDialogCollega"
      />
      <BtnSoft etichetta="Nuovo conto" data-testid="nuovo-conto" @click="apriDialogConto(null)" />
    </template>

    <div class="imm-elenco">
      <RigaElenco
        v-for="(c, i) in conti"
        :key="c.id"
        :ultima="i === conti.length - 1"
        data-testid="riga-conto"
      >
        <template #tile>
          <TileIcona
            icona="wallet"
            :colore="c.id === contoUtenzeId ? 'var(--vp-terra)' : 'var(--vp-ink-3)'"
            :bg="c.id === contoUtenzeId ? 'var(--vp-terra-soft)' : 'var(--vp-paper-2)'"
          />
        </template>
        <template #titolo>{{ c.intestatario }} — {{ c.banca }}</template>
        <template #badge>
          <EtichettaStato v-if="c.id === contoUtenzeId" tono="terra">
            Incassi e utenze
          </EtichettaStato>
          <EtichettaStato v-if="!c.attivo" tono="off">Non attivo</EtichettaStato>
        </template>
        <template #meta>
          <span class="vp-mono imm-iban">{{ c.iban }}</span>
        </template>
        <template #azioni>
          <AzioniRiga
            :oggetto="`conto ${c.banca}`"
            :puo-modificare="c.owner === mioOwnerProfileId || sonoSuperuser"
            :puo-eliminare="c.owner === mioOwnerProfileId || sonoSuperuser"
            @modifica="apriDialogConto(c)"
            @elimina="eliminaConto(c)"
          >
            <BtnIcona
              v-if="puoGestire"
              icona="x"
              :etichetta="`Togli il conto ${c.banca} da questo immobile`"
              tooltip="Togli da questo immobile"
              data-testid="scollega-conto"
              @click="scollegaConto(c)"
            />
          </AzioniRiga>
        </template>
      </RigaElenco>
      <div v-if="conti.length === 0" class="imm-vuoto">
        Nessun conto in uso su questo immobile: senza, gli inquilini non hanno un IBAN su
        cui versare.
      </div>
    </div>
  </CardSezione>

  <!-- Dialog: mette in uso su questo immobile un conto che esiste già -->
  <q-dialog v-model="dialogCollega">
    <q-card style="min-width: 420px">
      <q-card-section>
        <div class="vp-section-title">Usa un conto esistente</div>
        <div class="vp-hint">
          I conti dei membri non ancora in uso su questo immobile. Metterlo in uso lo rende
          selezionabile come destinazione dei bonifici.
        </div>
      </q-card-section>
      <q-card-section>
        <q-select
          v-model="contoDaCollegare"
          :options="opzioniCollegabili"
          label="Conto"
          outlined
          dense
          emit-value
          map-options
          data-testid="conto-da-collegare"
        />
        <div v-if="opzioniCollegabili.length === 0" class="imm-vuoto">
          Nessun altro conto disponibile: tutti quelli dei membri sono già in uso qui.
        </div>
        <q-banner v-if="erroreCollega" class="vp-banner-errore q-mt-md" rounded dense>
          {{ erroreCollega }}
        </q-banner>
      </q-card-section>
      <q-card-actions align="right">
        <q-btn v-close-popup flat label="Annulla" />
        <q-btn
          color="primary"
          label="Usa qui"
          :disable="!contoDaCollegare"
          :loading="collegando"
          data-testid="conferma-collega"
          @click="collegaConto"
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
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { api } from 'boot/axios';
import { messaggioErrore } from 'src/utils/apiErrors';
import { useAuthStore } from 'stores/auth';
import { useOwnerBankAccountsStore, type BankAccountFull } from 'stores/ownerBankAccounts';
import { usePropertiesStore, type Membro } from 'stores/properties';
import CardSezione from './ui/CardSezione.vue';
import RigaElenco from './ui/RigaElenco.vue';
import TileIcona from './ui/TileIcona.vue';
import EtichettaStato from './ui/EtichettaStato.vue';
import BtnSoft from './ui/BtnSoft.vue';
import BtnIcona from './ui/BtnIcona.vue';
import AzioniRiga from './ui/AzioniRiga.vue';

/** Un conto di un membro non ancora in uso su questo immobile. */
interface ContoCollegabile {
  id: number;
  owner: number;
  owner_nominativo: string;
  banca: string;
  intestatario: string;
  iban_finale: string;
}

const props = defineProps<{
  /** Il conto scelto in "Dati" come conto per incassi e utenze (chip). */
  contoUtenzeId: number | null;
  membri: Membro[];
}>();

const $q = useQuasar();
const auth = useAuthStore();
const contiStore = useOwnerBankAccountsStore();
const propStore = usePropertiesStore();

const conti = ref<BankAccountFull[]>([]);
const dialogCollega = ref(false);
const collegabili = ref<ContoCollegabile[]>([]);
const contoDaCollegare = ref<number | null>(null);
const collegando = ref(false);
const erroreCollega = ref('');
const dialogConto = ref(false);
const contoInModifica = ref<BankAccountFull | null>(null);
const formConto = ref({ banca: '', intestatario: '', iban: '', attivo: true });
/** Solo superuser: profilo proprietario per cui si crea il conto. */
const formContoOwner = ref<number | null>(null);
const savingConto = ref(false);
const erroreConto = ref('');

const mioOwnerProfileId = computed(() => auth.user?.owner_profile_id ?? null);
const sonoSuperuser = computed(() => !!auth.user?.is_superuser);
/** Mettere in uso o togliere un conto è gestione dell'immobile, non
 *  titolarità del conto: stesso gate del backend. */
const puoGestire = computed(
  () =>
    sonoSuperuser.value ||
    propStore.mioRuolo === 'proprietario' ||
    propStore.mioRuolo === 'gestore',
);
/** Nel select non va l'IBAN intero: è il solo punto in cui compaiono conti
 *  estranei a questo immobile. */
const opzioniCollegabili = computed(() =>
  collegabili.value.map((c) => ({
    label: `${c.intestatario} — ${c.banca} (…${c.iban_finale})`,
    value: c.id,
  })),
);
/** I membri con profilo proprietario: gli intestatari possibili quando il
 *  superuser crea un conto a nome altrui. */
const opzioniIntestatario = computed(() =>
  props.membri
    .filter((m) => m.owner_profile !== null)
    .map((m) => ({ label: m.nominativo, value: m.owner_profile as number })),
);

async function caricaConti() {
  const { data } = await api.get<BankAccountFull[] | { results: BankAccountFull[] }>(
    '/api/v1/bank-accounts/',
  );
  conti.value = Array.isArray(data) ? data : (data.results ?? []);
}

async function apriDialogCollega() {
  erroreCollega.value = '';
  contoDaCollegare.value = null;
  try {
    const { data } = await api.get<ContoCollegabile[]>('/api/v1/bank-accounts/collegabili/');
    collegabili.value = data;
  } catch {
    collegabili.value = [];
  }
  dialogCollega.value = true;
}

async function collegaConto() {
  if (!contoDaCollegare.value) return;
  collegando.value = true;
  erroreCollega.value = '';
  try {
    await api.post(`/api/v1/bank-accounts/${contoDaCollegare.value}/collega/`);
    dialogCollega.value = false;
    await ricaricaTutto();
    $q.notify({ type: 'positive', message: 'Conto ora in uso su questo immobile.' });
  } catch (e: unknown) {
    erroreCollega.value = messaggioErrore(e, 'Operazione non riuscita.');
  } finally {
    collegando.value = false;
  }
}

function scollegaConto(c: BankAccountFull) {
  $q.dialog({
    title: 'Togliere il conto da questo immobile?',
    message:
      `${c.intestatario} — ${c.banca} non comparirà più fra le destinazioni dei ` +
      'bonifici e i suoi movimenti spariranno dalla riconciliazione di questo ' +
      'immobile. Il conto e i suoi dati restano intatti.',
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'primary', label: 'Togli' },
  }).onOk(() => {
    void (async () => {
      try {
        await api.post(`/api/v1/bank-accounts/${c.id}/scollega/`);
        await ricaricaTutto();
        $q.notify({ type: 'positive', message: 'Conto tolto da questo immobile.' });
      } catch (e: unknown) {
        $q.notify({
          type: 'negative',
          message: messaggioErrore(e, 'Operazione non riuscita.'),
        });
      }
    })();
  });
}

/** L'elenco e lo store da cui pescano i select del conto: sempre insieme. */
async function ricaricaTutto() {
  await caricaConti();
  await contiStore.ensureLoaded(true);
}

function apriDialogConto(c: BankAccountFull | null) {
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
    // Il select del conto dell'immobile pesca dallo store: va riallineato.
    await ricaricaTutto();
    $q.notify({ type: 'positive', message: 'Conto salvato.' });
  } catch (e: unknown) {
    erroreConto.value = messaggioErrore(e, 'Salvataggio non riuscito.');
  } finally {
    savingConto.value = false;
  }
}

function eliminaConto(c: BankAccountFull) {
  $q.dialog({
    title: 'Eliminare il conto?',
    message:
      `${c.intestatario} — ${c.banca} verrà rimosso ovunque. Se serve solo ` +
      'toglierlo da questo immobile, usa «Togli da questo immobile».',
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Elimina' },
  }).onOk(() => {
    void (async () => {
      try {
        await api.delete(`/api/v1/bank-accounts/${c.id}/`);
        await ricaricaTutto();
        $q.notify({ type: 'positive', message: 'Conto eliminato.' });
      } catch (e: unknown) {
        $q.notify({
          type: 'negative',
          message: messaggioErrore(
            e,
            'Eliminazione non riuscita: ha movimenti collegati. Puoi toglierlo da questo immobile.',
          ),
        });
      }
    })();
  });
}

onMounted(caricaConti);
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
.imm-iban {
  font-size: 11.5px;
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
