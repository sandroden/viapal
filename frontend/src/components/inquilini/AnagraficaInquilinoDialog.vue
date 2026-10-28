<template>
  <!-- no-route-dismiss: questo dialog si apre da un parametro della query
       (?modifica=anagrafica), e subito dopo la pagina riscrive la query per
       consumarlo. Senza, quella navigazione lo richiuderebbe all'istante. -->
  <q-dialog v-model="aperto" no-route-dismiss @before-show="carica">
    <q-card style="width: 520px; max-width: min(640px, 92vw)">
      <q-card-section>
        <div class="vp-section-title">Anagrafica</div>
        <div class="vp-hint">
          Nascita, residenza ed estremi del documento servono ai documenti
          generati (atto di subentro, cessione di fabbricato).
        </div>
      </q-card-section>

      <q-card-section style="max-height: 62vh; overflow-y: auto">
        <q-inner-loading :showing="caricamento" />

        <q-input
          v-model="form.nominativo"
          label="Nominativo"
          outlined
          dense
          hint="Come compare in tutta l'applicazione"
          class="q-mb-md"
          data-testid="anagrafica-nominativo"
        />

        <AnagraficaPersonaCampi ref="campiRef" v-model="form" />

        <div class="vp-section-title q-mt-md">Recapiti</div>
        <div class="row q-col-gutter-sm">
          <div class="col-6">
            <q-input
              :ref="(el) => registra('telefono', el)"
              v-model="form.telefono"
              label="Telefono"
              outlined
              dense
            />
          </div>
          <div class="col-6">
            <q-input v-model="form.email" label="Email" type="email" outlined dense />
          </div>
        </div>

        <q-banner v-if="errore" class="vp-banner-errore q-mt-md" rounded dense>
          {{ errore }}
        </q-banner>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn v-close-popup flat no-caps label="Annulla" />
        <q-btn
          color="primary"
          no-caps
          label="Salva"
          :loading="salvataggio"
          data-testid="salva-anagrafica"
          @click="salva"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue';
import { useQuasar, type QInput } from 'quasar';
import { isAxiosError } from 'axios';
import { api } from 'boot/axios';
import AnagraficaPersonaCampi from './AnagraficaPersonaCampi.vue';
import {
  anagraficaVuota,
  payloadAnagrafica,
  riempi,
  type AnagraficaPersona,
} from './anagrafica';

const props = defineProps<{
  modelValue: boolean;
  tenantId: number;
  /** Campo su cui portare il fuoco (dal link dei "dati mancanti"). */
  campo?: string | null;
}>();

const emit = defineEmits<{
  'update:modelValue': [valore: boolean];
  salvato: [];
}>();

interface FormAnagrafica extends AnagraficaPersona {
  nominativo: string;
  telefono: string;
  email: string;
}

function vuoto(): FormAnagrafica {
  return { ...anagraficaVuota(), nominativo: '', telefono: '', email: '' };
}

const $q = useQuasar();
const form = ref<FormAnagrafica>(vuoto());
const caricamento = ref(false);
const salvataggio = ref(false);
const errore = ref('');
const campiRef = ref<InstanceType<typeof AnagraficaPersonaCampi> | null>(null);
const campi = new Map<string, QInput>();

const aperto = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
});

function registra(campo: string, el: unknown) {
  if (el) campi.set(campo, el as QInput);
  else campi.delete(campo);
}

async function carica() {
  caricamento.value = true;
  errore.value = '';
  try {
    const { data } = await api.get<Partial<FormAnagrafica>>(
      `/api/v1/tenants/${props.tenantId}/`,
    );
    form.value = riempi(vuoto(), data);
  } catch {
    errore.value = 'Impossibile leggere i dati.';
  } finally {
    caricamento.value = false;
  }
  await focusCampo();
}

async function focusCampo() {
  if (!props.campo) return;
  await nextTick();
  // Recapiti stanno qui, il resto nel componente dei campi anagrafici.
  if (campi.has(props.campo)) campi.get(props.campo)?.focus();
  else campiRef.value?.focus(props.campo);
}

async function salva() {
  salvataggio.value = true;
  errore.value = '';
  const f = form.value;
  try {
    await api.patch(`/api/v1/tenants/${props.tenantId}/`, {
      ...payloadAnagrafica(f),
      nominativo: f.nominativo,
      telefono: f.telefono,
      email: f.email,
    });
    $q.notify({ type: 'positive', message: 'Anagrafica aggiornata.' });
    aperto.value = false;
    emit('salvato');
  } catch (e: unknown) {
    errore.value = isAxiosError(e)
      ? ((e.response?.data as { detail?: string })?.detail ?? 'Salvataggio non riuscito.')
      : 'Salvataggio non riuscito.';
  } finally {
    salvataggio.value = false;
  }
}
</script>
