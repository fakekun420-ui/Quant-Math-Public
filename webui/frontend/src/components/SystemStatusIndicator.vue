<template>
  <div class="status-indicator" :class="statusClass">
    <div class="status-dot" :class="statusClass" />
    <span class="status-text">{{ statusText }}</span>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useDashboardStore } from "@/stores/dashboard";

const store = useDashboardStore();

const statusClass = computed(() => {
  if (!store.health) return "unknown";
  if (store.health.status === "healthy") return "healthy";
  return "warning";
});

const statusText = computed(() => {
  if (!store.health) return "Cargando...";
  return store.health.status === "healthy"
    ? "Sistema Saludable"
    : "Advertencia";
});
</script>

<style scoped>
.status-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0.75rem;
  border-radius: var(--radius-full);
  font-size: 0.75rem;
  font-weight: 500;
}

.status-indicator.healthy {
  background: var(--success-bg);
  color: var(--accent-success);
  border: 1px solid var(--success-border);
}

.status-indicator.warning {
  background: var(--warning-bg);
  color: var(--accent-warning);
  border: 1px solid var(--warning-border);
}

.status-indicator.unknown {
  background: var(--info-bg);
  color: var(--accent-info);
  border: 1px solid var(--info-border);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  animation: pulse 2s infinite;
}

.status-dot.healthy {
  background: var(--accent-success);
  box-shadow: 0 0 8px var(--accent-success);
}

.status-dot.warning {
  background: var(--accent-warning);
  box-shadow: 0 0 8px var(--accent-warning);
}

.status-dot.unknown {
  background: var(--accent-info);
}
</style>
