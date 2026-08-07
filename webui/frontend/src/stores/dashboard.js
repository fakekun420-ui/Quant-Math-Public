import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { useApi, useDashboardApi } from "@/composables/useApi";
import { useWebSocket } from "@/composables/useWebSocket";

export const useDashboardStore = defineStore("dashboard", () => {
  // API composable
  const api = useDashboardApi();

  // State
  const health = ref(null);
  const aqde = ref(null);
  const trading = ref(null);
  const hypotheses = ref([]);
  const events = ref([]);
  const activeStrategies = ref([]);

  // WebSocket for real-time updates
  const wsUrl = computed(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}/api/v1/ws`;
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

  // Computed
  const isHealthy = computed(() => health.value?.status === "healthy");
  const isAutonomousRunning = computed(() => aqde.value?.is_running || false);

  // Active strategies computed from trading data or separate API
  const activeStrategiesList = computed(() => activeStrategies.value);

  // Actions
  async function fetchAll() {
    try {
      const [
        healthRes,
        aqdeRes,
        tradingRes,
        hypothesesRes,
        eventsRes,
        strategiesRes,
      ] = await Promise.all([
        api.get("/health"),
        api.get("/aqde"),
        api.get("/trading"),
        api.get("/hypotheses"),
        api.get("/events"),
        api.get("/active-strategies"),
      ]);

      health.value = healthRes;
      aqde.value = aqdeRes;
      trading.value = tradingRes;
      hypotheses.value = hypothesesRes;
      events.value = eventsRes.events || [];
      activeStrategies.value = strategiesRes || [];
    } catch (error) {
      console.error("Failed to fetch dashboard data:", error);
    }
  }

  async function stopStrategy(strategyId) {
    try {
      await api.post(`/trading/stop-strategy/${strategyId}`);
      // Refresh strategies after stopping
      const strategiesRes = await api.get("/active-strategies");
      activeStrategies.value = strategiesRes || [];
    } catch (error) {
      console.error("Failed to stop strategy:", error);
    }
  }

  function handleWebSocketMessage(message) {
    switch (message.type) {
      case "init":
        if (message.data) {
          health.value = message.data.health;
          aqde.value = message.data.aqde;
          trading.value = message.data.trading;
          hypotheses.value = message.data.hypotheses;
          events.value = message.data.events;
        }
        break;
      case "health_update":
        health.value = message.data;
        break;
      case "aqde_update":
        aqde.value = { ...aqde.value, ...message.data };
        break;
      case "trading_update":
        trading.value = { ...trading.value, ...message.data };
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
      case "event":
        events.value = [message.data, ...events.value].slice(0, 100);
        break;
      case "autonomous_iteration_start":
      case "autonomous_iteration_complete":
      case "autonomous_completed":
      case "autonomous_error":
      case "autonomous_stopped":
        aqde.value = { ...aqde.value, ...message.data };
        break;
      case "backtest_completed":
        // Refresh trading data
        fetchAll();
        break;
      case "config_updated":
        console.log("Config updated:", message.data);
        break;
    }
  }

  return {
    health,
    aqde,
    trading,
    hypotheses,
    events,
    activeStrategies,
    wsConnected,
    isHealthy,
    isAutonomousRunning,
    fetchAll,
    stopStrategy,
    connectWebSocket: connectWS,
    disconnectWebSocket: disconnectWS,
  };
});
