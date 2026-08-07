<template>
  <div class="monitoring-view">
    <div class="page-header">
      <h1 class="page-title">Panel de Monitoreo</h1>
      <p class="page-subtitle">
        Vista en tiempo real de hipótesis, estrategias y flujo del sistema
      </p>
    </div>

    <!-- Flow State -->
    <Card title="Flujo del Sistema AQDE">
      <div v-if="flow" class="flow-visualization">
        <div class="flow-steps">
          <div
            v-for="(step, index) in flow.steps"
            :key="step.name"
            class="flow-step"
            :class="{
              active: step.status === 'in_progress',
              completed: step.status === 'completed',
            }"
          >
            <div
              class="step-node"
              :class="{
                active: step.status === 'in_progress',
                completed: step.status === 'completed',
              }"
            >
              <span v-if="step.status === 'completed'"
                ><IconCheck class="icon"
              /></span>
              <span v-else-if="step.status === 'in_progress'"
                ><IconLoader class="icon spin"
              /></span>
              <span v-else>{{ index + 1 }}</span>
            </div>
            <div class="step-info">
              <span class="step-name">{{ step.name }}</span>
              <span class="step-count">{{ step.count }}</span>
            </div>
            <div
              v-if="index < flow.steps.length - 1"
              class="step-connector"
              :class="{ active: step.status === 'completed' }"
            />
          </div>
        </div>

        <div class="flow-metrics">
          <div class="metric-item">
            <span class="metric-label">Hipótesis/hora</span>
            <span class="metric-value">{{
              flow.metrics.hypotheses_per_hour
            }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">Tiempo Prom. Validación</span>
            <span class="metric-value">{{
              formatDuration(flow.metrics.avg_validation_time)
            }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">Tasa Aprobación</span>
            <span class="metric-value"
              >{{ (flow.metrics.approval_rate * 100).toFixed(1) }}%</span
            >
          </div>
        </div>
      </div>
    </Card>

    <!-- Hypotheses & Strategies Grid -->
    <div class="grid grid-2" style="margin-top: var(--space-lg)">
      <Card title="Hipótesis">
        <div class="filter-bar">
          <select v-model="hypFilter.strategy_type" class="filter-select">
            <option value="">Todos los tipos</option>
            <option v-for="type in strategyTypes" :key="type" :value="type">
              {{ type }}
            </option>
          </select>
          <select v-model="hypFilter.status" class="filter-select">
            <option value="">Todos los estados</option>
            <option
              v-for="status in hypothesisStatuses"
              :key="status"
              :value="status"
            >
              {{ status }}
            </option>
          </select>
        </div>

        <div class="hypotheses-table">
          <table class="monitor-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Nombre</th>
                <th>Tipo</th>
                <th>Estado</th>
                <th>Score Val.</th>
                <th>Score Cient.</th>
                <th>Creado</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="hyp in filteredHypotheses"
                :key="hyp.hypothesis_id"
                class="clickable-row"
                @click="selectHypothesis(hyp)"
              >
                <td>
                  <span class="hyp-id"
                    >{{ hyp.hypothesis_id.slice(0, 12) }}...</span
                  >
                </td>
                <td>{{ hyp.name }}</td>
                <td>
                  <span class="type-badge">{{ hyp.strategy_type }}</span>
                </td>
                <td>
                  <span class="status-badge" :class="hyp.status">{{
                    hyp.status
                  }}</span>
                </td>
                <td :class="hyp.validation_score >= 0.7 ? 'good' : 'low'">
                  {{ (hyp.validation_score * 100).toFixed(0) }}%
                </td>
                <td :class="hyp.scientific_score >= 0.7 ? 'good' : 'low'">
                  {{ (hyp.scientific_score * 100).toFixed(0) }}%
                </td>
                <td class="date-cell">{{ formatDate(hyp.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Estrategias por Etapa">
        <div v-if="strategies" class="stages-grid">
          <StageColumn
            v-for="(items, stage) in stages"
            :key="stage"
            :title="stageLabels[stage] || stage"
            :items="items"
            :stage="stage"
          />
        </div>
      </Card>
    </div>

    <!-- Active Simulations & Recent Trades -->
    <div class="grid grid-2" style="margin-top: var(--space-lg)">
      <Card title="Simulaciones Activas">
        <div
          v-if="
            simulations &&
            (simulations.backtests.length > 0 ||
              simulations.monte_carlo.length > 0 ||
              simulations.walk_forward.length > 0)
          "
          class="simulations-list"
        >
          <template v-for="(sims, type) in simulationGroups" :key="type">
            <div v-if="sims.length > 0" class="simulation-group">
              <div class="group-label">{{ type }}</div>
              <div v-for="sim in sims" :key="sim.id" class="simulation-item">
                <div class="sim-info">
                  <span class="sim-id">{{ sim.hypothesis_id }}</span>
                  <span class="sim-progress">{{ sim.progress }}%</span>
                </div>
                <div class="sim-progress-bar">
                  <div
                    class="sim-progress-fill"
                    :style="{ width: sim.progress + '%' }"
                  />
                </div>
              </div>
            </div>
          </template>
        </div>
        <div v-else class="empty-state">
          <IconActivity class="empty-icon" />
          <p>No hay simulaciones en ejecución</p>
        </div>
      </Card>

      <Card title="Operaciones Recientes (Paper Trading)">
        <div v-if="trades.length > 0" class="trades-table">
          <table class="monitor-table">
            <thead>
              <tr>
                <th>Hora</th>
                <th>Símbolo</th>
                <th>Dir.</th>
                <th>Entrada</th>
                <th>Salida</th>
                <th>PnL</th>
                <th>Estrategia</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="trade in trades.slice(0, 20)" :key="trade.trade_id">
                <td class="date-cell">{{ formatTime(trade.exit_time) }}</td>
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
                <td class="strategy-cell">{{ trade.strategy_name }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty-state">
          <IconBarChart2 class="empty-icon" />
          <p>No hay operaciones recientes</p>
        </div>
      </Card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useMonitoringStore } from "@/stores/monitoring";
import Card from "@/components/Card.vue";
import StageColumn from "@/components/StageColumn.vue";
import { Check, Loader, Activity, BarChart2 } from "lucide-vue-next";
import { format } from "date-fns";

const store = useMonitoringStore();

const flow = computed(() => store.flow);
const hypotheses = computed(() => store.hypotheses);
const strategies = computed(() => store.strategies);
const simulations = computed(() => store.simulations);
const trades = computed(() => store.trades);
const loading = computed(() => store.loading);
const wsConnected = computed(() => store.wsConnected);

const hypFilter = ref({ strategy_type: "", status: "" });

const strategyTypes = computed(() => [
  ...new Set(hypotheses.value.map((h) => h.strategy_type)),
]);
const hypothesisStatuses = [
  "draft",
  "generated",
  "validated",
  "backtested",
  "monte_carlo_tested",
  "approved",
  "deployed",
  "rejected",
];

const filteredHypotheses = computed(() => {
  return hypotheses.value.filter((h) => {
    if (
      hypFilter.value.strategy_type &&
      h.strategy_type !== hypFilter.value.strategy_type
    )
      return false;
    if (hypFilter.value.status && h.status !== hypFilter.value.status)
      return false;
    return true;
  });
});

const stages = computed(() => strategies.value || {});
const stageLabels = {
  generated: "Generadas",
  validating: "Validando",
  backtesting: "Backtesting",
  monte_carlo: "Monte Carlo",
  approved: "Aprobadas",
  rejected: "Rechazadas",
};

const simulationGroups = computed(() => {
  if (!simulations.value) return {};
  return {
    Backtests: simulations.value.backtests || [],
    "Monte Carlo": simulations.value.monte_carlo || [],
    "Walk-Forward": simulations.value.walk_forward || [],
  };
});

function formatDate(isoString) {
  const date = new Date(isoString);
  return format(date, "dd/MM/yyyy HH:mm");
}

function formatTime(isoString) {
  const date = new Date(isoString);
  return format(date, "HH:mm:ss");
}

function formatDuration(seconds) {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

function selectHypothesis(hyp) {
  console.log("Selected hypothesis:", hyp);
}

onMounted(() => {
  store.loadAll();
  store.connect();
});

onUnmounted(() => {
  store.disconnect();
});
</script>

<style scoped>
.monitoring-view {
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

/* Flow Visualization */
.flow-visualization {
  padding: var(--space-sm) 0;
}

.flow-steps {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-md);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  overflow-x: auto;
  margin-bottom: var(--space-lg);
}

.flow-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-sm);
  flex-shrink: 0;
}

.step-node {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-full);
  background: var(--bg-secondary);
  border: 2px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
}

.step-node .icon {
  width: 18px;
  height: 18px;
  color: var(--text-muted);
}

.step-node.active {
  background: var(--accent-primary);
  border-color: var(--accent-primary);
}

.step-node.active .icon {
  color: white;
}

.step-node.completed {
  background: var(--accent-success);
  border-color: var(--accent-success);
}

.step-node.completed .icon {
  color: white;
}

.step-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.step-name {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-secondary);
  white-space: nowrap;
}

.step-count {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--accent-primary);
}

.flow-step.completed .step-name {
  color: var(--accent-success);
  font-weight: 600;
}

.flow-step.active .step-name {
  color: var(--accent-primary);
  font-weight: 600;
}

.step-connector {
  width: 40px;
  height: 2px;
  background: var(--border-color);
  flex-shrink: 0;
  margin-top: 19px;
}

.step-connector.active {
  background: var(--accent-success);
}

.flow-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-md);
}

