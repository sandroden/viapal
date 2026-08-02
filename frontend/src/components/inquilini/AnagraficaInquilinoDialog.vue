<template>
  <q-dialog v-model="aperto" @before-show="carica">
    <q-card style="min-width: 520px; max-width: 640px">
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

        <div class="row q-col-gutter-sm">
          <div class="col-6">
            <q-input
              :ref="(el) => registra('cognome', el)"
              v-model="form.cognome"
              label="Cognome"
              outlined
              dense
              data-testid="anagrafica-cognome"
            />
          </div>
          <div class="col-6">
            <q-input
              :ref="(el) => registra('nome', el)"
              v-model="form.nome"
              label="Nome"
              outlined
              dense
              data-testid="anagrafica-nome"
            />
          </div>
        </div>

        <div class="row q-col-gutter-sm q-mt-none">
          <div class="col-4">
            <q-input
              :ref="(el) => registra('data_nascita', el)"
              v-model="form.data_nascita"
              label="Data di nascita"
              type="date"
              outlined
              dense
              clearable
              data-testid="anagrafica-data-nascita"
            />
          </div>
          <div class="col-4">
            <q-input
              :ref="(el) => registra('comune_nascita', el)"
              v-model="form.comune_nascita"
              label="Comune di nascita"
              outlined
              dense
            />
          </div>
          <div class="col-4">
            <q-input
              :ref="(el) => registra('provincia_nascita', el)"
              v-model="form.provincia_nascita"
              label="Provincia o nazione"
              outlined
              dense
              hint="MB, oppure Marocco"
            />
          </div>
        </div>

        <div class="row q-col-gutter-sm q-mt-none">
          <div class="col-6">
            <q-input
              :ref="(el) => registra('cittadinanza', el)"
              v-model="form.cittadinanza"
              label="Cittadinanza"
              outlined
              dense
            />
          </div>
          <div class="col-6">
            <q-input
              :ref="(el) => registra('codice_fiscale', el)"
              v-model="form.codice_fiscale"
              label="Codice fiscale"
              outlined
              dense
            />
          </div>
        </div>

        <div class="vp-section-title q-mt-md">Residenza</div>
        <div class="row q-col-gutter-sm">
          <div class="col-12">
            <q-input
              :ref="(el) => registra('residenza_via', el)"
              v-model="form.residenza_via"
              label="Via e numero civico"
              outlined
              dense
            />
          </div>
          <div class="col-5">
            <q-input
              :ref="(el) => registra('residenza_comune', el)"
              v-model="form.residenza_comune"
              label="Comune"
              outlined
              dense
            />
          </div>
          <div class="col-3">
            <q-input
              :ref="(el) => registra('residenza_provincia', el)"
              v-model="form.residenza_provincia"
              label="Prov."
              outlined
              dense
            />
          </div>
          <div class="col-4">
            <q-input
              :ref="(el) => registra('residenza_cap', el)"
              v-model="form.residenza_cap"
              label="CAP"
              outlined
              dense
            />
          </div>
        </div>

        <div class="vp-section-title q-mt-md">Documento d'identità</div>
        <div class="vp-hint q-mb-sm">
          Lo chiede la comunicazione di cessione di fabbricato.
        </div>
        <div class="row q-col-gutter-sm">
          <div class="col-6">
            <q-select
              :ref="(el) => registra('documento_tipo', el)"
              v-model="form.documento_tipo"
              :options="TIPI_DOCUMENTO_IDENTITA"
              label="Tipo"
              outlined
              dense
              emit-value
              map-options
              clearable
              data-testid="anagrafica-documento-tipo"
            />
          </div>
          <div class="col-6">
            <q-input
              :ref="(el) => registra('documento_numero', el)"
              v-model="form.documento_numero"
              label="Numero"
              outlined
              dense
              data-testid="anagrafica-documento-numero"
            />
          </div>
          <div class="col-7">
            <q-input
              :ref="(el) => registra('documento_autorita', el)"
              v-model="form.documento_autorita"
              label="Rilasciato da"
              outlined
              dense
            />
          </div>
          <div class="col-5">
            <q-input
              :ref="(el) => registra('documento_data_rilascio', el)"
              v-model="form.documento_data_rilascio"
              label="Data di rilascio"
              type="date"
              outlined
              dense
              clearable
            />
          </div>
        </div>

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

const TIPI_DOCUMENTO_IDENTITA = [
  { label: "Carta d'identità", value: 'carta_identita' },
  { label: 'Passaporto', value: 'passaporto' },
  { label: 'Permesso di soggiorno', value: 'permesso_soggiorno' },
];

interface FormAnagrafica {
  nominativo: string;
  cognome: string;
  nome: string;
  data_nascita: string | null;
  comune_nascita: string;
  provincia_nascita: string;
  cittadinanza: string;
  codice_fiscale: string;
  residenza_via: string;
  residenza_comune: string;
  residenza_provincia: string;
  residenza_cap: string;
  documento_tipo: string | null;
  documento_numero: string;
  documento_autorita: string;
  documento_data_rilascio: string | null;
  telefono: string;
  email: string;
}

function vuoto(): FormAnagrafica {
  return {
    nominativo: '',
    cognome: '',
    nome: '',
    data_nascita: null,
    comune_nascita: '',
    provincia_nascita: '',
    cittadinanza: '',
    codice_fiscale: '',
    residenza_via: '',
    residenza_comune: '',
    residenza_provincia: '',
    residenza_cap: '',
    documento_tipo: null,
    documento_numero: '',
    documento_autorita: '',
    documento_data_rilascio: null,
    telefono: '',
    email: '',
  };
}

const $q = useQuasar();
const form = ref<FormAnagrafica>(vuoto());
const caricamento = ref(false);
const salvataggio = ref(false);
const errore = ref('');
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
    const dati = vuoto();
    for (const chiave of Object.keys(dati) as Array<keyof FormAnagrafica>) {
      const valore = data[chiave];
      if (valore !== undefined && valore !== null) {
        (dati[chiave] as string) = String(valore);
      }
    }
    form.value = dati;
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
  campi.get(props.campo)?.focus();
}

async function salva() {
  salvataggio.value = true;
  errore.value = '';
  const f = form.value;
  try {
    await api.patch(`/api/v1/tenants/${props.tenantId}/`, {
      ...f,
      // Le date vuote arrivano come stringa vuota dagli input: il backend
      // vuole null.
      data_nascita: f.data_nascita || null,
      documento_data_rilascio: f.documento_data_rilascio || null,
      documento_tipo: f.documento_tipo ?? '',
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
