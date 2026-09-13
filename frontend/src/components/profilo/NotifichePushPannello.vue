<template>
  <!-- Il pannello si disegna se il *server* ha il canale (chiavi VAPID), o se
       non si è potuto chiedere. Quando il server non ce l'ha resta invisibile:
       un toggle che non fa nulla sarebbe peggio di nessun toggle. Ma se il
       canale c'è e questo browser non può usarlo, il pannello lo dice —
       l'assenza muta non si distingue da un bug. -->
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
          :disable="loading || negato || !supportato || verificaFallita"
          data-testid="push-toggle"
          @update:model-value="toggle"
        />
      </q-item-section>
    </q-item>
    <!-- Il browser non espone le API push. Le due cause portano a rimedi
         opposti — cambiare indirizzo, o cambiare finestra — quindi vanno
         dette separate, con l'indirizzo in chiaro. -->
    <q-card-section v-if="!supportato" class="q-pt-none">
      <q-banner class="text-white bg-grey-7" rounded dense data-testid="push-non-supportato">
        <template v-if="!contestoSicuro">
          Le notifiche richiedono una connessione sicura: apri l'app su
          <strong>https://</strong> oppure su <strong>localhost</strong>. Questa pagina è su
          <strong>{{ origine }}</strong
          >.
        </template>
        <template v-else>
          Questo browser non espone le notifiche push: capita nelle finestre in navigazione privata
          e nei browser con i service worker disattivati.
        </template>
      </q-banner>
    </q-card-section>
    <q-card-section v-else-if="verificaFallita" class="q-pt-none">
      <q-banner class="text-white bg-orange-8" rounded dense data-testid="push-verifica-fallita">
        {{ errore }} Ricarica la pagina quando il server è di nuovo su.
      </q-banner>
    </q-card-section>
    <q-card-section v-else-if="negato" class="q-pt-none">
      <q-banner class="text-white bg-orange-8" rounded dense>
        Le notifiche sono bloccate per questo sito: sbloccale dalle impostazioni del browser e
        ricarica la pagina.
      </q-banner>
    </q-card-section>
    <q-card-section v-else-if="errore" class="q-pt-none">
      <q-banner class="text-white bg-red-7" rounded dense>{{ errore }}</q-banner>
    </q-card-section>
    <q-card-section v-if="attivo && supportato" class="q-pt-none">
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

    <!-- Elenco dei device sottoscritti. La sottoscrizione è del browser, non
         della persona: chi entra dopo su uno stesso browser se la prende, e
         senza questa lista il primo se ne accorge solo da una notifica che
         non arriva più. Si mostra anche quando questo browser non è attivo:
         è proprio quel caso che va reso visibile. -->
    <q-card-section
      v-if="dispositivi.length && !verificaFallita"
      class="q-pt-none"
      data-testid="push-dispositivi"
    >
      <div class="vp-section-title q-mb-xs">Dispositivi attivi</div>
      <q-list dense separator>
        <q-item v-for="d in dispositivi" :key="d.id" class="q-px-none">
          <q-item-section avatar class="vp-push-dev__icona">
            <q-icon :name="d.corrente ? 'smartphone' : 'devices'" size="20px" />
          </q-item-section>
          <q-item-section>
            <q-item-label>
              {{ d.device_label || 'Dispositivo senza nome' }}
              <span v-if="d.corrente" class="vp-badge vp-badge--ok q-ml-xs">questo</span>
            </q-item-label>
            <q-item-label caption>{{ descrizioneDevice(d) }}</q-item-label>
          </q-item-section>
          <q-item-section side>
            <q-btn
              flat
              dense
              round
              size="sm"
              icon="close"
              color="grey-7"
              :disable="loading"
              :aria-label="`Disattiva su ${d.device_label || 'questo dispositivo'}`"
              @click="rimuovi(d)"
            />
          </q-item-section>
        </q-item>
      </q-list>
    </q-card-section>

    <!-- Zero device con il canale acceso non è un dettaglio: è la ragione per
         cui non arriva niente, e va detta dove la si cerca. -->
    <q-card-section
      v-else-if="supportato && !attivo && !negato && !verificaFallita && !dispositiviNonLetti"
      class="q-pt-none"
    >
      <div class="vp-hint" data-testid="push-nessun-dispositivo">
        Nessun dispositivo attivo: finché l'interruttore resta spento non ricevi notifiche da
        nessuna parte.
      </div>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { usePush, type DispositivoPush } from 'src/composables/usePush';
import { messaggioErrore } from 'src/utils/apiErrors';
import { useFormatoData } from 'src/composables/useFormatoData';

// La sottoscrizione è per dispositivo e per utente, identica nei due lati
// dell'app: cambia solo *cosa* arriva, quindi solo la descrizione.
withDefaults(
  defineProps<{
    descrizione?: string;
  }>(),
  { descrizione: 'Avvisi e scadenze anche ad app chiusa' },
);

const $q = useQuasar();
const {
  supportato,
  contestoSicuro,
  origine,
  verificaFallita,
  disponibile,
  attivo,
  negato,
  loading,
  errore,
  dispositivi,
  dispositiviNonLetti,
  init,
  abilita,
  disabilita,
  rimuoviDispositivo,
  provaNotifica,
} = usePush();
const provaLoading = ref(false);
const { formattaData } = useFormatoData();

/** Riga di dettaglio: l'ultima notifica ricevuta dice se il device è vivo;
 *  finché non ne è arrivata nessuna resta la data di attivazione. */
function descrizioneDevice(d: DispositivoPush): string {
  return d.ultima_attivita
    ? `Ultima notifica il ${formattaData(d.ultima_attivita)}`
    : `Attivato il ${formattaData(d.created_at)}, nessuna notifica ancora`;
}

async function rimuovi(d: DispositivoPush) {
  await rimuoviDispositivo(d.id);
  if (!errore.value) {
    $q.notify({
      type: 'positive',
      message: `Notifiche disattivate su ${d.device_label || 'quel dispositivo'}.`,
    });
  }
}

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

<style scoped>
.vp-push-dev__icona {
  min-width: 32px;
  color: var(--vp-ink-3);
}
</style>
