<template>
  <q-card data-testid="password-pannello">
    <q-expansion-item icon="lock_reset" label="Cambia password" header-class="text-primary">
      <q-form ref="cambioForm" class="q-pa-md q-gutter-md" @submit.prevent="cambiaPassword">
        <q-input
          v-model="pwdVecchia"
          type="password"
          label="Password attuale"
          outlined
          dense
          :rules="[(v) => !!v || 'Inserisci la password attuale']"
          autocomplete="current-password"
        />
        <q-input
          v-model="pwdNuova1"
          type="password"
          label="Nuova password"
          outlined
          dense
          :rules="[(v) => !!v || 'Inserisci la nuova password', (v) => v.length >= 8 || 'Almeno 8 caratteri']"
          autocomplete="new-password"
        />
        <q-input
          v-model="pwdNuova2"
          type="password"
          label="Conferma nuova password"
          outlined
          dense
          :rules="[(v) => v === pwdNuova1 || 'Le password non coincidono']"
          autocomplete="new-password"
        />
        <q-banner v-if="pwdErrore" class="text-white bg-red-7" rounded dense>
          {{ pwdErrore }}
        </q-banner>
        <q-btn
          type="submit"
          label="Aggiorna password"
          color="primary"
          unelevated
          no-caps
          :loading="pwdLoading"
        />
      </q-form>
    </q-expansion-item>
  </q-card>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue';
import { useQuasar, type QForm } from 'quasar';
import { useAuthStore } from 'stores/auth';

const auth = useAuthStore();
const $q = useQuasar();

const cambioForm = ref<QForm | null>(null);
const pwdVecchia = ref('');
const pwdNuova1 = ref('');
const pwdNuova2 = ref('');
const pwdErrore = ref('');
const pwdLoading = ref(false);

// Gli errori di allauth arrivano per campo: il primo utile è quello che
// spiega il rifiuto (password attuale sbagliata, nuova troppo debole).
function estraiErrorePwd(e: unknown): string {
  const data = (e as { response?: { data?: Record<string, unknown> } })?.response?.data;
  if (data) {
    for (const chiave of ['old_password', 'new_password2', 'new_password1', 'detail']) {
      const v = data[chiave];
      if (Array.isArray(v) && v.length) return String(v[0]);
      if (typeof v === 'string' && v) return v;
    }
  }
  return 'Impossibile aggiornare la password. Riprova.';
}

async function cambiaPassword() {
  pwdErrore.value = '';
  pwdLoading.value = true;
  try {
    await auth.changePassword(pwdVecchia.value, pwdNuova1.value, pwdNuova2.value);
    pwdVecchia.value = '';
    pwdNuova1.value = '';
    pwdNuova2.value = '';
    void nextTick(() => cambioForm.value?.resetValidation());
    $q.notify({ type: 'positive', message: 'Password aggiornata.' });
  } catch (e: unknown) {
    pwdErrore.value = estraiErrorePwd(e);
  } finally {
    pwdLoading.value = false;
  }
}
</script>
