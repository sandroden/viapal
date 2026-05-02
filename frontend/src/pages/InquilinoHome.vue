<template>
  <q-page padding>
    <div class="q-mb-md">
      <div class="text-h5 text-display">Ciao, {{ auth.user?.first_name || auth.user?.username }}</div>
      <div class="text-subtitle2 text-grey-7">la casa, in tasca</div>
    </div>

    <q-card class="viapal-card q-mb-md">
      <div class="text-overline text-grey-7">Da pagare</div>
      <div class="text-h6 q-mt-sm">Tutto in regola</div>
      <p class="text-grey-7 q-mt-sm">
        Quando ci sarà un affitto o un conguaglio da saldare, lo vedrai qui.
      </p>
    </q-card>

    <q-card class="viapal-card">
      <div class="text-overline text-grey-7">I tuoi pagamenti</div>
      <div class="text-h6 q-mt-sm">Storico vuoto</div>
      <p class="text-grey-7 q-mt-sm">Nessun pagamento registrato ancora.</p>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { useAuthStore } from 'stores/auth';
const auth = useAuthStore();
</script>
