<template>
  <div ref="chartRef" class="equity-chart">
    <svg
      :viewBox="viewBox"
      preserveAspectRatio="none"
      @mousemove="handleMouseMove"
      @mouseleave="handleMouseLeave"
    >
      <defs>
        <linearGradient id="equityGradient" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop
            :offset="color === 'success' ? '0%' : '100%'"
            :stop-color="fillColor"
            stop-opacity="0.2"
          />
          <stop
            :offset="color === 'success' ? '100%' : '0%'"
            :stop-color="fillColor"
            stop-opacity="0"
          />
        </linearGradient>

        <!-- Grid pattern -->
        <pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse">
          <path
            d="M 50 0 L 0 0 0 50"
            fill="none"
            stroke="var(--border-color)"
            stroke-width="0.5"
          />
        </pattern>
      </defs>

      <!-- Grid Background -->
      <rect width="100%" height="100%" fill="url(#grid)" />

      <!-- Zero Line -->
      <line
        v-if="zeroY !== null"
        x1="0"
        :y1="zeroY"
        x2="width"
        :y2="zeroY"
        stroke="var(--border-color)"
        stroke-width="1"
        stroke-dasharray="4,4"
      />

      <!-- Fill Area -->
      <path
        v-if="data.length > 1"
        :d="areaPath"
        fill="url(#equityGradient)"
        stroke="none"
      />

      <!-- Line -->
      <path
        v-if="data.length > 1"
        :d="linePath"
        :stroke="strokeColor"
        stroke-width="2"
        fill="none"
        stroke-linecap="round"
        stroke-linejoin="round"
      />

      <!-- Points -->
      <circle
        v-for="(p, i) in points"
        :key="i"
        :cx="p.x"
        :cy="p.y"
        r="3"
        :fill="p.color || strokeColor"
        stroke="var(--bg-primary)"
        stroke-width="2"
        :class="{ highlight: i === hoverIndex }"
      />

      <!-- Current Value Dot -->
      <circle
        v-if="points.length > 0"
        :cx="points[points.length - 1].x"
        :cy="points[points.length - 1].y"
        r="5"
        :fill="strokeColor"
        stroke="var(--bg-primary)"
        stroke-width="3"
      />
    </svg>

    <!-- Tooltip -->
    <div
      v-show="hoverIndex !== null"
      class="chart-tooltip"
      :style="tooltipStyle"
    >
      <div class="tooltip-row">
        <span class="tooltip-label">Valor:</span>
        <span
          class="tooltip-value"
          :class="{
            positive: data[hoverIndex] >= 0,
            negative: data[hoverIndex] < 0,
          }"
        >
          {{ formatValue(data[hoverIndex]) }}
        </span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-label">Punto:</span>
        <span class="tooltip-index"
          >{{ hoverIndex + 1 }} / {{ data.length }}</span
        >
      </div>
      <div v-if="hoverIndex > 0" class="tooltip-row">
        <span class="tooltip-label">Cambio:</span>
        <span
          class="tooltip-change"
          :class="{
            positive: data[hoverIndex] - data[hoverIndex - 1] >= 0,
            negative: data[hoverIndex] - data[hoverIndex - 1] < 0,
          }"
        >
          {{ formatChange(data[hoverIndex] - data[hoverIndex - 1]) }}
        </span>
      </div>
    </div>

    <!-- Legend -->
    <div class="chart-legend">
      <div class="legend-item">
        <span class="legend-color" :style="{ background: strokeColor }"></span>
        <span class="legend-label">Equity</span>
      </div>
      <div class="legend-stats">
        <span class="stat">
          <span class="stat-label">Inicio:</span>
          <span class="stat-value">{{ formatValue(data[0]) }}</span>
        </span>
        <span class="stat">
          <span class="stat-label">Actual:</span>
          <span
            class="stat-value"
            :class="{
              positive: data[data.length - 1] >= 0,
              negative: data[data.length - 1] < 0,
            }"
          >
            {{ formatValue(data[data.length - 1]) }}
          </span>
        </span>
        <span class="stat">
          <span class="stat-label">Máx:</span>
          <span class="stat-value">{{ formatValue(maxVal) }}</span>
        </span>
        <span class="stat">
          <span class="stat-label">Mín:</span>
          <span class="stat-value">{{ formatValue(minVal) }}</span>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  data: {
    type: Array,
    required: true,
  },
  color: {
    type: String,
    default: "success",
    validator: (v) => ["success", "danger", "warning", "info"].includes(v),
  },
});

const hoverIndex = ref(null);
const chartRef = ref(null);

const colorMap = {
  success: { fill: "#10b981", stroke: "#10b981" },
  danger: { fill: "#ef4444", stroke: "#ef4444" },
  warning: { fill: "#f59e0b", stroke: "#f59e0b" },
  info: { fill: "#3b82f6", stroke: "#3b82f6" },
};

