<template>
  <div class="dashboard">
    <div class="page-header">
      <div class="header-content">
        <h1 class="page-title">Centro de Mando</h1>
        <p class="page-subtitle">Quant-Math Command Center - Dashboard</p>
      </div>
      <div class="header-actions">
        <ControlButtons
          :running="quantMathRunning"
          :autonomous-running="aqde?.is_running"
          @start="startQuantMath"
          @stop="stopQuantMath"
          @restart="restartQuantMath"
          @autonomous="toggleAutonomous"
          @backtest="runBacktest"
          @real-trading="enableRealTrading"
        />
      </div>
    </div>

    <!-- System Health & AQDE Status Row -->
    <div class="grid grid-4">
      <Card title="Salud del Sistema">
        <template #header>
          <div class="card-header-flex">
            <h3 class="card-title">Salud del Sistema</h3>
            <SystemStatusIndicator />
            <div class="health-status-badge" :class="systemHealthClass">
              {{ systemHealth }}
            </div>
          </div>
        </template>
        <div v-if="health" class="health-metrics">
          <div class="metric-row">
            <span class="metric-label">CPU</span>
            <div class="metric-bar">
              <div
                class="metric-fill"
                :style="{ width: health.cpu_percent + '%' }"
                :class="health.cpu_percent > 80 ? 'warning' : ''"
              />
            </div>
            <span
              class="metric-value"
              :class="health.cpu_percent > 80 ? 'warning' : ''"
              >{{ health.cpu_percent.toFixed(1) }}%</span
            >
          </div>
          <div class="metric-row">
            <span class="metric-label">Memoria</span>
            <div class="metric-bar">
              <div
                class="metric-fill"
                :style="{ width: health.memory_percent + '%' }"
                :class="health.memory_percent > 85 ? 'warning' : ''"
              />
            </div>
            <span
              class="metric-value"
              :class="health.memory_percent > 85 ? 'warning' : ''"
              >{{ health.memory_percent.toFixed(1) }}%</span
            >
          </div>
          <div class="metric-row">
            <span class="metric-label">Disco</span>
            <div class="metric-bar">
              <div
                class="metric-fill"
                :style="{ width: health.disk_percent + '%' }"
                :class="health.disk_percent > 90 ? 'warning' : ''"
              />
            </div>
            <span
              class="metric-value"
              :class="health.disk_percent > 90 ? 'warning' : ''"
              >{{ health.disk_percent.toFixed(1) }}%</span
            >
          </div>
          <div class="metric-row">
            <span class="metric-label">Uptime</span>
            <div class="metric-bar">
              <div class="metric-fill" style="width: 100%" />
            </div>
            <span class="metric-value">{{
              formatUptime(health.uptime_seconds)
            }}</span>
          </div>
        </div>
        <div v-else class="loading">Cargando...</div>
      </Card>

      <Card title="Estado AQDE">
        <template #header>
          <div class="card-header-flex">
            <h3 class="card-title">Estado AQDE</h3>
            <div class="aqde-status-container">
              <span class="status-badge" :class="aqdeStatusClass">{{
                aqde?.phase || "idle"
              }}</span>
              <div class="aqde-phase-indicator" :class="aqdePhaseClass"></div>
            </div>
          </div>
        </template>
        <div v-if="aqde" class="aqde-metrics">
          <div class="metric-grid">
            <div class="metric-item">
              <span class="metric-value">{{ aqde.active_hypotheses }}</span>
              <span class="metric-label">Activas</span>
            </div>
            <div class="metric-item">
              <span class="metric-value">{{ aqde.total_hypotheses }}</span>
              <span class="metric-label">Total</span>
            </div>
            <div class="metric-item">
              <span class="metric-value">{{ aqde.hypotheses_tested }}</span>
              <span class="metric-label">Probadas</span>
            </div>
            <div class="metric-item">
              <span class="metric-value">{{ aqde.current_iteration }}</span>
              <span class="metric-label">Iteración</span>
            </div>
          </div>
          <div
            v-if="aqde.is_running && aqde.max_iterations > 0"
            class="aqde-progress"
          >
            <div class="progress-bar-small">
              <div
                class="progress-fill-small"
                :style="{ width: aqdeProgress + '%' }"
              />
            </div>
            <span class="progress-text"
              >{{ aqdeProgress.toFixed(1) }}% completado</span
            >
          </div>
          <div class="aqde-actions">
            <Button
              variant="primary"
              :disabled="aqde.is_running"
              size="sm"
              @click="startAutonomous"
            >
              <IconPlay class="btn-icon" /> Iniciar
            </Button>
            <Button
              variant="danger"
              :disabled="!aqde.is_running"
              size="sm"
              @click="stopAutonomous"
            >
              <IconSquare class="btn-icon" /> Detener
            </Button>
          </div>
        </div>
        <div v-else class="loading">Cargando...</div>
      </Card>

      <Card title="Paper Trading">
        <template #header>
          <div class="card-header-flex">
            <h3 class="card-title">Paper Trading</h3>
            <span class="status-badge paper">Paper</span>
          </div>
        </template>
        <div v-if="trading" class="trading-metrics">
          <div class="main-metric">
            <span class="metric-label">Balance</span>
            <span class="metric-value large">{{
              formatCurrency(trading.paper_balance)
            }}</span>
          </div>
          <div class="metric-grid">
            <div
              class="metric-item"
              :class="trading.pnl >= 0 ? 'positive' : 'negative'"
            >
              <span class="metric-value"
                >{{ trading.pnl >= 0 ? "+" : ""
                }}{{ formatCurrency(trading.pnl) }}</span
              >
              <span class="metric-label"
                >PnL ({{ trading.pnl_pct >= 0 ? "+" : ""
                }}{{ trading.pnl_pct.toFixed(2) }}%)</span
              >
            </div>
            <div class="metric-item">
              <span class="metric-value"
                >{{ trading.win_rate.toFixed(1) }}%</span
              >
              <span class="metric-label">Win Rate</span>
            </div>
            <div class="metric-item warning">
              <span class="metric-value"
                >{{ trading.max_drawdown.toFixed(2) }}%</span
              >
              <span class="metric-label">Max DD</span>
            </div>
          </div>
          <div
            v-if="trading.equity_curve && trading.equity_curve.length > 1"
            class="mini-chart"
          >
            <svg
              class="sparkline"
              viewBox="0 0 200 40"
              preserveAspectRatio="none"
            >
              <polyline
                :points="sparklinePoints"
                fill="none"
                :stroke="
                  trading.pnl >= 0
                    ? 'var(--accent-success)'
                    : 'var(--accent-danger)'
                "
                stroke-width="2"
              />
            </svg>
          </div>
          <div v-if="trading.active_strategy" class="strategy-info">
            <span class="label">Estrategia:</span>
            <span class="value">{{ trading.active_strategy }}</span>
          </div>
        </div>
        <div v-else class="loading">Cargando...</div>
      </Card>

      <Card title="Recursos del Sistema">
        <template #header>
          <h3 class="card-title">Recursos</h3>
        </template>
        <div class="resource-metrics">
          <div class="resource-item">
            <div class="resource-icon cpu">
              <IconCpu class="icon" />
            </div>
            <div class="resource-info">
              <span class="resource-label">CPU</span>
              <div class="resource-bar">
                <div
                  class="resource-fill"
                  :style="{ width: health?.cpu_percent + '%' || '0%' }"
                />
              </div>
              <span class="resource-value"
                >{{ health?.cpu_percent?.toFixed(1) || "0.0" }}%</span
              >
            </div>
          </div>
          <div class="resource-item">
            <div class="resource-icon memory">
              <IconMemoryStick class="icon" />
            </div>
            <div class="resource-info">
              <span class="resource-label">Memoria</span>
              <div class="resource-bar">
                <div
                  class="resource-fill"
                  :style="{ width: health?.memory_percent + '%' || '0%' }"
                />
              </div>
              <span class="resource-value"
                >{{ health?.memory_percent?.toFixed(1) || "0.0" }}%</span
              >
            </div>
          </div>
          <div class="resource-item">
            <div class="resource-icon disk">
              <IconDatabase class="icon" />
            </div>
            <div class="resource-info">
              <span class="resource-label">Disco</span>
              <div class="resource-bar">
                <div
                  class="resource-fill"
                  :style="{ width: health?.disk_percent + '%' || '0%' }"
                />
              </div>
              <span class="resource-value"
                >{{ health?.disk_percent?.toFixed(1) || "0.0" }}%</span
              >
            </div>
          </div>
          <div class="resource-item">
            <div class="resource-icon network">
              <IconWifi class="icon" />
            </div>
            <div class="resource-info">
              <span class="resource-label">Red</span>
              <div class="resource-bar">
                <div class="resource-fill" style="width: 100%" />
              </div>
              <span
                class="resource-value"
                :class="wsConnected ? '' : 'warning'"
                >{{ wsConnected ? "Conectado" : "Desconectado" }}</span
              >
            </div>
          </div>
        </div>
      </Card>
    </div>

    <!-- Pipeline Visual -->
    <Card title="Pipeline de Quant-Math" class="pipeline-card">
      <div class="pipeline-visualization">
        <div
          v-for="(stage, index) in pipelineStages"
          :key="stage.id"
          class="pipeline-stage"
          :class="{
            active: stage.active,
            completed: stage.completed,
            hasError: stage.hasError,
          }"
        >
          <div class="stage-node">
            <div class="stage-icon" :class="stage.iconClass">
              <component :is="stage.icon" class="icon" />
            </div>
            <div class="stage-status-ring" :class="stage.statusClass"></div>
          </div>
          <div class="stage-label">{{ stage.name }}</div>
          <div v-if="stage.metrics" class="stage-metrics">
            <span
              v-for="(metric, key) in stage.metrics"
              :key="key"
              class="stage-metric"
              >{{ metric }}</span
            >
          </div>
          <div
            v-if="index < pipelineStages.length - 1"
            class="stage-connector"
            :class="{ active: stage.completed }"
          ></div>
        </div>
      </div>
    </Card>

    <!-- Active Hypotheses & Recent Events Row -->
    <div class="grid grid-2" style="margin-top: var(--space-lg)">
      <Card title="Hipótesis Activas">
        <div v-if="hypotheses.length > 0" class="hypotheses-list">
          <div
            v-for="hyp in hypotheses"
            :key="hyp.hypothesis_id"
            class="hypothesis-item"
          >
            <div class="hyp-info">
              <span class="hyp-name">{{ hyp.name }}</span>
              <span class="hyp-type">{{ hyp.strategy_type }}</span>
            </div>
            <div class="hyp-metrics">
              <div class="score-bar">
                <div
                  class="score-fill"
                  :style="{ width: hyp.validation_score * 100 + '%' }"
                  :class="hyp.validation_score >= 0.7 ? 'good' : 'low'"
                />
              </div>
              <span
                class="hyp-score"
                :class="hyp.validation_score >= 0.7 ? 'good' : 'low'"
                >{{ (hyp.validation_score * 100).toFixed(0) }}%</span
              >
              <span class="hyp-status" :class="hyp.status">{{
                hyp.status
              }}</span>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          <IconFileQuestion class="empty-icon" />
          <p>No hay hipótesis activas</p>
        </div>
      </Card>

      <Card title="Eventos en Tiempo Real">
        <div v-if="events.length > 0" class="events-list">
          <div
            v-for="event in events.slice(0, 15)"
            :key="event.timestamp"
            class="event-item"
            :class="event.level"
          >
            <div class="event-icon" :class="event.level">
              <IconCheckCircle v-if="event.level === 'success'" class="icon" />
              <IconAlertCircle
                v-else-if="event.level === 'warning'"
                class="icon"
              />
              <IconInfo v-else class="icon" />
            </div>
            <div class="event-content">
              <div class="event-message">{{ event.message }}</div>
              <div class="event-time">{{ formatTime(event.timestamp) }}</div>
            </div>
            <span v-if="event.source" class="event-source">{{
              event.source
            }}</span>
          </div>
        </div>
        <div v-else class="empty-state">
          <IconClock class="empty-icon" />
          <p>No hay eventos recientes</p>
        </div>
      </Card>
    </div>
  </div>
