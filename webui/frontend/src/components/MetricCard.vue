<template>
  <div
    class="metric-card"
    :class="{
      positive: positive !== false && value >= 0,
      negative: positive === false || value < 0,
    }"
  >
    <div class="metric-header">
      <span class="metric-title">{{ title }}</span>
    </div>
    <div class="metric-body">
      <span class="metric-value" :style="{ color: valueColor }">
        {{ positive !== false && value >= 0 ? "+" : "" }}{{ formattedValue
        }}{{ unit || "" }}
      </span>
      <span v-if="subtitle" class="metric-subtitle">{{ subtitle }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  title: { type: String, required: true },
  value: { type: Number, required: true },
  unit: { type: String, default: "" },
  decimals: { type: Number, default: 2 },
  positive: { type: Boolean, default: true }, // true = higher is better, false = lower is better
  subtitle: { type: String, default: "" },
});

const formattedValue = computed(() => {
  if (props.value === null || props.value === undefined) return "N/A";
  return props.value.toFixed(props.decimals);
});

const valueColor = computed(() => {
  if (props.value === null || props.value === undefined)
    return "var(--text-muted)";
  if (props.positive) {
    return props.value >= 0 ? "var(--accent-success)" : "var(--accent-danger)";
  } else {
    return props.value >= 0 ? "var(--accent-danger)" : "var(--accent-success)";
  }
});
</script>

<style scoped>
.metric-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-md);
  transition: all var(--transition-fast);
}

.metric-card:hover {
  border-color: var(--accent-primary);
}

.metric-header {
  margin-bottom: var(--space-xs);
}

.metric-title {
  font-size: 0.65rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.metric-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.metric-value {
  font-family: var(--font-mono);
  font-size: 1.5rem;
  font-weight: 700;
  line-height: 1;
}

.metric-subtitle {
  font-size: 0.65rem;
  color: var(--text-muted);
  font-family: var(--font-mono);
}
</style>
