<template>
  <div
    class="th-check"
    :class="{ 'th-check--on': on }"
    :style="{ width: `${size}px`, height: `${size}px` }"
  >
    <q-icon v-if="on" name="check" :size="`${Math.round(size * 0.66)}px`" color="white" />
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ on: boolean; size?: number }>(), { size: 22 });
</script>

<style scoped>
.th-check {
  border-radius: 7px;
  flex-shrink: 0;
  border: 1.5px solid var(--vp-ink-4);
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.12s, border-color 0.12s;
}
.th-check--on {
  border-color: transparent;
  background: var(--vp-terra);
}
</style>
