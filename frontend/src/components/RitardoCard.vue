<template>
  <div class="th-card" :class="[`th-card--${stacco}`, { 'th-card--sel': selected }]">
    <div class="th-card__row" @click="emit('toggle')">
      <ThCheck :on="selected" :size="20" />

      <ThDonut v-if="item.parziale" :pct="pct" :size="38" :stroke="4" />
      <div v-else class="th-card__icona">
        <q-icon :name="iconaTipo" size="18px" :style="{ color: 'var(--vp-wood)' }" />
      </div>

      <div class="th-card__txt">
        <div class="th-card__mese">{{ item.descrizione }}</div>
        <div class="th-card__sub">
          <template v-if="item.parziale">Resta {{ formattaEuro(item.residuo) }}</template>
          <template v-else>Scad. {{ formattaData(item.scadenza) }}</template>
          <template v-if="showRitardo">
            · <span class="th-card__late">{{ item.giorni_ritardo }} g di ritardo</span>
          </template>
        </div>
      </div>

      <div class="th-card__importo vp-mono">{{ formattaEuro(item.residuo) }}</div>
    </div>

    <div class="th-card__azioni">
      <button class="th-card__btn th-card__btn--primary" @click="emit('paga')">
        {{ item.parziale ? 'Salda il resto' : 'Paga' }}
      </button>
      <div class="th-card__div" />
      <button class="th-card__btn th-card__btn--ghost" @click="emit('hoPagato')">
        Ho già pagato
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import ThCheck from './ThCheck.vue';
import ThDonut from './ThDonut.vue';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';
import type { DaPagareItem } from 'src/stores/dashboard';

const props = withDefaults(
  defineProps<{
    item: DaPagareItem;
    selected: boolean;
    showRitardo?: boolean;
    stacco?: 'soft' | 'medio' | 'forte';
  }>(),
  { showRitardo: false, stacco: 'forte' },
);

const emit = defineEmits<{ toggle: []; paga: []; hoPagato: [] }>();

const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

const pct = computed(() =>
  props.item.importo_dovuto
    ? Math.round((props.item.importo_pagato / props.item.importo_dovuto) * 100)
    : 0,
);
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
.th-card {
  background: var(--vp-cream);
  border-radius: var(--vp-r-md);
  border: 1px solid var(--vp-paper-3);
  border-left: 3px solid transparent;
  overflow: hidden;
  transition: border-color 0.12s, box-shadow 0.12s;
}
.th-card--soft {
  box-shadow: none;
}
.th-card--medio {
  box-shadow: var(--vp-shadow-1);
}
.th-card--forte {
  box-shadow: var(--vp-shadow-2);
}
.th-card--sel {
  border-left-color: var(--vp-terra);
  box-shadow: 0 0 0 1px var(--vp-terra), var(--vp-shadow-1);
}
.th-card__row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 14px;
  cursor: pointer;
}
.th-card__icona {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: var(--vp-paper-2);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.th-card__txt {
  flex: 1;
  min-width: 0;
}
.th-card__mese {
  font-size: 14.5px;
  font-weight: 500;
  color: var(--vp-ink);
}
.th-card__sub {
  font-size: 12px;
  color: var(--vp-ink-3);
  margin-top: 1px;
}
.th-card__late {
  color: var(--vp-status-late-fg);
}
.th-card__importo {
  font-size: 17px;
  color: var(--vp-terra);
  text-align: right;
}
.th-card__azioni {
  display: flex;
  border-top: 1px solid var(--vp-paper-3);
}
.th-card__btn {
  height: 40px;
  border: none;
  cursor: pointer;
  background: transparent;
  font-family: var(--vp-font-ui);
  font-size: 13px;
}
.th-card__btn--primary {
  flex: 1.4;
  font-weight: 600;
  color: var(--vp-terra);
}
.th-card__btn--ghost {
  flex: 1;
  font-weight: 400;
  color: var(--vp-ink-3);
}
.th-card__div {
  width: 1px;
  background: var(--vp-paper-3);
}
</style>
