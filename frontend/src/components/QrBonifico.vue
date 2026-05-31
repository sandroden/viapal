<template>
  <q-card class="vp-qr">
    <div class="vp-eyebrow">Paga con bonifico</div>
    <p class="vp-qr__hint">
      Inquadra il QR con l'app della tua banca: il bonifico si precompila con importo e causale.
    </p>

    <div class="vp-qr__wrap">
      <img v-if="qrDataUrl" :src="qrDataUrl" alt="QR bonifico" class="vp-qr__img" />
    </div>

    <div class="vp-qr__dati">
      <div class="vp-qr__dato">
        <span class="vp-qr__lbl">Beneficiario</span>
        <span>{{ pagamento.beneficiario }}</span>
      </div>
      <div class="vp-qr__dato">
        <span class="vp-qr__lbl">IBAN</span>
        <span class="vp-mono vp-qr__iban">{{ pagamento.iban }}</span>
      </div>
      <div class="vp-qr__dato">
        <span class="vp-qr__lbl">Causale</span>
        <span>{{ pagamento.causale }}</span>
      </div>
    </div>

    <div class="vp-qr__copia">
      <q-btn
        flat
        dense
        no-caps
        color="primary"
        icon="content_copy"
        label="Copia IBAN"
        @click="copia(pagamento.iban, 'IBAN copiato')"
      />
      <q-btn
        flat
        dense
        no-caps
        color="primary"
        icon="content_copy"
        label="Copia causale"
        @click="copia(pagamento.causale, 'Causale copiata')"
      />
    </div>
  </q-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Notify } from 'quasar';
import { useEpcQr, type EpcDati } from 'src/composables/useEpcQr';
import type { DatiPagamento } from 'src/stores/dashboard';

const props = defineProps<{ pagamento: DatiPagamento; importo: number }>();

const epcDati = computed<EpcDati | null>(() => ({
  beneficiario: props.pagamento.beneficiario,
  iban: props.pagamento.iban,
  causale: props.pagamento.causale,
  importo: props.importo || 0,
}));
const { dataUrl: qrDataUrl } = useEpcQr(epcDati);

async function copia(testo: string, msg: string) {
  try {
    await navigator.clipboard.writeText(testo);
    Notify.create({ type: 'positive', message: msg, icon: 'check' });
  } catch {
    Notify.create({ type: 'warning', message: 'Copia non riuscita' });
  }
}
</script>

<style scoped>
.vp-qr {
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  padding: var(--vp-gap-4);
}
.vp-qr__hint {
  margin: var(--vp-gap-1) 0 var(--vp-gap-3);
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-3);
}
.vp-qr__wrap {
  display: flex;
  justify-content: center;
  margin-bottom: var(--vp-gap-3);
}
.vp-qr__img {
  width: 200px;
  height: 200px;
  border-radius: var(--vp-r-md);
  background: #fff;
  padding: var(--vp-gap-2);
  box-shadow: var(--vp-shadow-1);
}
.vp-qr__dati {
  display: flex;
  flex-direction: column;
  gap: var(--vp-gap-2);
  margin-bottom: var(--vp-gap-3);
}
.vp-qr__dato {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.vp-qr__lbl {
  font-size: var(--vp-text-xs);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--vp-ink-3);
}
.vp-qr__iban {
  word-break: break-all;
}
.vp-qr__copia {
  display: flex;
  gap: var(--vp-gap-2);
  flex-wrap: wrap;
}
</style>
