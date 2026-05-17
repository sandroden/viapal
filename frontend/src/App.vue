<template>
  <router-view />
  <div v-if="isDev" class="env-ribbon">DEV · LOCALE</div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';

// import.meta.env.DEV è true solo con `quasar dev` (server locale),
// false nella build di produzione: distingue locale da remoto.
const isDev = import.meta.env.DEV;

onMounted(() => {
  // Prefisso nel <title> del tab, così è riconoscibile anche tra le tab.
  if (isDev && !document.title.startsWith('[DEV]')) {
    document.title = `[DEV] ${document.title}`;
  }
});
</script>

<style>
.env-ribbon {
  position: fixed;
  bottom: 8px;
  right: 8px;
  z-index: 99999;
  background: #b71c1c;
  color: #fff;
  font: bold 11px/1 sans-serif;
  letter-spacing: 1px;
  padding: 6px 10px;
  border-radius: 4px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.35);
  pointer-events: none;
}
</style>
