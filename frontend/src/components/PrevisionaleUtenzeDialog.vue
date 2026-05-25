<template>
  <q-dialog v-model="aperto" persistent>
    <q-card class="vp-prev-dlg">
      <q-card-section class="row items-center q-pb-none">
        <div>
          <div class="vp-eyebrow">Previsionale utenze</div>
          <div class="vp-display vp-prev-dlg__titolo">
            Addebito a uscita inquilino
          </div>
          <div class="vp-prev-dlg__sub">
            Stima del consumo utenze tra l'ultima bolletta nota e la
            restituzione del deposito, trattenuta dall'importo da rendere.
          </div>
        </div>
        <q-space />
        <q-btn icon="close" flat round dense @click="annulla" />
      </q-card-section>

      <q-card-section>
        <div v-if="caricamento" class="vp-prev-dlg__loader">
          <q-spinner color="primary" size="32px" />
        </div>
        <q-banner v-else-if="erroreStima" class="bg-amber-1 text-amber-9" rounded>
          {{ erroreStima }}
        </q-banner>
        <template v-else-if="stima">
          <q-list dense class="vp-prev-dlg__lista">
            <q-item>
              <q-item-section>Periodo coperto</q-item-section>
              <q-item-section side>
                {{ formattaData(stima.data_da) }} →
                {{ formattaData(stima.data_a) }}
              </q-item-section>
            </q-item>
            <q-item>
              <q-item-section>Giorni</q-item-section>
              <q-item-section side>{{ stima.giorni }}</q-item-section>
            </q-item>
            <q-item>
              <q-item-section>Media giornaliera</q-item-section>
              <q-item-section side>
                <span class="vp-mono">{{ formattaEuro(stima.media_giornaliera) }}/g</span>
              </q-item-section>
            </q-item>
          </q-list>

          <q-form class="q-gutter-md q-mt-sm" @submit.prevent="salva">
            <q-input
              v-model.number="importo"
              type="number"
              step="0.01"
              outlined
              dense
              label="Importo a debito inquilino (€)"
              hint="Puoi correggere la stima per sconti concordati."
            />
            <q-input
              v-model="descrizione"
              outlined
              dense
              label="Descrizione"
              maxlength="200"
            />
            <q-banner v-if="errore" class="bg-red-1 text-red-9" rounded>
              {{ errore }}
            </q-banner>
          </q-form>

          <q-expansion-item
            v-if="stima.basato_su.length"
            dense
            label="Bollette utenze di riferimento"
            class="vp-prev-dlg__exp"
          >
            <q-list dense>
              <q-item v-for="r in stima.basato_su" :key="r.receivable_id">
                <q-item-section>
                  <q-item-label>
                    {{ formattaData(r.periodo_da) }} → {{ formattaData(r.periodo_a) }}
                  </q-item-label>
                  <q-item-label caption>
                    {{ r.giorni_presenza }} giorni · media
                    {{ formattaEuro(r.importo_dovuto / r.giorni_presenza) }}/g
                  </q-item-label>
                </q-item-section>
                <q-item-section side>
                  <span class="vp-mono">{{ formattaEuro(r.importo_dovuto) }}</span>
                </q-item-section>
              </q-item>
            </q-list>
          </q-expansion-item>
        </template>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn flat color="primary" label="Annulla" no-caps @click="annulla" />
        <q-btn
          unelevated
          color="primary"
          label="Crea addebito"
          no-caps
          :loading="salvando"
          :disable="!stima || !importo || importo <= 0"
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
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';

interface RigaBasatoSu {
  receivable_id: number;
  periodo_da: string | null;
  periodo_a: string | null;
  importo_dovuto: number;
  giorni_presenza: number;
}

interface Stima {
  tenant_id: number;
  data_da: string;
  data_a: string;
  giorni: number;
  media_giornaliera: number;
  importo_stimato: number;
  basato_su: RigaBasatoSu[];
}

const props = defineProps<{
  modelValue: boolean;
  tenantId: number;
  assignmentId: number;
  dataTarget?: string | null;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void;
  (e: 'saved'): void;
}>();

const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

const aperto = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
});

const caricamento = ref(false);
const erroreStima = ref('');
const stima = ref<Stima | null>(null);
const importo = ref(0);
const descrizione = ref('');
const salvando = ref(false);
const errore = ref('');

async function caricaStima() {
  caricamento.value = true;
  erroreStima.value = '';
  stima.value = null;
  try {
    const params = props.dataTarget ? { data_target: props.dataTarget } : {};
    const resp = await api.get<Stima>(
      `/api/v1/tenants/${props.tenantId}/previsionale-utenze/`,
      { params },
    );
    stima.value = resp.data;
    importo.value = Number(resp.data.importo_stimato.toFixed(2));
    descrizione.value =
      `Previsionale utenze ${formattaData(resp.data.data_da)} → ${formattaData(resp.data.data_a)}`;
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } };
    erroreStima.value =
      err.response?.data?.detail ?? 'Impossibile calcolare la stima.';
  } finally {
    caricamento.value = false;
  }
}

watch(
  () => props.modelValue,
  (apertoNuovo) => {
    if (apertoNuovo) {
      void caricaStima();
      errore.value = '';
    }
  },
);

function annulla() {
  aperto.value = false;
}

async function salva() {
  if (!stima.value || !importo.value || importo.value <= 0) return;
  salvando.value = true;
  errore.value = '';
  try {
    await api.post('/api/v1/extra-charges/', {
      assignment: props.assignmentId,
      data: stima.value.data_a,
      scadenza: stima.value.data_a,
      descrizione: descrizione.value || 'Previsionale utenze',
      importo: importo.value.toFixed(2),
    });
    Notify.create({
      type: 'positive',
      message: 'Addebito previsionale creato.',
    });
    aperto.value = false;
    emit('saved');
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } };
    errore.value =
      err.response?.data?.detail ?? 'Errore nella creazione del Receivable.';
  } finally {
    salvando.value = false;
  }
}
</script>

<style lang="scss" scoped>
.vp-prev-dlg {
  min-width: 480px;
  max-width: 92vw;
}
.vp-prev-dlg__titolo {
  font-size: var(--vp-text-lg, 1.1rem);
}
.vp-prev-dlg__sub {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm, 0.9rem);
  margin-top: 2px;
}
.vp-prev-dlg__loader {
  display: flex;
  justify-content: center;
  padding: var(--vp-gap-4);
}
.vp-prev-dlg__lista {
  background: var(--vp-paper-1);
  border-radius: var(--vp-r-md);
  padding: var(--vp-gap-1) 0;
}
.vp-prev-dlg__exp {
  margin-top: var(--vp-gap-3);
}
</style>
