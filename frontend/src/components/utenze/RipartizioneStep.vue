<script setup lang="ts">
// STEP 2 · RIPARTIZIONE
// Selettore criterio + tabella per inquilino divisa per utenza.
// Il backend implementa solo il pro-rata giorni: gli altri criteri sono
// mostrati ma disabilitati (`criteriAttivi`).
import { computed } from 'vue';
import VpIcon from './VpIcon.vue';
import VpAvatar from './VpAvatar.vue';
import { eur, CRITERI, CRITERI_ATTIVI } from './format';
import type { Criterio, QuotaView } from './format';

const props = defineProps<{
  criterio: Criterio;
  quote: QuotaView[];
  hasNuovoIngresso?: boolean;
  ingressoNota?: string;
}>();
const emit = defineEmits<{ 'update:criterio': [c: Criterio] }>();

const sommaQuote = computed(() => props.quote.reduce((s, q) => s + q.quota, 0));

function attivo(c: Criterio): boolean {
  return CRITERI_ATTIVI.includes(c);
}
function scegli(c: Criterio): void {
  if (attivo(c)) emit('update:criterio', c);
}
</script>

<template>
  <div>
    <!-- Criterio -->
    <div class="vp-card crit">
      <div class="sec-head">
        <div class="vp-display" style="font-size: 20px">Come dividiamo le utenze?</div>
        <div class="muted">Per ora la ripartizione è pro-rata sui giorni di presenza.</div>
      </div>
      <div class="crit-grid">
        <button
          v-for="c in CRITERI"
          :key="c.id"
          class="crit-opt"
          :class="{ sel: criterio === c.id, disabled: !attivo(c.id) }"
          :disabled="!attivo(c.id)"
          @click="scegli(c.id)"
        >
          <div class="crit-top">
            <VpIcon :name="c.icon" :size="16" /><span class="crit-title">{{ c.titolo }}</span>
            <span v-if="!attivo(c.id)" class="crit-na">non disponibile</span>
          </div>
          <div class="crit-sub">{{ c.sub }}</div>
        </button>
      </div>
    </div>

    <!-- Tabella per inquilino -->
    <div class="vp-card tbl-wrap">
      <div class="tbl-head">
        <div class="vp-display" style="font-size: 20px">Quota per inquilino</div>
        <span class="muted">Importo a carico di ciascuno sui giorni di presenza</span>
      </div>
      <table class="vp-table">
        <thead>
          <tr>
            <th>Inquilino</th>
            <th class="r">{{ criterio === 'mq' ? 'm²' : 'Giorni' }}</th>
            <th class="r">Quota</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="q in quote" :key="q.id">
            <td>
              <div class="who">
                <VpAvatar :name="q.nome" :size="30" :hue="q.avatarHue" />
                <div>
                  <div class="who-name">{{ q.nome }}</div>
                  <div v-if="q.stanza" class="who-room">{{ q.stanza }}</div>
                </div>
              </div>
            </td>
            <td class="r vp-mono">{{ criterio === 'mq' ? q.mq : q.giorni }}</td>
            <td class="r vp-mono"><span class="quota">{{ eur(q.quota) }}</span></td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td style="font-weight: 600">Totale</td>
            <td></td>
            <td class="r vp-mono"><b>{{ eur(sommaQuote) }}</b></td>
          </tr>
        </tfoot>
      </table>
    </div>

    <div v-if="hasNuovoIngresso" class="vp-banner">
      <VpIcon name="clock" :size="18" style="margin-top: 2px" />
      <div style="flex: 1">{{ ingressoNota }}</div>
    </div>
  </div>
</template>

<style scoped>
.muted {
  font-size: 13px;
  color: var(--vp-ink-3);
}
.sec-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 14px;
}
.crit {
  padding: 22px 24px;
  margin-bottom: 16px;
}
.crit-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 10px;
}
.crit-opt {
  padding: 14px 16px;
  border-radius: 12px;
  cursor: pointer;
  text-align: left;
  background: var(--vp-paper-2);
  border: 1.5px solid transparent;
  font-family: inherit;
  color: var(--vp-ink);
}
.crit-opt.sel {
  background: var(--vp-terra-soft);
  border-color: var(--vp-terra);
  color: var(--vp-terra-deep);
}
.crit-opt.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.crit-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.crit-title {
  font-size: 14px;
  font-weight: 500;
}
.crit-na {
  margin-left: auto;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--vp-ink-3);
  background: var(--vp-paper-3);
  border-radius: var(--vp-r-pill);
  padding: 1px 7px;
}
.crit-sub {
  font-size: 12px;
  color: var(--vp-ink-3);
}
.crit-opt.sel .crit-sub {
  color: var(--vp-terra-deep);
}

.tbl-wrap {
  overflow: hidden;
  margin-bottom: 16px;
}
.tbl-head {
  padding: 16px 22px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.r {
  text-align: right;
}
.who {
  display: flex;
  align-items: center;
  gap: 10px;
}
.who-name {
  font-weight: 500;
}
.who-room {
  font-size: 12px;
  color: var(--vp-ink-3);
}
.quota {
  font-weight: 600;
  font-size: 15px;
}

@media (max-width: 720px) {
  .crit-grid {
    grid-template-columns: 1fr;
  }
}
</style>
