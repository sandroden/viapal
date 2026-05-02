<template>
  <q-page class="vp-login-page row items-center justify-center">
    <q-card class="vp-login-card q-pa-lg">
      <div class="text-h5 text-display q-mb-xs">Viapal</div>
      <div class="text-subtitle2 text-grey-7 q-mb-md">la casa, in tasca</div>

      <q-form @submit.prevent="onSubmit" class="q-gutter-md">
        <q-input
          v-model="username"
          label="Nome utente"
          autofocus
          outlined
          :rules="[(v) => !!v || 'Inserisci nome utente']"
          autocomplete="username"
        />
        <q-input
          v-model="password"
          type="password"
          label="Password"
          outlined
          :rules="[(v) => !!v || 'Inserisci password']"
          autocomplete="current-password"
        />

        <q-banner v-if="errore" class="text-white bg-red-7 q-mb-sm" rounded>
          {{ errore }}
        </q-banner>

        <q-btn
          type="submit"
          label="Entra"
          color="primary"
          class="full-width"
          :loading="loading"
          unelevated
          size="lg"
        />
      </q-form>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from 'stores/auth';

const username = ref('');
const password = ref('');
const errore = ref('');
const loading = ref(false);

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();

async function onSubmit() {
  errore.value = '';
  loading.value = true;
  try {
    await auth.login(username.value, password.value);
    const next = (route.query.next as string) || auth.homePath;
    await router.replace(next);
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { non_field_errors?: string[] } } })
      ?.response?.data?.non_field_errors?.[0];
    errore.value = msg || 'Credenziali non valide';
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.vp-login-page {
  min-height: 100vh;
  background: var(--vp-paper);
}
.vp-login-card {
  width: min(420px, 92vw);
  background: var(--vp-cream);
  border-radius: var(--vp-r-lg);
  box-shadow: var(--vp-shadow-2);
}
</style>
