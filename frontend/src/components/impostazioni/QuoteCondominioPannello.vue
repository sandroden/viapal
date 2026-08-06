<template>
  <CardSezione
    titolo="Quota condominiale degli inquilini"
    descrizione="Quota mensile che si somma al canone. Senza inquilino vale per tutti; con un inquilino indicato vale solo per lui e prevale sulla quota di tutti."
  >
    <template v-if="puoModificare" #azioni>
      <BtnSoft
        etichetta="Nuova quota"
        data-testid="nuova-quota-condominio"
        @click="apriDialog(null)"
      />
    </template>

    <div v-if="loading" class="q-pa-md flex flex-center">
      <q-spinner size="28px" />
    </div>
    <div v-else class="imm-elenco">
      <RigaElenco
        v-for="(q, i) in quote"
        :key="q.id"
        :ultima="i === quote.length - 1"
        data-testid="riga-quota"
      >
        <template #titolo>
          <span class="vp-mono">{{ importo(q.importo_mensile) }}/mese</span>
        </template>
        <template #badge>
          <EtichettaStato :tono="q.tenant ? 'terra' : 'off'">
            {{ q.tenant ? q.tenant_nominativo : 'Tutti' }}
          </EtichettaStato>
          <EtichettaStato v-if="!q.valid_to" tono="ok">In vigore</EtichettaStato>
        </template>
        <template #meta>{{ periodo(q) }}</template>
        <template #azioni>
          <AzioniRiga
            :oggetto="`quota dal ${q.valid_from}`"
            :puo-modificare="puoModificare"
            :puo-eliminare="puoModificare"
            @modifica="apriDialog(q)"
            @elimina="elimina(q)"
          />
        </template>
      </RigaElenco>
      <div v-if="quote.length === 0" class="imm-vuoto">
        Nessuna quota condominiale a carico degli inquilini.
      </div>
    </div>
  </CardSezione>

  <!-- Dialog quota condominio -->
  <q-dialog v-model="dialog">
    <q-card style="min-width: 420px">
      <q-card-section>
        <div class="vp-section-title">
          {{ inModifica ? 'Modifica quota condominio' : 'Nuova quota condominio' }}
        </div>
      </q-card-section>
      <q-card-section class="q-gutter-md">
        <q-select
          v-model="form.tenant"
          :options="opzioniInquilino"
          label="Vale per"
          outlined
          dense
          emit-value
          map-options
          data-testid="quota-tenant"
        />
        <q-input
          v-model="form.importo_mensile"
          label="Importo mensile"
          type="number"
          min="0"
          step="0.01"
          suffix="€"
          outlined
          dense
          data-testid="quota-importo"
        />
        <div class="row q-col-gutter-sm">
          <div class="col-6">
            <q-input
              v-model="form.valid_from"
              label="Valida dal"
              type="date"
              outlined
              dense
              data-testid="quota-valid-from"
            />
          </div>
          <div class="col-6">
            <q-input
              v-model="form.valid_to"
              label="Valida fino al"
              type="date"
              outlined
              dense
              clearable
              hint="Vuoto = tuttora in vigore"
            />
          </div>
        </div>
        <q-input v-model="form.note" label="Note" type="textarea" autogrow outlined dense />
        <div class="vp-hint">
          La modifica vale sui canoni generati d'ora in poi: quelli già
          emessi non cambiano da soli.
        </div>
        <q-banner v-if="errore" class="vp-banner-errore" rounded dense>{{ errore }}</q-banner>
      </q-card-section>
      <q-card-actions align="right">
        <q-btn v-close-popup flat label="Annulla" />
        <q-btn
          color="primary"
          label="Salva"
          :loading="saving"
          data-testid="salva-quota"
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
import { useTenantsStore } from 'stores/tenants';
import { useFormatoData } from 'src/composables/useFormatoData';
import CardSezione from './ui/CardSezione.vue';
import RigaElenco from './ui/RigaElenco.vue';
import EtichettaStato from './ui/EtichettaStato.vue';
import BtnSoft from './ui/BtnSoft.vue';
import AzioniRiga from './ui/AzioniRiga.vue';

interface QuotaCondominio {
  id: number;
  tenant: number | null;
  tenant_nominativo: string | null;
  valid_from: string;
  valid_to: string | null;
  importo_mensile: string;
  note: string;
}

