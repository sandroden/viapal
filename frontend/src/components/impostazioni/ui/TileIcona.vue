<template>
  <div
    class="imm-tile"
    :style="{
      width: size + 'px',
      height: size + 'px',
      background: bg,
      color: colore,
    }"
  >
    <VpIcon :name="icona" :size="Math.round(size / 2)" />
  </div>
</template>

<script setup lang="ts">
import VpIcon from 'components/utenze/VpIcon.vue';

withDefaults(
  defineProps<{
    icona: string;
    colore?: string;
    bg?: string;
    size?: number;
  }>(),
  {
    colore: 'var(--vp-ink-3)',
    bg: 'var(--vp-paper-2)',
    size: 34,
  },
);
</script>

<style scoped>
.imm-tile {
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
</style>
