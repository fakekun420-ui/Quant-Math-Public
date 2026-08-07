import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { useApi, useTradingApi } from "@/composables/useApi";

export const useTradingStore = defineStore("trading", () => {
  // API composable
  const api = useTradingApi();

  // State
  const status = ref({
    enabled: false,
    exchange: "bybit",
    sandbox_mode: true,
    paper_balance: 100000,
    real_balance: 0,
    open_orders: 0,
    today_pnl: 0,
  });
  const positions = ref([]);
  const riskLimits = ref({
    max_position_pct: 10,
    max_daily_drawdown: 5,
    max_trades_per_day: 20,
    global_stop_loss: 10,
  });
  const enabling = ref(false);
  const error = ref(null);

  async function loadStatus() {
    try {
      status.value = await api.get("/status");

      if (status.value.enabled) {
        const [posRes, riskRes] = await Promise.all([
          api.get("/positions"),
          api.get("/risk-limits"),
        ]);
        positions.value = posRes;
        riskLimits.value = riskRes;
      }
    } catch (err) {
      console.error("Failed to load trading status:", err);
    }
  }

  async function enableTrading(params) {
    enabling.value = true;
    error.value = null;
    try {
      const response = await api.post("/enable", params);
      if (response.success) {
        await loadStatus();
        return true;
      } else {
        error.value = response.error;
        return false;
      }
    } catch (err) {
      error.value = err.response?.data?.detail || err.message;
      return false;
    } finally {
      enabling.value = false;
    }
  }

  async function disableTrading() {
    try {
      await api.post("/disable");
      await loadStatus();
    } catch (err) {
      console.error("Failed to disable trading:", err);
    }
  }

  async function emergencyStop() {
    try {
      await api.post("/emergency-stop");
      await loadStatus();
    } catch (err) {
      console.error("Emergency stop failed:", err);
      throw err;
    }
  }

  async function closePosition(symbol) {
    try {
      await api.post("/close-position", { symbol });
      await loadStatus();
    } catch (err) {
      console.error("Close position failed:", err);
      throw err;
    }
  }

  async function updateRiskLimits(limits) {
    try {
      const response = await api.put("/risk-limits", limits);
      if (response.success) {
        riskLimits.value = limits;
      }
    } catch (err) {
      console.error("Failed to update risk limits:", err);
    }
  }

  return {
    status,
    positions,
    riskLimits,
    enabling,
    error,
    loadStatus,
    enableTrading,
    disableTrading,
    emergencyStop,
    closePosition,
    updateRiskLimits,
  };
});
