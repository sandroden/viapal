<template>
  <q-dialog v-model="aperto" @hide="svuota">
    <q-card class="imm-sheet">
      <q-card-section class="imm-sheet__head">
        <div class="imm-sheet__titolo">Carica documenti</div>
        <BtnIcona icona="x" etichetta="Chiudi" @click="aperto = false" />
      </q-card-section>

      <q-card-section class="imm-sheet__corpo">
        <!-- Multi-file per davvero: contratto + side letter insieme, o
             fronte e retro dello stesso documento. -->
        <div
          class="imm-drop"
          :class="{ 'imm-drop--sopra': sopra }"
          @dragover.prevent="sopra = true"
          @dragleave="sopra = false"
          @drop.prevent="rilascia"
          @click="inputFile?.click()"
        >
          <VpIcon name="upload" :size="20" />
          <div class="imm-drop__titolo">Trascina qui o scegli i file</div>
          <div class="imm-drop__nota">
            Anche più di uno insieme: contratto e side letter, o fronte e
            retro dello stesso documento.
          </div>
          <input
            ref="inputFile"
            type="file"
            multiple
            accept=".pdf,.jpg,.jpeg,.png"
            class="hidden"
            @change="scegli"
          />
        </div>

        <div v-if="voci.length" class="imm-staged">
          <div v-for="(v, i) in voci" :key="i" class="imm-staged__riga">
            <TileIcona icona="doc" :size="30" />
            <span class="imm-staged__nome">{{ v.file.name }}</span>
            <q-select
              v-model="v.tipo"
              :options="tipi"
              dense
              borderless
              emit-value
              map-options
              class="imm-pillola"
              :aria-label="`Tipo di ${v.file.name}`"
            />
            <BtnIcona icona="x" :etichetta="`Togli ${v.file.name}`" @click="togli(i)" />
          </div>
          <div class="imm-staged__nota">
            Tipo proposto dal nome del file — correggibile per ciascun file.
          </div>
        </div>

        <!-- Un solo campo decide dove finiscono i file: un contratto o la
             casa. Aperto dal «+» di un contratto, è già compilato. -->
        <q-select
          v-model="contract"
          :options="opzioniDestinazione"
          label="Collega a"
          outlined
          dense
          emit-value
          map-options
          hint="I file di un contratto compaiono sulla sua riga. «La casa» per regolamento e documenti generali."
          data-testid="carica-collega-a"
        />

        <q-toggle v-model="visibile" dense class="imm-sheet__vis">
          <span class="imm-sheet__vis-testo">Visibile agli inquilini</span>
          <span class="imm-sheet__vis-nota">{{ notaVisibilita }}</span>
        </q-toggle>

        <q-banner
          v-if="contrattualiSenzaContratto.length"
          class="vp-banner-errore"
          rounded
          dense
          data-testid="avviso-ambito"
        >
          Contratto, side letter e ricevuta di registrazione sono carte di un
          contratto: scegli quale in «Collega a», altrimenti finiscono fra i
          documenti generali della casa.
        </q-banner>

        <q-banner
          v-else-if="giaPresenti.length"
          class="imm-sheet__avviso"
          rounded
          dense
          data-testid="avviso-doppione"
        >
          Qui c'è già: {{ giaPresenti.join(', ') }}. Se è lo stesso documento,
          modifica quello invece di caricarne un altro.
        </q-banner>

        <q-banner v-if="errore" class="vp-banner-errore" rounded dense>{{ errore }}</q-banner>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn v-close-popup flat label="Annulla" />
        <q-btn
          color="primary"
          unelevated
          :label="voci.length > 1 ? `Carica ${voci.length} file` : 'Carica'"
          :disable="voci.length === 0 || contrattualiSenzaContratto.length > 0"
          :loading="store.uploading"
          data-testid="carica-documenti"
          @click="carica"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useQuasar } from 'quasar';
import { richiedeContratto } from 'stores/documenti';
import type { DocumentiStore, TipoDocumentoOption } from 'stores/documenti';
import VpIcon from 'components/utenze/VpIcon.vue';
import BtnIcona from './ui/BtnIcona.vue';
import TileIcona from './ui/TileIcona.vue';

const props = withDefaults(
  defineProps<{
    store: DocumentiStore;
    tipi: TipoDocumentoOption[];
    /** Contratti dell'immobile, per il campo «Collega a». */
    contratti?: { id: number; nome: string; data_decorrenza: string }[];
    /** Destinazione preselezionata: il contratto da cui si è aperto il
     *  foglio, o null per la casa. */
    contrattoIniziale?: number | null;
  }>(),
  { contratti: () => [], contrattoIniziale: null },
);

const emit = defineEmits<{ (e: 'caricati'): void }>();

const $q = useQuasar();

const aperto = defineModel<boolean>({ default: false });

interface Voce {
  file: File;
  tipo: string;
}

const voci = ref<Voce[]>([]);
const visibile = ref(false);
const sopra = ref(false);
const errore = ref('');
const inputFile = ref<HTMLInputElement | null>(null);
const contract = ref<number | null>(props.contrattoIniziale);

const opzioniDestinazione = computed(() => [
  { label: 'La casa (documento generale)', value: null },
  ...props.contratti.map((c) => ({
    label: `Contratto · ${c.nome || `dal ${c.data_decorrenza}`}`,
    value: c.id,
  })),
]);

/** Un tipo contrattuale destinato alla casa: il backend lo rifiuta, e
 *  prima di rifiutarlo lo diceva soltanto lui. */
