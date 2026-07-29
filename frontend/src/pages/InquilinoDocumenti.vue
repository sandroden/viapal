<template>
  <q-page padding class="vp-i-doc">
    <div class="vp-eyebrow">Profilo</div>
    <h1 class="vp-display vp-i-doc__titolo">I miei documenti</h1>
    <p class="vp-i-doc__intro">
      Carica qui i tuoi documenti (carta d'identità, codice fiscale, passaporto,
      permesso di soggiorno, contratto di lavoro). Per i documenti fronte/retro
      carica due file indicando "fronte" e "retro" nella descrizione.
    </p>

    <DocumentiPannello :store="store" :tipi="TIPI_DOCUMENTO_INQUILINO" />

    <div class="vp-i-doc__back">
      <q-btn flat color="primary" icon="arrow_back" label="Torna al profilo" no-caps to="/i/profilo" />
    </div>
  </q-page>
</template>

<script setup lang="ts">
import DocumentiPannello from 'components/DocumentiPannello.vue';
import { useDocumentiStore, TIPI_DOCUMENTO_INQUILINO } from 'stores/documenti';

const store = useDocumentiStore();
</script>

<style scoped>
.vp-i-doc {
  max-width: 640px;
  margin: 0 auto;
}
.vp-i-doc__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 var(--vp-gap-2);
}
.vp-i-doc__intro {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm);
  margin-bottom: var(--vp-gap-4);
}
.vp-i-doc__back {
  margin-top: var(--vp-gap-5);
  display: flex;
  justify-content: center;
}
</style>
