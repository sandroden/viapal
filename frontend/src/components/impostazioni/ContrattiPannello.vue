<template>
  <CardSezione
    titolo="Contratti"
    descrizione="Più contratti attivi convivono (affitto a stanze): ogni inquilino vede solo il proprio, la proprietà li vede tutti."
  >
    <template v-if="puoModificare" #azioni>
      <BtnSoft
        etichetta="Nuovo contratto"
        data-testid="nuovo-contratto"
        @click="apriDialog(null)"
      />
    </template>

    <div v-if="loading" class="q-pa-md flex flex-center">
      <q-spinner size="28px" />
    </div>
    <template v-else>
      <div class="imm-elenco">
        <RigaElenco
          v-for="(c, i) in attivi"
          :key="c.id"
          :ultima="i === attivi.length - 1"
          data-testid="riga-contratto"
        >
          <template #tile>
            <TileIcona icona="contract" colore="var(--vp-terra)" bg="var(--vp-terra-soft)" />
          </template>
          <template #titolo>{{ nomeContratto(c) }}</template>
          <template #badge>
            <EtichettaStato tono="ok">{{ etichettaValidita(c) }}</EtichettaStato>
            <EtichettaStato v-if="c.asseverato" tono="line">Asseverato</EtichettaStato>
          </template>
          <template #meta>
            <span class="imm-contratto__meta">
              {{ dettaglio(c) }}
              <!-- I file del contratto vivono sulla sua riga: partendo da
                   qui l'associazione è implicita, non da ricordare. -->
              <span class="imm-contratto__file">
                <span v-for="d in fileDi(c.id)" :key="d.id" class="imm-dc-gruppo">
                  <button
                    type="button"
                    class="imm-dc"
                    :title="`${nomeFileDi(d)} — apri`"
                    @click="apriFile(d)"
                  >
                    <VpIcon name="doc" :size="13" />
                    {{ etichettaFile(d) }}
                    <VpIcon name="open" :size="11" />
                  </button>
                  <!-- Un file di contratto non compare più in "Altri
                       documenti": senza questo non sarebbe più eliminabile,
                       né correggibile nel tipo o nel contratto. -->
                  <button
                    v-if="puoModificare"
                    type="button"
                    class="imm-dc imm-dc--edit"
                    :aria-label="`Modifica ${etichettaFile(d)}`"
                    :data-testid="`modifica-file-${d.id}`"
                    @click="modificaFile(d)"
                  >
                    <VpIcon name="edit" :size="12" />
                    <q-tooltip>Modifica tipo, descrizione, contratto</q-tooltip>
                  </button>
                  <button
                    v-if="puoModificare"
                    type="button"
                    class="imm-dc imm-dc--copia"
                    :aria-label="`Copia per la lettura di ${etichettaFile(d)}`"
                    :data-testid="`copia-lettura-${d.id}`"
                    @click="copiaLettura(d)"
                  >
                    <VpIcon name="link" :size="12" />
                    <q-tooltip>
                      Copia per la lettura: la versione oscurata da mandare a
                      chi deve ancora firmare
                    </q-tooltip>
                  </button>
                  <button
                    v-if="puoModificare"
                    type="button"
                    class="imm-dc imm-dc--del"
                    :aria-label="`Elimina ${etichettaFile(d)}`"
                    @click="eliminaFile(d)"
                  >
                    <VpIcon name="trash" :size="12" />
                    <q-tooltip>Elimina il file</q-tooltip>
                  </button>
                </span>
                <button
                  v-if="puoModificare"
                  type="button"
                  class="imm-dc imm-dc--add"
                  :data-testid="`aggiungi-file-${c.id}`"
                  @click="apriCaricamento(c.id)"
                >
                  <VpIcon name="plus" :size="12" />
                  {{ mancaIlFirmato(c) ? 'manca il firmato — aggiungi' : 'Aggiungi file' }}
                </button>
              </span>
            </span>
          </template>
          <template #azioni>
            <AzioniRiga
              :oggetto="nomeContratto(c)"
              :puo-modificare="puoModificare"
              :puo-eliminare="puoModificare"
              @modifica="apriDialog(c)"
              @elimina="elimina(c)"
            />
          </template>
        </RigaElenco>
        <div v-if="attivi.length === 0" class="imm-vuoto">Nessun contratto attivo.</div>
      </div>

      <!-- I terminati restano per completezza, ma piegati: non devono
           contendere spazio a quelli in corso. -->
      <template v-if="archiviati.length">
        <button
          type="button"
          class="imm-arch"
          :aria-expanded="archivioAperto"
          data-testid="archivio-contratti"
          @click="archivioAperto = !archivioAperto"
        >
          <VpIcon
            name="chevron"
            :size="13"
            :style="{ transform: archivioAperto ? 'rotate(90deg)' : 'none' }"
          />
          Archivio · {{ archiviati.length }}
          {{ archiviati.length === 1 ? 'contratto terminato' : 'contratti terminati' }}
        </button>
        <div v-if="archivioAperto" class="imm-elenco">
          <RigaElenco
            v-for="(c, i) in archiviati"
            :key="c.id"
            tenue
            :ultima="i === archiviati.length - 1"
            data-testid="riga-contratto"
          >
            <template #tile><TileIcona icona="contract" /></template>
            <template #titolo>{{ nomeContratto(c) }}</template>
            <template #badge>
              <EtichettaStato tono="off">Terminato il {{ dataIt(c.termine) }}</EtichettaStato>
              <EtichettaStato v-if="c.asseverato" tono="line">Asseverato</EtichettaStato>
            </template>
            <template #meta>
              <span class="imm-contratto__meta">
                {{ dettaglio(c) }}
                <span class="imm-contratto__file">
                  <button
                    v-for="d in fileDi(c.id)"
                    :key="d.id"
                    type="button"
                    class="imm-dc"
                    :title="d.tipo_display"
                    @click="apriFile(d)"
                  >
                    <VpIcon name="doc" :size="13" />
                    {{ etichettaFile(d) }}
                    <VpIcon name="open" :size="11" />
                  </button>
                </span>
              </span>
            </template>
            <template #azioni>
              <AzioniRiga
                :oggetto="nomeContratto(c)"
                :puo-modificare="puoModificare"
                :puo-eliminare="puoModificare"
                @modifica="apriDialog(c)"
                @elimina="elimina(c)"
              />
            </template>
          </RigaElenco>
        </div>
      </template>
    </template>
  </CardSezione>

  <!-- Dialog contratto -->
  <!-- no-route-dismiss: la pagina riscrive la query consumando ?contratto=,
       e senza questo il dialog appena aperto dal deep link verrebbe chiuso
       dal cambio rotta. -->
  <q-dialog v-model="dialog" no-route-dismiss>
    <q-card style="width: 460px; max-width: 92vw">
      <q-card-section>
        <div class="vp-section-title">
          {{ inModifica ? 'Modifica contratto' : 'Nuovo contratto' }}
        </div>
      </q-card-section>
      <q-card-section class="q-gutter-md">
        <q-input
          v-model="form.nome"
          label="Nome (es. 'Contratto 2025')"
          outlined
          dense
          autofocus
          data-testid="contratto-nome"
        />
        <div class="row q-col-gutter-sm">
          <div class="col-6">
            <q-input
              v-model="form.data_stipula"
              label="Data stipula"
              type="date"
              outlined
              dense
              data-testid="contratto-stipula"
            />
          </div>
          <div class="col-6">
            <q-input
              v-model="form.data_decorrenza"
              label="Data decorrenza"
              type="date"
              outlined
              dense
              data-testid="contratto-decorrenza"
            />
          </div>
        </div>
        <div class="row q-col-gutter-sm">
          <div class="col-4">
            <q-input
              v-model="form.durata_anni"
              label="Durata (anni)"
              type="number"
              min="1"
              outlined
              dense
              data-testid="contratto-durata"
            />
          </div>
          <div class="col-4">
            <q-input
              v-model="form.durata_rinnovo_anni"
              label="Rinnovo (anni)"
              type="number"
              min="0"
              outlined
              dense
              hint="Il «+2» di 4+2"
              data-testid="contratto-rinnovo"
            />
          </div>
          <div class="col-4">
            <q-input
              v-model="form.termine"
              label="Termine anticipato"
              type="date"
              outlined
              dense
              clearable
              hint="Solo se chiuso prima"
            />
          </div>
        </div>
        <q-select
          v-model="form.regime_fiscale"
          :options="OPZIONI_REGIME"
          label="Regime fiscale"
          outlined
          dense
          emit-value
          map-options
          data-testid="contratto-regime"
        />
        <q-select
          v-model="form.default_pagatore_bollette"
          :options="opzioniPagatore"
          label="Pagatore bollette (convenzione)"
          outlined
          dense
          emit-value
          map-options
          clearable
          data-testid="contratto-pagatore"
        />
        <q-toggle v-model="form.asseverato" label="Asseverato" dense />

        <!-- Estremi citati nelle premesse dell'atto di subentro: finora
             esistevano solo dentro la ricevuta di registrazione caricata. -->
        <div class="vp-section-title q-mt-md">Registrazione</div>
        <div class="vp-hint q-mb-sm">
          Servono all'atto di subentro. Li trovi sulla ricevuta rilasciata
          dall'Agenzia delle Entrate.
        </div>
        <div class="row q-col-gutter-sm">
          <div class="col-7">
            <q-input
              v-model="form.ufficio_registrazione"
              label="Ufficio territoriale"
              outlined
              dense
              data-testid="contratto-ufficio"
            />
          </div>
          <div class="col-5">
            <q-input
              v-model="form.data_registrazione"
              label="Data registrazione"
              type="date"
              outlined
              dense
              clearable
              data-testid="contratto-data-registrazione"
            />
          </div>
        </div>
        <div class="row q-col-gutter-sm">
          <div class="col-7">
            <q-input
              v-model="form.numero_registrazione"
              label="Numero"
              outlined
              dense
              data-testid="contratto-numero-registrazione"
            />
          </div>
          <div class="col-5">
            <q-input
              v-model="form.serie_registrazione"
              label="Serie"
              outlined
              dense
              data-testid="contratto-serie"
            />
          </div>
        </div>
        <q-input
          v-model="form.codice_identificativo"
          label="Codice identificativo del contratto"
          outlined
          dense
          data-testid="contratto-codice-identificativo"
        />
        <q-input v-model="form.note" label="Note" type="textarea" autogrow outlined dense />
        <q-banner v-if="errore" class="vp-banner-errore" rounded dense>{{ errore }}</q-banner>
      </q-card-section>
      <q-card-actions align="right">
        <q-btn v-close-popup flat label="Annulla" />
        <q-btn
          color="primary"
          label="Salva"
          :loading="saving"
          data-testid="salva-contratto"
          @click="salva"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>

  <CaricaDocumentiSheet
    v-model="sheetAperto"
    :store="documentiStore"
    :tipi="TIPI_DOCUMENTO_PROPRIETA"
    :contratti="contratti"
    :contratto-iniziale="contrattoPerCaricamento"
  />

  <ModificaDocumentoDialog
    v-model="modificaAperta"
    :store="documentiStore"
    :documento="fileInModifica"
    :tipi="TIPI_DOCUMENTO_PROPRIETA"
    :contratti="contratti"
  />

  <CopiaLetturaDialog v-model="copiaAperta" :originale="originalePerCopia" />
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { api } from 'boot/axios';
import { messaggioErrore } from 'src/utils/apiErrors';
import {
  useDocumentiProprietaStore,
  TIPI_DOCUMENTO_PROPRIETA,
  type DocumentoFE,
} from 'stores/documenti';
import VpIcon from 'components/utenze/VpIcon.vue';
import CaricaDocumentiSheet from './CaricaDocumentiSheet.vue';
import ModificaDocumentoDialog from './ModificaDocumentoDialog.vue';
import CopiaLetturaDialog from './CopiaLetturaDialog.vue';
import CardSezione from './ui/CardSezione.vue';
import RigaElenco from './ui/RigaElenco.vue';
import TileIcona from './ui/TileIcona.vue';
import EtichettaStato from './ui/EtichettaStato.vue';
import BtnSoft from './ui/BtnSoft.vue';
import AzioniRiga from './ui/AzioniRiga.vue';

