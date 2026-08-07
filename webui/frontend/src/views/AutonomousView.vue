<template>
  <div class="autonomous-view">
    <div class="page-header">
      <div class="header-content">
        <h1 class="page-title">Modo Autónomo</h1>
        <p class="page-subtitle">
          Ejecución automática del ciclo AQDE de descubrimiento y validación
        </p>
      </div>
      <div class="header-actions">
        <ControlButtons
          :running="running"
          :autonomous-running="running"
          @start="startAutonomous"
          @stop="stopAutonomous"
          @autonomous="toggleAutonomous"
        />
      </div>
    </div>

    <!-- AQDE Lab Panel -->
    <AQDELabPanel />

    <!-- Configuration -->
    <Card title="Configuración">
      <div class="config-form">
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Símbolos</label>
            <MultiSelect
              v-model="config.symbols"
              :options="availableSymbols"
              placeholder="Seleccionar símbolos..."
            />
          </div>
          <div class="form-group">
            <label class="form-label">Máx. Iteraciones</label>
            <input
              v-model.number="config.max_iterations"
              type="number"
              class="form-input"
              min="1"
              max="100"
            />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Sharpe Mínimo</label>
            <input
              v-model.number="config.min_sharpe"
              type="number"
              class="form-input"
              min="0"
              step="0.1"
            />
          </div>
          <div class="form-group">
            <label class="form-label">Win Rate Mínimo (%)</label>
            <input
              v-model.number="config.min_win_rate"
              type="number"
              class="form-input"
              min="0"
              max="100"
              step="1"
            />
          </div>
          <div class="form-group">
            <label class="form-label">Max Drawdown (%)</label>
            <input
              v-model.number="config.max_drawdown"
              type="number"
              class="form-input"
              min="0"
              max="100"
              step="1"
            />
          </div>
        </div>
      </div>
    </Card>

    <!-- Recent Activity -->
    <Card title="Actividad Reciente">
      <div v-if="activity.length > 0" class="activity-list">
        <div
          v-for="act in activity"
          :key="act.timestamp"
          class="activity-item"
          :class="act.type"
        >
          <div class="activity-icon" :class="act.type">
            <component :is="getActivityIcon(act.type)" class="icon" />
          </div>
          <div class="activity-content">
            <div class="activity-message">{{ act.message }}</div>
            <div class="activity-time">{{ formatTime(act.timestamp) }}</div>
          </div>
          <span v-if="act.data?.iteration" class="activity-badge"
            >Iter {{ act.data.iteration }}</span
          >
        </div>
      </div>
      <div v-else class="empty-state">
        <IconActivity class="empty-icon" />
        <p>No hay actividad reciente. Inicia el modo autónomo para comenzar.</p>
      </div>
    </Card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useAutonomousStore } from "@/stores/autonomous";
import Card from "@/components/Card.vue";
import ControlButtons from "@/components/ControlButtons.vue";
import MultiSelect from "@/components/MultiSelect.vue";
import AQDELabPanel from "@/components/AQDELabPanel.vue";
import {
  Play,
  Square,
  Activity,
  RefreshCw,
  FileText,
  Check,
  Loader,
  AlertCircle,
  Info,
  CheckCircle,
} from "lucide-vue-next";

const store = useAutonomousStore();

const running = computed(() => store.running);
const phase = computed(() => store.phase);
const iteration = computed(() => store.iteration);
const maxIterations = computed(() => store.config.max_iterations);
const activeHypotheses = computed(() => store.activeHypotheses);
const progress = computed(() => store.progress);
const steps = computed(() => store.steps);
const activity = computed(() => store.activity);
const config = computed(() => store.config);
const starting = computed(() => store.starting);
const wsConnected = computed(() => store.wsConnected);

const availableSymbols = [
  "BTCUSDT",
  "ETHUSDT",
  "SOLUSDT",
  "ADAUSDT",
  "DOTUSDT",
  "LINKUSDT",
  "MATICUSDT",
  "AVAXUSDT",
];