</template>

<script setup>
import { onMounted, computed, ref } from "vue";
import { useDashboardStore } from "@/stores/dashboard";
import Card from "@/components/Card.vue";
import Button from "@/components/Button.vue";
import SystemStatusIndicator from "@/components/SystemStatusIndicator.vue";
import ControlButtons from "@/components/ControlButtons.vue";
import ActiveStrategiesPanel from "@/components/ActiveStrategiesPanel.vue";
import {
  Play,
  Square,
  Cpu,
  MemoryStick,
  Database,
  FileQuestion,
  Clock,
  CheckCircle,
  AlertCircle,
  Info,
  Brain,
  BarChart2,
  Server,
  RotateCw,
  Wifi,
  Activity,
  TrendingUp,
} from "lucide-vue-next";
import { format } from "date-fns";

const store = useDashboardStore();

const health = computed(() => store.health);
const aqde = computed(() => store.aqde);
const trading = computed(() => store.trading);
const hypotheses = computed(() => store.hypotheses);
const events = computed(() => store.events);
const wsConnected = computed(() => store.wsConnected);

const quantMathRunning = ref(false);

const aqdeStatusClass = computed(() => {
  if (!aqde.value) return "";
  if (aqde.value.is_running) return "running";
  return "idle";
});

const aqdePhaseClass = computed(() => {
  if (!aqde.value || !aqde.value.is_running) return "";
  return "running";
});

