<template>
  <div class="mini-chart" :class="color">
    <svg :viewBox="viewBox" preserveAspectRatio="none">
      <defs>
        <linearGradient id="gradient" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop
            :offset="color === 'success' ? '0%' : '100%'"
            :stop-color="fillColor"
            stop-opacity="0.3"
          />
          <stop
            :offset="color === 'success' ? '100%' : '0%'"
            :stop-color="fillColor"
            stop-opacity="0"
          />
        </linearGradient>
      </defs>

      <!-- Fill Area -->
      <path
        v-if="data.length > 1"
        :d="areaPath"
        fill="url(#gradient)"
        stroke="none"
      />

      <!-- Line -->
      <path
        v-if="data.length > 1"
        :d="linePath"
        :stroke="strokeColor"
        stroke-width="1.5"
        fill="none"
        stroke-linecap="round"
        stroke-linejoin="round"
      />

      <!-- Current Value Dot -->
      <circle
        v-if="data.length > 0"
        :cx="points[points.length - 1].x"
        :cy="points[points.length - 1].y"
        r="3"
        :fill="strokeColor"
        stroke="var(--bg-primary)"
        stroke-width="2"
      />
    </svg>

    <!-- Tooltip -->
    <div
      v-show="hoverPoint !== null"
      class="chart-tooltip"
      :style="tooltipStyle"
    >
      <div class="tooltip-value">{{ formatValue(data[hoverPoint]) }}</div>
      <div class="tooltip-index">{{ hoverPoint + 1 }} / {{ data.length }}</div>
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
  height: {
    type: Number,
    default: 80,
  },
  width: {
    type: Number,
    default: 300,
  },
});

const hoverPoint = ref(null);
const svgRef = ref(null);

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

const viewBox = computed(() => `0 0 ${props.width} ${props.height}`);

const points = computed(() => {
  if (props.data.length === 0) return [];
  const stepX = props.width / Math.max(1, props.data.length - 1);
  return props.data.map((val, i) => ({
    x: i * stepX,
    y:
      props.height -
      ((val - minVal.value) / range.value) * (props.height - 10) -
      5,
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
  return `${linePath.value} L ${last.x} ${props.height} L ${first.x} ${props.height} Z`;
});

const tooltipStyle = computed(() => {
  if (hoverPoint.value === null || !points.value[hoverPoint.value]) return {};
  const p = points.value[hoverPoint.value];
  return {
    left: `${p.x + 10}px`,
    top: `${p.y - 40}px`,
  };
});

function formatValue(val) {
  return `${val >= 0 ? "+" : ""}${val.toFixed(2)}%`;
}

function handleMouseMove(event) {
  if (!svgRef.value || props.data.length === 0) return;
  const rect = svgRef.value.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const stepX = props.width / Math.max(1, props.data.length - 1);
  const index = Math.round(x / stepX);
  hoverPoint.value = Math.max(0, Math.min(props.data.length - 1, index));
}

function handleMouseLeave() {
  hoverPoint.value = null;
}
</script>

<style scoped>
.mini-chart {
  width: 100%;
  height: 100%;
  position: relative;
  border-radius: var(--radius-md);
  background: var(--bg-tertiary);
}

.mini-chart svg {
  width: 100%;
  height: 100%;
  display: block;
}

.chart-tooltip {
  position: absolute;
  pointer-events: none;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--space-xs) var(--space-sm);
  font-size: 0.7rem;
  font-family: var(--font-mono);
  color: var(--text-primary);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  z-index: 10;
  white-space: nowrap;
  transform: translateX(-50%);
}

.tooltip-value {
  font-weight: 600;
}

.tooltip-index {
  font-size: 0.6rem;
  color: var(--text-muted);
  margin-top: 2px;
}
</style>