type RegimeFiscale = 'cedolare_10' | 'cedolare_21' | 'irpef';

export interface Contratto {
  id: number;
  nome: string;
  data_stipula: string;
  data_decorrenza: string;
  termine: string | null;
  durata_anni: number;
  durata_rinnovo_anni: number;
  asseverato: boolean;
  regime_fiscale: RegimeFiscale;
  regime_fiscale_display?: string;
  default_pagatore_bollette: number | null;
  note: string;
  ufficio_registrazione: string;
  data_registrazione: string | null;
  numero_registrazione: string;
  serie_registrazione: string;
  codice_identificativo: string;
}

interface Owner {
  id: number;
  nominativo: string;
}

defineProps<{ puoModificare: boolean }>();

const $q = useQuasar();
const documentiStore = useDocumentiProprietaStore();

const OPZIONI_REGIME = [
  { label: 'Cedolare secca 10%', value: 'cedolare_10' },
  { label: 'Cedolare secca 21%', value: 'cedolare_21' },
  { label: 'IRPEF ordinario', value: 'irpef' },
];

const contratti = ref<Contratto[]>([]);
const owners = ref<Owner[]>([]);
const loading = ref(true);
const archivioAperto = ref(false);

const oggi = new Date().toISOString().slice(0, 10);
/** Terminato per davvero: un termine in futuro è una scadenza annunciata,
 *  non un contratto da archiviare. */
