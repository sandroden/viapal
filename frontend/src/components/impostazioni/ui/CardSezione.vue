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
  gap: 10px 14px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}
/* La base di 180px è la soglia sotto cui il titolo si spezzerebbe parola per
   parola: prima di scendere lì, le azioni vanno a capo. Il valore lascia
   intere su una riga anche le card della colonna di servizio (340px), che
   hanno titoli corti e un solo bottone. */
.imm-card__testo {
  flex: 1 1 180px;
  min-width: 0;
}
/* Sul telefono le azioni stanno sempre sotto: una riga di testo larga metà
   card si legge peggio di un bottone in più a capo, e così tutte le card
   della scheda hanno la stessa forma. */
@media (max-width: 599px) {
  .imm-card__testo {
    flex-basis: 100%;
  }
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
