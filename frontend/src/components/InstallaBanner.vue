<template>
  <!-- Striscia di invito all'installazione. Vive nei layout di inquilino e
       proprietario perché il problema che risolve è la scoperta: la pagina
       /installa esiste, ma nessuno la cerca da solo. Sparisce da sé una
       volta installata l'app (`display-mode: standalone`). -->
  <q-banner
    v-if="visibile"
    dense
    :inline-actions="$q.screen.gt.xs"
    class="vp-inst-banner"
    data-testid="installa-banner"
  >
    <template #avatar>
      <q-icon name="install_mobile" color="primary" size="22px" />
    </template>
    <span class="vp-inst-banner__testo">{{ testo }}</span>
    <template #action>
      <q-btn
        flat
        dense
        no-caps
        color="primary"
        label="Come si fa"
        data-testid="installa-banner-vai"
        @click="vai"
      />
      <q-btn
        flat
        dense
        round
        icon="close"
        color="grey-7"
        aria-label="Nascondi"
        data-testid="installa-banner-chiudi"
        @click="rinvia"
      />
    </template>
  </q-banner>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useInstallPwa } from 'src/composables/useInstallPwa';

/** Quanto resta nascosto dopo una chiusura. Non "per sempre": chi la chiude
 *  di fretta è esattamente chi non ha ancora installato nulla, ed è il caso
 *  che questo banner esiste per risolvere. */
const GIORNI_RINVIO = 30;
const CHIAVE = 'vp-installa-rinviato';

const router = useRouter();
const { piattaforma, installabile, installata } = useInstallPwa();

function letturaRinvio(): number {
  // localStorage può mancare o sollevare (navigazione privata, cookie di
  // sito bloccati): senza, il banner si limita a comparire sempre.
  try {
    return Number(localStorage.getItem(CHIAVE)) || 0;
  } catch {
    return 0;
  }
}

const rinviatoAl = ref(letturaRinvio());

// Niente invito dove installare non si può (Firefox su computer): sarebbe
// un invito a un'azione inesistente. Lì le notifiche si accendono comunque
// dal profilo, che è la strada che resta.
const visibile = computed(
  () => installabile.value && !installata.value && Date.now() > rinviatoAl.value,
);

// L'installazione è *necessaria* per le notifiche solo su iOS. Altrove è un
// vantaggio, non un requisito: dirlo requisito sarebbe falso.
const testo = computed(() => {
  if (piattaforma === 'desktop') {
    return 'Installa Viapal: si apre come un’applicazione, senza passare dal browser.';
  }
  if (piattaforma === 'ios') {
    return 'Metti Viapal nella schermata principale: su iPhone è l’unico modo per ricevere le notifiche.';
  }
  return 'Metti Viapal nella schermata principale: si apre con un tocco e ti avvisa delle scadenze.';
});

function rinvia() {
  const scadenza = Date.now() + GIORNI_RINVIO * 24 * 3600 * 1000;
  rinviatoAl.value = scadenza;
  try {
    localStorage.setItem(CHIAVE, String(scadenza));
  } catch {
    // Niente memoria: resta nascosto per questa sessione e basta.
  }
}

function vai() {
  void router.push('/installa');
}
</script>

<style scoped>
.vp-inst-banner {
  background: var(--vp-honey-soft);
  color: var(--vp-ink-2);
  font-size: var(--vp-text-sm);
}
.vp-inst-banner__testo {
  line-height: 1.4;
}
</style>