const archiviati = computed(() => contratti.value.filter((c) => c.termine && c.termine <= oggi));
const attivi = computed(() => contratti.value.filter((c) => !c.termine || c.termine > oggi));

const opzioniPagatore = computed(() =>
  owners.value.map((o) => ({ label: o.nominativo, value: o.id })),
);

function nominativoOwner(id: number): string {
  return owners.value.find((o) => o.id === id)?.nominativo ?? `#${id}`;
}

function nomeContratto(c: Contratto): string {
  return c.nome || `Contratto dal ${dataIt(c.data_decorrenza)}`;
}

function dataIt(iso: string | null): string {
  if (!iso) return '';
  const [a, m, g] = iso.split('-');
  return g && m && a ? `${g}/${m}/${a}` : iso;
}

function etichettaValidita(c: Contratto): string {
  return c.termine ? `Termina il ${dataIt(c.termine)}` : 'Attivo';
}

function dettaglio(c: Contratto): string {
  const parti = [
    `dal ${dataIt(c.data_decorrenza)}`,
    `${c.durata_anni} ${c.durata_anni === 1 ? 'anno' : 'anni'}`,
    c.regime_fiscale_display || c.regime_fiscale,
  ];
  if (c.default_pagatore_bollette) {
    parti.push(`bollette: ${nominativoOwner(c.default_pagatore_bollette)}`);
  }
  return parti.join(' · ');
}

