<template>
  <div class="connection-status" :class="statusClass">
    <div class="connection-dot" :class="statusClass" />
    <span class="connection-text">{{ statusText }}</span>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, watch } from "vue";
import { useRoute } from "vue-router";
import { useDashboardStore } from "@/stores/dashboard";
import { useMonitoringStore } from "@/stores/monitoring";
import { useAutonomousStore } from "@/stores/autonomous";

const route = useRoute();
const dashboardStore = useDashboardStore();
const monitoringStore = useMonitoringStore();
const autonomousStore = useAutonomousStore();

// Map routes to their respective stores
const routeStoreMap = {
  "/": dashboardStore,
  "/dashboard": dashboardStore,
  "/monitoring": monitoringStore,
  "/autonomous": autonomousStore,
  "/backtest": dashboardStore, // Backtest uses dashboard WS for now
  "/trading": dashboardStore,
  "/config": dashboardStore,
};

const currentStore = computed(() => {
  // Find the most specific matching route
  const matchedRoute = Object.keys(routeStoreMap)
    .sort((a, b) => b.length - a.length) // longest first
    .find((r) => route.path.startsWith(r));

  return routeStoreMap[matchedRoute] || dashboardStore;
});

const statusClass = computed(() =>
  currentStore.value.wsConnected ? "connected" : "disconnected",
);
const statusText = computed(() =>
  currentStore.value.wsConnected ? "Conectado" : "Desconectado",
);

onMounted(() => {
  currentStore.value.connectWebSocket();

  // Watch for route changes to connect/disconnect appropriately
  watch(
    () => route.path,
    (newPath, oldPath) => {
      const oldStore =
        routeStoreMap[
          Object.keys(routeStoreMap)
            .sort((a, b) => b.length - a.length)
            .find((r) => oldPath.startsWith(r))
        ];
      const newStore = currentStore.value;

      if (oldStore && oldStore !== newStore) {
        oldStore.disconnectWebSocket();
      }
      newStore.connectWebSocket();
    },
  );
});

onUnmounted(() => {
  // Don't disconnect on unmount - let the route watcher handle it
  // This component stays mounted in the header
});
</script>

<style scoped>
.connection-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0.75rem;
  border-radius: var(--radius-full);
  font-size: 0.75rem;
  font-weight: 500;
}

.connection-status.connected {
  background: var(--success-bg);
  color: var(--accent-success);
  border: 1px solid var(--success-border);
}

.connection-status.disconnected {
  background: var(--danger-bg);
  color: var(--accent-danger);
  border: 1px solid var(--danger-border);
}

.connection-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
}

.connection-dot.connected {
  background: var(--accent-success);
  box-shadow: 0 0 8px var(--accent-success);
  animation: pulse 2s infinite;
}

.connection-dot.disconnected {
  background: var(--accent-danger);
}
</style>
