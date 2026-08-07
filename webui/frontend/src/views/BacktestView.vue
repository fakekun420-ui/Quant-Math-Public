<template>
  <div class="backtest-view">
    <div class="page-header">
      <h1 class="page-title">Backtesting</h1>
      <p class="page-subtitle">
        Ejecuta simulaciones con parámetros personalizados
      </p>
    </div>

    <div class="grid grid-2" style="gap: var(--space-lg)">
      <!-- Backtest Form -->
      <Card title="Configuración del Backtest">
        <form class="backtest-form" @submit.prevent="runBacktest">
          <div class="form-group">
            <label class="form-label">Hipótesis *</label>
            <select v-model="form.hypothesis_id" class="form-select" required>
              <option value="">Seleccionar hipótesis...</option>
              <option
                v-for="hyp in hypotheses"
                :key="hyp.hypothesis_id"
                :value="hyp.hypothesis_id"
              >
                {{ hyp.name }} ({{ hyp.strategy_type }})
              </option>
            </select>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Símbolo *</label>
              <input
                v-model="form.symbol"
                type="text"
                class="form-input"
                placeholder="BTCUSDT"
                required
              />
            </div>
            <div class="form-group">
              <label class="form-label">Timeframe</label>
              <select v-model="form.timeframe" class="form-select">
                <option value="1m">1m</option>
                <option value="5m">5m</option>
                <option value="15m">15m</option>
                <option value="1h">1h</option>
                <option value="4h">4h</option>
                <option value="1d">1d</option>
              </select>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Fecha Inicio *</label>
              <input
                v-model="form.start_date"
                type="date"
                class="form-input"
                required
              />
            </div>
            <div class="form-group">
              <label class="form-label">Fecha Fin *</label>
              <input
                v-model="form.end_date"
                type="date"
                class="form-input"
                required
              />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Capital Inicial</label>
            <input
              v-model.number="form.initial_capital"
              type="number"
              class="form-input"
              min="1000"
              step="1000"
              :placeholder="`Config: ${formatCurrency(effectiveConfig.initial_capital || 100000)}`"
            />
            <p v-if="effectiveConfig.initial_capital" class="form-help">
              Usando capital configurado:
              {{ formatCurrency(effectiveConfig.initial_capital) }}
            </p>
          </div>

          <!-- Effective Config Display -->
          <div
            v-if="Object.keys(effectiveConfig).length > 0"
            class="config-summary"
          >
            <div class="config-summary-header">
              <IconSettings class="icon" />
              <span class="label"
                >Parámetros Efectivos (desde Configuración)</span
              >
              <Button
                variant="ghost"
                size="sm"
                class="config-link"
                @click="navigateToConfig"
              >
                <IconExternalLink class="btn-icon" /> Editar
              </Button>
            </div>
            <div class="config-summary-grid">
              <div class="config-item">
                <span class="config-key">Comisión</span>
                <span class="config-value"
                  >{{ (effectiveConfig.commission || 0.1).toFixed(2) }}%</span
                >
              </div>
              <div class="config-item">
                <span class="config-key">Slippage</span>
                <span class="config-value"
                  >{{ (effectiveConfig.slippage || 0.05).toFixed(2) }}%</span
                >
              </div>
              <div class="config-item">
                <span class="config-key">Stop Loss</span>
                <span class="config-value"
                  >{{ effectiveConfig.stop_loss_type }}:
                  {{ effectiveConfig.stop_loss_value }}%</span
                >
              </div>
              <div class="config-item">
                <span class="config-key">Take Profit</span>
                <span class="config-value"
                  >{{ effectiveConfig.take_profit_type }}:
                  {{ effectiveConfig.take_profit_value }}%</span
                >
              </div>
              <div
                v-if="effectiveConfig.trailing_stop_enabled"
                class="config-item"
              >
                <span class="config-key">Trailing Stop</span>
                <span class="config-value"
                  >{{ effectiveConfig.trailing_stop_distance }}%</span
                >
              </div>
              <div
                v-if="effectiveConfig.break_even_enabled"
                class="config-item"
              >
                <span class="config-key">Break Even</span>
                <span class="config-value"
                  >En {{ effectiveConfig.break_even_trigger }}%</span
                >
              </div>
              <div
                v-if="effectiveConfig.walk_forward_enabled"
                class="config-item"
              >
                <span class="config-key">Walk-Forward</span>
                <span class="config-value"
                  >Train: {{ effectiveConfig.train_window }}, Test:
                  {{ effectiveConfig.test_window }}</span
                >
              </div>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label"
              >Parámetros Personalizados (JSON)
              <span class="optional">(opcional)</span></label
            >
            <textarea
              v-model="form.custom_params_json"
              class="form-textarea"
              rows="6"
              placeholder='{"ema_fast": 12, "ema_slow": 26, "rsi_period": 14}'
            />
            <p class="form-help">
              Sobrescribe parámetros específicos de la estrategia. Estos se
              fusionan con la configuración global.
            </p>
          </div>

          <div class="form-actions">
            <Button
              type="submit"
              variant="primary"
              :loading="running"
              class="w-full"
            >
              <IconPlay class="btn-icon" /> Ejecutar Backtest
            </Button>
            <Button
              v-if="results"
              type="button"
              variant="secondary"
              @click="clearResults"
            >
              <IconRotateCcw class="btn-icon" /> Limpiar
            </Button>
          </div>
        </form>
      </Card>

      <!-- Quick Stats -->
      <Card title="Resumen Rápido">
        <div v-if="results" class="quick-stats">
          <div
            class="stat-card"
            :class="results.total_return_pct >= 0 ? 'positive' : 'negative'"
          >
            <span class="stat-label">Retorno Total</span>
            <span class="stat-value"
              >{{ results.total_return_pct >= 0 ? "+" : ""
              }}{{ results.total_return_pct.toFixed(2) }}%</span
            >
            <span class="stat-sub">{{
              formatCurrency(results.total_return)
            }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">Sharpe Ratio</span>
            <span class="stat-value">{{
              results.sharpe_ratio.toFixed(3)
            }}</span>
          </div>
          <div class="stat-card warning">
            <span class="stat-label">Max Drawdown</span>
            <span class="stat-value"
              >{{ results.max_drawdown.toFixed(2) }}%</span
            >
          </div>
          <div class="stat-card">
            <span class="stat-label">Win Rate</span>
            <span class="stat-value">{{ results.win_rate.toFixed(1) }}%</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">Profit Factor</span>
            <span class="stat-value">{{
              results.profit_factor.toFixed(2)
            }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">Operaciones</span>
            <span class="stat-value">{{ results.num_trades }}</span>
          </div>
        </div>
        <div v-else class="empty-state">
          <IconBarChart2 class="empty-icon" />
          <p>Ejecuta un backtest para ver resultados</p>
        </div>
      </Card>
    </div>

    <!-- Results Charts & Tables -->
    <div v-if="results" class="results-section">
      <div class="grid grid-2" style="margin-bottom: var(--space-lg)">
        <Card title="Curva de Capital (Equity Curve)">
          <EquityCurveChart
            :data="results.equity_curve"
            :initial-capital="form.initial_capital"
          />
        </Card>

        <Card title="Distribución de PnL">
          <PnlDistributionChart :trades="results.trades" />
        </Card>
      </div>

      <Card title="Operaciones">
        <div class="table-container">
          <table class="results-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Símbolo</th>
                <th>Dirección</th>
                <th>Entrada</th>
                <th>Salida</th>
                <th>PnL</th>
                <th>PnL %</th>
                <th>Duración</th>
                <th>Comisión</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(trade, index) in results.trades"
                :key="trade.trade_id"
              >
                <td>{{ index + 1 }}</td>
                <td>{{ trade.symbol }}</td>
                <td>
                  <span class="trade-side" :class="trade.side">{{
                    trade.side.toUpperCase()
                  }}</span>
                </td>
                <td>{{ trade.entry_price.toFixed(2) }}</td>
                <td>{{ trade.exit_price.toFixed(2) }}</td>
                <td :class="trade.pnl >= 0 ? 'positive' : 'negative'">
                  {{ trade.pnl >= 0 ? "+" : "" }}{{ trade.pnl.toFixed(2) }}
                </td>
                <td :class="trade.pnl_pct >= 0 ? 'positive' : 'negative'">
                  {{ trade.pnl_pct >= 0 ? "+" : ""
                  }}{{ trade.pnl_pct.toFixed(2) }}%
                </td>
                <td>{{ formatDuration(trade.hold_duration) }}</td>
                <td>{{ trade.commission.toFixed(4) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>
    </div>

    <!-- Loading Overlay -->
    <div v-if="running" class="loading-overlay">
      <div class="loading-spinner">
        <div class="spinner" />
        <p>Ejecutando backtest...</p>
        <p class="loading-detail">{{ loadingDetail }}</p>
      </div>
    </div>

    <!-- Error Toast -->
    <div v-show="error" class="toast error">
      <IconAlertCircle class="toast-icon" />
      <span>{{ error }}</span>
      <button class="toast-close" @click="error = null">
        <IconX class="icon" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useBacktestStore } from "@/stores/backtest";
import { useConfigStore } from "@/stores/config";
import Card from "@/components/Card.vue";
import Button from "@/components/Button.vue";
import EquityCurveChart from "@/components/charts/EquityCurveChart.vue";
import PnlDistributionChart from "@/components/charts/PnlDistributionChart.vue";
import {
  Play,
  RotateCcw,
  BarChart2,
  AlertCircle,
  X,
  Settings,
  ExternalLink,
} from "lucide-vue-next";

const backtestStore = useBacktestStore();
const configStore = useConfigStore();

const hypotheses = computed(() => backtestStore.hypotheses);
const results = computed(() => backtestStore.results);
const running = computed(() => backtestStore.running);
const loadingDetail = computed(() => backtestStore.loadingDetail);
const configValues = computed(() => backtestStore.configValues);
const error = ref(null);

const form = ref({
  hypothesis_id: "",
  symbol: "BTCUSDT",
  start_date: "",
  end_date: "",
  initial_capital: 100000,
  timeframe: "1h",
  custom_params_json: "{}",
});

// Computed to show effective config values
const effectiveConfig = computed(() => {
  if (!configValues.value.trading) return {};
  return {
    initial_capital: configValues.value.trading.initial_capital,
    commission: configValues.value.exchange?.commission_rate || 0.1,
    slippage: configValues.value.exchange?.slippage_rate || 0.05,
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
    walk_forward_enabled:
      configValues.value.backtesting?.walk_forward_enabled || false,
    train_window: configValues.value.backtesting?.train_window || 252,
    test_window: configValues.value.backtesting?.test_window || 63,
    step_size: configValues.value.backtesting?.step_size || 63,
  };
});

// Set default dates
const today = new Date();
const threeMonthsAgo = new Date();
threeMonthsAgo.setMonth(today.getMonth() - 3);

onMounted(async () => {
  form.value.start_date = threeMonthsAgo.toISOString().split("T")[0];
  form.value.end_date = today.toISOString().split("T")[0];
  await backtestStore.loadHypotheses();
  await backtestStore.loadConfigValues();
});

async function runBacktest() {
  error.value = null;

  let customParams = {};
  try {
    customParams = JSON.parse(form.value.custom_params_json || "{}");
  } catch (e) {
    error.value = "JSON inválido en parámetros personalizados";
    return;
  }

  // Merge with backend config
  const mergedConfig = backtestStore.getMergedConfig(customParams);

  const success = await backtestStore.runBacktest({
    hypothesis_id: form.value.hypothesis_id,
    symbol: form.value.symbol,
    start_date: form.value.start_date,
    end_date: form.value.end_date,
    initial_capital:
      form.value.initial_capital || effectiveConfig.value.initial_capital,
    timeframe: form.value.timeframe,
    custom_params: mergedConfig,
  });

  if (!success) {
    error.value =
      backtestStore.error || "Error desconocido al ejecutar backtest";
  }
}

function clearResults() {
  backtestStore.clearResults();
}

function formatCurrency(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatDuration(hours) {
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `${hours.toFixed(1)}h`;
  return `${(hours / 24).toFixed(1)}d`;
}

function navigateToConfig() {
  window.location.hash = "/config";
}
</script>

<style scoped>
.backtest-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.page-header {
  margin-bottom: var(--space-md);
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 var(--space-xs);
}

.page-subtitle {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin: 0;
}

/* Form */
.backtest-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-md);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.form-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.form-input,
.form-select,
.form-textarea {
  padding: 0.5rem 0.75rem;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 0.875rem;
  transition: all var(--transition-fast);
}

.form-input:focus,
.form-select:focus,
.form-textarea:focus {
  outline: none;
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.2);
}

.form-textarea {
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  resize: vertical;
  min-height: 100px;
}

.form-help {
  font-size: 0.7rem;
  color: var(--text-muted);
  margin: 0;
}

.form-actions {
  display: flex;
  gap: var(--space-sm);
  margin-top: var(--space-sm);
}

.w-full {
  width: 100%;
}

/* Quick Stats */
.quick-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-sm);
}

