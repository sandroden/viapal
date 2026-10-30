<template>
  <q-dialog v-model="dialogModel">
    <q-card style="width: 480px; max-width: min(560px, 92vw)">
      <q-card-section>
        <div class="vp-asg__titolo">
          {{ isUnitaIntera ? 'Assegna appartamento' : 'Assegna stanza' }} a
          {{ tenantNominativo }}
        </div>
      </q-card-section>
      <q-card-section class="q-gutter-md">
        <q-banner
          v-if="isUnitaIntera && unitaOccupata"
          class="vp-asg__banner-warn"
          rounded
          dense
          data-testid="assegna-unita-occupata"
        >
          Appartamento occupato — per sostituire l'inquilino usa il wizard
          "Cessione" dal dettaglio dell'inquilino attuale.
        </q-banner>
        <q-select
          v-if="!isUnitaIntera"
          v-model="form.room"
          :options="opzioniStanze"
          label="Stanza"
          outlined
          dense
          emit-value
          map-options
          :loading="loadingStanze"
          hint="Solo stanze libere o in liberazione entro 2 mesi."
          data-testid="assegna-stanza"
        />
        <q-banner
          v-if="!isUnitaIntera && !loadingStanze && opzioniStanze.length === 0"
          class="vp-asg__banner-warn"
          rounded
          dense
        >
          Nessuna stanza libera o in liberazione entro 2 mesi. Per un subentro
          in una stanza occupata usa il wizard "Cessione" dalla stanza stessa.
        </q-banner>
        <q-input
          v-model="form.validFrom"
          label="Data inizio"
          type="date"
          outlined
          dense
          data-testid="assegna-data-inizio"
        />
        <q-input
          v-model="form.validTo"
          label="Data fine"
          type="date"
          outlined
          dense
          clearable
          :max="fineMassima ?? undefined"
          :hint="hintDataFine"
          :error="!!fineMassima && !form.validTo"
          :error-message="hintDataFine"
          data-testid="assegna-data-fine"
        />
        <div>
          <div class="vp-asg__label">Ciclo di fatturazione</div>
          <q-btn-toggle
            v-model="form.ciclo"
            no-caps
            unelevated
            toggle-color="primary"
            :options="OPZIONI_CICLO"
            data-testid="assegna-ciclo"
          />
        </div>
        <q-input
          v-model="form.canoneMensile"
          label="Canone mensile"
          type="number"
          min="0"
          step="0.01"
          suffix="€"
          outlined
          dense
          data-testid="assegna-canone"
        />
        <!-- Sotto quale contratto entra: decide quali carte del contratto
             l'inquilino vedrà nella sua area. Senza contratto non ne vede
             nessuna. -->
        <q-select
          v-model="form.contract"
          :options="opzioniContratti"
          label="Contratto"
          outlined
          dense
          emit-value
          map-options
          clearable
          :loading="loadingContratti"
          hint="Le carte del contratto (firmato, side letter) le vede solo chi vi è dentro."
          data-testid="assegna-contratto"
        />
        <q-input
          v-model="form.quotaCondominio"
          label="Quota condominio mensile"
          type="number"
          min="0"
          step="0.01"
          suffix="€"
          outlined
          dense
          clearable
          :hint="hintQuota"
          data-testid="assegna-quota"
        />

        <template v-if="depositoGiaRegistrato">
          <q-banner class="vp-asg__banner-info" rounded dense>
            Il deposito risulta già registrato per questo inquilino: non è
            possibile registrarne un altro da qui.
          </q-banner>
        </template>
        <template v-else>
          <q-separator />
          <div class="vp-asg__label">Deposito</div>
          <q-input
            v-model="form.depositoTotale"
            label="Importo totale (facoltativo)"
            type="number"
            min="0"
            step="0.01"
            suffix="€"
            outlined
            dense
            clearable
            data-testid="assegna-deposito-totale"
          />
          <q-input
            v-model="form.dataVersamento"
            label="Data versamento"
            type="date"
            outlined
            dense
            data-testid="assegna-deposito-data"
          />
          <div>
            <div class="vp-asg__label">Numero rate</div>
            <q-btn-toggle
              v-model="form.numRate"
              no-caps
              unelevated
              toggle-color="primary"
              :options="OPZIONI_NUM_RATE"
              data-testid="assegna-deposito-rate"
            />
          </div>

          <div v-if="mostraRate" class="vp-asg__rate">
            <div class="row items-center q-col-gutter-sm vp-asg__rata-riga" v-for="(r, i) in rate" :key="i">
              <div class="col-6">
                <q-input
                  v-model="r.importo"
                  :label="`Rata ${i + 1}: importo`"
                  type="number"
                  min="0"
                  step="0.01"
                  suffix="€"
                  outlined
                  dense
                  :data-testid="`assegna-rata-importo-${i}`"
                />
              </div>
              <div class="col-6">
                <q-input
                  v-model="r.scadenza"
                  label="Scadenza"
                  type="date"
                  outlined
                  dense
                  :data-testid="`assegna-rata-scadenza-${i}`"
                />
              </div>
            </div>
            <div class="vp-asg__somma-rate">
              Somma rate: {{ formattaEuro(sommaRate) }}
              <template v-if="!sommaCoerente">
                — non coincide con il totale ({{ formattaEuro(Number(form.depositoTotale) || 0) }})
              </template>
            </div>
            <q-banner v-if="!sommaCoerente" class="vp-asg__banner-warn" rounded dense>
              La somma delle rate non coincide con l'importo totale del deposito.
            </q-banner>
          </div>
        </template>

        <q-banner v-if="errore" class="vp-asg__banner-errore" rounded dense>
          {{ errore }}
        </q-banner>
      </q-card-section>
      <q-card-actions align="right">
        <q-btn v-close-popup flat label="Annulla" />
        <q-btn
          color="primary"
          label="Assegna"
          :loading="salvando"
          :disable="!sommaCoerente || (isUnitaIntera && (loadingStanze || unitaOccupata))"
          data-testid="assegna-salva"
          @click="salva"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useQuasar } from 'quasar';