const systemHealth = computed(() => {
  if (!health.value) return "Desconocido";
  const cpu = health.value.cpu_percent || 0;
  const mem = health.value.memory_percent || 0;
  const disk = health.value.disk_percent || 0;
  if (cpu > 85 || mem > 90 || disk > 95) return "Crítico";
  if (cpu > 70 || mem > 80 || disk > 85) return "Advertencia";
  return "Saludable";
});

const systemHealthClass = computed(() => {
  const status = systemHealth.value;
  if (status === "Crítico") return "critical";
  if (status === "Advertencia") return "warning";
  return "healthy";
});

const aqdeProgress = computed(() => {
  if (!aqde.value || !aqde.value.max_iterations) return 0;
  return (aqde.value.current_iteration / aqde.value.max_iterations) * 100;
});

// Pipeline stages with dynamic states
const pipelineStages = computed(() => [
  {
    id: "market",
    name: "Mercado",
    icon: TrendingUp,
    iconClass: "market",
    statusClass: "active",
    active: true,
    completed: true,
    hasError: false,
    metrics: { live: true },
  },
  {
    id: "aqde",
    name: "AQDE",
    icon: Brain,
    iconClass: "aqde",
    statusClass: aqde.value?.is_running ? "running" : "idle",
    active: aqde.value?.is_running || false,
    completed: aqde.value?.hypotheses_tested > 0 || false,
    hasError: false,
    metrics: {
      hypotheses: aqde.value?.total_hypotheses || 0,
      running: aqde.value?.is_running || false,
    },
  },
  {
    id: "hypothesis",
    name: "Hipótesis",
    icon: FileQuestion,
    iconClass: "hypothesis",
    statusClass: hypotheses.value.length > 0 ? "active" : "idle",
    active: hypotheses.value.length > 0,
    completed: hypotheses.value.some((h) => h.status === "validated"),
    hasError: hypotheses.value.some((h) => h.status === "failed"),
    metrics: {
      count: hypotheses.value.length,
      validated: hypotheses.value.filter((h) => h.status === "validated")
        .length,
    },
  },
  {
    id: "backtesting",
    name: "Backtesting",
    icon: BarChart2,
    iconClass: "backtesting",
    statusClass: "idle",
    active: false,
    completed: hypotheses.value.some((h) => h.status === "backtested"),
    hasError: false,
    metrics: {
      backtested: hypotheses.value.filter((h) => h.status === "backtested")
        .length,
    },
  },
  {
    id: "monte_carlo",
    name: "Monte Carlo",
    icon: Activity,
    iconClass: "monte-carlo",
    statusClass: "idle",
    active: false,
    completed: hypotheses.value.some((h) => h.status === "monte_carlo_tested"),
    hasError: false,
    metrics: {
      tested: hypotheses.value.filter((h) => h.status === "monte_carlo_tested")
        .length,
    },
  },
  {
    id: "validation",
    name: "Validación",
    icon: CheckCircle,
    iconClass: "validation",
    statusClass: "idle",
    active: false,
    completed: hypotheses.value.some((h) => h.status === "approved"),
    hasError: false,
    metrics: {
      approved: hypotheses.value.filter((h) => h.status === "approved").length,
    },
  },
  {
    id: "paper_trading",
    name: "Paper Trading",
    icon: Server,
    iconClass: "paper-trading",
    statusClass: trading.value?.total_trades > 0 ? "active" : "idle",
    active: trading.value?.total_trades > 0,
    completed: trading.value?.total_trades > 0,
    hasError: false,
    metrics: {
      trades: trading.value?.total_trades || 0,
      pnl: trading.value?.pnl || 0,
    },
  },
  {
    id: "production",
    name: "Producción",
    icon: Server,
    iconClass: "production",
    statusClass: "idle",
    active: false,
    completed: false,
    hasError: false,
    metrics: {
      enabled: false,
    },
  },
]);

