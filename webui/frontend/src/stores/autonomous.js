import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { useApi, useAutonomousApi } from "@/composables/useApi";
import { useWebSocket } from "@/composables/useWebSocket";

export const useAutonomousStore = defineStore("autonomous", () => {
  // API composable
  const api = useAutonomousApi();

  // State
  const running = ref(false);
  const phase = ref("idle");
  const iteration = ref(0);
  const config = ref({
    symbols: ["BTCUSDT", "ETHUSDT"],
    max_iterations: 10,
    min_sharpe: 1.0,
    min_win_rate: 50.0,
    max_drawdown: 20.0,
  });
  const activeHypotheses = ref(0);
  const progress = ref(0);
  const steps = ref([
    { name: "Generación", status: "pending", count: 0 },
    { name: "Validación", status: "pending", count: 0 },
    { name: "Backtesting", status: "pending", count: 0 },
    { name: "Monte Carlo", status: "pending", count: 0 },
    { name: "Despliegue", status: "pending", count: 0 },
  ]);
  const activity = ref([]);
  const starting = ref(false);

  // WebSocket for real-time updates
  const wsUrl = computed(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}/api/v1/ws/autonomous`;
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

  async function loadStatus() {
    try {
      const data = await api.get("/status");
      running.value = data.is_running;
      phase.value = data.current_phase;
      iteration.value = data.iteration;
      activeHypotheses.value = data.active_hypotheses;
      updateProgress();
    } catch (error) {
      console.error("Failed to load autonomous status:", error);
    }
  }

  async function startAutonomous(params) {
    starting.value = true;
    try {
      config.value = { ...config.value, ...params };
      resetState();

      const response = await api.post("/start", config.value);

      if (response.success) {
        running.value = true;
        phase.value = "hypothesis_generation";
        addActivity(
          "iteration_complete",
          `Ciclo autónomo iniciado con ${config.value.symbols.length} símbolos`,
        );
      }
    } catch (error) {
      console.error("Failed to start autonomous:", error);
      addActivity("error", "Error al iniciar modo autónomo");
    } finally {
      starting.value = false;
    }
  }

  async function stopAutonomous() {
    try {
      await api.post("/stop");
      running.value = false;
      phase.value = "idle";
      addActivity(
        "iteration_complete",
        "Modo autónomo detenido por el usuario",
      );
    } catch (error) {
      console.error("Failed to stop autonomous:", error);
    }
  }

  function handleWebSocketMessage(message) {
    switch (message.type) {
      case "autonomous_iteration_start":
        iteration.value = message.data.iteration;
        phase.value = "hypothesis_generation";
        updateSteps();
        addActivity(
          "iteration_complete",
          `Iniciando iteración ${message.data.iteration} de ${message.data.max_iterations}`,
        );
        break;

      case "hypothesis_generated":
        steps.value[0].count++;
        steps.value[0].status = "in_progress";
        addActivity(
          "hypothesis_generated",
          `Hipótesis generada para ${message.data.symbol}`,
          message.data,
        );
        break;

      case "autonomous_iteration_complete":
        updateProgress();
        updateSteps();
        addActivity(
          "iteration_complete",
          `Iteración ${message.data.iteration} completada - ${message.data.hypotheses_tested} hipótesis probadas`,
          message.data,
        );
        break;

      case "autonomous_completed":
        running.value = false;
        phase.value = "completed";
        progress.value = 100;
        steps.value.forEach((s) => {
          s.status = "completed";
        });
        addActivity(
          "iteration_complete",
          `Ciclo autónomo completado: ${message.data.total_iterations} iteraciones`,
        );
        break;

      case "autonomous_error":
        running.value = false;
        phase.value = "error";
        addActivity("error", `Error: ${message.data.error}`);
        break;

      case "autonomous_stopped":
        running.value = false;
        phase.value = "idle";
        addActivity("iteration_complete", "Modo autónomo detenido");
        break;
    }
  }

  function updateProgress() {
    if (config.value.max_iterations > 0) {
      progress.value = (iteration.value / config.value.max_iterations) * 100;
    }
  }

  function updateSteps() {
    const phaseOrder = [
      "hypothesis_generation",
      "validation",
      "backtesting",
      "monte_carlo_testing",
      "deployment",
    ];
    const currentPhaseIndex = phaseOrder.indexOf(phase.value);

    steps.value.forEach((step, index) => {
      if (index < currentPhaseIndex) {
        step.status = "completed";
      } else if (index === currentPhaseIndex && running.value) {
        step.status = "in_progress";
      } else {
        step.status = "pending";
      }
    });
  }

  function addActivity(type, message, data = {}) {
    activity.value = [
      {
        type,
        message,
        timestamp: new Date().toISOString(),
        data,
      },
      ...activity.value,
    ].slice(0, 100);
  }

  function resetState() {
    iteration.value = 0;
    phase.value = "hypothesis_generation";
    progress.value = 0;
    steps.value.forEach((s) => {
      s.status = "pending";
      s.count = 0;
    });
    activity.value = [];
    activeHypotheses.value = 0;
  }

  function connect() {
    connectWS();
  }

  function disconnect() {
    disconnectWS();
  }

  return {
    running,
    phase,
    iteration,
    config,
    activeHypotheses,
    progress,
    steps,
    activity,
    starting,
    wsConnected,
    loadStatus,
    startAutonomous,
    stopAutonomous,
    handleWebSocketMessage,
    connect,
    disconnect,
  };
});
