<template>
  <div class="vp-kpi" :class="{ 'vp-kpi--accent': accent }">
    <div class="vp-kpi__head">
      <div class="vp-kpi__label">{{ label }}</div>
      <q-btn
        v-if="$slots.dettaglio || infoTooltip"
        flat
        round
        dense
        size="sm"
        color="primary"
        icon="info"
        :title="infoTooltip || 'Dettaglio'"
        @click="onInfoClick"
        class="vp-kpi__info-btn"
      />
    </div>
    <div class="vp-kpi__value vp-display">
      <template v-if="isCurrency">{{ formattaEuro(numericValue) }}</template>
      <template v-else>{{ value }}</template>
    </div>
    <div v-if="sublabel" class="vp-kpi__sub">{{ sublabel }}</div>
    <slot />

    <q-dialog v-if="$slots.dettaglio" v-model="dettaglioOpen">
      <q-card class="vp-kpi__dialog">
        <q-card-section class="row items-center q-pb-none">
          <div class="vp-display vp-kpi__dialog-titolo">{{ label }}</div>
          <q-space />
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>
        <q-card-section>
          <slot name="dettaglio" />
        </q-card-section>
      </q-card>
    </q-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, useSlots } from 'vue';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';

const props = withDefaults(
  defineProps<{
    label: string;
    value: number | string;
    sublabel?: string;
    isCurrency?: boolean;
    accent?: boolean;
    infoTooltip?: string;
  }>(),
  { isCurrency: false, accent: false },
);

const emit = defineEmits<{ (e: 'info-click'): void }>();
const slots = useSlots();
const dettaglioOpen = ref(false);
const { formattaEuro } = useFormatoEuro();
const numericValue = computed(() =>
  typeof props.value === 'string' ? Number(props.value) : props.value,
);

function onInfoClick() {
  if (slots.dettaglio) dettaglioOpen.value = true;
  emit('info-click');
}
</script>

<style scoped>
.vp-kpi {
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  padding: var(--vp-gap-5);
  box-shadow: var(--vp-shadow-1);
  display: flex;
  flex-direction: column;
  gap: var(--vp-gap-2);
}
.vp-kpi--accent {
  background: var(--vp-terra-soft);
  border-color: transparent;
}
.vp-kpi__label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--vp-ink-3);
}
.vp-kpi__value {
  font-family: var(--vp-font-display);
  font-size: var(--vp-text-3xl);
  color: var(--vp-ink);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}
.vp-kpi__sub {
  color: var(--vp-ink-2);
  font-size: var(--vp-text-sm);
}
.vp-kpi__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.vp-kpi__info-btn {
  margin: -6px -6px 0 0;
}
.vp-kpi__dialog {
  min-width: min(560px, 92vw);
  max-width: 720px;
  border-radius: var(--vp-r-lg);
  background: var(--vp-cream);
}
.vp-kpi__dialog-titolo {
  font-size: var(--vp-text-xl);
}
</style>
