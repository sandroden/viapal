<template>
  <q-page padding class="vp-404">
    <div class="vp-404__icon">
      <q-icon name="signpost" size="64px" />
    </div>
    <div class="vp-display vp-404__codice">404</div>
    <div class="vp-display vp-404__titolo">La pagina non esiste</div>
    <p class="vp-404__msg">
      Forse il link è cambiato o c'è un refuso nell'indirizzo.
    </p>
    <q-btn unelevated color="primary" no-caps :to="homePath" label="Torna a casa" />
  </q-page>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useAuthStore } from 'stores/auth';

const auth = useAuthStore();
const homePath = computed(() => auth.homePath);
</script>

<style scoped>
.vp-404 {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: var(--vp-gap-3);
  background: var(--vp-paper);
  color: var(--vp-ink);
}
.vp-404__icon {
  color: var(--vp-terra);
  opacity: 0.7;
}
.vp-404__codice {
  font-size: var(--vp-text-5xl);
  color: var(--vp-terra-deep);
  line-height: 1;
}
.vp-404__titolo {
  font-size: var(--vp-text-2xl);
}
.vp-404__msg {
  color: var(--vp-ink-2);
  max-width: 360px;
  margin: 0 0 var(--vp-gap-3);
}
</style>
