<template>
  <div class="active-strategies">
    <Card title="Estrategias Activas">
      <template #header>
        <div class="card-header-flex">
          <h3 class="card-title">Estrategias Activas</h3>
          <div class="strategies-summary">
            <span class="summary-item">
              <span class="summary-value">{{ activeCount }}</span>
              <span class="summary-label">Activas</span>
            </span>
            <span class="summary-item">
              <span class="summary-value"
                >{{ totalPnL >= 0 ? "+" : "" }}{{ totalPnL.toFixed(2) }}%</span
              >
              <span class="summary-label">P&L Total</span>
            </span>
            <span class="summary-item">
              <span class="summary-value">{{ avgSharpe.toFixed(2) }}</span>
              <span class="summary-label">Sharpe Prom.</span>
            </span>
          </div>
        </div>
      </template>

      <!-- Strategies Grid -->
      <div v-if="strategies.length > 0" class="strategies-grid">
        <div
          v-for="strategy in strategies"
          :key="strategy.id"
          class="strategy-card"
          :class="strategy.status"
        >
          <div class="strategy-header">
            <div class="strategy-info">
              <h4 class="strategy-name">{{ strategy.name }}</h4>
              <div class="strategy-meta">
                <span class="strategy-symbol">{{ strategy.symbol }}</span>
                <span class="strategy-timeframe">{{ strategy.timeframe }}</span>
                <span class="strategy-status-badge" :class="strategy.status">{{
                  statusLabels[strategy.status]
                }}</span>
              </div>
            </div>
            <div class="strategy-actions">
              <Button
                variant="ghost"
                size="sm"
                title="Ver detalles"
                @click="viewStrategy(strategy)"
              >
                <IconEye class="btn-icon" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                :disabled="strategy.status !== 'running'"
                title="Detener"
                @click="stopStrategy(strategy)"
              >
                <IconSquare class="btn-icon" />
              </Button>
            </div>
          </div>

          <!-- Key Metrics -->
          <div class="strategy-metrics">
            <div
              class="metric-group pnl"
              :class="{
                positive: strategy.pnl >= 0,
                negative: strategy.pnl < 0,
              }"
            >
              <span class="metric-label">P&L</span>
              <span class="metric-value"
                >{{ strategy.pnl >= 0 ? "+" : ""
                }}{{ strategy.pnl.toFixed(2) }}%</span
              >
              <span class="metric-sub"
                >{{ strategy.unrealized_pnl >= 0 ? "+" : ""
                }}{{ strategy.unrealized_pnl.toFixed(2) }}% unrealizado</span
              >
            </div>

            <div class="metric-group">
              <span class="metric-label">Sharpe</span>
              <span class="metric-value">{{
                strategy.sharpe?.toFixed(2) || "N/A"
              }}</span>
              <span class="metric-sub"
                >Sortino: {{ strategy.sortino?.toFixed(2) || "N/A" }}</span
              >
            </div>

            <div class="metric-group">
              <span class="metric-label">Win Rate</span>
              <span class="metric-value"
                >{{ strategy.win_rate?.toFixed(1) || "N/A" }}%</span
              >
              <span class="metric-sub"
                >{{ strategy.total_trades || 0 }} trades</span
              >
            </div>

            <div class="metric-group">
              <span class="metric-label">Max DD</span>
              <span class="metric-value"
                >{{ strategy.max_drawdown?.toFixed(1) || "N/A" }}%</span
              >
              <span class="metric-sub"
                >Actual:
                {{ strategy.current_drawdown?.toFixed(1) || "N/A" }}%</span
              >
            </div>

            <div class="metric-group">
              <span class="metric-label">Profit Factor</span>
              <span class="metric-value">{{
                strategy.profit_factor?.toFixed(2) || "N/A"
              }}</span>
              <span class="metric-sub"
                >Avg Trade: {{ strategy.avg_trade?.toFixed(2) || "N/A" }}%</span
              >
            </div>

            <div class="metric-group">
              <span class="metric-label">Exposición</span>
              <span class="metric-value"
                >{{ strategy.exposure?.toFixed(1) || "N/A" }}%</span
              >
              <span class="metric-sub"
                >Leverage: {{ strategy.leverage || 1 }}x</span
              >
            </div>
          </div>

          <!-- Mini Chart -->
          <div v-if="strategy.equity_curve?.length > 0" class="strategy-chart">
            <MiniChart
              :data="strategy.equity_curve"
              :color="strategy.pnl >= 0 ? 'success' : 'danger'"
            />
          </div>

          <!-- Position Info -->
          <div v-if="strategy.positions?.length > 0" class="strategy-positions">
            <div
              v-for="pos in strategy.positions"
              :key="pos.id"
              class="position-row"
            >
              <span class="pos-side" :class="pos.side">{{ pos.side }}</span>
              <span class="pos-size">{{ pos.size }}</span>
              <span class="pos-entry">{{ pos.entry_price }}</span>
              <span
                class="pos-pnl"
                :class="{ positive: pos.pnl >= 0, negative: pos.pnl < 0 }"
              >
                {{ pos.pnl >= 0 ? "+" : "" }}{{ pos.pnl.toFixed(2) }}%
              </span>
            </div>
          </div>

          <!-- Progress Bar for Running Strategies -->
          <div
            v-if="
              strategy.status === 'running' && strategy.progress !== undefined
            "
            class="strategy-progress"
          >
            <div class="progress-label">
              <span>Próximo Check</span>
              <span>{{ formatTimeRemaining(strategy.next_check) }}</span>
            </div>
            <div class="progress-bar">
              <div
                class="progress-fill"
                :style="{ width: strategy.progress + '%' }"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-if="strategies.length === 0" class="empty-state">
        <IconTrendingUp class="empty-icon" />
        <h4>No hay estrategias activas</h4>
        <p>
          Inicia el modo autónomo o despliega estrategias desde backtesting para
          verlas aquí.
        </p>
        <Button
          variant="primary"
          class="mt-md"
          @click="$router.push('/autonomous')"
        >
          <IconPlay class="btn-icon" /> Ir a Modo Autónomo
        </Button>
      </div>

      <!-- Strategy Detail Modal -->
      <Teleport to="body">
        <div
          v-if="selectedStrategy"
          class="modal-overlay"
          @click.self="closeModal"
        >
          <div class="modal" @click.stop>
            <div class="modal-header">
              <h3>{{ selectedStrategy.name }}</h3>
              <Button
                variant="ghost"
                size="sm"
                class="close-btn"
                @click="closeModal"
              >
                <IconX class="btn-icon" />
              </Button>
            </div>
            <div class="modal-body">
              <StrategyDetail :strategy="selectedStrategy" />
            </div>
          </div>
        </div>
      </Teleport>
    </Card>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { useDashboardStore } from "@/stores/dashboard";
