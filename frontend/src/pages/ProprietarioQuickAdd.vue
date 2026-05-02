<template>
  <q-page padding class="vp-p-qa">
    <div class="vp-eyebrow">Da mobile</div>
    <h1 class="vp-display vp-p-qa__titolo">Aggiungi rapida</h1>
    <p class="vp-p-qa__intro">
      Annota al volo una spesa: data, importo, due righe di descrizione.
    </p>

    <q-card class="vp-p-qa__card">
      <q-form class="q-gutter-md" @submit.prevent="salva">
        <q-input
          v-model="form.data"
          type="date"
          outlined
          label="Data"
          :rules="[(v) => !!v || 'Inserisci la data']"
        />
        <q-input
          v-model.number="form.importo"
          type="number"
          step="0.01"
          inputmode="decimal"
          outlined
          label="Importo (€)"
          autofocus
          :rules="[(v) => (v != null && v > 0) || 'Importo non valido']"
        />
        <q-input
          v-model="form.descrizione"
          outlined
          label="Cosa hai pagato?"
          :rules="[(v) => !!v || 'Inserisci una descrizione']"
        />
        <q-select
          v-model="form.categoria"
          outlined
          label="Categoria"
          :options="categorie"
          emit-value
          map-options
        />

        <q-banner v-if="errore" class="bg-red-1 text-red-9" rounded>{{ errore }}</q-banner>

        <q-btn
          unelevated
          color="primary"
          icon-right="check"
          label="Salva spesa"
          class="full-width"
          size="lg"
          type="submit"
          :loading="loading"
          no-caps
        />
        <q-btn
          flat
          color="primary"
          label="Vai alla lista spese"
          no-caps
          to="/p/spese"
          class="full-width"
        />
      </q-form>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue';
import { Notify } from 'quasar';
import { useExpensesStore, type NuovaSpesa } from 'stores/expenses';

const store = useExpensesStore();
const loading = ref(false);
const errore = ref('');

const form = reactive<NuovaSpesa>({
  data: new Date().toISOString().slice(0, 10),
  descrizione: '',
  importo: 0,
  categoria: '',
});

const categorie = [
  { label: 'Manutenzione', value: 'manutenzione' },
  { label: 'Utenze', value: 'utenze' },
  { label: 'Pulizie', value: 'pulizie' },
  { label: 'Tasse', value: 'tasse' },
  { label: 'Altro', value: 'altro' },
];

async function salva() {
  errore.value = '';
  if (!form.descrizione || !form.data || !form.importo || form.importo <= 0) {
    errore.value = 'Compila i campi obbligatori';
    return;
  }
  loading.value = true;
  try {
    await store.creaSpesa({
      data: form.data,
      descrizione: form.descrizione,
      importo: form.importo,
      categoria: form.categoria || undefined,
    });
    Notify.create({ type: 'positive', message: 'Spesa salvata', icon: 'check_circle' });
    form.descrizione = '';
    form.importo = 0;
    form.categoria = '';
  } catch (e: unknown) {
    const msg =
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
      'Salvataggio non riuscito';
    errore.value = msg;
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.vp-p-qa {
  max-width: 480px;
  margin: 0 auto;
}
.vp-p-qa__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 var(--vp-gap-2);
}
.vp-p-qa__intro {
  color: var(--vp-ink-2);
  margin-bottom: var(--vp-gap-4);
}
.vp-p-qa__card {
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  padding: var(--vp-gap-5);
}
</style>
