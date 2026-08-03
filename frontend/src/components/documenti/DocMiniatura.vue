<template>
  <!-- Immagine: anteprima vera -->
  <div v-if="!pagina.is_pdf" class="vp-dmin" :style="dimensioni">
    <div class="vp-dmin__bordo" :style="{ background: stile.dot }" />
    <!-- Miniatura decorativa: il nome del documento è già nella riga accanto. -->
    <img :src="pagina.file" alt="" class="vp-dmin__img" />
    <div v-if="etichetta" class="vp-dmin__lab vp-mono">{{ etichetta }}</div>
  </div>

  <!-- PDF: carta rigata (non c'è anteprima senza render lato server) -->
  <div v-else class="vp-dmin" :style="dimensioni">
    <div class="vp-dmin__bordo" :style="{ background: stile.dot }" />
    <div class="vp-dmin__righe" />
    <div class="vp-dmin__lab vp-mono">PDF</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { PaginaDocumento, StatoDocumento } from 'stores/fascicolo';
import { STILI_STATO } from 'src/utils/statoDocumento';

const props = withDefaults(
  defineProps<{
    /** Il file da mostrare: una voce del fascicolo ne ha sempre almeno uno. */
    pagina: PaginaDocumento;
    stato: StatoDocumento;
    larghezza?: number;
    altezza?: number;
  }>(),
  { larghezza: 40, altezza: 50 },
);

const stile = computed(() => STILI_STATO[props.stato]);
const dimensioni = computed(() => ({
  width: `${props.larghezza}px`,
  height: `${props.altezza}px`,
}));
// Solo le etichette vere ("fronte", "retro"): "pagina 1" è rumore.
const etichetta = computed(() => {
  const descrizione = props.pagina?.descrizione ?? '';
  return descrizione.length <= 8 ? descrizione : '';
});
</script>

<style scoped>
.vp-dmin {
  position: relative;
  flex: none;
  overflow: hidden;
  border-radius: var(--vp-r-sm);
  border: 1px solid var(--vp-paper-3);
  background: var(--vp-cream);
  box-shadow: var(--vp-shadow-1);
  display: flex;
  flex-direction: column;
}
.vp-dmin__bordo {
  height: 5px;
  flex: none;
  opacity: 0.55;
}
.vp-dmin__img {
  flex: 1;
  min-height: 0;
  width: 100%;
  object-fit: cover;
}
.vp-dmin__righe {
  flex: 1;
  opacity: 0.85;
  background-image: repeating-linear-gradient(
    0deg,
    var(--vp-paper-3) 0 1px,
    transparent 1px 6px
  );
  background-position: 0 6px;
}
.vp-dmin__lab {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 1px 0;
  text-align: center;
  font-size: 8px;
  letter-spacing: 0.02em;
  color: var(--vp-ink-3);
  background: var(--vp-paper-2);
}
</style>
