<template>
  <q-dialog v-model="aperto" persistent>
    <q-card class="vp-dep-dlg">
      <q-card-section class="row items-center q-pb-none">
        <div>
          <div class="vp-eyebrow">Restituzione deposito</div>
          <div class="vp-display vp-dep-dlg__titolo">
            {{ stato?.esiste ? 'Modifica restituzione' : 'Genera addebito di restituzione' }}
          </div>
          <div class="vp-dep-dlg__sub">
            Crea l'addebito (importo negativo) del deposito da rendere
            all'inquilino, datato alla restituzione. Serve a chiudere i conti.
          </div>
        </div>
        <q-space />
        <q-btn icon="close" flat round dense @click="annulla" />
      </q-card-section>

      <q-card-section>
        <div v-if="caricamento" class="vp-dep-dlg__loader">
          <q-spinner color="primary" size="32px" />
        </div>
        <q-banner v-else-if="erroreStato" class="bg-amber-1 text-amber-9" rounded>
          {{ erroreStato }}
        </q-banner>
        <template v-else-if="stato">
          <q-banner
            v-if="stato.pagato"
            class="bg-amber-1 text-amber-9 q-mb-md"
            rounded
          >
            La restituzione risulta già pagata: non è più modificabile da qui.
          </q-banner>
          <q-banner
            v-else-if="stato.ha_allocazioni"
            class="bg-amber-1 text-amber-9 q-mb-md"
            rounded
          >
            La restituzione è già riconciliata con dei bonifici: modificala
            dalla riconciliazione.
          </q-banner>

          <q-form class="q-gutter-md" @submit.prevent="salva">
            <q-input
              v-model="dataRestituzione"
              type="date"
              outlined
              dense
              label="Data restituzione"
              :readonly="bloccato"
            />
            <q-input
              v-model.number="importo"
              type="number"
              step="0.01"
              outlined
              dense
              label="Importo lordo da restituire (€)"
              hint="Il deposito versato; correggi per trattenute concordate (es. danni)."
              :readonly="bloccato"
            />
            <q-banner v-if="errore" class="bg-red-1 text-red-9" rounded>
              {{ errore }}
            </q-banner>
          </q-form>
        </template>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn flat color="primary" label="Annulla" no-caps @click="annulla" />
        <q-btn
          unelevated
          color="primary"
          :label="stato?.esiste ? 'Aggiorna' : 'Crea addebito'"
          no-caps
          :loading="salvando"
          :disable="bloccato || !importo || importo <= 0 || !dataRestituzione"
          @click="salva"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { Notify } from 'quasar';
import { api } from 'boot/axios';

interface StatoRestituzione {
  tenant_id: number;
  esiste: boolean;
  receivable_id: number | null;
  data_corrente: string | null;
  importo_corrente: number | null;
  pagato: boolean;
  ha_allocazioni: boolean;
  data_suggerita: string | null;
  importo_suggerito: number;
}

const props = defineProps<{
  modelValue: boolean;
  tenantId: number;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void;
  (e: 'saved'): void;
}>();

const aperto = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
});

const caricamento = ref(false);
const erroreStato = ref('');
const stato = ref<StatoRestituzione | null>(null);
const dataRestituzione = ref('');
const importo = ref(0);
const salvando = ref(false);
const errore = ref('');

const bloccato = computed(
  () => !!stato.value && (stato.value.pagato || stato.value.ha_allocazioni),
);

async function caricaStato() {
  caricamento.value = true;
  erroreStato.value = '';
  stato.value = null;
  try {
    const resp = await api.get<StatoRestituzione>(
      `/api/v1/tenants/${props.tenantId}/restituzione-deposito/`,
    );
    stato.value = resp.data;
    dataRestituzione.value = resp.data.data_corrente ?? resp.data.data_suggerita ?? '';
    importo.value = Number(
      (resp.data.importo_corrente ?? resp.data.importo_suggerito).toFixed(2),
    );
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } };
    erroreStato.value =
      err.response?.data?.detail ?? 'Impossibile leggere lo stato del deposito.';
  } finally {
    caricamento.value = false;
  }
}

watch(
  () => props.modelValue,
  (apertoNuovo) => {
    if (apertoNuovo) {
      errore.value = '';
      void caricaStato();
    }
  },
);

function annulla() {
  aperto.value = false;
}

async function salva() {
  if (bloccato.value || !importo.value || importo.value <= 0 || !dataRestituzione.value) {
    return;
  }
  salvando.value = true;
  errore.value = '';
  try {
    await api.post(`/api/v1/tenants/${props.tenantId}/restituzione-deposito/`, {
      data_restituzione: dataRestituzione.value,
      importo: importo.value.toFixed(2),
    });
    Notify.create({
      type: 'positive',
      message: stato.value?.esiste
        ? 'Restituzione deposito aggiornata.'
        : 'Addebito di restituzione creato.',
    });
    aperto.value = false;
    emit('saved');
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } };
    errore.value =
      err.response?.data?.detail ?? 'Errore nel salvataggio della restituzione.';
  } finally {
    salvando.value = false;
  }
}
</script>

<style lang="scss" scoped>
.vp-dep-dlg {
  min-width: 440px;
  max-width: 92vw;
}
.vp-dep-dlg__titolo {
  font-size: var(--vp-text-lg, 1.1rem);
}
.vp-dep-dlg__sub {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm, 0.9rem);
  margin-top: 2px;
}
.vp-dep-dlg__loader {
  display: flex;
  justify-content: center;
  padding: var(--vp-gap-4);
}
</style>
