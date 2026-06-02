<script setup lang="ts">
// Avatar monogramma: iniziale su disco terracotta tenue, tinta variabile.
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    name?: string;
    size?: number;
    hue?: number;
  }>(),
  { name: '', size: 36, hue: 38 },
);

const initial = computed(() => (props.name.trim().charAt(0) || '·').toUpperCase());
</script>

<template>
  <div
    class="vp-avatar"
    :style="{
      width: size + 'px',
      height: size + 'px',
      background: `oklch(0.86 0.05 ${hue})`,
      color: `oklch(0.40 0.08 ${hue})`,
      fontSize: size * 0.45 + 'px',
    }"
  >
    {{ initial }}
  </div>
</template>

<style scoped>
.vp-avatar {
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: var(--vp-font-display);
  font-weight: 500;
  flex-shrink: 0;
}
</style>
