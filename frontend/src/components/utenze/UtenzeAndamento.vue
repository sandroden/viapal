<template>
  <div class="andamento">
    <div v-if="store.loading && !hasData" class="empty-state">
      <q-spinner-dots size="32px" color="primary" />
    </div>

    <template v-else-if="hasData">
      <!-- Header + selettore range -->
      <div class="header">
        <div class="header-text">
          <div class="vp-eyebrow">Utenze · luce e gas</div>
          <h2 class="vp-display title">Andamento dei costi</h2>
          <div class="subtitle">
            Bolletta mensile — prezzo unitario e consumo nel tempo.
            La spesa sale per il prezzo o per i consumi?
          </div>
        </div>
        <div class="range-sel">
          <button :class="rangeBtnCls(mode === 'rolling')" @click="mode = 'rolling'">
            Ultimi 12 mesi
          </button>
          <div class="range-div" />
          <button :class="rangeBtnCls(false)" style="padding: 7px 8px" :disabled="yearIdx <= 0" @click="shiftYear(-1)" aria-label="Anno precedente">‹</button>
          <button :class="rangeBtnCls(mode === 'year')" @click="mode = 'year'">{{ currentYear }}</button>
          <button :class="rangeBtnCls(false)" style="padding: 7px 8px" :disabled="yearIdx >= anni.length - 1" @click="shiftYear(1)" aria-label="Anno successivo">›</button>
        </div>
      </div>

      <!-- KPI strip -->
      <div v-if="ultimo" class="kpi-strip">
        <div class="vp-card kpi big">
          <div class="vp-eyebrow">Spesa del mese</div>
          <div class="vp-display kpi-val big-val">{{ fmtEuro(totaleUltimo) }}</div>
          <div class="kpi-trend">
            <TrendChip :value="trendTotale" />
            <span class="kpi-sub">vs anno scorso</span>
          </div>
        </div>
        <div class="vp-card kpi">
          <div class="vp-eyebrow">Prezzo luce</div>
          <div class="vp-display kpi-val">
            {{ fmtPrezzo(ultimo.luce_prezzo_unitario) }}
            <span class="kpi-unit">€/kWh</span>
          </div>
          <TrendChip :value="trendLucePrezzo" />
        </div>
        <div class="vp-card kpi">
          <div class="vp-eyebrow">Prezzo gas</div>
          <div class="vp-display kpi-val">
            {{ fmtPrezzo(ultimo.gas_prezzo_unitario) }}
            <span class="kpi-unit">€/m³</span>
          </div>
          <TrendChip :value="trendGasPrezzo" />
        </div>
        <div class="vp-card kpi">
          <div class="vp-eyebrow">kWh / presenza</div>
          <div class="vp-display kpi-val">
            {{ kwhPPUltimo !== null ? fmtDec(kwhPPUltimo, 1) : '—' }}
            <span class="kpi-unit">kWh</span>
          </div>
          <TrendChip :value="trendKwhPP" />
        </div>
        <div class="vp-card kpi">
          <div class="vp-eyebrow">Presenze</div>
          <div class="vp-display kpi-val">
            {{ ultimo.presenze !== null ? Math.round(ultimo.presenze).toLocaleString('it-IT') : '—' }}
            <span class="kpi-unit">notti</span>
          </div>
          <TrendChip :value="trendPresenze" :invert="false" />
        </div>
      </div>

      <!-- Insight automatico: prezzo o consumo? -->
      <div v-if="insight" class="vp-banner insight-banner" :style="{ borderLeftColor: insight.color }">
        <div class="insight-icon" :style="{ color: insight.color }">
          <VpIcon :name="insight.icon" :size="18" />
        </div>
        <div>
          <div class="insight-title">
            {{ insight.mese }}: <strong>{{ insight.delta }}</strong> in più vs anno scorso
            — soprattutto per <strong>{{ insight.driver }}</strong>.
          </div>
          <div class="insight-sub">
            {{ insight.breakdownPct }}% dall'aumento delle tariffe · {{ 100 - insight.breakdownPct }}% da consumi più alti.
          </div>
        </div>
      </div>

      <!-- Grafici combo: Luce e Gas affiancati -->
      <div v-if="view.length > 1" class="combo-grid">
        <div v-for="fluid in fluids" :key="fluid.key" class="vp-card combo-card">
          <div class="combo-head">
            <div class="combo-title-row">
              <div class="tipo-icon" :style="{ color: fluid.color }">
                <VpIcon :name="fluid.icon" :size="17" />
              </div>
              <div class="vp-display combo-label">{{ fluid.label }}</div>
            </div>
            <div class="combo-right">
              <div class="vp-mono combo-amount">{{ fluid.costoFmt }}</div>
              <div class="combo-sub">{{ fluid.consFmt }} · {{ fluid.prezzoFmt }} {{ fluid.unitP }}</div>
            </div>
          </div>
          <div class="legend">
            <span class="leg-item">
              <span class="leg-bar" :style="{ background: fluid.color }" />
              Consumo ({{ fluid.unitC }})
            </span>
            <span class="leg-item">
              <span class="leg-line" />
              Prezzo ({{ fluid.unitP }})
            </span>
          </div>
          <ComboChart
            :data="view"
            :bar-vals="fluid.barVals"
            :line-vals="fluid.lineVals"
            :bar-color="fluid.color"
            :bar-fmt="fluid.barFmt"
            :line-fmt="fluid.lineFmt"
            :height="184"
          />
        </div>
      </div>

      <!-- kWh per presenza -->
      <div v-if="view.length > 1 && hasPresenze" class="vp-card kwh-card">
        <div class="kwh-head">
          <div class="kwh-title-row">
            <div class="tipo-icon" style="color: var(--vp-wood)">
              <VpIcon name="trend" :size="17" />
            </div>
            <div>
              <div class="vp-display combo-label">kWh per presenza</div>
              <div class="kwh-desc">Consumo elettrico depurato dagli ospiti: se sale, è inefficienza, non solo più affitti.</div>
            </div>
          </div>
          <div v-if="kwhPPUltimo !== null" class="combo-right">
            <div class="vp-mono combo-amount">{{ fmtDec(kwhPPUltimo, 1) }} <span class="kpi-unit">kWh/notte</span></div>
            <div class="kwh-trend-row">vs anno scorso <TrendChip :value="trendKwhPP" /></div>
          </div>
        </div>
        <div class="legend">
          <span class="leg-item">
            <span class="leg-bar" style="background: var(--vp-sage); opacity: 0.55" />
            Presenze (notti)
          </span>
          <span class="leg-item">
            <span class="leg-line" style="background: var(--vp-wood)" />
            kWh / presenza
          </span>
        </div>
        <ComboChart
          :data="view"
          :bar-vals="presenzeVals"
          :line-vals="kwhPPVals"
          bar-color="var(--vp-sage)"
          line-color="var(--vp-wood)"
          :bar-fmt="(v: number) => Math.round(v).toLocaleString('it-IT')"
          :line-fmt="(v: number) => fmtDec(v, 1)"
          :height="150"
        />
      </div>
    </template>

    <div v-else class="empty-state">
      <q-icon name="bar_chart" size="48px" color="grey-4" />
      <div>Nessun dato disponibile. Carica delle bollette per vedere l'andamento.</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, ref, watch, type PropType } from 'vue';
