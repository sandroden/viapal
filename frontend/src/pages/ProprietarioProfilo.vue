<template>
  <q-page padding class="vp-page vp-area-personale">
    <div class="vp-eyebrow">Area personale</div>
    <h1 class="vp-area-personale__titolo">{{ nominativo }}</h1>

    <!-- Dati dell'account, in sola lettura: l'anagrafica del proprietario
         (nominativo, codice fiscale, indirizzo) si modifica dal tab Membri
         dell'immobile, dove vive insieme alle quote. -->
    <q-card class="vp-area-personale__card">
      <q-list>
        <q-item>
          <q-item-section>
            <q-item-label caption>Username</q-item-label>
            <q-item-label>{{ auth.user?.username }}</q-item-label>
          </q-item-section>
        </q-item>
        <q-item v-if="auth.user?.email">
          <q-item-section>
            <q-item-label caption>Email</q-item-label>
            <q-item-label>{{ auth.user.email }}</q-item-label>
          </q-item-section>
        </q-item>
        <q-item v-if="propStore.mioRuolo">
          <q-item-section>
            <q-item-label caption>Ruolo su {{ propStore.activeProperty?.nome }}</q-item-label>
            <q-item-label>{{ etichettaRuolo(propStore.mioRuolo) }}</q-item-label>
          </q-item-section>
        </q-item>
      </q-list>
    </q-card>

    <NotifichePushPannello
      class="vp-area-personale__card q-mt-md"
      descrizione="Avvisi sugli immobili che gestisci, anche ad app chiusa"
    />

    <CambioPasswordPannello class="vp-area-personale__card q-mt-md" />

    <div class="vp-area-personale__logout">
      <q-btn outline color="primary" icon="logout" label="Esci" no-caps @click="logout" />
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from 'stores/auth';
import { etichettaRuolo, usePropertiesStore } from 'stores/properties';
import NotifichePushPannello from 'components/profilo/NotifichePushPannello.vue';
import CambioPasswordPannello from 'components/profilo/CambioPasswordPannello.vue';

const auth = useAuthStore();
const propStore = usePropertiesStore();
const router = useRouter();

const nominativo = computed(
  () =>
    [auth.user?.first_name, auth.user?.last_name].filter(Boolean).join(' ') ||
    auth.user?.username ||
    '—',
);

async function logout() {
  await auth.logout();
  await router.replace('/login');
}
</script>

<style scoped>
.vp-area-personale {
  max-width: 640px;
  margin: 0 auto;
}
.vp-area-personale__titolo {
  font-family: var(--vp-font-display);
  font-size: 30px;
  font-weight: 500;
  line-height: 1.1;
  margin: var(--vp-gap-1) 0 var(--vp-gap-4);
}
.vp-area-personale__card {
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  overflow: hidden;
}
.vp-area-personale__logout {
  margin-top: var(--vp-gap-5);
  display: flex;
  justify-content: center;
}
</style>