import { api } from 'boot/axios';
import { messaggioErrore } from 'src/utils/apiErrors';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { usePropertiesStore } from 'stores/properties';

interface Stanza {
  id: number;
  nome: string;
}

interface AssignmentApi {
  id: number;
  room: number;
  valid_from: string;
  valid_to: string | null;
  /** Assegnazione mai perfezionata (l'inquilino non è mai entrato): non
   *  occupa la stanza, nemmeno per il giorno in cui risulta aperta. */
  rinunciata: boolean;
  data_rinuncia: string | null;
}

type CicloFatturazione = 'solare' | 'ingresso';

interface RataDeposito {
  importo: string;
  scadenza: string;
}

const props = defineProps<{
  modelValue: boolean;
  tenantId: number;
  tenantNominativo: string;
  quotaGenerica: number | null;
  depositoGiaRegistrato: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void;
  (e: 'saved'): void;
}>();

const $q = useQuasar();
const { formattaEuro } = useFormatoEuro();
const propStore = usePropertiesStore();
const isUnitaIntera = computed(() => propStore.isUnitaIntera);

const dialogModel = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
});

const OPZIONI_CICLO: { label: string; value: CicloFatturazione }[] = [
  { label: 'Mese solare (1-31)', value: 'solare' },
  { label: 'Dal giorno di ingresso', value: 'ingresso' },
];
const OPZIONI_NUM_RATE = [
  { label: '1', value: 1 },
  { label: '2', value: 2 },
  { label: '3', value: 3 },
];

function oggiISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function asArray<T>(data: T[] | { results: T[] } | undefined | null): T[] {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  return data.results ?? [];
}