function asArray<T>(data: T[] | { results: T[] } | undefined | null): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : (data.results ?? []);
}

// ---------------------------------------------------------------------------
// I file del contratto, sulla riga del contratto
// ---------------------------------------------------------------------------

const sheetAperto = ref(false);
const contrattoPerCaricamento = ref<number | null>(null);
const modificaAperta = ref(false);
const fileInModifica = ref<DocumentoFE | null>(null);
const copiaAperta = ref(false);
const originalePerCopia = ref<DocumentoFE | null>(null);

/** Le copie per la lettura non sono chip del contratto: stanno nella loro
 *  sezione, così l'archivio ufficiale resta quello che è. */
function fileDi(contractId: number): DocumentoFE[] {
  return documentiStore.documenti.filter((d) => d.contract === contractId && !d.copia_di);
}

/** Il nome del file, quando è leggibile.
 *
 *  Con lo storage firmato l'URL porta la querystring (``?X-Amz-…``) e il
 *  nome mostrato diventava un troncone illeggibile: due file diversi
 *  sembravano lo stesso, ed è così che è passato inosservato un doppione.
 *  Tolta la query resta il nome; se il tipo è già parlante lo si preferisce. */
function nomeFileDi(d: DocumentoFE): string {
  const senzaQuery = (d.file ?? '').split('?')[0] ?? '';
  return decodeURIComponent(senzaQuery.split('/').pop() ?? '');
}

function etichettaBase(d: DocumentoFE): string {
  return d.descrizione || d.tipo_display || '';
}

/** Due file dello stesso tipo senza descrizione sullo stesso contratto
 *  darebbero due chip identici — la stessa indistinguibilità che ha lasciato
 *  passare un doppione. In quel caso torna il nome del file. */
function etichettaFile(d: DocumentoFE): string {
  const base = etichettaBase(d);
  if (!base) return nomeFileDi(d);
  const gemelli = documentiStore.documenti.some(
    (x) =>
      x.id !== d.id &&
      (x.contract ?? null) === (d.contract ?? null) &&
      etichettaBase(x) === base,
  );
  return gemelli ? `${base} · ${nomeFileDi(d)}` : base;
}

function apriFile(d: DocumentoFE) {
  window.open(d.file, '_blank', 'noopener');
}

/** Segnala il buco più comune: il contratto senza la sua copia firmata. */
function mancaIlFirmato(c: Contratto): boolean {
  return !fileDi(c.id).some((d) => d.tipo === 'contratto');
}