function formatCurrency(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatTime(isoString) {
  const date = new Date(isoString);
  return format(date, "HH:mm:ss");
}

function formatUptime(seconds) {
  if (!seconds) return "N/A";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

// Sparkline points for mini chart
const sparklinePoints = computed(() => {
  if (!trading.value?.equity_curve || trading.value.equity_curve.length < 2)
    return "";
  const points = trading.value.equity_curve;
  const min = Math.min(...points.map((p) => p[1]));
  const max = Math.max(...points.map((p) => p[1]));
  const range = max - min || 1;
  return points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * 200;
      const y = 40 - ((p[1] - min) / range) * 40;
      return `${x},${y}`;
    })
    .join(" ");
});

async function startQuantMath() {
  quantMathRunning.value = true;
  try {
    await fetch("/api/v1/quant-math/start", { method: "POST" });
  } catch (error) {
    console.error("Failed to start Quant-Math:", error);
  }
}

async function stopQuantMath() {
  try {
    await fetch("/api/v1/quant-math/stop", { method: "POST" });
  } catch (error) {
    console.error("Failed to stop Quant-Math:", error);
  } finally {
    quantMathRunning.value = false;
  }
}

async function restartQuantMath() {
  await stopQuantMath();
  await startQuantMath();
}

async function toggleAutonomous() {
  if (aqde.value?.is_running) {
    await stopAutonomous();
  } else {
    await startAutonomous();
  }
}