interface Form {
  room: number | null;
  contract: number | null;
  validFrom: string;
  validTo: string | null;
  ciclo: CicloFatturazione;
  canoneMensile: string;
  quotaCondominio: string;
  depositoTotale: string;
  dataVersamento: string;
  numRate: 1 | 2 | 3;
}

function formVuoto(): Form {
  return {
    room: null,
    contract: null,
    validFrom: oggiISO(),
    validTo: null,
    ciclo: 'solare',
    canoneMensile: '',
    quotaCondominio: props.quotaGenerica !== null ? String(props.quotaGenerica) : '',
    depositoTotale: '',
    dataVersamento: oggiISO(),
    numRate: 1,
  };
}

const form = ref<Form>(formVuoto());
const rate = ref<RataDeposito[]>([]);
const errore = ref('');
const salvando = ref(false);

const stanze = ref<Stanza[]>([]);
const assignments = ref<AssignmentApi[]>([]);
const loadingStanze = ref(false);

interface ContrattoApi {
  id: number;
  nome: string;
  data_decorrenza: string;
  termine: string | null;
}

const contratti = ref<ContrattoApi[]>([]);
const loadingContratti = ref(false);

const opzioniContratti = computed(() =>
  contratti.value.map((c) => ({
    label: `${c.nome || `Contratto dal ${formattaDataIt(c.data_decorrenza)}`}${
      c.termine ? ` (terminato il ${formattaDataIt(c.termine)})` : ''
    }`,
    value: c.id,
  })),
);

/** Il contratto attivo alla data d'ingresso è quasi sempre quello giusto:
 *  si propone da solo, e resta cambiabile o cancellabile. */
function contrattoAllaData(data: string): number | null {
  const candidati = contratti.value
    .filter((c) => c.data_decorrenza <= data && (!c.termine || c.termine >= data))
    .sort((a, b) => b.data_decorrenza.localeCompare(a.data_decorrenza));
  return candidati[0]?.id ?? null;
}

// Stato di occupazione per stanza: si mostrano le stanze libere alla data di
// inizio scelta o liberabili entro 2 mesi da oggi (fine assegnazione già
// fissata). Una stanza libera ma già promessa a un altro da una data futura
// è assegnabile fino al giorno prima del suo arrivo: la data fine diventa
// obbligatoria. Le occupate a tempo indeterminato non compaiono: per il
// subentro c'è il wizard Cessione.
const ORIZZONTE_MESI = 2;

interface Finestra {
  /** Primo giorno libero; null = libera da sempre. */
  dal: string | null;
  /** Ultimo giorno libero; null = libera senza limite. */
  al: string | null;
}

function spostaGiorni(iso: string, giorni: number): string {
  const d = new Date(iso + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() + giorni);
  return d.toISOString().slice(0, 10);
}

function finestreLibere(roomId: number): Finestra[] {
  // Le rinunce non sono occupazione: si scartano del tutto, altrimenti la
  // stanza risulterebbe "libera dal giorno dopo la rinuncia" invece che
  // semplicemente libera. Date inclusive, come nel backend.
  const delle = assignments.value
    .filter((a) => a.room === roomId && !a.rinunciata)
    .sort((a, b) => a.valid_from.localeCompare(b.valid_from));
  const finestre: Finestra[] = [];
  let dal: string | null = null;
  for (const a of delle) {
    if (dal === null || a.valid_from > dal) {
      finestre.push({ dal, al: spostaGiorni(a.valid_from, -1) });
    }
    if (a.valid_to === null) return finestre;
    const dopo = spostaGiorni(a.valid_to, 1);
    if (dal === null || dopo > dal) dal = dopo;
  }
  finestre.push({ dal, al: null });
  return finestre;
}

function finestraAl(roomId: number, data: string): Finestra | undefined {
  return finestreLibere(roomId).find(
    (f) => (f.dal === null || f.dal <= data) && (f.al === null || data <= f.al),
  );
}

