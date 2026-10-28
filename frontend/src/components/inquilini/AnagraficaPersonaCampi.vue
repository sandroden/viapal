<template>
  <div class="vp-anagrafica-campi">
    <div class="row q-col-gutter-sm">
      <div class="col-12 col-sm-6">
        <q-input
          :ref="(el) => registra('cognome', el)"
          v-model="dati.cognome"
          label="Cognome"
          outlined
          dense
          data-testid="anagrafica-cognome"
        />
      </div>
      <div class="col-12 col-sm-6">
        <q-input
          :ref="(el) => registra('nome', el)"
          v-model="dati.nome"
          label="Nome"
          outlined
          dense
          data-testid="anagrafica-nome"
        />
      </div>
    </div>

    <div class="row q-col-gutter-sm q-mt-none">
      <div class="col-12 col-sm-4">
        <q-input
          :ref="(el) => registra('data_nascita', el)"
          v-model="dati.data_nascita"
          label="Data di nascita"
          type="date"
          stack-label
          outlined
          dense
          clearable
          data-testid="anagrafica-data-nascita"
        />
      </div>
      <div class="col-12 col-sm-4">
        <q-input
          :ref="(el) => registra('comune_nascita', el)"
          v-model="dati.comune_nascita"
          label="Comune di nascita"
          outlined
          dense
        />
      </div>
      <div class="col-12 col-sm-4">
        <q-input
          :ref="(el) => registra('provincia_nascita', el)"
          v-model="dati.provincia_nascita"
          label="Prov. o nazione"
          outlined
          dense
          hint="MB, oppure Marocco"
        />
      </div>
    </div>

    <div class="row q-col-gutter-sm q-mt-none">
      <div class="col-12 col-sm-6">
        <q-input
          :ref="(el) => registra('cittadinanza', el)"
          v-model="dati.cittadinanza"
          label="Cittadinanza"
          outlined
          dense
        />
      </div>
      <div class="col-12 col-sm-6">
        <q-input
          :ref="(el) => registra('codice_fiscale', el)"
          v-model="dati.codice_fiscale"
          label="Codice fiscale"
          outlined
          dense
          maxlength="16"
          input-style="text-transform: uppercase"
          data-testid="anagrafica-codice-fiscale"
        />
      </div>
    </div>

    <div class="vp-section-title q-mt-md">Residenza</div>
    <div class="row q-col-gutter-sm">
      <div class="col-12">
        <q-input
          :ref="(el) => registra('residenza_via', el)"
          v-model="dati.residenza_via"
          label="Via e numero civico"
          outlined
          dense
        />
      </div>
      <div class="col-12 col-sm-5">
        <q-input
          :ref="(el) => registra('residenza_comune', el)"
          v-model="dati.residenza_comune"
          label="Comune"
          outlined
          dense
        />
      </div>
      <div class="col-5 col-sm-3">
        <q-input
          :ref="(el) => registra('residenza_provincia', el)"
          v-model="dati.residenza_provincia"
          label="Prov."
          outlined
          dense
          maxlength="4"
          input-style="text-transform: uppercase"
        />
      </div>
      <div class="col-7 col-sm-4">
        <q-input
          :ref="(el) => registra('residenza_cap', el)"
          v-model="dati.residenza_cap"
          label="CAP"
          outlined
          dense
          maxlength="8"
        />
      </div>
    </div>

    <div class="vp-section-title q-mt-md">Documento d'identità</div>
    <div class="vp-hint q-mb-sm">
      Lo chiede la comunicazione di cessione di fabbricato.
    </div>
    <div class="row q-col-gutter-sm">
      <div class="col-12 col-sm-6">
        <q-select
          :ref="(el) => registra('documento_tipo', el)"
          v-model="dati.documento_tipo"
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
      <div class="col-12 col-sm-6">
        <q-input
          :ref="(el) => registra('documento_numero', el)"
          v-model="dati.documento_numero"
          label="Numero"
          outlined
          dense
          data-testid="anagrafica-documento-numero"
        />
      </div>
      <div class="col-12 col-sm-7">
        <q-input
          :ref="(el) => registra('documento_autorita', el)"
          v-model="dati.documento_autorita"
          label="Rilasciato da"
          outlined
          dense
        />
      </div>
      <div class="col-12 col-sm-5">
        <q-input
          :ref="(el) => registra('documento_data_rilascio', el)"
          v-model="dati.documento_data_rilascio"
          label="Data di rilascio"
          type="date"
          stack-label
          outlined
          dense
          clearable
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { QInput } from 'quasar';
import { TIPI_DOCUMENTO_IDENTITA, type AnagraficaPersona } from './anagrafica';

// L'oggetto è del genitore: i campi lo modificano in place.
const dati = defineModel<AnagraficaPersona>({ required: true });

const campi = new Map<string, QInput>();

function registra(campo: string, el: unknown) {
  if (el) campi.set(campo, el as QInput);
  else campi.delete(campo);
}

/** Porta il fuoco sul campo indicato (dal link dei "dati mancanti"). */
function focus(campo: string) {
  campi.get(campo)?.focus();
}

defineExpose({ focus });
</script>