async function startAutonomous() {
  try {
    await fetch("/api/v1/autonomous/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbols: ["BTCUSDT", "ETHUSDT"],
        max_iterations: 10,
        min_sharpe: 1.0,
        min_win_rate: 50,
        max_drawdown: 20,
      }),
    });
  } catch (error) {
    console.error("Failed to start autonomous mode:", error);
  }
}

async function stopAutonomous() {
  try {
    await fetch("/api/v1/autonomous/stop", { method: "POST" });
  } catch (error) {
    console.error("Failed to stop autonomous mode:", error);
  }
}

async function runBacktest() {
  // Navigate to backtest page
  window.location.href = "/backtest";
}

async function enableRealTrading() {
  alert("Trading real (Bybit) está deshabilitado en esta versión");
}

onMounted(() => {
  store.fetchAll();
});
</script>

<style scoped>
.dashboard {
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

/* Health Metrics */
.health-metrics,
.aqde-metrics,
.trading-metrics,
.resource-metrics {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.metric-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.metric-label {
  min-width: 70px;
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.metric-bar {
  flex: 1;
  height: 8px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.metric-fill {
  height: 100%;
  background: var(--accent-primary);
  border-radius: var(--radius-full);
  transition: width var(--transition-normal);
}

.metric-fill.warning {
  background: var(--accent-warning);
}

.metric-value {
  min-width: 60px;
  text-align: right;
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  font-weight: 600;
}

.metric-value.warning {
  color: var(--accent-warning);
}

.metric-value.positive {
  color: var(--accent-success);
}

.metric-value.negative {
  color: var(--accent-danger);
}

.metric-value.large {
  font-size: 1.5rem;
  font-weight: 700;
}

/* Metric Grid */
.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-sm);
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-sm);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
}

.metric-item.warning {
  border: 1px solid var(--warning-border);
}

.metric-item .metric-value {
  text-align: left;
  min-width: auto;
}

.metric-item .metric-label {
  min-width: auto;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.aqde-actions {
  display: flex;
  gap: var(--space-sm);
  margin-top: var(--space-sm);
}

.strategy-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: var(--space-sm);
  border-top: 1px solid var(--border-color);
  margin-top: var(--space-sm);
}

.strategy-info .label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.strategy-info .value {
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  font-weight: 500;
}

/* Resource Metrics */
.resource-item {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-sm);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
}