const contrattualiSenzaContratto = computed(() =>
  contract.value === null
    ? voci.value.filter((v) => richiedeContratto(v.tipo)).map((v) => v.file.name)
    : [],
);

/** Documento dello stesso tipo già presente nella stessa destinazione: non
 *  blocca (fronte e retro sono legittimi) ma è il segnale che mancava
 *  quando lo stesso file è finito in archivio due volte. */
const giaPresenti = computed(() => {
  const tipiInCoda = new Set(voci.value.map((v) => v.tipo));
  return props.store.documenti
    .filter(
      (d) => tipiInCoda.has(d.tipo) && (d.contract ?? null) === contract.value,
    )
    .map((d) => d.tipo_display);
});

const notaVisibilita = computed(() =>
  contract.value === null
    ? '— compare nella loro pagina «I miei documenti»'
    : '— collegato a un contratto, solo agli inquilini che vi stanno dentro',
);

/** Il tipo si indovina dal nome del file: chi carica «side letter.pdf» non
 *  deve anche dire che è una side letter. Resta correggibile riga per riga. */
function tipoDaNome(nome: string): string {
  const n = nome.toLowerCase();
  const indizi: [RegExp, string][] = [
    [/side.?letter|accompagnament|lettera/, 'side_letter'],
    // "registrazone" senza la i: il file reale ha il refuso nel nome.
    [/registrazion|registrazon|ricevuta|rli|agenzia.?entrate/, 'registrazione_contratto'],
    [/conviven/, 'regole_convivenza'],
    [/regolament/, 'regolamento_condominiale'],
    // "firmato" da solo basta: la copia firmata è quasi sempre il contratto.
    [/contratt|locazion|firmat/, 'contratto'],
  ];
  for (const [re, tipo] of indizi) {
    if (re.test(n) && props.tipi.some((t) => t.value === tipo)) return tipo;
  }
  return props.tipi[props.tipi.length - 1]?.value ?? 'altro';
}

function aggiungi(files: FileList | File[] | null) {
  if (!files) return;
  for (const file of Array.from(files)) {
    voci.value.push({ file, tipo: tipoDaNome(file.name) });
  }
  errore.value = '';
}

function scegli(ev: Event) {
  aggiungi((ev.target as HTMLInputElement).files);
  if (inputFile.value) inputFile.value.value = '';
}

function rilascia(ev: DragEvent) {
  sopra.value = false;
  aggiungi(ev.dataTransfer?.files ?? null);
}

function togli(i: number) {
  voci.value.splice(i, 1);
}

function svuota() {
  voci.value = [];
  visibile.value = false;
  errore.value = '';
  contract.value = props.contrattoIniziale;
}

// Riaprendo il foglio dal «+» di un altro contratto, la destinazione è
// quella nuova: il valore rimasto dall'apertura precedente sarebbe sbagliato.
watch(aperto, (ora) => {
  if (ora) contract.value = props.contrattoIniziale;
});

async function carica() {
  errore.value = '';
  const { ok, falliti } = await props.store.caricaTipizzati({
    voci: voci.value.map((v) => ({ file: v.file, tipo: v.tipo })),
    visibileInquilini: visibile.value,
    contract: contract.value,
  });
  if (falliti) {
    errore.value = props.store.errore ?? `${falliti} file non caricati.`;
    // I riusciti sono già nello store: restano solo i falliti in coda.
    voci.value = voci.value.slice(ok);
    return;
  }
  $q.notify({
    type: 'positive',
    message: ok > 1 ? `${ok} documenti caricati.` : 'Documento caricato.',
  });
  aperto.value = false;
  emit('caricati');
}
</script>

<style scoped>
.imm-sheet {
  width: 580px;
  max-width: 92vw;
}
.imm-sheet__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 4px;
}
.imm-sheet__titolo {
  font-family: var(--vp-font-display);
  font-size: 20px;
  font-weight: 500;
}
.imm-sheet__corpo {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.imm-drop {
  border: 1.5px dashed var(--vp-paper-3);
  border-radius: 12px;
  padding: 20px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  color: var(--vp-ink-3);
  background: var(--vp-paper);
  cursor: pointer;
  text-align: center;
}
.imm-drop--sopra {
  border-color: var(--vp-terra);
  background: var(--vp-terra-soft);
}
.imm-drop__titolo {
  font-size: 13.5px;
  font-weight: 500;
  color: var(--vp-ink-2);
}
.imm-drop__nota {
  font-size: 12px;
  max-width: 380px;
  line-height: 1.45;
}
.imm-staged__riga {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 9px 2px;
  border-bottom: 1px solid var(--vp-paper-3);
}
.imm-staged__riga:last-of-type {
  border-bottom: none;
}
.imm-staged__nome {
  flex: 1;
  min-width: 0;
  font-size: 13.5px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.imm-staged__nota {
  font-size: 11.5px;
  color: var(--vp-ink-3);
  margin-top: 6px;
}
.imm-sheet__vis-testo {
  font-weight: 500;
  font-size: 13.5px;
}
.imm-sheet__vis-nota {
  font-size: 12px;
  color: var(--vp-ink-3);
}
.imm-sheet__avviso {
  background: var(--vp-paper-2);
  color: var(--vp-ink-2);
  font-size: 12.5px;
}
.vp-banner-errore {
  background: var(--vp-clay-soft, #fbeae5);
  color: var(--vp-clay-deep, #8c3b21);
}
</style>
