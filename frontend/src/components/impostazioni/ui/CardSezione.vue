<template>
  <section class="vp-card imm-card">
    <header class="imm-card__head">
      <div class="imm-card__testo">
        <div class="imm-card__titolo">{{ titolo }}</div>
        <div v-if="descrizione || $slots.descrizione" class="imm-card__desc">
          <slot name="descrizione">{{ descrizione }}</slot>
        </div>
      </div>
      <div v-if="$slots.azioni" class="imm-card__azioni">
        <slot name="azioni" />
      </div>
    </header>
    <slot />
  </section>
</template>

<script setup lang="ts">
// Card della scheda Immobile: una sola gerarchia di superfici — stesso
// raggio, stesso bordo, titolo in serif che non ripete il nome del tab.
defineProps<{
  titolo: string;
  descrizione?: string;
}>();
</script>

<style scoped>
.imm-card {
  padding: 18px 22px 16px;
  display: flex;
  flex-direction: column;
}
.imm-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 6px;
}
.imm-card__testo {
  min-width: 0;
}
.imm-card__titolo {
  font-family: var(--vp-font-display);
  font-size: 19px;
  font-weight: 500;
  line-height: 1.25;
  color: var(--vp-ink);
}
.imm-card__desc {
  font-size: 12.5px;
  color: var(--vp-ink-3);
  margin-top: 3px;
  line-height: 1.5;
  max-width: 620px;
  text-wrap: pretty;
}
.imm-card__azioni {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
}
</style>