.resource-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}

.resource-icon.cpu {
  background: rgba(88, 166, 255, 0.1);
  color: var(--accent-primary);
}
.resource-icon.memory {
  background: rgba(163, 113, 247, 0.1);
  color: var(--accent-secondary);
}
.resource-icon.disk {
  background: rgba(57, 197, 207, 0.1);
  color: var(--accent-info);
}

.resource-icon .icon {
  width: 18px;
  height: 18px;
}

.resource-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.resource-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.resource-bar {
  height: 6px;
  background: var(--bg-primary);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.resource-fill {
  height: 100%;
  background: var(--accent-primary);
  border-radius: var(--radius-full);
  transition: width var(--transition-normal);
}

.resource-value {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 600;
}

/* Hypotheses List */
.hypotheses-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.hypothesis-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-sm);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  transition: background var(--transition-fast);
}

.hypothesis-item:hover {
  background: var(--bg-elevated);
}

.hyp-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.hyp-name {
  font-weight: 500;
  font-size: 0.875rem;
}

.hyp-type {
  font-size: 0.7rem;
  color: var(--text-secondary);
  text-transform: capitalize;
}

.hyp-metrics {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.hyp-score {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 600;
}

.hyp-score.good {
  color: var(--accent-success);
}
.hyp-score.low {
  color: var(--accent-warning);
}

.hyp-status {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: var(--radius-full);
}

.hyp-status.active {
  background: var(--success-bg);
  color: var(--accent-success);
}
.hyp-status.validated {
  background: var(--info-bg);
  color: var(--accent-info);
}
.hyp-status.backtested {
  background: var(--warning-bg);
  color: var(--accent-warning);
}
.hyp-status.deployed {
  background: var(--success-bg);
  color: var(--accent-success);
}
.hyp-status.failed {
  background: var(--danger-bg);
  color: var(--accent-danger);
}
.hyp-status.draft {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}

/* Events List */
.events-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.event-item {
  display: flex;
  gap: var(--space-sm);
  padding: var(--space-sm);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
}

.event-item.success {
  border-left: 3px solid var(--accent-success);
}
.event-item.warning {
  border-left: 3px solid var(--accent-warning);
}
.event-item.info {
  border-left: 3px solid var(--accent-info);
}

.event-icon {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
}

.event-icon.success {
  background: var(--success-bg);
  color: var(--accent-success);
}
.event-icon.warning {
  background: var(--warning-bg);
  color: var(--accent-warning);
}
.event-icon.info {
  background: var(--info-bg);
  color: var(--accent-info);
}

.event-icon .icon {
  width: 14px;
  height: 14px;
}

.event-content {
  flex: 1;
  min-width: 0;
}

.event-message {
  font-size: 0.8125rem;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.event-time {
  font-size: 0.7rem;
  color: var(--text-muted);
  font-family: var(--font-mono);
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

/* Status Badge */
.status-badge {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: var(--radius-full);
}

.status-badge.running {
  background: var(--success-bg);
  color: var(--accent-success);
}
.status-badge.idle {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}
.status-badge.paper {
  background: var(--info-bg);
  color: var(--accent-info);
}

/* Loading */
.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-xl);
  color: var(--text-muted);
}

/* Pipeline Visualization */
.pipeline-visualization {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: var(--space-md);
  padding: var(--space-md);
  overflow-x: auto;
}

.pipeline-stage {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-xs);
  flex-shrink: 0;
  position: relative;
}