function copiaLettura(d: DocumentoFE) {
  originalePerCopia.value = d;
  copiaAperta.value = true;
}

/** Da qui si sposta un file su un altro contratto, o lo si rimanda alla
 *  casa: prima l'unica via era eliminarlo e ricaricarlo. */
function modificaFile(d: DocumentoFE) {
  fileInModifica.value = d;
  modificaAperta.value = true;
}

function apriCaricamento(contractId: number) {
  contrattoPerCaricamento.value = contractId;
  sheetAperto.value = true;
}

function eliminaFile(d: DocumentoFE) {
  $q.dialog({
    title: 'Eliminare il file?',
    message: `"${etichettaFile(d)}" verrà rimosso dal contratto.`,
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Elimina' },
  }).onOk(() => {
    void (async () => {
      const ok = await documentiStore.elimina(d.id);
      $q.notify(
        ok
          ? { type: 'positive', message: 'File eliminato.' }
          : {
              type: 'negative',
              message: documentiStore.errore ?? 'Eliminazione non riuscita.',
            },
      );
    })();
  });
}

async function carica() {
  loading.value = true;
  try {
    const [{ data: dataContratti }, { data: dataOwners }] = await Promise.all([
      api.get<Contratto[] | { results: Contratto[] }>('/api/v1/contracts/'),
      api.get<Owner[] | { results: Owner[] }>('/api/v1/owners/'),
    ]);
    contratti.value = asArray(dataContratti);
    owners.value = asArray(dataOwners);
  } catch (e: unknown) {
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, 'Caricamento contratti non riuscito.'),
    });
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void carica();
  // I documenti servono ai chip sulla riga: lo store è condiviso con la card
  // "Altri documenti", che carica gli stessi dati una volta sola.
  if (documentiStore.documenti.length === 0) void documentiStore.fetch();
});

// ---------------------------------------------------------------------------
// Dialog
// ---------------------------------------------------------------------------

const dialog = ref(false);
const inModifica = ref<Contratto | null>(null);

interface FormContratto {
  nome: string;
  data_stipula: string;
  data_decorrenza: string;
  termine: string | null;
  durata_anni: string;
  durata_rinnovo_anni: string;
  asseverato: boolean;
  regime_fiscale: RegimeFiscale;
  default_pagatore_bollette: number | null;
  note: string;
  ufficio_registrazione: string;
  data_registrazione: string | null;
  numero_registrazione: string;
  serie_registrazione: string;
  codice_identificativo: string;
}

const form = ref<FormContratto>(formVuoto());
const saving = ref(false);
const errore = ref('');

function formVuoto(): FormContratto {
  return {
    nome: '',
    data_stipula: '',
    data_decorrenza: '',
    termine: null,
    durata_anni: '4',
    durata_rinnovo_anni: '2',
    asseverato: false,
    regime_fiscale: 'cedolare_10',
    default_pagatore_bollette: null,
    note: '',
    ufficio_registrazione: '',
    data_registrazione: null,
    numero_registrazione: '',
    serie_registrazione: '',
    codice_identificativo: '',
  };
}

function apriDialog(c: Contratto | null) {
  inModifica.value = c;
  errore.value = '';
  form.value = c
    ? {
        nome: c.nome,
        data_stipula: c.data_stipula,
        data_decorrenza: c.data_decorrenza,
        termine: c.termine,
        durata_anni: String(c.durata_anni),
        durata_rinnovo_anni: String(c.durata_rinnovo_anni),
        asseverato: c.asseverato,
        regime_fiscale: c.regime_fiscale,
        default_pagatore_bollette: c.default_pagatore_bollette,
        note: c.note,
        ufficio_registrazione: c.ufficio_registrazione,
        data_registrazione: c.data_registrazione,
        numero_registrazione: c.numero_registrazione,
        serie_registrazione: c.serie_registrazione,
        codice_identificativo: c.codice_identificativo,
      }
    : formVuoto();
  dialog.value = true;
}

/** Deep link `?tab=contratti&contratto=<id>`: apre il dialog del contratto
 *  da completare, altrimenti il link dei dati mancanti atterrerebbe sulla
 *  lista lasciando all'utente il compito di ritrovarlo. */
function apriContratto(id: number | null) {
  if (!id) return;
  const trovato = contratti.value.find((c) => c.id === id);
  if (trovato) apriDialog(trovato);
  // Se i contratti non sono ancora arrivati, riprova a caricamento finito.
  else if (loading.value) void carica().then(() => apriContratto(id));
}