import { useUtenzeStore, type StatisticaMensile } from 'stores/utenze';
import VpIcon from 'src/components/utenze/VpIcon.vue';

const store = useUtenzeStore();

onMounted(async () => {
  if (!store.statistiche.length) {
    await store.fetchStatistiche();
  }
});

const hasData = computed(() => store.statistiche.length > 0);

// ── Selettore range ──────────────────────────────────────────
const mode = ref<'rolling' | 'year'>('rolling');
const anni = computed(() => [...new Set(store.statistiche.map((d) => d.anno))].sort((a, b) => a - b));
const currentYear = ref(0);

watch(anni, (a) => {
  if (a.length && !a.includes(currentYear.value)) {
    currentYear.value = a[a.length - 1] ?? 0;
  }
}, { immediate: true });

const yearIdx = computed(() => anni.value.indexOf(currentYear.value));

function shiftYear(d: number): void {
  const ni = Math.max(0, Math.min(anni.value.length - 1, yearIdx.value + d));
  currentYear.value = anni.value[ni] ?? currentYear.value;
  mode.value = 'year';
}

function rangeBtnCls(active: boolean): string[] {
  return ['range-btn', ...(active ? ['active'] : [])];
}

const view = computed<StatisticaMensile[]>(() => {
  if (!hasData.value) return [];
  if (mode.value === 'rolling') return store.statistiche.slice(-12);
  return store.statistiche.filter((d) => d.anno === currentYear.value);
});

