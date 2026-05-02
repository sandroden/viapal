<template>
  <article class="vp-pag-card">
    <header class="vp-pag-card__head">
      <div class="vp-pag-card__tipo">
        <q-icon :name="iconaTipo" size="20px" />
        <span>{{ tipoLabel }}</span>
      </div>
      <SemaforoBadge :livello="item.semaforo" :giorni-ritardo="item.giorni_ritardo" />
    </header>

    <div class="vp-pag-card__descrizione">{{ item.descrizione }}</div>

    <div class="vp-pag-card__meta">
      <div class="vp-pag-card__importo vp-display">{{ formattaEuro(item.importo) }}</div>
      <div class="vp-pag-card__scadenza">Scadenza: {{ formattaData(item.scadenza) }}</div>
    </div>

    <footer class="vp-pag-card__azioni">
      <q-btn
        v-if="item.stato !== 'dichiarato'"
        unelevated
        color="primary"
        :to="`/i/paga/${item.tipo}/${item.id}`"
        label="Ho pagato"
        icon-right="check"
      />
      <q-chip v-else dense color="amber-2" text-color="amber-9" icon="hourglass_top">
        In attesa di conferma
      </q-chip>
      <q-btn
        v-if="item.tipo === 'utility_charge'"
        flat
        color="primary"
        :to="`/i/conguaglio/${item.id}`"
        label="Dettaglio"
      />
    </footer>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import SemaforoBadge from 'src/components/SemaforoBadge.vue';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';
import type { DaPagareItem } from 'src/stores/dashboard';

const props = defineProps<{ item: DaPagareItem }>();

const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

const tipoLabel = computed(() => {
  switch (props.item.tipo) {
    case 'rent':
      return 'Affitto';
    case 'utility_charge':
      return 'Conguaglio utenze';
    case 'extra':
      return 'Spesa extra';
    default:
      return 'Pagamento';
  }
});

const iconaTipo = computed(() => {
  switch (props.item.tipo) {
    case 'rent':
      return 'home';
    case 'utility_charge':
      return 'bolt';
    case 'extra':
      return 'note_add';
    default:
      return 'payments';
  }
});
</script>

<style scoped>
.vp-pag-card {
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  box-shadow: var(--vp-shadow-1);
  padding: var(--vp-gap-4);
  display: flex;
  flex-direction: column;
  gap: var(--vp-gap-3);
}
.vp-pag-card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--vp-gap-3);
}
.vp-pag-card__tipo {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--vp-ink-2);
  font-size: var(--vp-text-sm);
  font-weight: 500;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}
.vp-pag-card__descrizione {
  font-family: var(--vp-font-display);
  font-size: var(--vp-text-xl);
  color: var(--vp-ink);
  line-height: 1.25;
}
.vp-pag-card__meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--vp-gap-3);
  flex-wrap: wrap;
}
.vp-pag-card__importo {
  font-size: var(--vp-text-2xl);
  color: var(--vp-terra-deep);
  font-variant-numeric: tabular-nums;
}
.vp-pag-card__scadenza {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm);
}
.vp-pag-card__azioni {
  display: flex;
  gap: var(--vp-gap-2);
  justify-content: flex-end;
  flex-wrap: wrap;
}
</style>
