<template>
  <q-card class="vp-dett">
    <header class="vp-dett__head">
      <div class="vp-dett__icona">
        <q-icon :name="iconaTipo" size="20px" :style="{ color: 'var(--vp-wood)' }" />
      </div>
      <div class="vp-dett__head-txt">
        <div class="vp-eyebrow">{{ tipoLabel }}</div>
        <h3 class="vp-dett__titolo">{{ item.descrizione }}</h3>
      </div>
      <q-btn flat round dense icon="close" v-close-popup class="vp-dett__close" />
    </header>

    <!-- Riepilogo importi -->
    <div class="vp-dett__riepilogo">
      <ThDonut :pct="pct" :size="68" :stroke="6" />
      <div class="vp-dett__cifre">
        <div class="vp-dett__riga">
          <span class="vp-dett__riga-lbl">Dovuto</span>
          <span class="vp-mono">{{ formattaEuro(item.importo_dovuto) }}</span>
        </div>
        <div class="vp-dett__riga">
          <span class="vp-dett__riga-lbl">Pagato</span>
          <span class="vp-mono vp-dett__pagato">{{ formattaEuro(item.importo_pagato) }}</span>
        </div>
        <div class="vp-dett__riga vp-dett__riga--resto">
          <span class="vp-dett__riga-lbl">Resta</span>
          <span class="vp-mono">{{ formattaEuro(item.residuo) }}</span>
        </div>
      </div>
    </div>

    <!-- Bonifici imputati -->
    <div class="vp-dett__sezione">
      <div class="vp-eyebrow vp-dett__sez-titolo">Pagamenti ricevuti</div>
      <div v-if="item.allocazioni.length === 0" class="vp-dett__vuoto">
        Nessun bonifico ancora abbinato a questa voce.
      </div>
      <ul v-else class="vp-dett__bonifici">
        <li v-for="(a, i) in item.allocazioni" :key="i" class="vp-dett__bonifico">
          <q-icon name="south_east" size="16px" :style="{ color: 'var(--vp-sage-deep)' }" />
          <div class="vp-dett__bonifico-txt">
            <div class="vp-dett__bonifico-data">Bonifico del {{ formattaData(a.data) }}</div>
            <div v-if="a.bonifico_totale !== a.quota" class="vp-dett__bonifico-nota">
              quota di un bonifico da {{ formattaEuro(a.bonifico_totale) }}
            </div>
          </div>
          <span class="vp-mono vp-dett__bonifico-imp">{{ formattaEuro(a.quota) }}</span>
        </li>
      </ul>
    </div>

    <!-- Azione -->
    <q-btn
      v-if="item.residuo > 0"
      unelevated
      no-caps
      color="primary"
      icon="account_balance_wallet"
      :label="item.parziale ? 'Salda il resto' : 'Paga'"
      class="vp-dett__paga"
      v-close-popup
      @click="emit('paga')"
    />
  </q-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import ThDonut from './ThDonut.vue';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';
import type { DaPagareItem, TipoPagamento } from 'src/stores/dashboard';

const props = defineProps<{ item: DaPagareItem }>();
const emit = defineEmits<{ paga: [] }>();

const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

const pct = computed(() =>
  props.item.importo_dovuto
    ? Math.round((props.item.importo_pagato / props.item.importo_dovuto) * 100)
    : 0,
);

const LABEL_TIPO: Record<TipoPagamento, string> = {
  rent: 'Affitto',
  utility_charge: 'Utenze',
  extra: 'Addebito extra',
};
const tipoLabel = computed(() => LABEL_TIPO[props.item.tipo] ?? 'Pagamento');

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
.vp-dett {
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  padding: var(--vp-gap-4);
  width: 100%;
  max-width: 440px;
}
.vp-dett__head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.vp-dett__icona {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--vp-paper-2);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.vp-dett__head-txt {
  flex: 1;
  min-width: 0;
}
.vp-dett__titolo {
  font-size: 18px;
  font-weight: 600;
  color: var(--vp-ink);
  margin: 2px 0 0;
  line-height: 1.25;
}
.vp-dett__close {
  color: var(--vp-ink-3);
  margin: -4px -4px 0 0;
}
.vp-dett__riepilogo {
  display: flex;
  align-items: center;
  gap: 18px;
  margin: var(--vp-gap-4) 0;
  padding: var(--vp-gap-3);
  background: var(--vp-paper-2);
  border-radius: var(--vp-r-md);
}
.vp-dett__cifre {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.vp-dett__riga {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  font-size: 14px;
  color: var(--vp-ink-2);
}
.vp-dett__riga-lbl {
  color: var(--vp-ink-3);
}
.vp-dett__pagato {
  color: var(--vp-sage-deep);
}
.vp-dett__riga--resto {
  margin-top: 3px;
  padding-top: 6px;
  border-top: 1px solid var(--vp-paper-3);
  font-weight: 600;
  font-size: 15px;
  color: var(--vp-terra);
}
.vp-dett__riga--resto .vp-dett__riga-lbl {
  color: var(--vp-ink-2);
}
.vp-dett__sez-titolo {
  margin-bottom: var(--vp-gap-2);
}
.vp-dett__vuoto {
  font-size: 13px;
  color: var(--vp-ink-3);
  padding: 4px 0;
}
.vp-dett__bonifici {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.vp-dett__bonifico {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--vp-paper-3);
}
.vp-dett__bonifico:last-child {
  border-bottom: none;
}
.vp-dett__bonifico-txt {
  flex: 1;
  min-width: 0;
}
.vp-dett__bonifico-data {
  font-size: 13.5px;
  color: var(--vp-ink);
}
.vp-dett__bonifico-nota {
  font-size: 11.5px;
  color: var(--vp-ink-3);
  margin-top: 1px;
}
.vp-dett__bonifico-imp {
  font-size: 14px;
  color: var(--vp-sage-deep);
  font-weight: 500;
}
.vp-dett__paga {
  width: 100%;
  height: 46px;
  font-size: 15px;
  font-weight: 600;
  border-radius: var(--vp-r-md);
  margin-top: var(--vp-gap-4);
}
</style>
