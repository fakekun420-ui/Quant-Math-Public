<template>
  <div ref="chartRef" class="chart-container" style="height: 300px"></div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from "vue";
import { Chart, registerables } from "chart.js";
import "chartjs-adapter-date-fns";

Chart.register(...registerables);

const props = defineProps({
  data: {
    type: Array,
    required: true,
  },
  initialCapital: {
    type: Number,
    default: 100000,
  },
});

const chartRef = ref(null);
let chart = null;

function createChart() {
  if (!chartRef.value || !props.data.length) return;

  const ctx = chartRef.value.getContext("2d");

  // Process equity curve data
  const labels = props.data.map(([timestamp]) => new Date(timestamp * 1000));
  const values = props.data.map(([, value]) => value);

  const gradient = ctx.createLinearGradient(0, 0, 0, 300);
  gradient.addColorStop(0, "rgba(88, 166, 255, 0.4)");
  gradient.addColorStop(1, "rgba(88, 166, 255, 0)");

  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Equity",
          data: values,
          borderColor: "#58a6ff",
          backgroundColor: gradient,
          borderWidth: 2,
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          pointHoverRadius: 4,
        },
        {
          label: "Initial Capital",
          data: new Array(values.length).fill(props.initialCapital),
          borderColor: "rgba(139, 148, 158, 0.5)",
          borderWidth: 1,
          borderDash: [5, 5],
          fill: false,
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: "index",
      },
      plugins: {
        legend: {
          display: false,
        },
        tooltip: {
          backgroundColor: "#161b22",
          borderColor: "#30363d",
          borderWidth: 1,
          padding: 12,
          titleFont: { size: 13 },
          bodyFont: { size: 12, family: "JetBrains Mono" },
          callbacks: {
            label: (context) => {
              const value = context.parsed.y;
              const pct = (
                ((value - props.initialCapital) / props.initialCapital) *
                100
              ).toFixed(2);
              return `${context.dataset.label}: $${value.toLocaleString()} (${pct >= 0 ? "+" : ""}${pct}%)`;
            },
          },
        },
      },
      scales: {
        x: {
          type: "time",
          time: {
            unit: "day",
            displayFormats: { day: "MMM dd" },
          },
          grid: { color: "rgba(48, 54, 61, 0.5)" },
          ticks: { color: "#8b949e", font: { size: 11 } },
        },
        y: {
          grid: { color: "rgba(48, 54, 61, 0.5)" },
          ticks: {
            color: "#8b949e",
            font: { size: 11, family: "JetBrains Mono" },
            callback: (value) => "$" + value.toLocaleString(),
          },
        },
      },
    },
  });
}

function updateChart() {
  if (!chart) return;

  const labels = props.data.map(([timestamp]) => new Date(timestamp * 1000));
  const values = props.data.map(([, value]) => value);

  chart.data.labels = labels;
  chart.data.datasets[0].data = values;
  chart.data.datasets[1].data = new Array(values.length).fill(
    props.initialCapital,
  );
  chart.update("none");
}

onMounted(() => {
  nextTick(() => createChart());
});

watch(
  () => props.data,
  () => {
    if (chart) {
      updateChart();
    } else {
      nextTick(() => createChart());
    }
  },
  { deep: true },
);

watch(
  () => props.initialCapital,
  () => {
    if (chart) updateChart();
  },
);
</script>

<style scoped>
.chart-container {
  width: 100%;
  height: 100%;
}
</style>