.stage-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-xs);
}

.stage-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-tertiary);
  border: 2px solid var(--border-color);
  position: relative;
  transition: all var(--transition-normal);
}

.stage-icon .icon {
  width: 24px;
  height: 24px;
  color: var(--text-secondary);
  transition: all var(--transition-normal);
}

.stage-icon.market {
  border-color: var(--accent-primary);
  background: rgba(88, 166, 255, 0.1);
}
.stage-icon.market .icon {
  color: var(--accent-primary);
}
.stage-icon.aqde {
  border-color: var(--accent-secondary);
  background: rgba(163, 113, 247, 0.1);
}
.stage-icon.aqde .icon {
  color: var(--accent-secondary);
}
.stage-icon.hypothesis {
  border-color: var(--accent-info);
  background: rgba(57, 197, 207, 0.1);
}
.stage-icon.hypothesis .icon {
  color: var(--accent-info);
}
.stage-icon.backtesting {
  border-color: var(--accent-warning);
  background: rgba(255, 184, 77, 0.1);
}
.stage-icon.backtesting .icon {
  color: var(--accent-warning);
}
.stage-icon.monte-carlo {
  border-color: var(--accent-secondary);
  background: rgba(163, 113, 247, 0.1);
}
.stage-icon.monte-carlo .icon {
  color: var(--accent-secondary);
}
.stage-icon.validation {
  border-color: var(--accent-success);
  background: rgba(34, 197, 94, 0.1);
}
.stage-icon.validation .icon {
  color: var(--accent-success);
}
.stage-icon.paper-trading {
  border-color: var(--accent-primary);
  background: rgba(88, 166, 255, 0.1);
}
.stage-icon.paper-trading .icon {
  color: var(--accent-primary);
}
.stage-icon.production {
  border-color: var(--accent-danger);
  background: rgba(239, 68, 68, 0.1);
}
.stage-icon.production .icon {
  color: var(--accent-danger);
}

.pipeline-stage.active .stage-icon {
  box-shadow:
    0 0 0 3px var(--accent-primary),
    0 0 20px rgba(88, 166, 255, 0.3);
  animation: pulse 2s infinite;
}

.pipeline-stage.completed .stage-icon {
  background: var(--success-bg);
  border-color: var(--accent-success);
}

.pipeline-stage.completed .stage-icon .icon {
  color: var(--accent-success);
}

.pipeline-stage.hasError .stage-icon {
  background: var(--danger-bg);
  border-color: var(--accent-danger);
}

.pipeline-stage.hasError .stage-icon .icon {
  color: var(--accent-danger);
}