const opzioniStanze = computed(() => {
  const oggi = oggiISO();
  const limite = addMonthsClamped(oggi, ORIZZONTE_MESI);
  const inizio = form.value.validFrom || oggi;
  const opzioni: { label: string; value: number; disable?: boolean }[] = [];
  for (const s of stanze.value) {
    const libera = finestraAl(s.id, inizio);
    if (libera) {
      const note: string[] = [];
      if (libera.dal !== null && libera.dal > oggi) note.push(`libera dal ${formattaDataIt(libera.dal)}`);
      if (libera.al !== null) note.push(`fino al ${formattaDataIt(libera.al)}`);
      opzioni.push({ label: note.length ? `${s.nome} — ${note.join(' ')}` : s.nome, value: s.id });
      continue;
    }
    // Occupata alla data scelta: si mostra (non selezionabile) se si libera
    // entro l'orizzonte, così si sa da quando spostare l'inizio.
    const prossima = finestreLibere(s.id).find((f) => f.dal !== null && f.dal > inizio);
    if (prossima?.dal && prossima.dal <= limite) {
      opzioni.push({
        label: `${s.nome} — libera dal ${formattaDataIt(prossima.dal)}`,
        value: s.id,
        disable: true,
      });
    }
  }
  return opzioni;
});

// Ultimo giorno assegnabile per la stanza scelta alla data d'inizio: c'è
// solo se la stanza è già promessa a un altro da una data futura.
const fineMassima = computed<string | null>(() => {
  const roomId = isUnitaIntera.value ? stanze.value[0]?.id : form.value.room;
  if (!roomId || !form.value.validFrom) return null;
  return finestraAl(roomId, form.value.validFrom)?.al ?? null;
});

const hintDataFine = computed(() =>
  fineMassima.value
    ? `Obbligatoria: la stanza è già assegnata ad altri dal ${formattaDataIt(spostaGiorni(fineMassima.value, 1))}.`
    : 'Vuota: assegnazione a tempo indeterminato.',
);

// Scegliendo una stanza prenotata si propone la fine massima; resta
// accorciabile.
watch(fineMassima, (max) => {
  if (max && (!form.value.validTo || form.value.validTo > max)) form.value.validTo = max;
});

function formattaDataIt(iso: string): string {
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

// Unità intera: l'unica stanza è l'appartamento implicito. È "occupata" se
// oggi non è libera. In quel caso non si assegna da qui: il subentro passa
// dal wizard Cessione.
const unitaOccupata = computed(() => {
  if (!isUnitaIntera.value) return false;
  const room = stanze.value[0];
  if (!room) return false;
  return finestraAl(room.id, oggiISO()) === undefined;
});

// Se cambiando la data di inizio la stanza scelta non è più selezionabile,
// deselezionala per non lasciare un valore invalido nel form.
watch(opzioniStanze, (opts) => {
  const scelta = opts.find((o) => o.value === form.value.room);
  if (form.value.room !== null && (!scelta || scelta.disable)) {
    form.value.room = null;
  }
});

const hintQuota = computed(() =>
  props.quotaGenerica !== null
    ? `Quota base dell'immobile: ${formattaEuro(props.quotaGenerica)}/mese — modificala per creare una quota specifica per ${props.tenantNominativo}.`
    : 'Nessuna quota base configurata.',
);

async function caricaStanze(): Promise<void> {
  loadingStanze.value = true;
  try {
    const [rooms, assegn] = await Promise.all([
      api.get<Stanza[] | { results: Stanza[] }>('/api/v1/rooms/'),
      api.get<AssignmentApi[] | { results: AssignmentApi[] }>('/api/v1/room-assignments/'),
    ]);
    stanze.value = asArray(rooms.data);
    assignments.value = asArray(assegn.data);
  } catch (e: unknown) {
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, 'Caricamento stanze non riuscito.'),
    });
  } finally {
    loadingStanze.value = false;
  }
}

