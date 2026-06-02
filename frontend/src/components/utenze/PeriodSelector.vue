<script setup lang="ts">
// Selettore periodo compatto: frecce ‹ › per mese e anno + dropdown mese.
// Il dropdown mostra il tag "inviato" sui mesi i cui avvisi sono stati
// realmente spediti (non basta che gli addebiti siano stati creati).
import { ref } from 'vue';
import VpIcon from './VpIcon.vue';
import StatoBadge from './StatoBadge.vue';

export interface MeseStato {
  anno: number;
  mese: number;
  stato: string; // 'inviato' | 'da-inviare' | 'incompleto'
}

const props = defineProps<{
  anno: number;
  mese: number; // 1-12
  stato: string;
  mancanti?: number;
  periodi: MeseStato[];
}>();
const emit = defineEmits<{ cambia: [v: { anno: number; mese: number }] }>();

const MESI = [
  'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
  'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre',
];

const open = ref(false);

function vai(anno: number, mese: number): void {
  emit('cambia', { anno, mese });
}
function shiftMese(d: number): void {
  let m = props.mese + d;
  let a = props.anno;
  if (m < 1) {
    m = 12;
    a -= 1;
  } else if (m > 12) {
    m = 1;
    a += 1;
  }
  vai(a, m);
}
function shiftAnno(d: number): void {
  vai(props.anno + d, props.mese);
}
function pickMese(m: number): void {
  open.value = false;
  if (m !== props.mese) vai(props.anno, m);
}
function statoMese(m: number): string | null {
  return props.periodi.find((p) => p.anno === props.anno && p.mese === m)?.stato ?? null;
}
</script>

<template>
  <div class="wrap">
    <div class="vp-eyebrow" style="margin-bottom: 4px">Periodo</div>
    <div class="bar">
      <!-- Mese: frecce + dropdown -->
      <div class="group mese-group">
        <button class="arrow" aria-label="Mese precedente" @click="shiftMese(-1)">
          <VpIcon name="back" :size="15" />
        </button>
        <div class="mese-wrap">
          <button class="mese" @click="open = !open">
            <span>{{ MESI[mese - 1] }}</span>
            <VpIcon
              name="chevron"
              :size="12"
              color="var(--vp-ink-3)"
              :style="{ transform: open ? 'rotate(90deg)' : 'none', transition: 'transform .15s' }"
            />
          </button>
          <div v-if="open" class="backdrop" @click="open = false"></div>
          <div v-if="open" class="menu">
            <button
              v-for="(label, i) in MESI"
              :key="label"
              class="opt"
              :class="{ sel: i + 1 === mese }"
              @click="pickMese(i + 1)"
            >
              <span>{{ label }}</span>
              <StatoBadge
                v-if="statoMese(i + 1) === 'inviato'"
                stato="inviato"
                compact
              />
            </button>
          </div>
        </div>
        <button class="arrow" aria-label="Mese successivo" @click="shiftMese(1)">
          <VpIcon name="chevron" :size="15" />
        </button>
      </div>

      <!-- Anno: frecce -->
      <div class="group">
        <button class="arrow" aria-label="Anno precedente" @click="shiftAnno(-1)">
          <VpIcon name="back" :size="15" />
        </button>
        <span class="anno-val vp-mono">{{ anno }}</span>
        <button class="arrow" aria-label="Anno successivo" @click="shiftAnno(1)">
          <VpIcon name="chevron" :size="15" />
        </button>
      </div>

      <StatoBadge :stato="stato" :mancanti="mancanti ?? 0" />
    </div>
  </div>
</template>

<style scoped>
.wrap {
  position: relative;
}
.bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.group {
  display: flex;
  align-items: center;
  gap: 2px;
  background: var(--vp-paper-2);
  border: 1.5px solid var(--vp-paper-3);
  border-radius: 10px;
  padding: 2px;
}
.mese-wrap {
  position: relative;
}
.mese {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 9px;
  border-radius: 8px;
  cursor: pointer;
  background: transparent;
  border: none;
  font-family: inherit;
  font-size: 14px;
  font-weight: 600;
  color: var(--vp-ink);
  min-width: 92px;
  justify-content: space-between;
}
.mese:hover {
  background: var(--vp-paper-3);
}
.arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 7px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--vp-ink-2);
}
.arrow:hover {
  background: var(--vp-paper-3);
}
.anno-val {
  font-size: 14px;
  font-weight: 600;
  min-width: 42px;
  text-align: center;
}
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 10;
}
.menu {
  position: absolute;
  left: 0;
  top: 100%;
  margin-top: 6px;
  z-index: 20;
  width: 180px;
  max-height: 280px;
  overflow: auto;
  background: var(--vp-paper);
  border: 1px solid var(--vp-paper-3);
  border-radius: 12px;
  box-shadow: var(--vp-shadow-3);
  padding: 4px;
}
.opt {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  text-align: left;
  padding: 8px 11px;
  border-radius: 8px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-family: inherit;
  font-size: 14px;
  color: var(--vp-ink);
}
.opt:hover {
  background: var(--vp-paper-2);
}
.opt.sel {
  background: var(--vp-terra-soft);
  color: var(--vp-terra-deep);
  font-weight: 600;
}
</style>
