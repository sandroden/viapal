<template>
  <q-page padding class="vp-page">
    <div class="vp-page-head row items-center q-gutter-sm">
      <h1 class="vp-h1">Immobile</h1>
      <q-chip v-if="dettaglio" dense outline data-testid="chip-ruolo">
        {{ etichettaRuolo(dettaglio.mio_ruolo) }}
      </q-chip>
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
import { computed, onMounted, ref } from 'vue';
import { isAxiosError } from 'axios';
import { useQuasar } from 'quasar';
import { type RuoloProperty } from 'stores/auth';
import {
  usePropertiesStore,
  type Membro,
  type PropertyDettaglio,
  type Quota,
} from 'stores/properties';

const $q = useQuasar();
const propStore = usePropertiesStore();

const loading = ref(true);
const dettaglio = ref<PropertyDettaglio | null>(null);
const membri = ref<Membro[]>([]);
const quote = ref<Quota[]>([]);

const formNome = ref('');
const formIndirizzo = ref('');
const savingDati = ref(false);

const dialogInvito = ref(false);
const invitoEmail = ref('');
const invitoNominativo = ref('');
const invitoRuolo = ref<RuoloProperty>('proprietario');
const invitoSaving = ref(false);
const invitoErrore = ref('');

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

const sonoProprietario = computed(() => dettaglio.value?.mio_ruolo === 'proprietario');
const puoModificare = computed(
  () => dettaglio.value?.mio_ruolo === 'proprietario' || dettaglio.value?.mio_ruolo === 'gestore',
);
const quoteCorrenti = computed(() => quote.value.filter((q) => q.valid_to === null));
const totalePercento = computed(() =>
  quoteForm.value.reduce((tot, r) => tot + (Number(r.percento) || 0), 0),
);

function etichettaRuolo(ruolo: RuoloProperty | null): string {
  const opzione = opzioniRuolo.find((o) => o.value === ruolo);
  return opzione?.label ?? '';
}

function percentuale(quota: string): string {
  return `${(Number(quota) * 100).toFixed(2).replace(/\.00$/, '')}%`;
}

function messaggioErrore(e: unknown, fallback: string): string {
  if (isAxiosError(e)) {
    return (e.response?.data as { detail?: string })?.detail ?? fallback;
  }
  return fallback;
}

async function carica() {
  const id = propStore.activePropertyId;
  if (!id) return;
  loading.value = true;
  try {
    dettaglio.value = await propStore.caricaDettaglio(id);
    formNome.value = dettaglio.value.nome;
    formIndirizzo.value = dettaglio.value.indirizzo;
    membri.value = await propStore.caricaMembri(id);
    quote.value = await propStore.caricaQuote(id);
  } finally {
    loading.value = false;
  }
}

async function salvaDati() {
  if (!dettaglio.value) return;
  savingDati.value = true;
  try {
    dettaglio.value = await propStore.aggiornaProperty(dettaglio.value.id, {
      nome: formNome.value.trim(),
      indirizzo: formIndirizzo.value.trim(),
    });
    $q.notify({ type: 'positive', message: 'Dati immobile salvati.' });
  } catch (e: unknown) {
    $q.notify({ type: 'negative', message: messaggioErrore(e, 'Salvataggio non riuscito.') });
  } finally {
    savingDati.value = false;
  }
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