const fillColor = computed(() => colorMap.value[props.color].fill);
const strokeColor = computed(() => colorMap.value[props.color].stroke);

const minVal = computed(() => Math.min(...props.data));
const maxVal = computed(() => Math.max(...props.data));
const range = computed(() => maxVal.value - minVal.value || 1);

const width = 600;
const height = 200;
const padding = 40;
const innerWidth = width - 2 * padding;
const innerHeight = height - 2 * padding;

const viewBox = computed(() => `0 0 ${width} ${height}`);

const zeroY = computed(() => {
  if (minVal.value >= 0 || maxVal.value <= 0) return null;
  return padding + (maxVal.value / range.value) * innerHeight;
});

const points = computed(() => {
  if (props.data.length === 0) return [];
  const stepX = innerWidth / Math.max(1, props.data.length - 1);
  return props.data.map((val, i) => ({
    x: padding + i * stepX,
    y: padding + ((maxVal.value - val) / range.value) * innerHeight,
    color: null,
  }));
});

const linePath = computed(() => {
  if (points.value.length < 2) return "";
  return points.value
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`)
    .join(" ");
});

const areaPath = computed(() => {
  if (points.value.length < 2) return "";
  const last = points.value[points.value.length - 1];
  const first = points.value[0];
  const zeroLineY = zeroY.value !== null ? zeroY.value : height;
  return `${linePath.value} L ${last.x} ${zeroLineY} L ${first.x} ${zeroLineY} Z`;
});

const tooltipStyle = computed(() => {
  if (hoverIndex.value === null || !points.value[hoverIndex.value]) return {};
  const p = points.value[hoverIndex.value];
  const rect = chartRef.value?.getBoundingClientRect();
  if (!rect) return {};

  const scaleX = rect.width / width;
  const scaleY = rect.height / height;

  return {
    left: `${p.x * scaleX + rect.left + 15}px`,
    top: `${p.y * scaleY + rect.top - 100}px`,
  };
});

function formatValue(val) {
  return `${val >= 0 ? "+" : ""}${val.toFixed(2)}%`;
}

function formatChange(val) {
  return `${val >= 0 ? "+" : ""}${val.toFixed(2)}%`;
}

function handleMouseMove(event) {
  if (!chartRef.value || props.data.length === 0) return;
  const rect = chartRef.value.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const scaleX = rect.width / width;
  const dataX = x / scaleX;

  if (dataX < padding || dataX > padding + innerWidth) {
    hoverIndex.value = null;
    return;
  }

  const stepX = innerWidth / Math.max(1, props.data.length - 1);
  const index = Math.round((dataX - padding) / stepX);
  hoverIndex.value = Math.max(0, Math.min(props.data.length - 1, index));
}

function handleMouseLeave() {
  hoverIndex.value = null;
}
</script>

<style scoped>
.equity-chart {
  width: 100%;
  height: 100%;
  position: relative;
  background: var(--bg-tertiary);
  border-radius: var(--radius-lg);
}

.equity-chart svg {
  width: 100%;
  height: 100%;
  display: block;
}

.equity-chart circle.highlight {
  r: 6;
  stroke-width: 3;
}

.chart-tooltip {
  position: absolute;
  pointer-events: none;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--space-sm) var(--space-md);
  font-size: 0.7rem;
  font-family: var(--font-mono);
  color: var(--text-primary);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
  z-index: 20;
  min-width: 160px;
  animation: tooltipFade 0.15s ease-out;
}

@keyframes tooltipFade {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.tooltip-row {
  display: flex;
  justify-content: space-between;
  gap: var(--space-md);
  padding: 2px 0;
}

.tooltip-label {
  color: var(--text-secondary);
}

.tooltip-value {
  font-weight: 600;
}

.tooltip-value.positive {
  color: var(--accent-success);
}
.tooltip-value.negative {
  color: var(--accent-danger);
}

.tooltip-index {
  color: var(--text-muted);
}

.tooltip-change {
  font-weight: 600;
}

.tooltip-change.positive {
  color: var(--accent-success);
}
.tooltip-change.negative {
  color: var(--accent-danger);
}

.chart-legend {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-md);
  margin-top: var(--space-sm);
  border-top: 1px solid var(--border-color);
  flex-wrap: wrap;
  gap: var(--space-md);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 2px;
}

.legend-label {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.legend-stats {
  display: flex;
  gap: var(--space-lg);
  flex-wrap: wrap;
}

.stat {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
}

.stat-label {
  font-size: 0.65rem;
  color: var(--text-muted);
}

.stat-value {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  font-weight: 600;
}

.stat-value.positive {
  color: var(--accent-success);
}
.stat-value.negative {
  color: var(--accent-danger);
}

/* Responsive */
@media (max-width: 768px) {
  .chart-legend {
    flex-direction: column;
    align-items: flex-start;
  }

  .legend-stats {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
