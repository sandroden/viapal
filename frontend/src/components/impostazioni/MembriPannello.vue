<template>
  <CardSezione
    titolo="Membri e quote"
    descrizione="Chi ha accesso alla casa e come è divisa la proprietà: ruolo e quota sono due facce della stessa riga."
  >
    <template v-if="sonoProprietario" #azioni>
      <BtnSoft
        etichetta="Nuovo assetto quote"
        icona="pencil"
        variante="ghost"
        data-testid="apri-quote"
        @click="apriDialogQuote"
      />
      <BtnSoft etichetta="Invita" data-testid="apri-invito" @click="dialogInvito = true" />
    </template>

    <div class="imm-elenco">
      <RigaElenco
        v-for="(m, i) in membri"
        :key="m.id"
        :ultima="i === membri.length - 1"
        data-testid="riga-membro"
      >
        <template #tile>
          <VpAvatar :name="m.nominativo" :size="34" :hue="tinta(m.nominativo)" />
        </template>
        <template #titolo>{{ m.nominativo }}</template>
        <template #meta>{{ m.email || m.username }}</template>
        <template #azioni>
          <q-select
            v-if="sonoProprietario"
            :model-value="m.ruolo"
            :options="OPZIONI_RUOLO"
            dense
            borderless
            emit-value
            map-options
            class="imm-pillola"
            :aria-label="`Ruolo di ${m.nominativo}`"
            @update:model-value="(r: RuoloProperty) => cambiaRuolo(m, r)"
          />
          <EtichettaStato v-else tono="line">{{ etichettaRuolo(m.ruolo) }}</EtichettaStato>

          <!-- La quota vive sulla riga della persona, ma si cambia solo
               dall'assetto: è un dato con storicità, non un campo. -->
          <span class="vp-mono imm-quota" :class="{ 'imm-quota--vuota': !quotaDi(m) }">
            {{ quotaDi(m) ?? '—' }}
          </span>

          <AzioniRiga
            :oggetto="m.nominativo"
            :puo-modificare="puoAnagrafica(m)"
            :puo-eliminare="sonoProprietario"
            @modifica="apriAnagrafica(m.owner_profile!)"
            @elimina="rimuovi(m)"
          />
        </template>
      </RigaElenco>
      <div v-if="membri.length === 0" class="imm-vuoto">Nessun membro.</div>
    </div>

    <div class="imm-assetto">
      <template v-if="quoteCorrenti.length">
        Assetto in vigore dal {{ formattaData(quoteCorrenti[0]?.valid_from) }} · totale
        {{ totaleQuote }}
      </template>
      <template v-else>Nessuna quota di proprietà configurata.</template>
    </div>
  </CardSezione>

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
          :options="OPZIONI_RUOLO"
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
          data-testid="invito-invia"
          @click="invia"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>

  <!-- Dialog nuovo assetto quote -->
  <q-dialog v-model="dialogQuote">
    <q-card style="width: 420px; max-width: 92vw">
      <q-card-section>
        <div class="vp-section-title">Nuovo assetto quote</div>
        <div class="vp-hint">
          La somma deve fare 100%. Valido dal giorno indicato; le quote
          precedenti vengono chiuse a quella data.
        </div>
      </q-card-section>
      <q-card-section class="q-gutter-sm">
        <q-input v-model="quoteValidFrom" label="Valido dal" type="date" outlined dense />
        <div v-for="riga in quoteForm" :key="riga.user" class="row items-center q-gutter-sm">
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
        <q-btn color="primary" label="Salva assetto" :loading="quoteSaving" @click="salvaAssetto" />
      </q-card-actions>
    </q-card>
  </q-dialog>

  <!-- Dialog anagrafica del membro (deep-link dai "dati mancanti") -->
  <AnagraficaOwnerDialog
    v-model="dialogAnagrafica"
    :owner-id="anagraficaOwnerId"
    :campo="anagraficaCampo"
    @salvato="anagraficaSalvata"
  />
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useQuasar } from 'quasar';
import { messaggioErrore } from 'src/utils/apiErrors';
import { useAuthStore, type RuoloProperty } from 'stores/auth';
import {
  OPZIONI_RUOLO,
  etichettaRuolo,
  usePropertiesStore,
  type Membro,
  type Quota,
} from 'stores/properties';
import { useOwnersStore } from 'stores/owners';
import { useFormatoData } from 'src/composables/useFormatoData';
import VpAvatar from 'components/utenze/VpAvatar.vue';
import AnagraficaOwnerDialog from 'components/impostazioni/AnagraficaOwnerDialog.vue';
import CardSezione from './ui/CardSezione.vue';
import RigaElenco from './ui/RigaElenco.vue';
import EtichettaStato from './ui/EtichettaStato.vue';
import BtnSoft from './ui/BtnSoft.vue';
import AzioniRiga from './ui/AzioniRiga.vue';

