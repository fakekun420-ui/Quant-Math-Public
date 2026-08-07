import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { useApi, useBacktestApi, useConfigApi } from "@/composables/useApi";

export const useBacktestStore = defineStore("backtest", () => {
  // API composables
  const api = useBacktestApi();
  const configApi = useConfigApi();

  // State
  const hypotheses = ref([]);
  const results = ref(null);
  const running = ref(false);
  const loadingDetail = ref("");
  const error = ref(null);
  const configValues = ref({});

  async function loadHypotheses() {
    try {
      hypotheses.value = await api.get("/hypotheses");
    } catch (err) {
      console.error("Failed to load hypotheses:", err);
    }
  }

  async function loadConfigValues() {
    try {
      configValues.value = await configApi.get("/values");
    } catch (err) {
      console.error("Failed to load config values:", err);
    }
  }

  async function runBacktest(params) {
    running.value = true;
    loadingDetail.value = "Obteniendo datos de mercado...";
    error.value = null;
    results.value = null;

    try {
      const response = await api.post("/run", params, {
        timeout: 300000, // 5 minutes
      });

      if (response.success) {
        results.value = response.results;
        loadingDetail.value = "Completado";
        return true;
      } else {
        error.value = response.error || "Error en backtest";
        return false;
      }
    } catch (err) {
      error.value =
        err.response?.data?.detail || err.message || "Error de conexión";
      return false;
    } finally {
      running.value = false;
      loadingDetail.value = "";
    }
  }

  function clearResults() {
    results.value = null;
    error.value = null;
  }

  // Get merged config: backend config + custom overrides
  function getMergedConfig(customParams = {}) {
    const backendConfig = {
      // Trading config
      initial_capital: configValues.value.trading?.initial_capital || 100000,
      commission: configValues.value.exchange?.commission_rate || 0.1,
      slippage: configValues.value.exchange?.slippage_rate || 0.05,
      // Risk config
      stop_loss_type: configValues.value.risk?.stop_loss_type || "fixed",
      stop_loss_value: configValues.value.risk?.stop_loss_value || 2.0,
      take_profit_type: configValues.value.risk?.take_profit_type || "fixed",
      take_profit_value: configValues.value.risk?.take_profit_value || 4.0,
      trailing_stop_enabled:
        configValues.value.risk?.trailing_stop_enabled || false,
      trailing_stop_distance:
        configValues.value.risk?.trailing_stop_distance || 1.0,
      break_even_enabled: configValues.value.risk?.break_even_enabled || false,
      break_even_trigger: configValues.value.risk?.break_even_trigger || 1.0,
      // Backtesting config
      walk_forward_enabled:
        configValues.value.backtesting?.walk_forward_enabled || false,
      train_window: configValues.value.backtesting?.train_window || 252,
      test_window: configValues.value.backtesting?.test_window || 63,
      step_size: configValues.value.backtesting?.step_size || 63,
    };

    // Merge custom params (they override backend config)
    return { ...backendConfig, ...customParams };
  }

  return {
    hypotheses,
    results,
    running,
    loadingDetail,
    error,
    configValues,
    loadHypotheses,
    loadConfigValues,
    runBacktest,
    clearResults,
    getMergedConfig,
  };
});
