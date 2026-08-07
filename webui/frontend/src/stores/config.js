import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { useApi, useConfigApi } from "@/composables/useApi";

export const useConfigStore = defineStore("config", () => {
  // API composable
  const api = useConfigApi();

  // State
  const sections = ref([]);
  const config = ref({});
  const loading = ref(false);
  const saving = ref(false);

  const defaultConfig = {
    trading: {
      initial_capital: 100000.0,
      capital_per_trade: 0.1,
      max_open_positions: 5,
      default_timeframe: "1h",
    },
    risk: {
      risk_per_trade: 2.0,
      max_drawdown_limit: 20.0,
      stop_loss_type: "fixed",
      stop_loss_value: 2.0,
      take_profit_type: "fixed",
      take_profit_value: 4.0,
      trailing_stop_enabled: false,
      trailing_stop_distance: 1.0,
      break_even_enabled: false,
      break_even_trigger: 1.0,
    },
    exchange: {
      exchange_id: "binance",
      symbols: ["BTCUSDT", "ETHUSDT"],
      api_key: "",
      api_secret: "",
      sandbox_mode: true,
      commission_rate: 0.1,
      slippage_rate: 0.05,
    },
    aqde: {
      max_iterations: 10,
      min_sharpe: 1.0,
      min_win_rate: 50.0,
      max_drawdown: 20.0,
      hypothesis_generation_rate: 5,
      validation_threshold: 0.7,
      monte_carlo_iterations: 1000,
      knowledge_base_path: "autonomous_research/data/hypotheses",
    },
    backtesting: {
      initial_capital: 100000.0,
      commission: 0.1,
      slippage: 0.05,
      walk_forward_enabled: false,
      train_window: 252,
      test_window: 63,
      step_size: 63,
    },
  };

  async function loadConfig() {
    loading.value = true;
    try {
      const [sectionsRes, configRes] = await Promise.all([
        api.get("/sections"),
        api.get("/values"),
      ]);

      sections.value = sectionsRes;
      config.value = configRes;
    } catch (error) {
      console.error("Failed to load config:", error);
      // Fallback to defaults
      sections.value = getDefaultSections();
      config.value = { ...defaultConfig };
    } finally {
      loading.value = false;
    }
  }

  function getDefaultSections() {
    return [
      {
        name: "trading",
        display_name: "Trading Parameters",
        parameters: [
          {
            key: "initial_capital",
            label: "Initial Capital",
            type: "number",
            value: 100000.0,
            min: 1000,
          },
          {
            key: "capital_per_trade",
            label: "Capital per Trade",
            type: "number",
            value: 0.1,
            min: 0.01,
            max: 1.0,
            step: 0.01,
          },
          {
            key: "max_open_positions",
            label: "Max Open Positions",
            type: "integer",
            value: 5,
            min: 1,
          },
          {
            key: "default_timeframe",
            label: "Default Timeframe",
            type: "select",
            value: "1h",
            options: ["1m", "5m", "15m", "1h", "4h", "1d"],
          },
        ],
      },
      {
        name: "risk",
        display_name: "Risk Management",
        parameters: [
          {
            key: "risk_per_trade",
            label: "Risk per Trade (%)",
            type: "number",
            value: 2.0,
            min: 0.1,
            max: 10.0,
            step: 0.1,
          },
          {
            key: "max_drawdown_limit",
            label: "Max Drawdown Limit (%)",
            type: "number",
            value: 20.0,
            min: 5.0,
            max: 50.0,
          },
          {
            key: "stop_loss_type",
            label: "Stop Loss Type",
            type: "select",
            value: "fixed",
            options: ["fixed", "atr", "percentage", "trailing"],
          },
          {
            key: "stop_loss_value",
            label: "Stop Loss Value",
            type: "number",
            value: 2.0,
            min: 0.1,
          },
          {
            key: "take_profit_type",
            label: "Take Profit Type",
            type: "select",
            value: "fixed",
            options: ["fixed", "risk_reward", "trailing"],
          },
          {
            key: "take_profit_value",
            label: "Take Profit Value",
            type: "number",
            value: 4.0,
            min: 0.1,
          },
          {
            key: "trailing_stop_enabled",
            label: "Enable Trailing Stop",
            type: "boolean",
            value: false,
          },
          {
            key: "trailing_stop_distance",
            label: "Trailing Stop Distance (%)",
            type: "number",
            value: 1.0,
            min: 0.1,
          },
          {
            key: "break_even_enabled",
            label: "Enable Break Even",
            type: "boolean",
            value: false,
          },
          {
            key: "break_even_trigger",
            label: "Break Even Trigger (%)",
            type: "number",
            value: 1.0,
            min: 0.1,
          },
        ],
      },
      {
        name: "exchange",
        display_name: "Exchange Settings",
        parameters: [
          {
            key: "exchange_id",
            label: "Exchange",
            type: "select",
            value: "binance",
            options: ["binance", "bybit", "coinbase", "kraken"],
          },
          {
            key: "symbols",
            label: "Trading Symbols",
            type: "array",
            value: ["BTCUSDT", "ETHUSDT"],
          },
          { key: "api_key", label: "API Key", type: "password", value: "" },
          {
            key: "api_secret",
            label: "API Secret",
            type: "password",
            value: "",
          },
          {
            key: "sandbox_mode",
            label: "Sandbox Mode",
            type: "boolean",
            value: true,
          },
          {
            key: "commission_rate",
            label: "Commission Rate (%)",
            type: "number",
            value: 0.1,
            min: 0.0,
            step: 0.01,
          },
          {
            key: "slippage_rate",
            label: "Slippage Rate (%)",
            type: "number",
            value: 0.05,
            min: 0.0,
            step: 0.01,
          },
        ],
      },
      {
        name: "aqde",
        display_name: "AQDE Parameters",
        parameters: [
          {
            key: "max_iterations",
            label: "Max Iterations",
            type: "integer",
            value: 10,
            min: 1,
          },
          {
            key: "min_sharpe",
            label: "Min Sharpe Ratio",
            type: "number",
            value: 1.0,
            min: 0.0,
            step: 0.1,
          },
          {
            key: "min_win_rate",
            label: "Min Win Rate (%)",
            type: "number",
            value: 50.0,
            min: 0.0,
            max: 100.0,
          },
          {
            key: "max_drawdown",
            label: "Max Drawdown (%)",
            type: "number",
            value: 20.0,
            min: 0.0,
            max: 100.0,
          },
          {
            key: "hypothesis_generation_rate",
            label: "Hypothesis Generation Rate",
            type: "integer",
            value: 5,
            min: 1,
          },
          {
            key: "validation_threshold",
            label: "Validation Threshold",
            type: "number",
            value: 0.7,
            min: 0.0,
            max: 1.0,
            step: 0.05,
          },
          {
            key: "monte_carlo_iterations",
            label: "Monte Carlo Iterations",
            type: "integer",
            value: 1000,
            min: 100,
          },
          {
            key: "knowledge_base_path",
            label: "Knowledge Base Path",
            type: "text",
            value: "autonomous_research/data/hypotheses",
          },
        ],
      },
      {
        name: "backtesting",
        display_name: "Backtesting Settings",
        parameters: [
          {
            key: "initial_capital",
            label: "Initial Capital",
            type: "number",
            value: 100000.0,
            min: 1000,
          },
          {
            key: "commission",
            label: "Commission (%)",
            type: "number",
            value: 0.1,
            min: 0.0,
            step: 0.01,
          },
          {
            key: "slippage",
            label: "Slippage (%)",
            type: "number",
            value: 0.05,
            min: 0.0,
            step: 0.01,
          },
          {
            key: "walk_forward_enabled",
            label: "Enable Walk-Forward",
            type: "boolean",
            value: false,
          },
          {
            key: "train_window",
            label: "Train Window (days)",
            type: "integer",
            value: 252,
            min: 30,
          },
          {
            key: "test_window",
            label: "Test Window (days)",
            type: "integer",
            value: 63,
            min: 10,
          },
          {
            key: "step_size",
            label: "Step Size (days)",
            type: "integer",
            value: 63,
            min: 10,
          },
        ],
      },
    ];
  }

  async function saveConfig() {
    saving.value = true;
    try {
      const response = await api.post("/values", config.value);
      return response.success;
    } catch (error) {
      console.error("Failed to save config:", error);
      return false;
    } finally {
      saving.value = false;
    }
  }

  function updateValue(section, key, value) {
    if (!config.value[section]) {
      config.value[section] = {};
    }
    config.value[section][key] = value;
  }

  function resetConfig() {
    config.value = { ...defaultConfig };
  }

  return {
    sections,
    config,
    loading,
    saving,
    loadConfig,
    saveConfig,
    updateValue,
    resetConfig,
  };
});
