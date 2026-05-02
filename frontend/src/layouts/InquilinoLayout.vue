<template>
  <q-layout view="lHh Lpr lFf">
    <q-header elevated class="vp-header">
      <q-toolbar>
        <q-toolbar-title class="text-display">
          Viapal
        </q-toolbar-title>
        <q-space />
        <q-btn flat dense icon="logout" aria-label="Esci" @click="logout" />
      </q-toolbar>
    </q-header>

    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
import { useAuthStore } from 'stores/auth';

const auth = useAuthStore();
const router = useRouter();

async function logout() {
  await auth.logout();
  await router.replace('/login');
}
</script>

<style scoped>
.vp-header {
  background: var(--vp-sage-deep);
  color: white;
}
</style>
