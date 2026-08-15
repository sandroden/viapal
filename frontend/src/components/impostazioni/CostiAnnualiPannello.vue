<template>
  <CardSezione
    titolo="Costi annuali"
    descrizione="TARI e altri costi annuali, spalmati sui conguagli utenze."
  >
    <template v-if="puoModificare" #azioni>
      <BtnSoft etichetta="Nuovo costo" data-testid="nuovo-costo" @click="apriDialog(null)" />
    </template>

    <div v-if="loading" class="q-pa-md flex flex-center">
      <q-spinner size="28px" />
    </div>
    <div v-else class="imm-elenco">
      <RigaElenco
        v-for="(c, i) in costi"
        :key="c.id"
        :ultima="i === costi.length - 1"
        data-testid="riga-costo"
      >
        <template #tile><TileIcona icona="receipt" /></template>
        <template #titolo>{{ c.voce_display || etichettaVoce(c.voce) }} {{ c.anno }}</template>
        <template #meta>{{ periodo(c) }}</template>
        <template #azioni>
          <span class="vp-mono imm-costo__importo">{{ importo(c.importo_annuale) }}/anno</span>
          <AzioniRiga
            :oggetto="`costo ${c.anno}`"
            :puo-modificare="puoModificare"
            :puo-eliminare="puoModificare"
            @modifica="apriDialog(c)"
            @elimina="elimina(c)"
          />
        </template>
      </RigaElenco>
      <div v-if="costi.length === 0" class="imm-vuoto">Nessun costo annuale configurato.</div>
    </div>
  </CardSezione>

  <!-- Dialog costo annuale -->
  <q-dialog v-model="dialog">
    <q-card style="width: 420px; max-width: 92vw">
      <q-card-section>
        <div class="vp-section-title">
          {{ inModifica ? 'Modifica costo annuale' : 'Nuovo costo annuale' }}
        </div>
      </q-card-section>
      <q-card-section class="q-gutter-md">
        <q-select
          v-model="form.voce"
          :options="OPZIONI_VOCE"
          label="Voce"
          outlined
          dense
          emit-value
          map-options
          data-testid="costo-voce"
        />
        <div class="row q-col-gutter-sm">
          <div class="col-6">
            <q-input
              v-model="form.anno"
              label="Anno"
              type="number"
              outlined
              dense
              data-testid="costo-anno"
            />
          </div>
          <div class="col-6">
            <q-input
              v-model="form.importo_annuale"
              label="Importo annuale"
              type="number"
              min="0"
              step="0.01"
              suffix="€"
              outlined
              dense
              data-testid="costo-importo"
            />
          </div>
        </div>
        <div class="row q-col-gutter-sm">
          <div class="col-6">
            <q-input
              v-model="form.valid_from"
              label="Valido dal"
              type="date"
              outlined
              dense
              data-testid="costo-valid-from"
            />
          </div>
          <div class="col-6">
            <q-input
              v-model="form.valid_to"
              label="Valido fino al"
              type="date"
              outlined
              dense
              clearable
              hint="Vuoto = tuttora in vigore"
            />
          </div>
        </div>
        <q-input v-model="form.note" label="Note" type="textarea" autogrow outlined dense />
        <q-banner v-if="errore" class="vp-banner-errore" rounded dense>{{ errore }}</q-banner>
      </q-card-section>
      <q-card-actions align="right">
        <q-btn v-close-popup flat label="Annulla" />
        <q-btn
          color="primary"
          label="Salva"
          :loading="saving"
          data-testid="salva-costo"
          @click="salva"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { api } from 'boot/axios';
import { messaggioErrore } from 'src/utils/apiErrors';
import { useFormatoData } from 'src/composables/useFormatoData';
import CardSezione from './ui/CardSezione.vue';
import RigaElenco from './ui/RigaElenco.vue';
import TileIcona from './ui/TileIcona.vue';
import BtnSoft from './ui/BtnSoft.vue';
import AzioniRiga from './ui/AzioniRiga.vue';

type VoceAnnuale = 'tari' | 'altro';

interface CostoAnnuale {
  id: number;
  voce: VoceAnnuale;
  voce_display?: string;
  anno: number;
  importo_annuale: string;
  valid_from: string;
  valid_to: string | null;
  note: string;
}

defineProps<{ puoModificare: boolean }>();

