<template>
  <div class="vp-kpi" :class="{ 'vp-kpi--accent': accent }">
    <div class="vp-kpi__label">{{ label }}</div>
    <div class="vp-kpi__value vp-display">
      <template v-if="isCurrency">{{ formattaEuro(numericValue) }}</template>
      <template v-else>{{ value }}</template>
    </div>
    <div v-if="sublabel" class="vp-kpi__sub">{{ sublabel }}</div>
    <slot />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';

const props = withDefaults(
  defineProps<{
    label: string;
    value: number | string;
    sublabel?: string;
    isCurrency?: boolean;
    accent?: boolean;
  }>(),
  { isCurrency: false, accent: false },
);

const { formattaEuro } = useFormatoEuro();
const numericValue = computed(() => {
  return typeof props.value === 'string' ? Number(props.value) : props.value;
});
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
</style>
