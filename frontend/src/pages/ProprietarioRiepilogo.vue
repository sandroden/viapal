<template>
  <q-page class="vp-riepilogo">
    <q-banner v-if="store.errore" class="vp-banner-error" rounded>
      <template #avatar><q-icon name="error" /></template>
      {{ store.errore }}
    </q-banner>

    <div class="vp-screen-tabs">
      <button :class="['vp-screen-tab', { active: tab === 'da-inviare' }]" @click="tab = 'da-inviare'">
        <q-icon name="mark_email_read" size="16px" />
        Da inviare
      </button>
      <button :class="['vp-screen-tab', { active: tab === 'inviati' }]" @click="tab = 'inviati'">
        <q-icon name="history" size="16px" />
        Inviati
      </button>
    </div>

    <div class="vp-riepilogo__body">
      <RiepilogoInvioStep
        v-if="tab === 'da-inviare'"
        :riepiloghi="riepiloghi"
        :escludi="escludi"
        :giorni="giorni"
        :loading="store.loading"
        @invia="confermaInvio"
        @toggle="onToggle"
      />
      <ComunicazioniPannello v-else />
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useRiepilogoAddebitiStore } from 'stores/riepilogoAddebiti';
import RiepilogoInvioStep from 'src/components/riepilogo/RiepilogoInvioStep.vue';
import ComunicazioniPannello from 'src/components/comunicazioni/ComunicazioniPannello.vue';

const $q = useQuasar();
const store = useRiepilogoAddebitiStore();

const tab = ref<'da-inviare' | 'inviati'>('da-inviare');
/** tenant_id deselezionati a mano dal proprietario. */
const escludi = ref<number[]>([]);

const riepiloghi = computed(() => store.anteprima?.riepiloghi ?? []);
const giorni = computed(() => store.anteprima?.giorni ?? 15);

function onToggle(tenantId: number): void {
  const i = escludi.value.indexOf(tenantId);
  if (i >= 0) escludi.value.splice(i, 1);
  else escludi.value.push(tenantId);
}

function confermaInvio(): void {
  const daInviare = riepiloghi.value.filter(
    (r) => r.notificare && r.email && !escludi.value.includes(r.tenant_id),
  );
  const giaInviati = daInviare.filter((r) => r.ultimo_invio_at).length;
  $q.dialog({
    title: 'Conferma invio',
    message:
      `Invio reale delle email a ${daInviare.length} inquilini.` +
      (giaInviati
        ? ` ${giaInviati} ${giaInviati === 1 ? 'ha' : 'hanno'} già ricevuto un riepilogo: procedere comunque?`
        : ' Procedere?'),
    cancel: true,
    persistent: true,
  }).onOk(() => {
    void inviaReale();
  });
}

async function inviaReale(): Promise<void> {
  const res = await store.invia(false, [...escludi.value]);
  if (!res) return;
  $q.notify({
    type: res.errori ? 'warning' : 'positive',
    message: `Inviate ${res.inviati} email${res.errori ? `, ${res.errori} errori` : ''}`,
  });
  // Ricarica l'anteprima: i badge "già inviato il …" si aggiornano e le voci
  // nel frattempo saldate escono dalla lista.
  await store.invia(true, [...escludi.value]);
}

onMounted(async () => {
  await store.invia(true);
});
</script>

<style scoped>
.vp-riepilogo {
  background: var(--vp-paper);
}
.vp-riepilogo__body {
  padding: 22px 20px 40px;
}

.vp-screen-tabs {
  display: flex;
  gap: 4px;
  padding: 0 20px;
  border-bottom: 1px solid var(--vp-paper-3);
  background: var(--vp-paper);
  position: sticky;
  top: 0;
  z-index: 10;
}
.vp-screen-tab {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 10px 14px 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-family: var(--vp-font-ui);
  font-size: 14px;
  font-weight: 400;
  color: var(--vp-ink-3);
  position: relative;
  transition: color 0.15s;
}
.vp-screen-tab:hover {
  color: var(--vp-ink);
}
.vp-screen-tab.active {
  color: var(--vp-ink);
  font-weight: 500;
}
.vp-screen-tab.active::after {
  content: '';
  position: absolute;
  left: 10px;
  right: 10px;
  bottom: -1px;
  height: 2px;
  background: var(--vp-clay);
  border-radius: 2px;
}
</style>
