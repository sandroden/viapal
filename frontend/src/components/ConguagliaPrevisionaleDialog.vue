<template>
  <q-dialog v-model="aperto" persistent>
    <q-card class="vp-cong-dlg">
      <q-card-section class="row items-center q-pb-none">
        <div>
          <div class="vp-eyebrow">Conguaglio previsionale</div>
          <div class="vp-display vp-cong-dlg__titolo">
            Compensa con le utenze reali
          </div>
          <div class="vp-cong-dlg__sub">
            Crea un Receivable di rettifica negativo pari alla somma delle
            utenze reali nel periodo del previsionale. La differenza resta
            come saldo a favore dell'inquilino.
          </div>
        </div>
        <q-space />
        <q-btn icon="close" flat round dense @click="annulla" />
      </q-card-section>

      <q-card-section>
        <div v-if="caricamento" class="vp-cong-dlg__loader">
          <q-spinner color="primary" size="32px" />
        </div>
        <q-banner v-else-if="erroreAnteprima" class="bg-amber-1 text-amber-9" rounded>
          {{ erroreAnteprima }}
        </q-banner>
        <template v-else-if="anteprima">
          <q-list dense class="vp-cong-dlg__lista">
            <q-item>
              <q-item-section>Previsionale</q-item-section>
              <q-item-section side>
                <span class="vp-mono">
                  + {{ formattaEuro(anteprima.previsionale_importo) }}
                </span>
              </q-item-section>
            </q-item>
            <q-item>
              <q-item-section>Periodo coperto</q-item-section>
              <q-item-section side>
                {{ formattaData(anteprima.data_da) }} →
                {{ formattaData(anteprima.data_a) }}
              </q-item-section>
            </q-item>
            <q-separator spaced />
            <q-item>
              <q-item-section>Somma utenze reali</q-item-section>
              <q-item-section side>
                <span class="vp-mono">
                  {{ formattaEuro(anteprima.somma_utenze_reali) }}
                </span>
              </q-item-section>
            </q-item>
            <q-item>
              <q-item-section>
                <strong>Rettifica proposta</strong>
                <q-item-label caption>segno opposto al previsionale</q-item-label>
              </q-item-section>
              <q-item-section side>
                <strong class="vp-mono">
                  {{ formattaEuro(anteprima.rettifica_proposta) }}
                </strong>
              </q-item-section>
            </q-item>
            <q-separator spaced />
            <q-item>
              <q-item-section>
                <strong>Netto a favore inquilino</strong>
                <q-item-label caption>previsionale + rettifica</q-item-label>
              </q-item-section>
              <q-item-section side>
                <strong class="vp-mono">
                  {{ formattaEuro(anteprima.netto_a_favore_inquilino) }}
                </strong>
              </q-item-section>
            </q-item>
          </q-list>

          <q-expansion-item
            v-if="anteprima.utenze_reali.length"
            dense
            label="Utenze reali del periodo"
            class="vp-cong-dlg__exp"
          >
            <q-list dense>
              <q-item v-for="u in anteprima.utenze_reali" :key="u.receivable_id">
                <q-item-section>
                  <q-item-label>
                    {{ formattaData(u.periodo_da) }} → {{ formattaData(u.periodo_a) }}
                  </q-item-label>
                  <q-item-label caption>
                    {{ u.giorni_presenza }} gg presenza · quota
                    {{ formattaEuro(u.importo_dovuto) }}
                  </q-item-label>
                </q-item-section>
                <q-item-section side>
                  <span class="vp-mono">
                    {{ formattaEuro(u.quota_nel_periodo) }}
                  </span>
                </q-item-section>
              </q-item>
            </q-list>
          </q-expansion-item>

          <q-banner v-if="errore" class="bg-red-1 text-red-9 q-mt-md" rounded>
            {{ errore }}
          </q-banner>
        </template>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn flat color="primary" label="Annulla" no-caps @click="annulla" />
        <q-btn
          unelevated
          color="primary"
          label="Conguaglia"
          no-caps
          :loading="salvando"
          :disable="!anteprima || anteprima.somma_utenze_reali === 0"
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

interface UtenzaReale {
  receivable_id: number;
  periodo_da: string;
  periodo_a: string;
  importo_dovuto: number;
  giorni_totali: number;
  giorni_presenza: number;
  quota_nel_periodo: number;
}

interface Anteprima {
  previsionale_id: number;
  previsionale_importo: number;
  data_da: string;
  data_a: string;
  utenze_reali: UtenzaReale[];
  somma_utenze_reali: number;
  rettifica_proposta: number;
  netto_a_favore_inquilino: number;
}

const props = defineProps<{
  modelValue: boolean;
  tenantId: number;
  previsionaleId: number | null;
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
const erroreAnteprima = ref('');
const anteprima = ref<Anteprima | null>(null);
const salvando = ref(false);
const errore = ref('');

async function caricaAnteprima() {
  if (!props.previsionaleId) return;
  caricamento.value = true;
  erroreAnteprima.value = '';
  anteprima.value = null;
  try {
    const resp = await api.get<Anteprima>(
      `/api/v1/tenants/${props.tenantId}/conguaglia-previsionale/`,
      { params: { previsionale_id: props.previsionaleId } },
    );
    anteprima.value = resp.data;
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } };
    erroreAnteprima.value =
      err.response?.data?.detail ?? 'Impossibile calcolare il conguaglio.';
  } finally {
    caricamento.value = false;
  }
}

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      void caricaAnteprima();
      errore.value = '';
    }
  },
);

function annulla() {
  aperto.value = false;
}

async function salva() {
  if (!props.previsionaleId || !anteprima.value) return;
  salvando.value = true;
  errore.value = '';
  try {
    await api.post(
      `/api/v1/tenants/${props.tenantId}/conguaglia-previsionale/`,
      { previsionale_id: props.previsionaleId },
    );
    Notify.create({ type: 'positive', message: 'Conguaglio creato.' });
    aperto.value = false;
    emit('saved');
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } };
    errore.value =
      err.response?.data?.detail ?? 'Errore nel conguaglio.';
  } finally {
    salvando.value = false;
  }
}
</script>

<style lang="scss" scoped>
.vp-cong-dlg {
  min-width: 480px;
  max-width: 92vw;
}
.vp-cong-dlg__titolo {
  font-size: var(--vp-text-lg, 1.1rem);
}
.vp-cong-dlg__sub {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm, 0.9rem);
  margin-top: 2px;
}
.vp-cong-dlg__loader {
  display: flex;
  justify-content: center;
  padding: var(--vp-gap-4);
}
.vp-cong-dlg__lista {
  background: var(--vp-paper-1);
  border-radius: var(--vp-r-md);
  padding: var(--vp-gap-1) 0;
}
.vp-cong-dlg__exp {
  margin-top: var(--vp-gap-3);
}
</style>
