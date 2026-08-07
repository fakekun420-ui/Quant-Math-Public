<template>
  <div ref="chartRef" class="chart-container" style="height: 300px"></div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from "vue";
import { Chart, registerables } from "chart.js";

Chart.register(...registerables);

const props = defineProps({
  trades: {
    type: Array,
    required: true,
  },
});

const chartRef = ref(null);
let chart = null;

function createChart() {
  if (!chartRef.value || !props.trades.length) return;

  const ctx = chartRef.value.getContext("2d");

  // Calculate PnL distribution
  const pnls = props.trades.map((t) => t.pnl_pct);
  const wins = pnls.filter((p) => p > 0);
  const losses = pnls.filter((p) => p < 0);

  // Create histogram bins
  const minPnl = Math.min(...pnls);
  const maxPnl = Math.max(...pnls);
  const binCount = 20;
  const binWidth = (maxPnl - minPnl) / binCount;

  const bins = new Array(binCount).fill(0);
  const binLabels = [];

  for (let i = 0; i < binCount; i++) {
    const binStart = minPnl + i * binWidth;
    const binEnd = binStart + binWidth;
    binLabels.push(`${binStart.toFixed(1)}%`);
    bins[i] = pnls.filter((p) => p >= binStart && p < binEnd).length;
  }
  // Add last bin edge
  binLabels[binLabels.length - 1] =
    `${minPnl.toFixed(1)}% - ${maxPnl.toFixed(1)}%`;

  chart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: binLabels,
      datasets: [
        {
          label: "Frecuencia",
          data: bins,
          backgroundColor: bins.map((_, i) => {
            const binCenter = minPnl + (i + 0.5) * binWidth;
            return binCenter >= 0
              ? "rgba(63, 185, 80, 0.7)"
              : "rgba(248, 81, 73, 0.7)";
          }),
          borderColor: bins.map((_, i) => {
            const binCenter = minPnl + (i + 0.5) * binWidth;
            return binCenter >= 0
              ? "rgba(63, 185, 80, 1)"
              : "rgba(248, 81, 73, 1)";
          }),
          borderWidth: 1,
          borderRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#161b22",
          borderColor: "#30363d",
          borderWidth: 1,
          padding: 12,
          titleFont: { size: 13 },
          bodyFont: { size: 12, family: "JetBrains Mono" },
          callbacks: {
            label: (context) => {
              const count = context.parsed.y;
              const pct = ((count / props.trades.length) * 100).toFixed(1);
              return `${context.dataset.label}: ${count} (${pct}%)`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: "#8b949e",
            font: { size: 10 },
            maxRotation: 45,
            minRotation: 45,
          },
        },
        y: {
          grid: { color: "rgba(48, 54, 61, 0.5)" },
          ticks: { color: "#8b949e", font: { size: 11 }, stepSize: 1 },
          beginAtZero: true,
        },
      },
    },
  });
}

onMounted(() => {
  nextTick(() => createChart());
});

watch(
  () => props.trades,
  () => {
    if (chart) {
      chart.destroy();
    }
    nextTick(() => createChart());
  },
  { deep: true },
);
</script>

<style scoped>
.chart-container {
  width: 100%;
  height: 100%;
}
</style>