async function caricaContratti(): Promise<void> {
  loadingContratti.value = true;
  try {
    const { data } = await api.get<ContrattoApi[] | { results: ContrattoApi[] }>(
      '/api/v1/contracts/',
    );
    contratti.value = asArray(data);
    form.value.contract = contrattoAllaData(form.value.validFrom);
  } catch (e: unknown) {
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, 'Caricamento contratti non riuscito.'),
    });
  } finally {
    loadingContratti.value = false;
  }
}

// Split di un importo in `n` rate uguali a 2 decimali, col resto (dovuto
// all'arrotondamento) accumulato sull'ultima rata.
function splitImporto(totale: number, n: number): string[] {
  const centesimi = Math.round(totale * 100);
  const base = Math.floor(centesimi / n);
  const resto = centesimi - base * n;
  const importi: number[] = [];
  for (let i = 0; i < n; i += 1) {
    importi.push(base + (i === n - 1 ? resto : 0));
  }
  return importi.map((c) => (c / 100).toFixed(2));
}

// Somma `mesi` alla data ISO, con clamp del giorno se il mese di arrivo è
// più corto (es. 31 gen + 1 mese → 28/29 feb).
function addMonthsClamped(dataISO: string, mesi: number): string {
  const [y, m, d] = dataISO.split('-').map(Number);
  if (!y || !m || !d) return dataISO;
  const base = new Date(Date.UTC(y, m - 1, d));
  const indiceAssoluto = base.getUTCMonth() + mesi;
  const annoTarget = base.getUTCFullYear() + Math.floor(indiceAssoluto / 12);
  const meseTarget = ((indiceAssoluto % 12) + 12) % 12;
  const ultimoGiornoMese = new Date(Date.UTC(annoTarget, meseTarget + 1, 0)).getUTCDate();
  const giorno = Math.min(base.getUTCDate(), ultimoGiornoMese);
  return new Date(Date.UTC(annoTarget, meseTarget, giorno)).toISOString().slice(0, 10);
}

function ricalcolaRate(): void {
  const totale = Number(form.value.depositoTotale);
  const n = form.value.numRate;
  const dataVersamento = form.value.dataVersamento || form.value.validFrom;
  if (!totale || totale <= 0 || n <= 1 || !dataVersamento) {
    rate.value = [];
    return;
  }
  const importi = splitImporto(totale, n);
  rate.value = importi.map((importo, i) => ({
    importo,
    scadenza: addMonthsClamped(dataVersamento, i),
  }));
}

watch(
  () => [form.value.depositoTotale, form.value.numRate, form.value.dataVersamento],
  ricalcolaRate,
);

const mostraRate = computed(() => rate.value.length > 1);
const sommaRate = computed(() =>
  rate.value.reduce((acc, r) => acc + (Number(r.importo) || 0), 0),
);
const sommaCoerente = computed(() => {
  if (!mostraRate.value) return true;
  const totale = Number(form.value.depositoTotale) || 0;
  return Math.abs(sommaRate.value - totale) < 0.005;
});

watch(
  () => props.modelValue,
  (aperto) => {
    if (!aperto) return;
    errore.value = '';
    form.value = formVuoto();
    rate.value = [];
    // Su unità intera non c'è scelta stanza, ma serve comunque l'elenco delle
    // assegnazioni per capire se l'appartamento è già occupato (banner +
    // submit disabilitato). A stanze serve per popolare il select.
    void caricaStanze();
    void caricaContratti();
  },
);

// Spostando la data d'ingresso cambia il contratto in vigore: si riallinea
// la proposta, senza scavalcare una scelta esplicita dell'utente.
watch(
  () => form.value.validFrom,
  (nuova, vecchia) => {
    if (!nuova || loadingContratti.value) return;
    if (form.value.contract !== null && form.value.contract !== contrattoAllaData(vecchia ?? '')) {
      return;
    }
    form.value.contract = contrattoAllaData(nuova);
  },
);

