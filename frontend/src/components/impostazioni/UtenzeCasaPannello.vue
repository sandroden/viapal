<template>
  <CardSezione
    titolo="Utenze della casa"
    descrizione="Quali utenze esistono e chi le gestisce. Le voci gestite dalla proprietà entrano nel conguaglio mensile e vengono ripartite tra gli inquilini; «a carico dell'inquilino» vuol dire intestata a lui e fuori dal conguaglio; «non presente» che la voce non esiste per questa casa."
  >
    <div v-if="loading" class="q-pa-md flex flex-center">
      <q-spinner size="28px" />
    </div>
    <div v-else class="imm-elenco">
      <RigaElenco
        v-for="(r, i) in righe"
        :key="r.voce"
        :ultima="i === righe.length - 1"
        :data-testid="`utenza-${r.voce}`"
      >
        <template #tile>
          <TileIcona
            :icona="r.icona"
            :colore="r.stato === 'assente' ? 'var(--vp-ink-4)' : r.colore"
            :bg="r.stato === 'assente' ? 'var(--vp-paper-2)' : r.bg"
          />
        </template>
        <template #titolo>{{ r.label }}</template>
        <template v-if="r.config" #meta>
          <q-input
            v-model="note[r.voce]"
            dense
            borderless
            class="imm-utenza__nota"
            placeholder="Nota (es. intestata all'inquilino, la paga al Comune)"
            :disable="!puoModificare"
            :aria-label="`Nota ${r.label}`"
            :data-testid="`utenza-nota-${r.voce}`"
            @blur="salvaNota(r.voce)"
          />
        </template>
        <template #azioni>
          <q-select
            :model-value="r.stato"
            :options="OPZIONI_GESTIONE"
            :disable="!puoModificare || salvando === r.voce"
            :loading="salvando === r.voce"
            dense
            borderless
            emit-value
            map-options
            class="imm-pillola"
            :class="{ 'imm-pillola--tenue': r.stato === 'assente' }"
            :aria-label="`Gestione ${r.label}`"
            :data-testid="`utenza-gestione-${r.voce}`"
            @update:model-value="(v: StatoUtenza) => cambiaGestione(r.voce, v)"
          />
        </template>
      </RigaElenco>
    </div>
  </CardSezione>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { api } from 'boot/axios';
import { messaggioErrore } from 'src/utils/apiErrors';
import CardSezione from './ui/CardSezione.vue';
import RigaElenco from './ui/RigaElenco.vue';
import TileIcona from './ui/TileIcona.vue';

type VoceUtenza = 'luce' | 'gas' | 'acqua' | 'tari';
type GestioneUtenza = 'proprieta' | 'inquilino';
/** Stato mostrato dalla select: il terzo valore non è una gestione ma
 *  l'assenza della riga a DB. */
type StatoUtenza = GestioneUtenza | 'assente';

interface UtenzaConfig {
  id: number;
  voce: VoceUtenza;
  voce_display?: string;
  gestione: GestioneUtenza;
  gestione_display?: string;
  note: string;
}

defineProps<{ puoModificare: boolean }>();

const $q = useQuasar();

/** L'elenco è fisso: le quattro voci sono sempre in pagina anche senza riga a
 *  DB, perché la loro assenza è essa stessa la configurazione "non presente". */
const VOCI: { voce: VoceUtenza; label: string; icona: string; colore: string; bg: string }[] = [
  { voce: 'luce', label: 'Luce', icona: 'bolt', colore: 'var(--vp-honey)', bg: 'var(--vp-honey-soft)' },
  { voce: 'gas', label: 'Gas', icona: 'flame', colore: 'var(--vp-clay)', bg: 'var(--vp-clay-soft)' },
  { voce: 'acqua', label: 'Acqua', icona: 'drop', colore: 'var(--vp-sky)', bg: 'var(--vp-sky-soft)' },
  { voce: 'tari', label: 'TARI', icona: 'receipt', colore: 'var(--vp-leaf)', bg: 'var(--vp-sage-soft)' },
];

const OPZIONI_GESTIONE: { label: string; value: StatoUtenza }[] = [
  { label: 'Gestita dalla proprietà', value: 'proprieta' },
  { label: "A carico dell'inquilino", value: 'inquilino' },
  { label: 'Non presente', value: 'assente' },
];

const config = ref<UtenzaConfig[]>([]);
// Parte a true: prima della GET tutte le voci risulterebbero "non presente",
// che è un'informazione sbagliata, non uno stato vuoto.
const loading = ref(true);
const salvando = ref<VoceUtenza | null>(null);
const note = ref<Record<VoceUtenza, string>>({ luce: '', gas: '', acqua: '', tari: '' });

