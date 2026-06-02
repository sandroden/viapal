<script setup lang="ts">
import { VP_ICONS } from './icons';

withDefaults(
  defineProps<{
    name: string;
    size?: number | string;
    color?: string;
    stroke?: number | string;
  }>(),
  { size: 20, color: 'currentColor', stroke: 1.6 },
);
</script>

<template>
  <svg
    v-if="VP_ICONS[name]"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    :stroke="color"
    :stroke-width="stroke"
    stroke-linecap="round"
    stroke-linejoin="round"
    style="flex-shrink: 0"
  >
    <path :d="VP_ICONS[name]" />
  </svg>
</template>
