<template>
  <q-page padding class="vp-page">
    <div class="vp-page-head">
      <h1 class="vp-h1">Nuova proprietà</h1>
      <p class="vp-sub">
        Crea un nuovo immobile da gestire con Viapal: stanze, contratti,
        pagamenti e conguagli restano separati per ogni casa.
      </p>
    </div>

    <q-card flat bordered class="vp-card" style="max-width: 560px">
      <q-card-section>
        <q-form class="q-gutter-md" @submit.prevent="crea">
          <q-input
            v-model="nome"
            label="Nome dell'immobile"
            hint="Es. «Appartamento Como», «Via Palestrina»"
            outlined
            :rules="[(v) => !!v?.trim() || 'Il nome è obbligatorio']"
            data-testid="nuova-nome"
          />
          <q-input
            v-model="indirizzo"
            label="Indirizzo"
            outlined
            data-testid="nuova-indirizzo"
          />

          <div>
            <div class="vp-label q-mb-sm">Il tuo ruolo su questo immobile</div>
            <q-option-group
              v-model="ruoloCreatore"
              :options="opzioniRuolo"
              type="radio"
            />
            <div class="vp-hint q-mt-xs">
              Scegli «Gestore» se l'immobile è di qualcun altro (es. lo
              amministri per un familiare): potrai fare tutto tranne gestire
              membri e quote, e non comparirai nei riparti economici. Il
              proprietario lo inviterai subito dopo, dalla pagina
              «Immobile».
            </div>
          </div>

          <q-banner v-if="errore" class="vp-banner-errore" rounded dense>
            {{ errore }}
          </q-banner>

          <div class="row q-gutter-sm">
            <q-btn
              type="submit"
              color="primary"
              label="Crea proprietà"
              :loading="saving"
              data-testid="nuova-crea"
            />
            <q-btn flat label="Annulla" to="/p/" />
          </div>
        </q-form>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { isAxiosError } from 'axios';
import { usePropertiesStore, STORAGE_KEY } from 'stores/properties';

const propStore = usePropertiesStore();

const nome = ref('');
const indirizzo = ref('');
const ruoloCreatore = ref<'proprietario' | 'gestore'>('proprietario');
const saving = ref(false);
const errore = ref('');

const opzioniRuolo = [
  { label: 'Proprietario (l’immobile è mio)', value: 'proprietario' },
  { label: 'Gestore (lo amministro per qualcun altro)', value: 'gestore' },
];

async function crea() {
  saving.value = true;
  errore.value = '';
  try {
    const creato = await propStore.creaProperty({
      nome: nome.value.trim(),
      indirizzo: indirizzo.value.trim(),
      ruolo_creatore: ruoloCreatore.value,
    });
    // Attiva subito il nuovo immobile e riparti puliti (hard reload, come
    // per ogni cambio di immobile).
    localStorage.setItem(STORAGE_KEY, String(creato.id));
    window.location.assign('/p/impostazioni/proprieta');
  } catch (e: unknown) {
    if (isAxiosError(e)) {
      errore.value =
        (e.response?.data as { detail?: string })?.detail ??
        'Creazione non riuscita. Riprova.';
    } else {
      errore.value = 'Creazione non riuscita. Riprova.';
    }
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.vp-page-head {
  margin-bottom: var(--vp-gap-4);
}
.vp-h1 {
  font-size: 26px;
  line-height: 1.2;
  margin: 0;
}
.vp-sub {
  color: var(--vp-ink-2);
}
.vp-label {
  font-weight: 600;
  color: var(--vp-ink-1);
}
.vp-hint {
  color: var(--vp-ink-3);
  font-size: 13px;
}
.vp-banner-errore {
  background: var(--vp-clay-soft, #fbeae5);
  color: var(--vp-clay-deep, #8c3b21);
}
</style>