async function salva(): Promise<void> {
  errore.value = '';
  const f = form.value;
  if (isUnitaIntera.value && unitaOccupata.value) {
    errore.value = 'Appartamento già occupato: usa il wizard Cessione per il subentro.';
    return;
  }
  if (!isUnitaIntera.value && !f.room) {
    errore.value = 'Selezionare la stanza.';
    return;
  }
  if (!f.validFrom) {
    errore.value = 'La data di inizio è obbligatoria.';
    return;
  }
  if (fineMassima.value && !f.validTo) {
    errore.value = `Indicare la data fine: la stanza è libera solo fino al ${formattaDataIt(fineMassima.value)}.`;
    return;
  }
  if (f.validTo && f.validTo <= f.validFrom) {
    errore.value = 'La data fine deve essere successiva alla data di inizio.';
    return;
  }
  if (f.validTo && fineMassima.value && f.validTo > fineMassima.value) {
    errore.value = `La stanza è libera solo fino al ${formattaDataIt(fineMassima.value)}.`;
    return;
  }
  if (f.canoneMensile === '' || Number(f.canoneMensile) < 0) {
    errore.value = 'Indicare il canone mensile.';
    return;
  }
  if (!sommaCoerente.value) {
    errore.value = "La somma delle rate non coincide con il deposito totale.";
    return;
  }

  const payload: Record<string, unknown> = {
    tenant: props.tenantId,
    valid_from: f.validFrom,
    valid_to: f.validTo || null,
    canone_mensile: f.canoneMensile,
    ciclo_fatturazione: f.ciclo,
  };
  // Su unità intera si omette `room`: il backend risolve l'unità implicita.
  if (!isUnitaIntera.value) payload.room = f.room;
  payload.contract = f.contract;
  if (!props.depositoGiaRegistrato && f.depositoTotale !== '') {
    payload.deposito_totale = f.depositoTotale;
    payload.data_versamento_deposito = f.dataVersamento || f.validFrom;
    if (rate.value.length > 1) {
      payload.rate_deposito = rate.value.map((r) => ({
        importo: r.importo,
        scadenza: r.scadenza,
      }));
    }
  }
  if (f.quotaCondominio !== '' && f.quotaCondominio !== null) {
    payload.quota_condominio_mensile = f.quotaCondominio;
  }

  salvando.value = true;
  try {
    await api.post('/api/v1/room-assignments/prima-assegnazione/', payload);
    $q.notify({
      type: 'positive',
      message: `${isUnitaIntera.value ? 'Appartamento assegnato' : 'Stanza assegnata'} a ${props.tenantNominativo}.`,
    });
    emit('saved');
    dialogModel.value = false;
  } catch (e: unknown) {
    errore.value = messaggioErrore(e, 'Assegnazione non riuscita.');
  } finally {
    salvando.value = false;
  }
}
</script>

<style scoped>
.vp-asg__titolo {
  font-weight: 600;
  font-size: 16px;
  color: var(--vp-ink-1);
}
.vp-asg__label {
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--vp-ink-3);
  margin-bottom: var(--vp-gap-1);
}
.vp-asg__rate {
  display: flex;
  flex-direction: column;
  gap: var(--vp-gap-2);
}
.vp-asg__rata-riga {
  margin: 0;
}
.vp-asg__somma-rate {
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-3);
  font-variant-numeric: tabular-nums;
}
.vp-asg__banner-info {
  background: var(--vp-paper-2, rgba(0, 0, 0, 0.04));
  color: var(--vp-ink-2);
}
.vp-asg__banner-warn {
  background: var(--vp-miele-soft, #fdf3d8);
  color: var(--vp-miele-deep, #7a5c0d);
}
.vp-asg__banner-errore {
  background: var(--vp-clay-soft, #fbeae5);
  color: var(--vp-clay-deep, #8c3b21);
}
</style>
