<template>
  <CardSezione :titolo="labels.unita">
    <template v-if="puoModificare && !nascondiNuova" #azioni>
      <BtnSoft
        :etichetta="`Nuova ${labels.singolare.toLowerCase()}`"
        data-testid="nuova-stanza"
        @click="apriDialog(null)"
      />
    </template>

    <div v-if="loading" class="q-pa-md flex flex-center">
      <q-spinner size="28px" />
    </div>
    <div v-else class="imm-elenco">
      <RigaElenco
        v-for="(s, i) in stanze"
        :key="s.id"
        :titolo="s.nome"
        :ultima="i === stanze.length - 1"
        :draggable="riordinabile"
        :class="{ 'imm-stanza--drag': trascinata === s.id }"
        data-testid="riga-stanza"
        @dragstart="iniziaTrascinamento(s, $event)"
        @dragover.prevent="sopra(i)"
        @dragend="fineTrascinamento"
        @drop.prevent="fineTrascinamento"
      >
        <template v-if="riordinabile" #tile>
          <span class="imm-stanza__presa" aria-hidden="true">
            <VpIcon name="grip" :size="17" />
          </span>
        </template>
        <template #meta>{{ superficie(s) }}</template>
        <template #azioni>
          <!-- Sul telefono il drag HTML5 non esiste: lì e solo lì il
               riordino si fa con le frecce. -->
          <template v-if="riordinabile">
            <BtnIcona
              class="imm-stanza__freccia"
              icona="up"
              :etichetta="`Sposta ${s.nome} in su`"
              :disabilitato="i === 0 || salvandoOrdine"
              @click="muovi(i, -1)"
            />
            <BtnIcona
              class="imm-stanza__freccia"
              icona="down"
              :etichetta="`Sposta ${s.nome} in giù`"
              :disabilitato="i === stanze.length - 1 || salvandoOrdine"
              @click="muovi(i, 1)"
            />
          </template>
          <AzioniRiga
            :oggetto="s.nome"
            :puo-modificare="puoModificare"
            :puo-eliminare="puoModificare && !nascondiElimina"
            @modifica="apriDialog(s)"
            @elimina="elimina(s)"
          />
        </template>
      </RigaElenco>
      <div v-if="stanze.length === 0" class="imm-vuoto">
        Nessuna {{ labels.singolare.toLowerCase() }} configurata.
      </div>
    </div>

    <div v-if="riordinabile" class="imm-stanza__nota">
      <VpIcon name="grip" :size="13" />
      Trascina per riordinare
    </div>
  </CardSezione>

  <!-- Dialog stanza -->
  <q-dialog v-model="dialog">
    <q-card style="min-width: 380px">
      <q-card-section>
        <div class="vp-section-title">
          {{
            inModifica
              ? `Modifica ${labels.singolare.toLowerCase()}`
              : `Nuova ${labels.singolare.toLowerCase()}`
          }}
        </div>
      </q-card-section>
      <q-card-section class="q-gutter-md">
        <q-input
          v-model="form.nome"
          label="Nome"
          outlined
          dense
          autofocus
          data-testid="stanza-nome"
        />
        <q-input
          v-model="form.superficie_mq"
          label="Superficie (mq)"
          type="number"
          min="0"
          step="0.01"
          outlined
          dense
          data-testid="stanza-superficie"
        />
        <q-banner v-if="errore" class="vp-banner-errore" rounded dense>
          {{ errore }}
        </q-banner>
      </q-card-section>
      <q-card-actions align="right">
        <q-btn v-close-popup flat label="Annulla" />
        <q-btn
          color="primary"
          label="Salva"
          :loading="saving"
          data-testid="salva-stanza"
          @click="salva"
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
import { usePropertiesStore } from 'stores/properties';
import VpIcon from 'components/utenze/VpIcon.vue';
import CardSezione from './ui/CardSezione.vue';
import RigaElenco from './ui/RigaElenco.vue';
import BtnSoft from './ui/BtnSoft.vue';
import BtnIcona from './ui/BtnIcona.vue';
import AzioniRiga from './ui/AzioniRiga.vue';

interface Stanza {
  id: number;
  nome: string;
  superficie_mq: string | null;
  ordinamento: number;
}

const props = defineProps<{ puoModificare: boolean }>();

const $q = useQuasar();
const propStore = usePropertiesStore();

const labels = computed(() => propStore.labels);
// Su unità intera l'unica stanza è l'appartamento implicito creato dal
// signal: niente "Nuova", niente elimina, niente riordino.
const nascondiNuova = computed(() => propStore.isUnitaIntera);
const nascondiElimina = computed(() => propStore.isUnitaIntera);

const stanze = ref<Stanza[]>([]);
const loading = ref(true);
const salvandoOrdine = ref(false);

const riordinabile = computed(
  () => props.puoModificare && !propStore.isUnitaIntera && stanze.value.length > 1,
);

function superficie(s: Stanza): string {
  return s.superficie_mq ? `${Number(s.superficie_mq).toLocaleString('it-IT')} mq` : '— mq';
}

function asArray<T>(data: T[] | { results: T[] } | undefined | null): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : (data.results ?? []);
}

async function carica() {
  loading.value = true;
  try {
    const { data } = await api.get<Stanza[] | { results: Stanza[] }>('/api/v1/rooms/');
    stanze.value = asArray(data).sort((a, b) => a.ordinamento - b.ordinamento);
  } catch (e: unknown) {
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, 'Caricamento stanze non riuscito.'),
    });
  } finally {
    loading.value = false;
  }
}

