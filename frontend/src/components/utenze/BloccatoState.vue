<script setup lang="ts">
// Mostrato al posto di Ripartizione / Invio quando il periodo è incompleto.
import VpIcon from './VpIcon.vue';

withDefaults(defineProps<{ mancanti?: number }>(), { mancanti: 0 });
defineEmits<{ torna: [] }>();
</script>

<template>
  <div class="blocked">
    <div class="ico"><VpIcon name="lock" :size="28" color="var(--vp-clay)" /></div>
    <div class="vp-display" style="font-size: 22px">Prima completa le bollette</div>
    <div class="txt">
      Mancano <b>{{ mancanti }} bollette</b> di questo periodo. La ripartizione e l'invio si
      sbloccano quando il totale è completo.
    </div>
    <button class="vp-btn vp-btn--primary" style="margin-top: 4px" @click="$emit('torna')">
      <VpIcon name="upload" :size="16" color="#fff" /> Torna a "Bolletta"
    </button>
  </div>
</template>

<style scoped>
.blocked {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 56px 24px;
  gap: 14px;
}
.ico {
  width: 64px;
  height: 64px;
  border-radius: 18px;
  background: var(--vp-clay-soft);
  display: flex;
  align-items: center;
  justify-content: center;
}
.txt {
  font-size: 14px;
  color: var(--vp-ink-2);
  max-width: 420px;
}
</style>