@keyframes pulse {
  0%,
  100% {
    box-shadow:
      0 0 0 3px var(--accent-primary),
      0 0 20px rgba(88, 166, 255, 0.3);
  }
  50% {
    box-shadow:
      0 0 0 3px var(--accent-primary),
      0 0 30px rgba(88, 166, 255, 0.5);
  }
}

.stage-status-ring {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--bg-tertiary);
  border: 2px solid var(--border-color);
}

.stage-status-ring.running {
  background: var(--accent-primary);
  border-color: var(--accent-primary);
  animation: spin 1s linear infinite;
}

.stage-status-ring.active {
  background: var(--accent-success);
  border-color: var(--accent-success);
}

.stage-status-ring.idle {
  background: var(--bg-tertiary);
  border-color: var(--border-color);
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.stage-label {
  font-size: 0.7rem;
  font-weight: 600;
  text-align: center;
  color: var(--text-secondary);
  white-space: nowrap;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pipeline-stage.active .stage-label,
.pipeline-stage.completed .stage-label {
  color: var(--text-primary);
}

.pipeline-stage.hasError .stage-label {
  color: var(--accent-danger);
}

.stage-metrics {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 4px;
  margin-top: 2px;
}

.stage-metric {
  font-size: 0.6rem;
  font-family: var(--font-mono);
  padding: 1px 6px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-full);
  color: var(--text-secondary);
}

.stage-connector {
  width: 2px;
  height: 40px;
  background: var(--border-color);
  flex-shrink: 0;
  margin: 0 auto;
  position: relative;
}

.stage-connector.active {
  background: var(--accent-success);
}

.stage-connector::after {
  content: "";
  position: absolute;
  bottom: -8px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 8px solid var(--border-color);
}

.stage-connector.active::after {
  border-top-color: var(--accent-success);
}

/* Header actions */
.header-actions {
  margin-top: var(--space-md);
}

/* Card header flex */
.card-header-flex {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: var(--space-sm);
}

.aqde-status-container {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.health-status-badge {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: var(--radius-full);
}

.health-status-badge.healthy {
  background: var(--success-bg);
  color: var(--accent-success);
}
.health-status-badge.warning {
  background: var(--warning-bg);
  color: var(--accent-warning);
}
.health-status-badge.critical {
  background: var(--danger-bg);
  color: var(--accent-danger);
}

/* AQDE Progress */
.aqde-progress {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  margin-top: var(--space-sm);
}

.progress-bar-small {
  height: 6px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.progress-fill-small {
  height: 100%;
  background: var(--accent-primary);
  border-radius: var(--radius-full);
  transition: width var(--transition-normal);
}

.progress-text {
  font-size: 0.7rem;
  color: var(--text-secondary);
  text-align: center;
}

/* Mini Chart */
.mini-chart {
  margin-top: var(--space-sm);
}

.sparkline {
  width: 100%;
  height: 40px;
}

/* Score Bar */
.score-bar {
  width: 60px;
  height: 6px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.score-fill {
  height: 100%;
  background: var(--accent-warning);
  border-radius: var(--radius-full);
  transition: width var(--transition-normal);
}

.score-fill.good {
  background: var(--accent-success);
}

/* Event Source */
.event-source {
  font-size: 0.6rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text-muted);
  white-space: nowrap;
}

/* Responsive */
@media (max-width: 1024px) {
  .grid-4 {
    grid-template-columns: repeat(2, 1fr) !important;
  }

  .pipeline-visualization {
    flex-wrap: nowrap;
    overflow-x: auto;
    padding-bottom: var(--space-md);
  }

  .pipeline-stage {
    min-width: 120px;
  }
}

@media (max-width: 768px) {
  .grid-4 {
    grid-template-columns: 1fr !important;
  }

  .grid-2 {
    grid-template-columns: 1fr !important;
  }

  .metric-grid {
    grid-template-columns: 1fr !important;
  }

  .header-content {
    margin-bottom: var(--space-md);
  }
}
</style>
