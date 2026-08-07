<template>
  <div class="strategy-detail">
    <div class="detail-section">
      <h4 class="section-title">Información General</h4>
      <div class="detail-grid">
        <div class="detail-item">
          <span class="detail-label">Nombre</span>
          <span class="detail-value">{{ strategy.name }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">Símbolo</span>
          <span class="detail-value">{{ strategy.symbol }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">Timeframe</span>
          <span class="detail-value">{{ strategy.timeframe }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">Estado</span>
          <span class="detail-value">
            <span class="status-badge" :class="strategy.status">{{
              statusLabels[strategy.status]
            }}</span>
          </span>
        </div>
        <div class="detail-item">
          <span class="detail-label">ID</span>
          <span class="detail-value font-mono">{{ strategy.id }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">Creada</span>
          <span class="detail-value">{{
            formatDate(strategy.created_at)
          }}</span>
        </div>
      </div>
    </div>

    <div class="detail-section">
      <h4 class="section-title">Métricas de Rendimiento</h4>
      <div class="metrics-grid">
        <MetricCard
          title="P&L Total"
          :value="strategy.pnl"
          :unit="'%'"
          :positive="strategy.pnl >= 0"
          :subtitle="`No realizado: ${strategy.unrealized_pnl >= 0 ? '+' : ''}${strategy.unrealized_pnl.toFixed(2)}%`"
        />
        <MetricCard
          title="Sharpe Ratio"
          :value="strategy.sharpe"
          :decimals="2"
          :subtitle="`Sortino: ${strategy.sortino?.toFixed(2) || 'N/A'}`"
        />
        <MetricCard
          title="Win Rate"
          :value="strategy.win_rate"
          :unit="'%'"
          :decimals="1"
          :subtitle="`${strategy.total_trades || 0} trades totales`"
        />
        <MetricCard
          title="Profit Factor"
          :value="strategy.profit_factor"
          :decimals="2"
          :subtitle="`Avg Trade: ${strategy.avg_trade?.toFixed(2) || 'N/A'}%`"
        />
        <MetricCard
          title="Max Drawdown"
          :value="strategy.max_drawdown"
          :unit="'%'"
          :decimals="1"
          :positive="false"
          :subtitle="`Actual: ${strategy.current_drawdown?.toFixed(1) || 'N/A'}%`"
        />
        <MetricCard
          title="Exposición"
          :value="strategy.exposure"
          :unit="'%'"
          :decimals="1"
          :subtitle="`Leverage: ${strategy.leverage || 1}x`"
        />
      </div>
    </div>

    <div class="detail-section">
      <h4 class="section-title">Curva de Capital</h4>
      <div v-if="strategy.equity_curve?.length > 0" class="equity-chart">
        <EquityChart
          :data="strategy.equity_curve"
          :color="strategy.pnl >= 0 ? 'success' : 'danger'"
        />
      </div>
      <div v-else class="no-data">
        <p>No hay datos de equity curve disponibles</p>
      </div>
    </div>

    <div v-if="strategy.trades?.length > 0" class="detail-section">
      <h4 class="section-title">Últimas Operaciones</h4>
      <div class="trades-table">
        <table>
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Lado</th>
              <th>Entrada</th>
              <th>Salida</th>
              <th>P&L</th>
              <th>Duración</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="trade in strategy.trades.slice(-10).reverse()"
              :key="trade.id"
            >
              <td>{{ formatDateTime(trade.timestamp) }}</td>
              <td>
                <span class="trade-side" :class="trade.side">{{
                  trade.side
                }}</span>
              </td>
              <td>{{ trade.entry_price }}</td>
              <td>{{ trade.exit_price }}</td>
              <td
                class="trade-pnl"
                :class="{ positive: trade.pnl >= 0, negative: trade.pnl < 0 }"
              >
                {{ trade.pnl >= 0 ? "+" : "" }}{{ trade.pnl.toFixed(2) }}%
              </td>
              <td>{{ formatDuration(trade.duration) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="strategy.parameters" class="detail-section">
      <h4 class="section-title">Parámetros de la Estrategia</h4>
      <div class="params-grid">
        <div
          v-for="(value, key) in strategy.parameters"
          :key="key"
          class="param-item"
        >
          <span class="param-label">{{ formatParamKey(key) }}</span>
          <span class="param-value">{{ value }}</span>
        </div>
      </div>
    </div>

    <div class="detail-actions">
      <Button
        variant="danger"
        :disabled="strategy.status !== 'running'"
        @click="$emit('stop')"
      >
        <IconSquare class="btn-icon" /> Detener Estrategia
      </Button>
      <Button variant="secondary" @click="$emit('view-backtest')">
        <IconBarChart2 class="btn-icon" /> Ver Backtest
      </Button>
      <Button variant="ghost" @click="$emit('clone')">
        <IconCopy class="btn-icon" /> Clonar
      </Button>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import MetricCard from "@/components/MetricCard.vue";
import EquityChart from "@/components/EquityChart.vue";
import { Square, BarChart2, Copy } from "lucide-vue-next";
import { format } from "date-fns";

const props = defineProps({
  strategy: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(["stop", "view-backtest", "clone"]);

const statusLabels = {
  running: "Ejecutándose",
  paused: "Pausada",
  stopped: "Detenida",
  error: "Error",
  pending: "Pendiente",
};

function formatDate(isoString) {
  if (!isoString) return "N/A";
  return format(new Date(isoString), "dd/MM/yyyy HH:mm");
}

function formatDateTime(isoString) {
  if (!isoString) return "N/A";
  return format(new Date(isoString), "dd/MM HH:mm:ss");
}

function formatDuration(ms) {
  if (!ms) return "N/A";
  const hours = Math.floor(ms / 3600000);
  const mins = Math.floor((ms % 3600000) / 60000);
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

function formatParamKey(key) {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
</script>

<style scoped>
.strategy-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.detail-section {
  background: var(--bg-tertiary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  padding: var(--space-lg);
}

.section-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 var(--space-lg);
  padding-bottom: var(--space-sm);
  border-bottom: 1px solid var(--border-color);
}

/* Detail Grid */
.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-md);
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px.;
}

.detail-label {
  font-size: 0.65rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.detail-value {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary);
}

.detail-value.font-mono {
  font-family: var(--font-mono);
  font-size: 0.75rem;
}

/* Metrics Grid */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-md);
}

/* Equity Chart */
.equity-chart {
  height: 200px;
}

.no-data {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 150px;
  color: var(--text-muted);
}

/* Trades Table */
.trades-table {
  overflow-x: auto;
}

.trades-table table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.75rem;
}

.trades-table th,
.trades-table td {
  padding: var(--space-sm) var(--space-md);
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}

.trades-table th {
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.65rem;
  background: var(--bg-secondary);
  position: sticky;
  top: 0;
}

.trades-table td {
  color: var(--text-primary);
}

.trade-side {
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.65rem;
  padding: 2px 6px;
  border-radius: var(--radius-full);
}

.trade-side.long {
  background: var(--success-bg);
  color: var(--accent-success);
}
.trade-side.short {
  background: var(--danger-bg);
  color: var(--accent-danger);
}

.trade-pnl.positive {
  color: var(--accent-success);
  font-weight: 600;
}
.trade-pnl.negative {
  color: var(--accent-danger);
  font-weight: 600;
}

/* Params Grid */
.params-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-sm);
}

.param-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.param-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.param-value {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* Actions */
.detail-actions {
  display: flex;
  gap: var(--space-sm);
  justify-content: flex-end;
  padding-top: var(--space-md);
  border-top: 1px solid var(--border-color);
}

/* Responsive */
@media (max-width: 768px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .metrics-grid {
    grid-template-columns: 1fr 1fr;
  }

  .detail-actions {
    flex-direction: column;
  }

  .detail-actions button {
    width: 100%;
  }
}
</style>