const props = defineProps<{
  propertyId: number;
  membri: Membro[];
  quote: Quota[];
  sonoProprietario: boolean;
}>();

const emit = defineEmits<{
  (e: 'aggiornati', membri: Membro[]): void;
  (e: 'aggiornate', quote: Quota[]): void;
}>();

const $q = useQuasar();
const propStore = usePropertiesStore();
const authStore = useAuthStore();
const ownersStore = useOwnersStore();
const { formattaData } = useFormatoData();

// ---------------------------------------------------------------------------
// Quote sulla riga del membro: erano una scheda a parte da tenere allineata
// a mano con quella dei membri.
// ---------------------------------------------------------------------------

const quoteCorrenti = computed(() => props.quote.filter((q) => q.valid_to === null));

function percentuale(quota: string): string {
  return `${(Number(quota) * 100).toFixed(2).replace(/\.00$/, '')}%`;
}

/** Prima per profilo owner (il legame vero), poi per nominativo: i membri
 *  senza profilo owner non hanno quota e mostrano un trattino. */
function quotaDi(m: Membro): string | null {
  const q = quoteCorrenti.value.find(
    (x) =>
      (m.owner_profile !== null && x.owner === m.owner_profile) ||
      x.owner_nominativo === m.nominativo,
  );
  return q ? percentuale(q.quota) : null;
}

const totaleQuote = computed(() => {
  const somma = quoteCorrenti.value.reduce((tot, q) => tot + Number(q.quota), 0);
  return `${(somma * 100).toFixed(2)}%`;
});

/** Tinta dell'avatar stabile per persona: stesso nome, stesso colore a ogni
 *  caricamento, senza doverla salvare da qualche parte. */
function tinta(nome: string): number {
  let h = 0;
  for (const ch of nome) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return h;
}

// ---------------------------------------------------------------------------
// Anagrafica
// ---------------------------------------------------------------------------

const dialogAnagrafica = ref(false);
const anagraficaOwnerId = ref<number | null>(null);
const anagraficaCampo = ref<string | null>(null);

/** Stesso gate del backend: il titolare modifica la propria anagrafica,
 *  i proprietari (e i superuser) quella di tutti i membri. */
function puoAnagrafica(m: Membro): boolean {
  if (!m.owner_profile) return false;
  if (props.sonoProprietario || authStore.isSuperuser) return true;
  return m.user === authStore.user?.id;
}

function apriAnagrafica(ownerId: number, campo: string | null = null) {
  anagraficaOwnerId.value = ownerId;
  anagraficaCampo.value = campo;
  dialogAnagrafica.value = true;
}

async function anagraficaSalvata() {
  // Il nominativo compare nella lista membri e nelle select intestatario:
  // ricarichiamo entrambe le fonti.
  await ownersStore.fetchOwners(true);
  emit('aggiornati', await propStore.caricaMembri(props.propertyId));
}

defineExpose({ apriAnagrafica });

// ---------------------------------------------------------------------------
// Invito e ruoli
// ---------------------------------------------------------------------------

const dialogInvito = ref(false);
const invitoEmail = ref('');
const invitoNominativo = ref('');
const invitoRuolo = ref<RuoloProperty>('proprietario');
const invitoSaving = ref(false);
const invitoErrore = ref('');