import Card from "@/components/Card.vue";
import Button from "@/components/Button.vue";
import MiniChart from "@/components/MiniChart.vue";
import StrategyDetail from "@/components/StrategyDetail.vue";
import { Eye, Square, TrendingUp, X } from "lucide-vue-next";

const store = useDashboardStore();

const strategies = computed(() => store.activeStrategies);
const selectedStrategy = ref(null);

const activeCount = computed(
  () => strategies.value.filter((s) => s.status === "running").length,
);

const totalPnL = computed(() =>
  strategies.value.reduce((sum, s) => sum + (s.pnl || 0), 0),
);

const avgSharpe = computed(() => {
  const running = strategies.value.filter(
    (s) => s.status === "running" && s.sharpe,
  );
  if (running.length === 0) return 0;
  return running.reduce((sum, s) => sum + s.sharpe, 0) / running.length;
});

const statusLabels = {
  running: "Ejecutándose",
  paused: "Pausada",
  stopped: "Detenida",
  error: "Error",
  pending: "Pendiente",
};

function viewStrategy(strategy) {
  selectedStrategy.value = strategy;
}

function stopStrategy(strategy) {
  store.stopStrategy(strategy.id);
}

function closeModal() {
  selectedStrategy.value = null;
}

function formatTimeRemaining(isoString) {
  if (!isoString) return "N/A";
  const diff = new Date(isoString).getTime() - Date.now();
  if (diff <= 0) return "Ahora";
  const mins = Math.floor(diff / 60000);
  const secs = Math.floor((diff % 60000) / 1000);
  return `${mins}m ${secs}s`;
}
</script>

<style scoped>
.active-strategies {
  min-height: 400px;
}

