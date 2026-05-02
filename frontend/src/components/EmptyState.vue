<template>
  <div class="vp-empty">
    <div class="vp-empty__icon">
      <q-icon :name="icon" size="48px" />
    </div>
    <div class="vp-empty__title vp-display">{{ title }}</div>
    <div v-if="message" class="vp-empty__message">{{ message }}</div>
    <slot />
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    icon?: string;
    title: string;
    message?: string;
  }>(),
  { icon: 'spa' },
);
</script>

<style scoped>
.vp-empty {
  text-align: center;
  padding: var(--vp-gap-7) var(--vp-gap-4);
  color: var(--vp-ink-2);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--vp-gap-3);
  background: var(--vp-paper-2);
  border-radius: var(--vp-r-lg);
  border: 1px dashed var(--vp-paper-3);
}
.vp-empty__icon {
  color: var(--vp-terra);
  opacity: 0.7;
}
.vp-empty__title {
  font-size: var(--vp-text-xl);
  color: var(--vp-ink);
}
.vp-empty__message {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-md);
  max-width: 320px;
}
</style>
