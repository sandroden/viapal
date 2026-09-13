<template>
  <!-- Il pannello esiste solo se il browser espone le API push *e* il server
       ha le chiavi VAPID: senza chiavi il canale è un no-op silenzioso e un
       toggle che non fa nulla sarebbe peggio di nessun toggle. -->
  <q-card v-if="disponibile" data-testid="push-pannello">
    <q-item>
      <q-item-section avatar>
        <q-icon name="notifications_active" color="primary" size="28px" />
      </q-item-section>
      <q-item-section>
        <q-item-label>Notifiche su questo dispositivo</q-item-label>
        <q-item-label caption>{{ descrizione }}</q-item-label>
      </q-item-section>
      <q-item-section side>
        <q-toggle
          :model-value="attivo"
          color="primary"
          :disable="loading || negato"
          data-testid="push-toggle"
          @update:model-value="toggle"
        />
      </q-item-section>
    </q-item>
    <q-card-section v-if="negato" class="q-pt-none">
      <q-banner class="text-white bg-orange-8" rounded dense>
        Le notifiche sono bloccate per questo sito: sbloccale dalle
        impostazioni del browser e ricarica la pagina.
      </q-banner>
    </q-card-section>
    <q-card-section v-else-if="errore" class="q-pt-none">
      <q-banner class="text-white bg-red-7" rounded dense>{{ errore }}</q-banner>
    </q-card-section>
    <q-card-section v-if="attivo" class="q-pt-none">
      <q-btn
        outline
        color="primary"
        icon="send"
        label="Invia notifica di prova"
        no-caps
        size="sm"
        :loading="provaLoading"
        data-testid="push-prova"
        @click="inviaProva"
      />
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { usePush } from 'src/composables/usePush';
import { messaggioErrore } from 'src/utils/apiErrors';

// La sottoscrizione è per dispositivo e per utente, identica nei due lati
// dell'app: cambia solo *cosa* arriva, quindi solo la descrizione.
withDefaults(
  defineProps<{
    descrizione?: string;
  }>(),
  { descrizione: 'Avvisi e scadenze anche ad app chiusa' },
);

const $q = useQuasar();
const { disponibile, attivo, negato, loading, errore, init, abilita, disabilita, provaNotifica } =
  usePush();
const provaLoading = ref(false);

onMounted(() => {
  void init();
});

async function toggle(valore: boolean) {
  if (valore) {
    await abilita();
    if (attivo.value) {
      $q.notify({ type: 'positive', message: 'Notifiche attivate su questo dispositivo.' });
    }
  } else {
    await disabilita();
  }
}

async function inviaProva() {
  provaLoading.value = true;
  try {
    const esito = await provaNotifica();
    $q.notify({
      type: esito.inviate ? 'positive' : 'warning',
      message: esito.inviate
        ? `Notifica di prova inviata (${esito.inviate} dispositivi).`
        : 'Nessun dispositivo raggiunto: riattiva le notifiche.',
    });
  } catch (e: unknown) {
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, 'Invio della prova non riuscito.'),
    });
  } finally {
    provaLoading.value = false;
  }
}
</script>
