<template>
  <q-page padding>
    <div class="q-mb-md">
      <div class="text-h4 text-display">Ciao, {{ auth.user?.first_name || auth.user?.username }}</div>
      <div class="text-subtitle2 text-grey-7">Area proprietari — hello world</div>
    </div>

    <div class="row q-gutter-md">
      <q-card class="viapal-card col-12 col-md-4">
        <div class="text-overline text-grey-7">Dashboard rendita</div>
        <div class="text-h6 q-mt-sm">Prossimamente</div>
        <p class="text-grey-7 q-mt-sm">KPI annuali, grafico mensile, prossime scadenze.</p>
      </q-card>

      <q-card class="viapal-card col-12 col-md-4">
        <div class="text-overline text-grey-7">Vista ritardi</div>
        <div class="text-h6 q-mt-sm">Prossimamente</div>
        <p class="text-grey-7 q-mt-sm">Pagamenti scaduti con codice colore semaforo.</p>
      </q-card>

      <q-card class="viapal-card col-12 col-md-4">
        <div class="text-overline text-grey-7">Conguagli</div>
        <div class="text-h6 q-mt-sm">Prossimamente</div>
        <p class="text-grey-7 q-mt-sm">Quadro annuale e generazione mensile.</p>
      </q-card>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { useAuthStore } from 'stores/auth';
const auth = useAuthStore();
</script>
