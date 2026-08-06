<template>
  <div class="imm-azioni">
    <slot />
    <BtnIcona
      v-if="puoModificare"
      icona="pencil"
      :etichetta="`Modifica ${oggetto}`"
      tooltip="Modifica"
      @click="emit('modifica')"
    />
    <BtnIcona
      v-if="puoEliminare"
      icona="trash"
      pericolo
      :etichetta="`Elimina ${oggetto}`"
      tooltip="Elimina"
      @click="emit('elimina')"
    />
  </div>
</template>

<script setup lang="ts">
import BtnIcona from './BtnIcona.vue';

withDefaults(
  defineProps<{
    /** Cosa si modifica o elimina: entra nell'etichetta per screen reader. */
    oggetto: string;
    puoModificare?: boolean;
    puoEliminare?: boolean;
  }>(),
  { puoModificare: true, puoEliminare: true },
);

const emit = defineEmits<{
  (e: 'modifica'): void;
  (e: 'elimina'): void;
}>();
</script>

<style scoped>
.imm-azioni {
  display: flex;
  gap: 2px;
  align-items: center;
}
</style>