function getActivityIcon(type) {
  const icons = {
    hypothesis_generated: FileText,
    validation_start: AlertCircle,
    validation_complete: CheckCircle,
    backtest_start: Loader,
    backtest_complete: CheckCircle,
    monte_carlo_start: Activity,
    monte_carlo_complete: CheckCircle,
    iteration_complete: CheckCircle,
    error: AlertCircle,
  };
  return icons[type] || Info;
}

function formatTime(isoString) {
  const date = new Date(isoString);
  return date.toLocaleTimeString("es-ES", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

async function startAutonomous() {
  await store.startAutonomous(config.value);
}

async function stopAutonomous() {
  await store.stopAutonomous();
}

async function toggleAutonomous() {
  if (running.value) {
    await stopAutonomous();
  } else {
    await startAutonomous();
  }
}

onMounted(() => {
  store.loadStatus();
  store.connect();
});

onUnmounted(() => {
  store.disconnect();
});
</script>

<style scoped>
.autonomous-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-md);
  margin-bottom: var(--space-md);
}

.header-content {
  flex: 1;
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

.header-actions {
  display: flex;
  gap: var(--space-sm);
}

/* Config Form */
.config-form {
  padding: var(--space-sm) 0;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
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

.form-input {
  padding: 0.5rem 0.75rem;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 0.875rem;
  transition: all var(--transition-fast);
}

.form-input:focus {
  outline: none;
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.2);
}

/* Activity List */
.activity-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.activity-item {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--border-color);
}

.activity-item.hypothesis_generated {
  border-left-color: var(--accent-info);
}
.activity-item.validation_start {
  border-left-color: var(--accent-warning);
}
.activity-item.validation_complete {
  border-left-color: var(--accent_success);
}
.activity-item.backtest_start {
  border-left-color: var(--accent-primary);
}
.activity-item.backtest_complete {
  border-left-color: var(--accent-success);
}
.activity-item.monte_carlo_start {
  border-left-color: var(--accent-secondary);
}
.activity-item.monte_carlo_complete {
  border-left-color: var(--accent-success);
}
.activity-item.iteration_complete {
  border-left-color: var(--accent-primary);
}
.activity-item.error {
  border-left-color: var(--accent-danger);
}

.activity-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.activity-icon.hypothesis_generated {
  background: var(--info-bg);
  color: var(--accent-info);
}
.activity-icon.validation_start {
  background: var(--warning-bg);
  color: var(--accent-warning);
}
.activity-icon.validation_complete {
  background: var(--success-bg);
  color: var(--accent-success);
}
.activity-icon.backtest_start {
  background: rgba(88, 166, 255, 0.1);
  color: var(--accent-primary);
}
.activity-icon.backtest_complete {
  background: var(--success-bg);
  color: var(--accent-success);
}
.activity-icon.monte_carlo_start {
  background: rgba(163, 113, 247, 0.1);
  color: var(--accent-secondary);
}
.activity-icon.monte_carlo_complete {
  background: var(--success-bg);
  color: var(--accent-success);
}
.activity-icon.iteration_complete {
  background: rgba(88, 166, 255, 0.1);
  color: var(--accent-primary);
}
.activity-icon.error {
  background: var(--danger-bg);
  color: var(--accent-danger);
}

.activity-icon .icon {
  width: 16px;
  height: 16px;
}

.activity-content {
  flex: 1;
  min-width: 0;
}

.activity-message {
  font-size: 0.8125rem;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.activity-time {
  font-size: 0.7rem;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.activity-badge {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--accent-primary);
  background: rgba(88, 166, 255, 0.1);
  padding: 2px 8px;
  border-radius: var(--radius-full);
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

/* Responsive */
@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .header-actions {
    flex-direction: column;
  }
}
</style>
