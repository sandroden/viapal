<template>
  <div class="imm-riga" :class="{ 'imm-riga--ultima': ultima, 'imm-riga--tenue': tenue }">
    <div v-if="$slots.tile" class="imm-riga__tile">
      <slot name="tile" />
    </div>
    <div class="imm-riga__corpo">
      <div class="imm-riga__testa">
        <span class="imm-riga__titolo"><slot name="titolo">{{ titolo }}</slot></span>
        <slot name="badge" />
      </div>
      <div v-if="meta || $slots.meta" class="imm-riga__meta">
        <slot name="meta">{{ meta }}</slot>
      </div>
    </div>
    <div v-if="$slots.azioni" class="imm-riga__azioni">
      <slot name="azioni" />
    </div>
  </div>
</template>

<script setup lang="ts">
// Anatomia di riga unica per tutta la scheda Immobile:
// icona o avatar · titolo + badge · riga di dettaglio · azioni a destra.
withDefaults(
  defineProps<{
    titolo?: string;
    meta?: string;
    /** Ultima riga dell'elenco: niente separatore sotto. */
    ultima?: boolean;
    /** Riga d'archivio: stesso impaginato, meno peso visivo. */
    tenue?: boolean;
  }>(),
  { titolo: '', meta: '', ultima: false, tenue: false },
);
</script>

<style scoped>
.imm-riga {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 11px 2px;
  border-bottom: 1px solid var(--vp-paper-3);
  border-radius: 6px;
  transition: background 0.12s;
}
.imm-riga:hover {
  background: var(--vp-paper-2);
}
.imm-riga--ultima {
  border-bottom: none;
}
.imm-riga--tenue {
  opacity: 0.75;
}
.imm-riga__tile {
  display: flex;
  flex-shrink: 0;
}
.imm-riga__corpo {
  flex: 1;
  min-width: 0;
}
.imm-riga__testa {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.imm-riga__titolo {
  font-weight: 500;
  font-size: 14.5px;
  color: var(--vp-ink);
}
.imm-riga__meta {
  font-size: 12.5px;
  color: var(--vp-ink-3);
  margin-top: 2px;
  line-height: 1.45;
}
.imm-riga__azioni {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

/* Sul telefono le azioni scendono sotto invece di comprimere il titolo. */
@media (max-width: 599px) {
  .imm-riga {
    flex-wrap: wrap;
  }
  .imm-riga__corpo {
    flex: 1 1 60%;
  }
  .imm-riga__azioni {
    flex: 1 1 100%;
    justify-content: flex-end;
  }
}
</style>
