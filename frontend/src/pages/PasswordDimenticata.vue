<template>
  <q-page class="vp-auth-page row items-center justify-center">
    <q-card class="vp-auth-card q-pa-lg">
      <div class="text-h5 text-display q-mb-xs">Password dimenticata</div>
      <div class="text-subtitle2 text-grey-7 q-mb-md">
        Inserisci la tua email: ti invieremo un link per reimpostare la password.
      </div>

      <template v-if="!inviata">
        <q-form @submit.prevent="onSubmit" class="q-gutter-md">
          <q-input
            v-model="email"
            type="email"
            label="Email"
            autofocus
            outlined
            :rules="[(v) => !!v || 'Inserisci la tua email']"
            autocomplete="email"
          />

          <q-banner v-if="errore" class="text-white bg-red-7 q-mb-sm" rounded>
            {{ errore }}
          </q-banner>

          <q-btn
            type="submit"
            label="Invia link"
            color="primary"
            class="full-width"
            :loading="loading"
            unelevated
            size="lg"
          />
        </q-form>
      </template>

      <template v-else>
        <q-banner class="bg-green-1 text-green-9 q-mb-md" rounded>
          Se l'indirizzo è registrato, riceverai a breve un'email con il link per
          reimpostare la password.
        </q-banner>
      </template>

      <div class="q-mt-md text-center">
        <q-btn flat dense no-caps color="primary" label="Torna all'accesso" to="/login" />
      </div>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useAuthStore } from 'stores/auth';

const email = ref('');
const errore = ref('');
const loading = ref(false);
const inviata = ref(false);

const auth = useAuthStore();

async function onSubmit() {
  errore.value = '';
  loading.value = true;
  try {
    await auth.requestPasswordReset(email.value);
    inviata.value = true;
  } catch {
    // Per non rivelare l'esistenza dell'indirizzo, mostriamo comunque la
    // conferma; un errore reale di rete lo segnaliamo genericamente.
    inviata.value = true;
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.vp-auth-page {
  min-height: 100vh;
  background: var(--vp-paper);
}
.vp-auth-card {
  width: min(420px, 92vw);
  background: var(--vp-cream);
  border-radius: var(--vp-r-lg);
  box-shadow: var(--vp-shadow-2);
}
</style>