.stat-card {
  padding: var(--space-md);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-left: 3px solid var(--border-color);
}

.stat-card.positive {
  border-left-color: var(--accent-success);
}

.stat-card.negative {
  border-left-color: var(--accent-danger);
}

.stat-card.warning {
  border-left-color: var(--accent-warning);
}

.stat-label {
  font-size: 0.7rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-value {
  font-family: var(--font-mono);
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-card.positive .stat-value {
  color: var(--accent-success);
}

.stat-card.negative .stat-value {
  color: var(--accent-danger);
}

.stat-card.warning .stat-value {
  color: var(--accent-warning);
}

.stat-sub {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

/* Results Section */
.results-section {
  animation: fadeIn var(--transition-normal);
}

.table-container {
  overflow-x: auto;
}

.results-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.results-table th,
.results-table td {
  padding: var(--space-sm) var(--space-md);
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}

.results-table th {
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.7rem;
  background: var(--bg-tertiary);
  position: sticky;
  top: 0;
}

.results-table tbody tr:hover {
  background: var(--bg-tertiary);
}

.trade-side {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: var(--radius-full);
}

.trade-side.buy {
  background: var(--success-bg);
  color: var(--accent-success);
}

.trade-side.sell {
  background: var(--danger-bg);
  color: var(--accent-danger);
}

.positive {
  color: var(--accent-success);
}

.negative {
  color: var(--accent-danger);
}

/* Loading Overlay */
.loading-overlay {
  position: fixed;
  inset: 0;
  background: rgba(13, 17, 23, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-xl);
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
}

.spinner {
  width: 48px;
  height: 48px;
  border: 4px solid var(--border-color);
  border-top-color: var(--accent-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.loading-spinner p {
  font-size: 1rem;
  color: var(--text-primary);
  margin: 0;
}

.loading-detail {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

/* Config Summary */
.config-summary {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--space-md);
  margin-top: var(--space-sm);
}

.config-summary-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-sm);
  gap: var(--space-sm);
}

.config-summary-header .icon {
  width: 18px;
  height: 18px;
  color: var(--accent-primary);
}

.config-summary-header .label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.config-link {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
}

.config-link .btn-icon {
  width: 14px;
  height: 14px;
}

.config-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: var(--space-sm);
}

.config-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-xs) var(--space-sm);
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
}

.config-key {
  font-size: 0.65rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.config-value {
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* Toast */
.toast {
  position: fixed;
  bottom: var(--space-lg);
  right: var(--space-lg);
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-md) var(--space-lg);
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  font-weight: 500;
  z-index: 1000;
  animation: slideUp var(--transition-normal);
  box-shadow: var(--shadow-lg);
}

.toast.error {
  background: var(--danger-bg);
  color: var(--accent-danger);
  border: 1px solid var(--danger-border);
}

.toast-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.toast-close {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  margin-left: var(--space-sm);
}

.toast-close:hover {
  color: var(--text-primary);
}

.toast-close .icon {
  width: 16px;
  height: 16px;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Responsive */
@media (max-width: 768px) {
  .quick-stats {
    grid-template-columns: 1fr 1fr;
  }

  .form-row {
    grid-template-columns: 1fr;
  }
}
</style>