onMounted(carica);

// ---------------------------------------------------------------------------
// Riordino: la colonna "Ordinamento" spariva dalla vista, ma il campo resta
// il dato salvato — qui si scrive trascinando (o con le frecce sul telefono,
// dove il drag HTML5 non esiste).
// ---------------------------------------------------------------------------

const trascinata = ref<number | null>(null);

function iniziaTrascinamento(s: Stanza, ev: DragEvent) {
  if (!riordinabile.value) return;
  trascinata.value = s.id;
  ev.dataTransfer?.setData('text/plain', String(s.id));
  if (ev.dataTransfer) ev.dataTransfer.effectAllowed = 'move';
}

function sopra(indice: number) {
  if (trascinata.value === null) return;
  const da = stanze.value.findIndex((x) => x.id === trascinata.value);
  if (da === -1 || da === indice) return;
  const copia = [...stanze.value];
  const [riga] = copia.splice(da, 1);
  if (riga) copia.splice(indice, 0, riga);
  stanze.value = copia;
}

function fineTrascinamento() {
  if (trascinata.value === null) return;
  trascinata.value = null;
  void salvaOrdine();
}

function muovi(indice: number, delta: number) {
  const destinazione = indice + delta;
  if (destinazione < 0 || destinazione >= stanze.value.length) return;
  const copia = [...stanze.value];
  const [riga] = copia.splice(indice, 1);
  if (riga) copia.splice(destinazione, 0, riga);
  stanze.value = copia;
  void salvaOrdine();
}

/** Scrive solo le righe il cui ordinamento è cambiato: un riordino locale
 *  non deve diventare N PATCH inutili. */
async function salvaOrdine() {
  const daSalvare = stanze.value
    .map((s, i) => ({ s, i }))
    .filter(({ s, i }) => s.ordinamento !== i);
  if (daSalvare.length === 0) return;
  salvandoOrdine.value = true;
  try {
    await Promise.all(
      daSalvare.map(({ s, i }) => api.patch(`/api/v1/rooms/${s.id}/`, { ordinamento: i })),
    );
    stanze.value = stanze.value.map((s, i) => ({ ...s, ordinamento: i }));
  } catch (e: unknown) {
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, 'Riordino non riuscito.'),
    });
    await carica();
  } finally {
    salvandoOrdine.value = false;
  }
}

// ---------------------------------------------------------------------------
// Dialog
// ---------------------------------------------------------------------------

const dialog = ref(false);
const inModifica = ref<Stanza | null>(null);
const form = ref({ nome: '', superficie_mq: '' });
const saving = ref(false);
const errore = ref('');

function apriDialog(s: Stanza | null) {
  inModifica.value = s;
  errore.value = '';
  form.value = { nome: s?.nome ?? '', superficie_mq: s?.superficie_mq ?? '' };
  dialog.value = true;
}

async function salva() {
  errore.value = '';
  if (!form.value.nome.trim()) {
    errore.value = 'Il nome è obbligatorio.';
    return;
  }
  saving.value = true;
  const payload = {
    nome: form.value.nome.trim(),
    superficie_mq: form.value.superficie_mq !== '' ? form.value.superficie_mq : null,
    // In coda: l'ordine si cambia trascinando, non digitando un numero.
    ...(inModifica.value ? {} : { ordinamento: stanze.value.length }),
  };
  try {
    if (inModifica.value) {
      await api.patch(`/api/v1/rooms/${inModifica.value.id}/`, payload);
      $q.notify({ type: 'positive', message: 'Stanza aggiornata.' });
    } else {
      await api.post('/api/v1/rooms/', payload);
      $q.notify({ type: 'positive', message: 'Stanza creata.' });
    }
    dialog.value = false;
    await carica();
  } catch (e: unknown) {
    errore.value = messaggioErrore(e, 'Salvataggio non riuscito.');
  } finally {
    saving.value = false;
  }
}

function elimina(s: Stanza) {
  $q.dialog({
    title: 'Eliminare la stanza?',
    message: `"${s.nome}" verrà rimossa dall'immobile.`,
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Elimina' },
  }).onOk(() => {
    void (async () => {
      try {
        await api.delete(`/api/v1/rooms/${s.id}/`);
        stanze.value = stanze.value.filter((x) => x.id !== s.id);
        $q.notify({ type: 'positive', message: 'Stanza eliminata.' });
      } catch (e: unknown) {
        $q.notify({
          type: 'negative',
          message: messaggioErrore(
            e,
            'Eliminazione non riuscita: la stanza ha assegnazioni collegate.',
          ),
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
.imm-stanza__presa {
  color: var(--vp-ink-4);
  cursor: grab;
  display: flex;
}
.imm-stanza--drag {
  opacity: 0.45;
}
.imm-stanza__freccia {
  display: none;
}
.imm-stanza__nota {
  font-size: 11.5px;
  color: var(--vp-ink-3);
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.vp-section-title {
  font-weight: 600;
  font-size: 16px;
  color: var(--vp-ink-1);
}
.vp-banner-errore {
  background: var(--vp-clay-soft, #fbeae5);
  color: var(--vp-clay-deep, #8c3b21);
}

@media (max-width: 599px) {
  .imm-stanza__freccia {
    display: inline-flex;
  }
  .imm-stanza__presa,
  .imm-stanza__nota {
    display: none;
  }
}
</style>
