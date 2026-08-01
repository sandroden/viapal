<template>
  <!-- I PDF non hanno anteprima nativa in <img>: iframe, che sull'app resta
       comunque dentro la pagina (i media privati sono same-origin). -->
  <iframe
    v-if="pagina.is_pdf"
    :src="pagina.file"
    :title="pagina.etichetta"
    class="vp-dpag vp-dpag--pdf"
  />
  <img v-else :src="pagina.file" :alt="pagina.etichetta" class="vp-dpag vp-dpag--img" />
</template>

<script setup lang="ts">
import type { PaginaDocumento } from 'stores/fascicolo';

defineProps<{ pagina: PaginaDocumento }>();
</script>

<style scoped>
.vp-dpag {
  display: block;
  border: none;
  border-radius: var(--vp-r-md);
}
.vp-dpag--pdf {
  width: 100%;
  height: 100%;
  background: var(--vp-cream);
}
/* L'immagine si adatta alla propria forma: niente bande di sfondo attorno. */
.vp-dpag--img {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.28);
}
</style>