.card-header-flex {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.strategies-summary {
  display: flex;
  gap: var(--space-lg);
}

.summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.summary-value {
  font-family: var(--font-mono);
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
}

.summary-label {
  font-size: 0.65rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Strategies Grid */
.strategies-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: var(--space-md);
}

.strategy-card {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  overflow: hidden;
  transition: all var(--transition-fast);
}

.strategy-card:hover {
  border-color: var(--accent-primary);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.strategy-card.running {
  border-left: 4px solid var(--accent-success);
}
.strategy-card.paused {
  border-left: 4px solid var(--accent-warning);
}
.strategy-card.stopped {
  border-left: 4px solid var(--text-muted);
}
.strategy-card.error {
  border-left: 4px solid var(--accent-danger);
}
.strategy-card.pending {
  border-left: 4px solid var(--accent-info);
}

.strategy-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: var(--space-md);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.strategy-info {
  flex: 1;
  min-width: 0;
}

.strategy-name {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-xs);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.strategy-meta {
  display: flex;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.strategy-symbol,
.strategy-timeframe {
  font-size: 0.7rem;
  font-family: var(--font-mono);
  color: var(--text-secondary);
  background: var(--bg-tertiary);
  padding: 2px 8px;
  border-radius: var(--radius-full);
}

.strategy-status-badge {
  font-size: 0.6rem;
  font-weight: 600;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: var(--radius-full);
}

.strategy-status-badge.running {
  background: var(--success-bg);
  color: var(--accent-success);
}
.strategy-status-badge.paused {
  background: var(--warning-bg);
  color: var(--accent-warning);
}
.strategy-status-badge.stopped {
  background: var(--bg-tertiary);
  color: var(--text-muted);
}
.strategy-status-badge.error {
  background: var(--danger-bg);
  color: var(--accent-danger);
}
.strategy-status-badge.pending {
  background: var(--info-bg);
  color: var(--accent-info);
}

.strategy-actions {
  display: flex;
  gap: var(--space-xs);
}

/* Strategy Metrics */
.strategy-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-sm);
  padding: var(--space-md);
}

.metric-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-sm);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.metric-group.pnl.positive .metric-value {
  color: var(--accent-success);
}
.metric-group.pnl.negative .metric-value {
  color: var(--accent-danger);
}

.metric-label {
  font-size: 0.6rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.metric-value {
  font-family: var(--font-mono);
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
}

.metric-sub {
  font-size: 0.65rem;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

/* Mini Chart */
.strategy-chart {
  height: 80px;
  padding: 0 var(--space-md) var(--space-md);
}

/* Positions */
.strategy-positions {
  padding: 0 var(--space-md) var(--space-md);
  border-top: 1px solid var(--border-color);
  margin-top: var(--space-sm);
  padding-top: var(--space-sm);
}

.position-row {
  display: grid;
  grid-template-columns: 60px 1fr 1fr 1fr;
  gap: var(--space-sm);
  padding: var(--space-xs) 0;
  font-size: 0.75rem;
  font-family: var(--font-mono);
}

.pos-side {
  font-weight: 600;
  text-transform: uppercase;
}

.pos-side.long {
  color: var(--accent-success);
}
.pos-side.short {
  color: var(--accent-danger);
}

.pos-size {
  color: var(--text-secondary);
}
.pos-entry {
  color: var(--text-secondary);
}

.pos-pnl.positive {
  color: var(--accent-success);
}
.pos-pnl.negative {
  color: var(--accent-danger);
}

/* Progress */
.strategy-progress {
  padding: var(--space-md);
  border-top: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.progress-label {
  display: flex;
  justify-content: space-between;
  margin-bottom: var(--space-xs);
  font-size: 0.7rem;
  color: var(--text-secondary);
}

.progress-bar {
  height: 6px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(
    90deg,
    var(--accent-primary),
    var(--accent-secondary)
  );
  border-radius: var(--radius-full);
  transition: width var(--transition-normal);
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-xl);
  color: var(--text-muted);
  text-align: center;
}

.empty-icon {
  width: 48px;
  height: 48px;
  margin-bottom: var(--space-md);
  opacity: 0.5;
}

.empty-state h4 {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0 0 var(--space-xs);
}

.empty-state p {
  font-size: 0.875rem;
  margin: 0 0 var(--space-lg);
  max-width: 300px;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: var(--space-lg);
  animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.modal {
  width: 100%;
  max-width: 800px;
  max-height: 90vh;
  background: var(--bg-secondary);
  border-radius: var(--radius-xl);
  border: 1px solid var(--border-color);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  animation: slideUp 0.3s ease-out;
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

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-md) var(--space-lg);
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
}

.close-btn {
  width: 32px;
  height: 32px;
  padding: 0;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-lg);
}

/* Responsive */
@media (max-width: 1024px) {
  .strategies-grid {
    grid-template-columns: 1fr;
  }

  .strategy-metrics {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .card-header-flex {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-md);
  }

  .strategies-summary {
    width: 100%;
    justify-content: space-between;
  }

  .strategy-metrics {
    grid-template-columns: 1fr;
  }

  .position-row {
    grid-template-columns: 50px 1fr 1fr;
  }

  .pos-entry {
    display: none;
  }
}
</style>