defineProps<{ puoModificare: boolean }>();

const $q = useQuasar();
const tenantsStore = useTenantsStore();
const { formattaData } = useFormatoData();

const quote = ref<QuotaCondominio[]>([]);
const loading = ref(true);

/** "Tutti" (quota base dell'immobile) più i singoli inquilini, per cui la
 *  quota è un'eccezione che prevale sulla base. Solo inquilini con almeno
 *  una assegnazione (anche futura): una quota su un profilo mai assegnato
 *  non entrerebbe mai nel calcolo del canone. */
const opzioniInquilino = computed(() => [
  { label: 'Tutti gli inquilini', value: null },
  ...tenantsStore.tenantsConAssignment.map((t) => ({ label: t.nominativo, value: t.id })),
]);

function importo(v: string): string {
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString('it-IT', { style: 'currency', currency: 'EUR' })
    : v;
}

function periodo(q: QuotaCondominio): string {
  const parti = [`dal ${formattaData(q.valid_from)}`];
  parti.push(q.valid_to ? `al ${formattaData(q.valid_to)}` : 'tuttora in vigore');
  if (q.note) parti.push(q.note);
  return parti.join(' · ');
}

function asArray<T>(data: T[] | { results: T[] } | undefined | null): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : (data.results ?? []);
}

async function carica() {
  loading.value = true;
  try {
    const { data } = await api.get<QuotaCondominio[] | { results: QuotaCondominio[] }>(
      '/api/v1/quote-condominio/',
    );
    quote.value = asArray(data);
  } catch (e: unknown) {
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, 'Caricamento quote condominio non riuscito.'),
    });
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void carica();
  void tenantsStore.fetchTenantsConAssignment();
});

const dialog = ref(false);
const inModifica = ref<QuotaCondominio | null>(null);

interface FormQuota {
  tenant: number | null;
  importo_mensile: string;
  valid_from: string;
  valid_to: string | null;
  note: string;
}

const form = ref<FormQuota>({
  tenant: null,
  importo_mensile: '',
  valid_from: '',
  valid_to: null,
  note: '',
});
const saving = ref(false);
const errore = ref('');

function apriDialog(q: QuotaCondominio | null) {
  inModifica.value = q;
  errore.value = '';
  form.value = {
    tenant: q?.tenant ?? null,
    importo_mensile: q?.importo_mensile ?? '',
    valid_from: q?.valid_from ?? new Date().toISOString().slice(0, 10),
    valid_to: q?.valid_to ?? null,
    note: q?.note ?? '',
  };
  void tenantsStore.fetchTenantsConAssignment(true);
  dialog.value = true;
}

async function salva() {
  errore.value = '';
  const f = form.value;
  if (f.importo_mensile === '' || !f.valid_from) {
    errore.value = 'Importo e data di inizio validità sono obbligatori.';
    return;
  }
  saving.value = true;
  const payload = {
    tenant: f.tenant,
    importo_mensile: f.importo_mensile,
    valid_from: f.valid_from,
    valid_to: f.valid_to || null,
    note: f.note,
  };
  try {
    if (inModifica.value) {
      await api.patch(`/api/v1/quote-condominio/${inModifica.value.id}/`, payload);
      $q.notify({ type: 'positive', message: 'Quota condominio aggiornata.' });
    } else {
      await api.post('/api/v1/quote-condominio/', payload);
      $q.notify({ type: 'positive', message: 'Quota condominio creata.' });
    }
    dialog.value = false;
    await carica();
  } catch (e: unknown) {
    errore.value = messaggioErrore(e, 'Salvataggio non riuscito.');
  } finally {
    saving.value = false;
  }
}

function elimina(q: QuotaCondominio) {
  $q.dialog({
    title: 'Eliminare la quota?',
    message: `La quota di ${q.importo_mensile}€/mese dal ${q.valid_from} verrà rimossa.`,
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Elimina' },
  }).onOk(() => {
    void (async () => {
      try {
        await api.delete(`/api/v1/quote-condominio/${q.id}/`);
        quote.value = quote.value.filter((x) => x.id !== q.id);
        $q.notify({ type: 'positive', message: 'Quota eliminata.' });
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
