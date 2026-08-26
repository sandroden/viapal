<template>
  <q-dialog v-model="aperto">
    <q-card class="dm-card">
      <q-card-section class="dm-titolo">{{ titolo }}</q-card-section>
      <q-card-section>
        <!-- I dati non si chiedono qui: si dice dove stanno di casa. È lo
             stesso patto del dialog dei documenti generati — chi compila un
             dato lo compila una volta, nel posto che è suo. -->
        <p class="dm-intro">
          {{ mancanti.length }} {{ mancanti.length === 1 ? 'dato' : 'dati' }}
          {{ mancanti.length === 1 ? 'manca' : 'mancano' }} all'immobile o al
          contratto. Si compilano dove stanno di casa: da lì torni e generi.
        </p>
        <ul class="dm-lista">
          <li v-for="m in mancanti" :key="m.campo + m.etichetta">
            <div class="dm-testo">
              <div class="dm-eti">{{ m.etichetta }}</div>
              <div class="dm-dove">{{ m.dove }}</div>
            </div>
            <BtnSoft etichetta="Vai" icona="open" variante="ghost" @click="vai(m)" />
          </li>
        </ul>
      </q-card-section>
      <q-card-actions align="right">
        <q-btn v-close-popup flat label="Chiudi" />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
import type { DatoMancante } from 'stores/documenti';
import BtnSoft from './ui/BtnSoft.vue';

withDefaults(
  defineProps<{
    mancanti: DatoMancante[];
    titolo?: string;
  }>(),
  { titolo: 'Non si può ancora generare' },
);

const aperto = defineModel<boolean>({ required: true });
const router = useRouter();

function vai(m: DatoMancante) {
  // Le fonti "esterne" stanno nell'admin Django, fuori dalla SPA: lì il
  // router non arriva e serve una scheda nuova.
  if (m.esterno) {
    window.open(m.link, '_blank', 'noopener');
    return;
  }
  aperto.value = false;
  void router.push(m.link);
}
</script>

<style scoped>
.dm-card {
  width: 520px;
  max-width: 93vw;
}
.dm-titolo {
  font-family: var(--vp-serif, Georgia, serif);
  font-size: 18px;
}
.dm-intro {
  font-size: 13px;
  color: var(--vp-ink-2);
  line-height: 1.5;
  margin: 0 0 10px;
}
.dm-lista {
  list-style: none;
  margin: 0;
  padding: 0;
}
.dm-lista li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--vp-paper-3);
}
.dm-lista li:last-child {
  border-bottom: none;
}
.dm-testo {
  min-width: 0;
}
.dm-eti {
  font-size: 13.5px;
}
.dm-dove {
  font-size: 12px;
  color: var(--vp-ink-3);
}
</style>