const $q = useQuasar();
const { formattaData } = useFormatoData();

const OPZIONI_VOCE = [
  { label: 'TARI (tassa rifiuti)', value: 'tari' },
  { label: 'Altro', value: 'altro' },
];

const costi = ref<CostoAnnuale[]>([]);
const loading = ref(true);

function etichettaVoce(voce: VoceAnnuale): string {
  return OPZIONI_VOCE.find((o) => o.value === voce)?.label ?? voce;
}

function importo(v: string): string {
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString('it-IT', { style: 'currency', currency: 'EUR' })
    : v;
}

function periodo(c: CostoAnnuale): string {
  const parti = [`dal ${formattaData(c.valid_from)}`];
  if (c.valid_to) parti.push(`al ${formattaData(c.valid_to)}`);
  if (c.note) parti.push(c.note);
  return parti.join(' · ');
}

function asArray<T>(data: T[] | { results: T[] } | undefined | null): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : (data.results ?? []);
}

async function carica() {
  loading.value = true;
  try {
    const { data } = await api.get<CostoAnnuale[] | { results: CostoAnnuale[] }>(
      '/api/v1/annual-utility-costs/',
    );
    costi.value = asArray(data).sort((a, b) => b.anno - a.anno);
  } catch (e: unknown) {
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, 'Caricamento costi annuali non riuscito.'),
    });
  } finally {
    loading.value = false;
  }
}

onMounted(carica);

const dialog = ref(false);
const inModifica = ref<CostoAnnuale | null>(null);

interface FormCosto {
  voce: VoceAnnuale;
  anno: string;
  importo_annuale: string;
  valid_from: string;
  valid_to: string | null;
  note: string;
}

const form = ref<FormCosto>({
  voce: 'tari',
  anno: String(new Date().getFullYear()),
  importo_annuale: '',
  valid_from: '',
  valid_to: null,
  note: '',
});
const saving = ref(false);
const errore = ref('');

function apriDialog(c: CostoAnnuale | null) {
  inModifica.value = c;
  errore.value = '';
  const annoCorrente = new Date().getFullYear();
  form.value = {
    voce: c?.voce ?? 'tari',
    anno: String(c?.anno ?? annoCorrente),
    importo_annuale: c?.importo_annuale ?? '',
    valid_from: c?.valid_from ?? `${annoCorrente}-01-01`,
    valid_to: c?.valid_to ?? null,
    note: c?.note ?? '',
  };
  dialog.value = true;
}

async function salva() {
  errore.value = '';
  const f = form.value;
  if (!Number(f.anno) || f.importo_annuale === '' || !f.valid_from) {
    errore.value = 'Anno, importo e data di inizio validità sono obbligatori.';
    return;
  }
  saving.value = true;
  const payload = {
    voce: f.voce,
    anno: Number(f.anno),
    importo_annuale: f.importo_annuale,
    valid_from: f.valid_from,
    valid_to: f.valid_to || null,
    note: f.note,
  };
  try {
    if (inModifica.value) {
      await api.patch(`/api/v1/annual-utility-costs/${inModifica.value.id}/`, payload);
      $q.notify({ type: 'positive', message: 'Costo annuale aggiornato.' });
    } else {
      await api.post('/api/v1/annual-utility-costs/', payload);
      $q.notify({ type: 'positive', message: 'Costo annuale creato.' });
    }
    dialog.value = false;
    await carica();
  } catch (e: unknown) {
    errore.value = messaggioErrore(e, 'Salvataggio non riuscito.');
  } finally {
    saving.value = false;
  }
}

function elimina(c: CostoAnnuale) {
  $q.dialog({
    title: 'Eliminare il costo annuale?',
    message: `${c.voce_display || etichettaVoce(c.voce)} ${c.anno} verrà rimosso.`,
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Elimina' },
  }).onOk(() => {
    void (async () => {
      try {
        await api.delete(`/api/v1/annual-utility-costs/${c.id}/`);
        costi.value = costi.value.filter((x) => x.id !== c.id);
        $q.notify({ type: 'positive', message: 'Costo annuale eliminato.' });
      } catch (e: unknown) {
        $q.notify({ type: 'negative', message: messaggioErrore(e, 'Eliminazione non riuscita.') });
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
.imm-costo__importo {
  font-size: 14px;
  font-weight: 600;
  color: var(--vp-ink);
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
</style>