function configDi(voce: VoceUtenza): UtenzaConfig | null {
  return config.value.find((u) => u.voce === voce) ?? null;
}

function etichettaVoce(voce: VoceUtenza): string {
  return VOCI.find((v) => v.voce === voce)?.label ?? voce;
}

function etichettaGestione(stato: StatoUtenza): string {
  return OPZIONI_GESTIONE.find((o) => o.value === stato)?.label ?? stato;
}

const righe = computed(() =>
  VOCI.map((v) => {
    const c = configDi(v.voce);
    const stato: StatoUtenza = c?.gestione ?? 'assente';
    return { ...v, config: c, stato };
  }),
);

function sincronizzaNote() {
  for (const v of VOCI) note.value[v.voce] = configDi(v.voce)?.note ?? '';
}

function asArray<T>(data: T[] | { results: T[] } | undefined | null): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : (data.results ?? []);
}

async function carica() {
  loading.value = true;
  try {
    const { data } = await api.get<UtenzaConfig[] | { results: UtenzaConfig[] }>(
      '/api/v1/utenze-config/',
    );
    config.value = asArray(data);
    sincronizzaNote();
  } catch (e: unknown) {
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, 'Caricamento utenze della casa non riuscito.'),
    });
  } finally {
    loading.value = false;
  }
}

onMounted(carica);

/** Rimpiazza la singola riga con quella restituita dal backend invece di
 *  ricaricare la lista: una GET riallineerebbe anche le note che l'utente sta
 *  scrivendo sulle altre voci. */
function aggiornaConfig(nuova: UtenzaConfig) {
  config.value = config.value.map((u) => (u.id === nuova.id ? nuova : u));
  note.value[nuova.voce] = nuova.note ?? '';
}

async function cambiaGestione(voce: VoceUtenza, stato: StatoUtenza) {
  const c = configDi(voce);
  if (stato === (c?.gestione ?? 'assente')) return;
  const etichetta = etichettaVoce(voce);
  salvando.value = voce;
  try {
    if (stato === 'assente') {
      if (c) {
        await api.delete(`/api/v1/utenze-config/${c.id}/`);
        config.value = config.value.filter((u) => u.id !== c.id);
        note.value[voce] = '';
      }
      $q.notify({
        type: 'positive',
        message: `${etichetta}: voce non presente in questa casa.`,
      });
      return;
    }
    if (c) {
      const { data } = await api.patch<UtenzaConfig>(`/api/v1/utenze-config/${c.id}/`, {
        gestione: stato,
      });
      aggiornaConfig(data);
    } else {
      const { data } = await api.post<UtenzaConfig>('/api/v1/utenze-config/', {
        voce,
        gestione: stato,
        note: '',
      });
      config.value = [...config.value, data];
      note.value[voce] = data.note ?? '';
    }
    $q.notify({
      type: 'positive',
      message: `${etichetta}: ${etichettaGestione(stato).toLowerCase()}.`,
    });
  } catch (e: unknown) {
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, 'Aggiornamento della voce non riuscito.'),
    });
    // La select rilegge lo stato dai dati: rileggerli dal server la riallinea.
    await carica();
  } finally {
    salvando.value = null;
  }
}

/** La nota si salva quando il campo perde il fuoco: è un dettaglio
 *  descrittivo, non vale un bottone per riga. */
async function salvaNota(voce: VoceUtenza) {
  const c = configDi(voce);
  if (!c || salvando.value === voce) return;
  const nota = note.value[voce].trim();
  if (nota === (c.note ?? '').trim()) return;
  salvando.value = voce;
  try {
    const { data } = await api.patch<UtenzaConfig>(`/api/v1/utenze-config/${c.id}/`, {
      note: nota,
    });
    aggiornaConfig(data);
    $q.notify({ type: 'positive', message: `Nota di ${etichettaVoce(voce)} aggiornata.` });
  } catch (e: unknown) {
    note.value[voce] = c.note ?? '';
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, 'Salvataggio della nota non riuscito.'),
    });
  } finally {
    salvando.value = null;
  }
}
</script>

<style scoped>
.imm-elenco {
  margin-top: 4px;
}
.imm-utenza__nota {
  max-width: 380px;
  font-size: 12.5px;
}
.imm-utenza__nota :deep(.q-field__control) {
  min-height: 26px;
  height: 26px;
}
.imm-utenza__nota :deep(input) {
  font-size: 12.5px;
  color: var(--vp-ink-3);
}
</style>