async function invia() {
  invitoSaving.value = true;
  invitoErrore.value = '';
  try {
    await propStore.invitaMembro(props.propertyId, {
      email: invitoEmail.value.trim(),
      ruolo: invitoRuolo.value,
      nominativo: invitoNominativo.value.trim(),
    });
    dialogInvito.value = false;
    invitoEmail.value = '';
    invitoNominativo.value = '';
    $q.notify({ type: 'positive', message: 'Invito inviato via email.' });
    emit('aggiornati', await propStore.caricaMembri(props.propertyId));
  } catch (e: unknown) {
    invitoErrore.value = messaggioErrore(e, 'Invito non riuscito.');
  } finally {
    invitoSaving.value = false;
  }
}

async function cambiaRuolo(m: Membro, ruolo: RuoloProperty) {
  if (m.ruolo === ruolo) return;
  try {
    await propStore.cambiaRuoloMembro(props.propertyId, m.id, ruolo);
    emit(
      'aggiornati',
      props.membri.map((x) => (x.id === m.id ? { ...x, ruolo } : x)),
    );
    $q.notify({ type: 'positive', message: `Ruolo di ${m.nominativo} aggiornato.` });
  } catch (e: unknown) {
    $q.notify({ type: 'negative', message: messaggioErrore(e, 'Cambio ruolo non riuscito.') });
    emit('aggiornati', await propStore.caricaMembri(props.propertyId));
  }
}

function rimuovi(m: Membro) {
  $q.dialog({
    title: 'Rimuovere il membro?',
    message: `${m.nominativo} non avrà più accesso a questo immobile.`,
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Rimuovi' },
  }).onOk(() => {
    void (async () => {
      try {
        await propStore.rimuoviMembro(props.propertyId, m.id);
        emit(
          'aggiornati',
          props.membri.filter((x) => x.id !== m.id),
        );
      } catch (e: unknown) {
        $q.notify({
          type: 'negative',
          message: messaggioErrore(e, 'Rimozione non riuscita.'),
        });
      }
    })();
  });
}

// ---------------------------------------------------------------------------
// Assetto quote
// ---------------------------------------------------------------------------

const dialogQuote = ref(false);
const quoteValidFrom = ref(new Date().toISOString().slice(0, 10));
const quoteForm = ref<Array<{ user: number; nominativo: string; percento: string }>>([]);
const quoteSaving = ref(false);
const quoteErrore = ref('');

const totalePercento = computed(() =>
  quoteForm.value.reduce((tot, r) => tot + (Number(r.percento) || 0), 0),
);

function apriDialogQuote() {
  quoteErrore.value = '';
  const proprietari = props.membri.filter((m) => m.ruolo === 'proprietario');
  const attive = new Map(quoteCorrenti.value.map((q) => [q.owner_nominativo, q.quota]));
  quoteForm.value = proprietari.map((m) => ({
    user: m.user,
    nominativo: m.nominativo,
    percento: attive.has(m.nominativo) ? String(Number(attive.get(m.nominativo)) * 100) : '',
  }));
  dialogQuote.value = true;
}

async function salvaAssetto() {
  quoteErrore.value = '';
  if (Math.abs(totalePercento.value - 100) > 0.1) {
    quoteErrore.value = `La somma è ${totalePercento.value.toFixed(2)}%: deve fare 100%.`;
    return;
  }
  quoteSaving.value = true;
  try {
    await propStore.salvaQuote(props.propertyId, {
      valid_from: quoteValidFrom.value,
      quote: quoteForm.value
        .filter((r) => Number(r.percento) > 0)
        .map((r) => ({ user: r.user, quota: (Number(r.percento) / 100).toFixed(4) })),
    });
    dialogQuote.value = false;
    emit('aggiornate', await propStore.caricaQuote(props.propertyId));
    $q.notify({ type: 'positive', message: 'Assetto quote salvato.' });
  } catch (e: unknown) {
    quoteErrore.value = messaggioErrore(e, 'Salvataggio quote non riuscito.');
  } finally {
    quoteSaving.value = false;
  }
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
.imm-quota {
  background: var(--vp-paper-2);
  border-radius: var(--vp-r-pill);
  padding: 5px 11px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--vp-ink);
  white-space: nowrap;
}
.imm-quota--vuota {
  color: var(--vp-ink-4);
  font-weight: 400;
}
.imm-assetto {
  font-size: 11.5px;
  color: var(--vp-ink-3);
  margin-top: 10px;
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