defineExpose({ apriContratto, ricarica: carica });

async function salva() {
  errore.value = '';
  const f = form.value;
  if (!f.data_stipula || !f.data_decorrenza) {
    errore.value = 'Data stipula e data decorrenza sono obbligatorie.';
    return;
  }
  if (!Number(f.durata_anni)) {
    errore.value = 'La durata in anni è obbligatoria.';
    return;
  }
  saving.value = true;
  const payload = {
    nome: f.nome.trim(),
    data_stipula: f.data_stipula,
    data_decorrenza: f.data_decorrenza,
    termine: f.termine || null,
    durata_anni: Number(f.durata_anni),
    durata_rinnovo_anni: Number(f.durata_rinnovo_anni) || 0,
    asseverato: f.asseverato,
    regime_fiscale: f.regime_fiscale,
    default_pagatore_bollette: f.default_pagatore_bollette,
    note: f.note,
    ufficio_registrazione: f.ufficio_registrazione.trim(),
    data_registrazione: f.data_registrazione || null,
    numero_registrazione: f.numero_registrazione.trim(),
    serie_registrazione: f.serie_registrazione.trim(),
    codice_identificativo: f.codice_identificativo.trim(),
  };
  try {
    if (inModifica.value) {
      await api.patch(`/api/v1/contracts/${inModifica.value.id}/`, payload);
      $q.notify({ type: 'positive', message: 'Contratto aggiornato.' });
    } else {
      await api.post('/api/v1/contracts/', payload);
      $q.notify({ type: 'positive', message: 'Contratto creato.' });
    }
    dialog.value = false;
    await carica();
  } catch (e: unknown) {
    errore.value = messaggioErrore(e, 'Salvataggio non riuscito.');
  } finally {
    saving.value = false;
  }
}

function elimina(c: Contratto) {
  $q.dialog({
    title: 'Eliminare il contratto?',
    message: `"${nomeContratto(c)}" verrà rimosso.`,
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Elimina' },
  }).onOk(() => {
    void (async () => {
      try {
        await api.delete(`/api/v1/contracts/${c.id}/`);
        contratti.value = contratti.value.filter((x) => x.id !== c.id);
        $q.notify({ type: 'positive', message: 'Contratto eliminato.' });
      } catch (e: unknown) {
        $q.notify({
          type: 'negative',
          message: messaggioErrore(e, 'Eliminazione non riuscita: dati collegati.'),
        });
      }
    })();
  });
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
.imm-contratto__meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.imm-contratto__file {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  min-width: 0;
  max-width: 100%;
}
.imm-dc {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 24px;
  padding: 0 9px;
  border-radius: 8px;
  border: 1px solid var(--vp-paper-3);
  background: var(--vp-cream);
  font-family: var(--vp-font-ui);
  font-size: 12px;
  color: var(--vp-ink-2);
  cursor: pointer;
  /* Il nome del file si accorcia con i puntini: sul telefono il chip non
     deve mai sporgere oltre il bordo della card. */
  flex: 0 1 auto;
  min-width: 0;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition:
    border-color 0.12s,
    color 0.12s;
}
.imm-dc:hover {
  border-color: var(--vp-terra);
  color: var(--vp-terra-deep);
}
.imm-dc--add {
  border-style: dashed;
  background: transparent;
  color: var(--vp-ink-3);
}
.imm-dc-gruppo {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  min-width: 0;
  max-width: 100%;
}
.imm-dc--del,
.imm-dc--copia,
.imm-dc--edit {
  padding: 0 6px;
  border-color: transparent;
  background: transparent;
  color: var(--vp-ink-4);
}
.imm-dc--edit:hover,
.imm-dc--copia:hover {
  border-color: transparent;
  background: var(--vp-paper-2);
  color: var(--vp-ink-1);
}
.imm-dc--del:hover {
  border-color: transparent;
  background: var(--vp-clay-soft);
  color: var(--vp-clay);
}
.imm-arch {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  border: none;
  border-top: 1px solid var(--vp-paper-3);
  background: transparent;
  padding: 12px 2px 8px;
  font-family: var(--vp-font-ui);
  font-size: 13px;
  font-weight: 500;
  color: var(--vp-ink-3);
  cursor: pointer;
}
.imm-arch:hover {
  color: var(--vp-ink);
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
