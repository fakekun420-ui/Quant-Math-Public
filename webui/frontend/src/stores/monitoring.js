import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { useApi, useMonitoringApi } from "@/composables/useApi";
import { useWebSocket } from "@/composables/useWebSocket";

export const useMonitoringStore = defineStore("monitoring", () => {
  // API composable
  const api = useMonitoringApi();

  // State
  const hypotheses = ref([]);
  const strategies = ref({});
  const simulations = ref({});
  const trades = ref([]);
  const flow = ref({});
  const loading = ref(false);

  // WebSocket for real-time updates
  const wsUrl = computed(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}/api/v1/ws/monitoring`;
  });

  const {
    connected: wsConnected,
    connect: connectWS,
    disconnect: disconnectWS,
  } = useWebSocket(wsUrl, {
    autoReconnect: true,
    reconnectInterval: 5000,
    onMessage: handleWebSocketMessage,
  });

  async function loadAll() {
    loading.value = true;
    try {
      const [hypRes, stratRes, simRes, tradeRes, flowRes] = await Promise.all([
        api.get("/monitoring/hypotheses"),
        api.get("/monitoring/strategies"),
        api.get("/monitoring/simulations"),
        api.get("/monitoring/trades"),
        api.get("/monitoring/flow"),
      ]);

      hypotheses.value = hypRes;
      strategies.value = stratRes;
      simulations.value = simRes;
      trades.value = tradeRes;
      flow.value = flowRes;
    } catch (error) {
      console.error("Failed to load monitoring data:", error);
    } finally {
      loading.value = false;
    }
  }

  function handleWebSocketMessage(message) {
    switch (message.type) {
      case "init":
        if (message.data) {
          hypotheses.value = message.data.hypotheses || [];
          strategies.value = message.data.strategies || {};
          simulations.value = message.data.simulations || {};
          trades.value = message.data.trades || [];
          flow.value = message.data.flow || {};
        }
        break;
      case "hypothesis_created":
      case "hypothesis_updated":
        hypotheses.value = [
          message.data,
          ...hypotheses.value.filter(
            (h) => h.hypothesis_id !== message.data.hypothesis_id,
          ),
        ];
        break;
      case "strategy_stage_changed":
        // Update strategy in appropriate stage
        if (strategies.value[message.data.old_stage]) {
          strategies.value[message.data.old_stage] = strategies.value[
            message.data.old_stage
          ].filter((s) => s.strategy_id !== message.data.strategy_id);
        }
        if (!strategies.value[message.data.new_stage]) {
          strategies.value[message.data.new_stage] = [];
        }
        strategies.value[message.data.new_stage].push(message.data.strategy);
        break;
      case "simulation_progress":
        if (simulations.value[message.data.type]) {
          const idx = simulations.value[message.data.type].findIndex(
            (s) => s.id === message.data.id,
          );
          if (idx >= 0) {
            simulations.value[message.data.type][idx] = {
              ...simulations.value[message.data.type][idx],
              ...message.data,
            };
          }
        }
        break;
      case "trade_executed":
        trades.value = [message.data, ...trades.value].slice(0, 100);
        break;
      case "flow_update":
        flow.value = { ...flow.value, ...message.data };
        break;
    }
  }

  function connect() {
    connectWS();
  }

  function disconnect() {
    disconnectWS();
  }

  return {
    hypotheses,
    strategies,
    simulations,
    trades,
    flow,
    loading,
    wsConnected,
    loadAll,
    connect,
    disconnect,
  };
});