const ultimo = computed<StatisticaMensile | null>(() => view.value[view.value.length - 1] ?? null);
const yoy = computed<StatisticaMensile | null>(() => {
  if (!ultimo.value) return null;
  return (
    store.statistiche.find(
      (d) => d.mese === ultimo.value!.mese && d.anno === ultimo.value!.anno - 1,
    ) ?? null
  );
});

// ── Formattatori ─────────────────────────────────────────────
function fmtEuro(n: number | null | undefined, d = 0): string {
  if (n == null) return '—';
  return '€ ' + n.toLocaleString('it-IT', { minimumFractionDigits: d, maximumFractionDigits: d });
}
function fmtPrezzo(n: number | null | undefined): string {
  if (n == null) return '—';
  return n.toLocaleString('it-IT', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
}
function fmtDec(n: number | null | undefined, d = 1): string {
  if (n == null) return '—';
  return n.toLocaleString('it-IT', { minimumFractionDigits: d, maximumFractionDigits: d });
}
function pctDelta(a: number | null | undefined, b: number | null | undefined): number | null {
  if (a == null || b == null || b === 0) return null;
  return ((a - b) / b) * 100;
}

// ── KPI calcolati ─────────────────────────────────────────────
const totaleUltimo = computed(() =>
  ultimo.value ? (ultimo.value.luce_importo ?? 0) + (ultimo.value.gas_importo ?? 0) : null,
);
const totaleYoy = computed(() =>
  yoy.value ? (yoy.value.luce_importo ?? 0) + (yoy.value.gas_importo ?? 0) : null,
);
const kwhPPUltimo = computed(() => {
  const u = ultimo.value;
  if (!u || u.luce_consumo == null || !u.presenze) return null;
  return u.luce_consumo / u.presenze;
});
const kwhPPYoy = computed(() => {
  const y = yoy.value;
  if (!y || y.luce_consumo == null || !y.presenze) return null;
  return y.luce_consumo / y.presenze;
});

const trendTotale = computed(() => pctDelta(totaleUltimo.value, totaleYoy.value));
const trendLucePrezzo = computed(() => pctDelta(ultimo.value?.luce_prezzo_unitario, yoy.value?.luce_prezzo_unitario));
const trendGasPrezzo = computed(() => pctDelta(ultimo.value?.gas_prezzo_unitario, yoy.value?.gas_prezzo_unitario));
const trendKwhPP = computed(() => pctDelta(kwhPPUltimo.value, kwhPPYoy.value));
const trendPresenze = computed(() => pctDelta(ultimo.value?.presenze, yoy.value?.presenze));

// ── Insight: prezzo o consumo? ────────────────────────────────
const MESI_LABEL = ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu', 'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic'];

const insight = computed(() => {
  const u = ultimo.value, y = yoy.value;
  if (!u || !y) return null;
  const leg = (p0: number, q0: number, p1: number, q1: number) => ({
    vol: (q1 - q0) * p0,
    price: (p1 - p0) * q1,
  });
  const l = leg(y.luce_prezzo_unitario ?? 0, y.luce_consumo ?? 0, u.luce_prezzo_unitario ?? 0, u.luce_consumo ?? 0);
  const g = leg(y.gas_prezzo_unitario ?? 0, y.gas_consumo ?? 0, u.gas_prezzo_unitario ?? 0, u.gas_consumo ?? 0);
  const delta = l.vol + l.price + g.vol + g.price;
  if (Math.abs(delta) < 0.5) return null;
  const price = l.price + g.price;
  const priceShare = Math.round((price / delta) * 100);
  const driverPrice = priceShare >= 50;
  return {
    icon: driverPrice ? 'euro' : 'trend',
    color: driverPrice ? 'var(--vp-clay)' : 'var(--vp-honey)',
    mese: `${MESI_LABEL[u.mese - 1]} '${String(u.anno).slice(2)}`,
    delta: fmtEuro(Math.abs(delta), 0),
    driver: driverPrice ? "il prezzo dell'energia" : 'i maggiori consumi',
    breakdownPct: Math.max(0, Math.min(100, priceShare)),
  };
});

// ── Dati per i grafici ────────────────────────────────────────
const hasPresenze = computed(() => view.value.some((d) => d.presenze != null));

const presenzeVals = computed(() => view.value.map((d) => d.presenze ?? 0));
const kwhPPVals = computed(() =>
  view.value.map((d) =>
    d.luce_consumo != null && d.presenze ? d.luce_consumo / d.presenze : 0,
  ),
);

const fluids = computed(() => {
  const u = ultimo.value;
  return [
    {
      key: 'luce',
      label: 'Luce',
      icon: 'bolt',
      color: 'var(--vp-honey)',
      unitC: 'kWh',
      unitP: '€/kWh',
      costoFmt: fmtEuro(u?.luce_importo ?? null, 0),
      consFmt: u?.luce_consumo != null ? Math.round(u.luce_consumo).toLocaleString('it-IT') + ' kWh' : '—',
      prezzoFmt: fmtPrezzo(u?.luce_prezzo_unitario ?? null),
      barVals: view.value.map((d) => d.luce_consumo ?? 0),
      lineVals: view.value.map((d) => d.luce_prezzo_unitario ?? 0),
      barFmt: (v: number) => Math.round(v).toLocaleString('it-IT'),
      lineFmt: (v: number) => v.toLocaleString('it-IT', { minimumFractionDigits: 3, maximumFractionDigits: 3 }),
    },
    {
      key: 'gas',
      label: 'Gas',
      icon: 'flame',
      color: 'var(--vp-clay)',
      unitC: 'm³',
      unitP: '€/m³',
      costoFmt: fmtEuro(u?.gas_importo ?? null, 0),
      consFmt: u?.gas_consumo != null ? Math.round(u.gas_consumo).toLocaleString('it-IT') + ' m³' : '—',
      prezzoFmt: fmtPrezzo(u?.gas_prezzo_unitario ?? null),
      barVals: view.value.map((d) => d.gas_consumo ?? 0),
      lineVals: view.value.map((d) => d.gas_prezzo_unitario ?? 0),
      barFmt: (v: number) => Math.round(v).toLocaleString('it-IT'),
      lineFmt: (v: number) => v.toLocaleString('it-IT', { minimumFractionDigits: 3, maximumFractionDigits: 3 }),
    },
  ];
});

// ── Sotto-componenti inline ───────────────────────────────────

// TrendChip: freccia colorata + percentuale
const TrendChip = defineComponent({
  props: {
    value: { type: Number as PropType<number | null>, default: null },
    invert: { type: Boolean, default: true },
    size: { type: Number, default: 12 },
  },
  setup(props) {
    return () => {
      const v = props.value;
      if (v == null) return h('span');
      const up = v >= 0;
      const bad = props.invert ? up : !up;
      const color = Math.abs(v) < 0.5
        ? 'var(--vp-ink-3)'
        : bad ? 'var(--vp-clay)' : 'var(--vp-sage-deep)';
      const pct =
        (v >= 0 ? '+' : '−') +
        Math.abs(v).toLocaleString('it-IT', { maximumFractionDigits: 0 }) +
        '%';
      return h(
        'span',
        {
          class: 'vp-mono',
          style: {
            color,
            fontSize: props.size + 'px',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '3px',
            fontWeight: 500,
          },
        },
        [
          h(
            'svg',
            {
              width: props.size - 1,
              height: props.size - 1,
              viewBox: '0 0 12 12',
              fill: 'none',
              style: { transform: up ? 'none' : 'scaleY(-1)' },
            },
            [h('path', { d: 'M6 2 L10 7 H7.5 V10 H4.5 V7 H2 Z', fill: color })],
          ),
          pct,
        ],
      );
    };
  },
});

// ComboChart: barre (consumo) + linea (prezzo) — SVG puro, responsive
const ComboChart = defineComponent({
  props: {
    data: { type: Array as PropType<StatisticaMensile[]>, required: true },
    barVals: { type: Array as PropType<number[]>, required: true },
    lineVals: { type: Array as PropType<number[]>, required: true },
    barColor: { type: String, default: 'var(--vp-honey)' },
    lineColor: { type: String, default: 'var(--vp-ink)' },
    barFmt: { type: Function as PropType<(v: number) => string>, default: () => (v: number) => Math.round(v).toLocaleString('it-IT') },
    lineFmt: { type: Function as PropType<(v: number) => string>, default: () => (v: number) => v.toLocaleString('it-IT', { minimumFractionDigits: 3, maximumFractionDigits: 3 }) },
    height: { type: Number, default: 190 },
  },
  setup(props) {
    const hovered = ref<number | null>(null);

    return () => {
      const { data, barVals, lineVals, barColor, lineColor, barFmt, lineFmt, height } = props;
      const W = 560, H = height;
      const padL = 34, padR = 44, padT = 22, padB = 30;
      const iw = W - padL - padR, ih = H - padT - padB;
      const n = data.length;
      if (!n) return h('div');

      const barMax = Math.max(...barVals, 1) * 1.14;
      const linVals = lineVals.filter((v) => v > 0);
      const linMin = linVals.length ? Math.min(...linVals) * 0.82 : 0;
      const linMax = linVals.length ? Math.max(...linVals) * 1.05 : 1;
      const slot = iw / n;
      const barW = Math.min(slot * 0.46, 26);
      const cx = (i: number) => padL + slot * i + slot / 2;
      const yL = (v: number) => padT + ih - ((v - linMin) / (linMax - linMin || 1)) * ih;
      const pts = lineVals.map((v, i) => [cx(i), yL(v)] as [number, number]);
      // Path spezzato: usa M quando il punto precedente era vuoto (v <= 0)
      const path = (() => {
        const segs: string[] = [];
        let connected = false;
        pts.forEach(([px, py], i) => {
          if ((lineVals[i] ?? 0) <= 0) { connected = false; return; }
          segs.push(`${connected ? 'L' : 'M'}${px.toFixed(1)} ${py.toFixed(1)}`);
          connected = true;
        });
        return segs.join(' ');
      })();
      const last = n - 1;
      const hi = hovered.value;

      // Tooltip per il punto in hover
      let tooltipEl = null;
      if (hi !== null) {
        const hiPt = (lineVals[hi] ?? 0) > 0 ? pts[hi] : undefined;
        if (hiPt) {
          const [tx, ty] = hiPt;
          const lineLabel = lineFmt(lineVals[hi] ?? 0);
          const barLabel = barFmt(barVals[hi] ?? 0);
          const tw = 76, th = 34;
          const tx0 = Math.max(padL, Math.min(tx - tw / 2, W - padR - tw));
          const ty0 = ty > padT + 44 ? ty - th - 9 : ty + 13;
          tooltipEl = h('g', { style: { pointerEvents: 'none' } }, [
            h('rect', { x: tx0, y: ty0, width: tw, height: th, rx: 7, fill: lineColor }),
            h('text', { x: tx0 + tw / 2, y: ty0 + 13, 'text-anchor': 'middle', 'font-size': 10.5, 'font-weight': 700, fill: 'var(--vp-cream)', 'font-family': 'var(--vp-font-mono)' }, lineLabel),
            h('text', { x: tx0 + tw / 2, y: ty0 + 26, 'text-anchor': 'middle', 'font-size': 8.5, fill: 'var(--vp-cream)', 'font-family': 'var(--vp-font-mono)', opacity: 0.7 }, barLabel),
          ]);
        }
      }

      return h(
        'svg',
        { viewBox: `0 0 ${W} ${H}`, width: '100%', height: H, style: { display: 'block', overflow: 'visible' } },
        [
          // Griglia
          ...[0, 0.25, 0.5, 0.75, 1].map((g, gi) => {
            const gy = padT + ih * (1 - g);
            return h('g', { key: `g${gi}` }, [
              g > 0 ? h('line', { x1: padL, x2: W - padR, y1: gy, y2: gy, stroke: 'var(--vp-paper-3)', 'stroke-width': 1, 'stroke-dasharray': '2 4' }) : null,
              h('text', { x: padL - 6, y: gy + 3.5, 'text-anchor': 'end', 'font-size': 9, fill: barColor, 'font-family': 'var(--vp-font-mono)', opacity: 0.9 }, barFmt(barMax * g)),
              h('text', { x: W - padR + 6, y: gy + 3.5, 'text-anchor': 'start', 'font-size': 9, fill: lineColor, 'font-family': 'var(--vp-font-mono)', opacity: 0.65 }, lineFmt(linMin + (linMax - linMin) * g)),
            ]);
          }),
          // Highlight colonna in hover (dietro le barre)
          hi !== null ? h('rect', { x: cx(hi) - slot / 2, y: padT, width: slot, height: ih, fill: 'var(--vp-paper-2)', opacity: 0.7, rx: 2 }) : null,
          // Barre
          ...barVals.map((v, i) => {
            const bh = (v / barMax) * ih;
            return h('rect', { key: `b${i}`, x: cx(i) - barW / 2, y: padT + ih - bh, width: barW, height: Math.max(bh, 1), rx: 3, fill: barColor, opacity: (i === last || i === hi) ? 0.95 : 0.42 });
          }),
          // Linea
          h('path', { d: path, fill: 'none', stroke: lineColor, 'stroke-width': 2.5, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }),
          // Punti (solo per mesi con dato linea)
          ...pts.map(([px, py], i) =>
            (lineVals[i] ?? 0) > 0
              ? h('circle', { key: `c${i}`, cx: px, cy: py, r: i === last ? 4.5 : (i === hi ? 4.0 : 2.6), fill: 'var(--vp-cream)', stroke: lineColor, 'stroke-width': i === last ? 2.5 : (i === hi ? 2.2 : 1.8) })
              : null,
          ),
          // Badge ultimo valore (nascosto quando è in hover — il tooltip lo sostituisce)
          (() => {
            const lp = pts[last];
            return lp && hi !== last ? h('g', [
              h('rect', { x: Math.min(lp[0] - 34, W - 70), y: lp[1] - 24, width: 68, height: 17, rx: 8, fill: lineColor }),
              h('text', { x: Math.min(lp[0], W - 36), y: lp[1] - 11.5, 'text-anchor': 'middle', 'font-size': 10.5, 'font-weight': 600, fill: 'var(--vp-cream)', 'font-family': 'var(--vp-font-mono)' }, lineFmt(lineVals[last] ?? 0)),
            ]) : null;
          })(),
          // Etichette mesi
          ...data.map((d, i) =>
            h('g', { key: `x${i}` }, [
              h('text', { x: cx(i), y: H - 11, 'text-anchor': 'middle', 'font-size': 9.5, fill: i === last ? 'var(--vp-ink)' : 'var(--vp-ink-3)', 'font-weight': i === last ? 600 : 400, 'font-family': 'var(--vp-font-ui)' }, MESI_LABEL[d.mese - 1] ?? ''),
              d.mese === 1 || i === 0
                ? h('text', { x: cx(i), y: H - 1, 'text-anchor': 'middle', 'font-size': 8.5, fill: 'var(--vp-ink-4)', 'font-family': 'var(--vp-font-mono)' }, String(d.anno).slice(2))
                : null,
            ]),
          ),
          // Hit area per colonna (trasparente, sopra tutto, cattura hover)
          ...data.map((_, i) =>
            h('rect', {
              key: `hit${i}`,
              x: cx(i) - slot / 2,
              y: padT,
              width: slot,
              height: ih,
              fill: 'transparent',
              style: { cursor: 'crosshair' },
              onMouseenter: () => { hovered.value = i; },
              onMouseleave: () => { hovered.value = null; },
            }),
          ),
          // Tooltip
          tooltipEl,
        ],
      );
    };
  },
});
</script>

<style scoped>
.andamento {
  padding: 20px 28px 48px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: 1200px;
}

.header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.title { font-size: 26px; margin: 4px 0 0; }
.subtitle { font-size: 13px; color: var(--vp-ink-3); margin-top: 3px; }

.range-sel {
  display: flex;
  gap: 4px;
  padding: 4px;
  background: var(--vp-paper-2);
  border-radius: var(--vp-r-pill);
  align-items: center;
  flex-shrink: 0;
}
.range-div { width: 1px; height: 18px; background: var(--vp-paper-3); }
.range-btn {
  border: none;
  background: transparent;
  color: var(--vp-ink-3);
  font-weight: 400;
  cursor: pointer;
  font-size: 12.5px;
  padding: 7px 13px;
  border-radius: var(--vp-r-pill);
  font-family: var(--vp-font-ui);
  white-space: nowrap;
  transition: background .12s, color .12s;
}
.range-btn:disabled { opacity: 0.35; cursor: default; }
.range-btn.active {
  background: var(--vp-cream);
  color: var(--vp-ink);
  font-weight: 600;
  box-shadow: var(--vp-shadow-1);
}

.kpi-strip {
  display: grid;
  grid-template-columns: 1.3fr 1fr 1fr 1fr 1fr;
  gap: 12px;
}
.kpi { padding: 15px 16px; display: flex; flex-direction: column; gap: 3px; }
.kpi.big { padding: 18px 20px; }
.kpi-val { font-size: 22px; line-height: 1.05; margin-top: 3px; }
.big-val { font-size: 30px; }
.kpi-unit { font-size: 12px; color: var(--vp-ink-3); margin-left: 2px; }
.kpi-trend { display: flex; align-items: center; gap: 8px; margin-top: 1px; }
.kpi-sub { font-size: 11px; color: var(--vp-ink-3); }

.insight-banner { align-items: center; }
.insight-icon {
  width: 34px; height: 34px; border-radius: 10px;
  background: var(--vp-paper-2);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.insight-title { font-weight: 500; margin-bottom: 2px; font-size: 14px; }
.insight-sub { font-size: 12.5px; color: var(--vp-ink-2); }

.combo-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.combo-card, .kwh-card {
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.combo-head, .kwh-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.combo-title-row, .kwh-title-row {
  display: flex;
  align-items: center;
  gap: 9px;
}
.tipo-icon {
  width: 30px; height: 30px;
  border-radius: 8px;
  background: var(--vp-paper-2);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.combo-label { font-size: 19px; }
.combo-right { text-align: right; }
.combo-amount { font-size: 17px; font-weight: 600; }
.combo-sub, .kwh-desc { font-size: 11.5px; color: var(--vp-ink-3); margin-top: 1px; }
.kwh-trend-row { font-size: 11.5px; color: var(--vp-ink-3); display: flex; gap: 6px; align-items: center; justify-content: flex-end; }

.legend { display: flex; gap: 14px; font-size: 11.5px; color: var(--vp-ink-2); }
.leg-item { display: flex; align-items: center; gap: 6px; }
.leg-bar { width: 11px; height: 8px; border-radius: 2px; display: inline-block; opacity: 0.55; }
.leg-line { width: 14px; height: 2.5px; border-radius: 2px; background: var(--vp-ink); display: inline-block; }

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  min-height: 300px;
  color: var(--vp-ink-3);
  text-align: center;
}
</style>