.metric-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: var(--space-md);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
}

.metric-label {
  font-size: 0.7rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  text-align: center;
}

.metric-value {
  font-family: var(--font-mono);
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* Filter Bar */
.filter-bar {
  display: flex;
  gap: var(--space-sm);
  margin-bottom: var(--space-md);
  padding-bottom: var(--space-sm);
  border-bottom: 1px solid var(--border-color);
}

.filter-select {
  padding: 0.375rem 0.75rem;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 0.8125rem;
  min-width: 140px;
}

.filter-select:focus {
  outline: none;
  border-color: var(--accent-primary);
}

/* Tables */
.monitor-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.monitor-table th,
.monitor-table td {
  padding: var(--space-sm) var(--space-md);
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}

.monitor-table th {
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.7rem;
  background: var(--bg-tertiary);
  position: sticky;
  top: 0;
}

.monitor-table tbody tr:hover {
  background: var(--bg-tertiary);
}

.clickable-row {
  cursor: pointer;
}

.hyp-id {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--text-muted);
}

.type-badge {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: capitalize;
  padding: 2px 6px;
  border-radius: var(--radius-full);
  background: var(--info-bg);
  color: var(--accent-info);
}

.status-badge {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: var(--radius-full);
}

.status-badge.draft {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}
.status-badge.generated {
  background: var(--info-bg);
  color: var(--accent-info);
}
.status-badge.validated {
  background: var(--success-bg);
  color: var(--accent-success);
}
.status-badge.backtested {
  background: var(--warning-bg);
  color: var(--accent-warning);
}
.status-badge.monte_carlo_tested {
  background: rgba(163, 113, 247, 0.1);
  color: var(--accent-secondary);
}
.status-badge.approved {
  background: var(--success-bg);
  color: var(--accent-success);
}
.status-badge.deployed {
  background: var(--success-bg);
  color: var(--accent-success);
}
.status-badge.rejected {
  background: var(--danger-bg);
  color: var(--accent-danger);
}

