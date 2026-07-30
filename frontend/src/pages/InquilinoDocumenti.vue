<template>
  <q-page padding class="vp-i-doc">
    <div class="vp-eyebrow">Profilo</div>
    <h1 class="vp-display vp-i-doc__titolo">I miei documenti</h1>
    <p class="vp-i-doc__intro">
      Carica qui i tuoi documenti (carta d'identità, codice fiscale, passaporto,
      permesso di soggiorno, contratto di lavoro). Per i documenti fronte/retro
      carica due file indicando "fronte" e "retro" nella descrizione.
      I documenti sono visibili solo a te e ai proprietari:
      <router-link to="/i/privacy">informativa privacy</router-link>.
    </p>

    <DocumentiPannello :store="store" :tipi="TIPI_DOCUMENTO_INQUILINO" />

    <h2 class="vp-i-doc__sottotitolo">Documenti della casa</h2>
    <p class="vp-i-doc__intro">
      Documenti condivisi dai proprietari: contratto di locazione, regolamento
      condominiale e simili. Puoi consultarli e scaricarli.
    </p>
    <DocumentiPannello
      :store="storeCasa"
      :tipi="TIPI_DOCUMENTO_PROPRIETA"
      solo-lettura
      testo-vuoto="I proprietari non hanno ancora condiviso documenti."
    />

    <div class="vp-i-doc__back">
      <q-btn flat color="primary" icon="arrow_back" label="Torna al profilo" no-caps to="/i/profilo" />
    </div>
  </q-page>
</template>

<script setup lang="ts">
import DocumentiPannello from 'components/DocumentiPannello.vue';
import {
  useDocumentiStore,
  useDocumentiProprietaStore,
  TIPI_DOCUMENTO_INQUILINO,
  TIPI_DOCUMENTO_PROPRIETA,
} from 'stores/documenti';

const store = useDocumentiStore();
const storeCasa = useDocumentiProprietaStore();
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
.vp-i-doc__sottotitolo {
  font-size: var(--vp-text-xl);
  font-weight: 600;
  color: var(--vp-ink);
  margin: var(--vp-gap-6) 0 var(--vp-gap-1);
}
.vp-i-doc__back {
  margin-top: var(--vp-gap-5);
  display: flex;
  justify-content: center;
}
</style>