.good {
  color: var(--accent-success);
}
.low {
  color: var(--accent-warning);
}

.date-cell {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-muted);
  white-space: nowrap;
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

.strategy-cell {
  font-size: 0.75rem;
  color: var(--text-secondary);
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Stages Grid */
.stages-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: var(--space-sm);
}

@media (max-width: 1024px) {
  .stages-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 640px) {
  .stages-grid {
    grid-template-columns: 1fr;
  }
}

/* Simulations */
.simulations-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.simulation-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.group-label {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.simulation-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sim-info {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
}

.sim-id {
  font-family: var(--font-mono);
  color: var(--text-secondary);
}

.sim-progress {
  color: var(--accent-primary);
  font-weight: 600;
}

.sim-progress-bar {
  height: 4px;
  background: var(--bg-primary);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.sim-progress-fill {
  height: 100%;
  background: var(--accent-primary);
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
  margin-bottom: var(--space-sm);
  opacity: 0.5;
}

.empty-state p {
  font-size: 0.875rem;
  margin: 0;
}

/* Spin Animation */
.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* Responsive */
@media (max-width: 768px) {
  .flow-steps {
    gap: var(--space-sm);
  }

  .step-connector {
    width: 20px;
  }

  .filter-bar {
    flex-direction: column;
  }

  .filter-select {
    min-width: 100%;
  }

  .flow-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
