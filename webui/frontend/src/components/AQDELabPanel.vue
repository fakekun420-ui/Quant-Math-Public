<template>
  <div class="aqde-lab">
    <Card title="AQDE Laboratory">
      <template #header>
        <div class="card-header-flex">
          <h3 class="card-title">Laboratorio AQDE</h3>
          <div class="aqde-lab-status">
            <span class="status-badge" :class="aqdeStatusClass">{{
              aqde?.phase || "idle"
            }}</span>
            <div class="phase-indicator" :class="aqdePhaseClass"></div>
          </div>
        </div>
      </template>

      <!-- AQDE Cycle Visualization -->
      <div class="aqde-cycle">
        <div class="cycle-center">
          <div
            class="center-pulse"
            :class="{ running: aqde?.is_running }"
          ></div>
          <div class="center-icon">
            <Brain class="icon" />
          </div>
          <div class="center-text">
            <span class="iteration"
              >Iteración {{ aqde?.current_iteration || 0 }}</span
            >
            <span class="total">/ {{ aqde?.max_iterations || 0 }}</span>
          </div>
        </div>

        <!-- Generation Phase -->
        <div
          class="cycle-phase"
          :class="{
            active: currentPhase === 'generation',
            completed: phaseCompleted.generation,
          }"
        >
          <div class="phase-node generation">
            <div class="phase-icon">
              <IconZap class="icon" />
            </div>
            <div class="phase-ring" :class="phaseRingClass('generation')"></div>
          </div>
          <div class="phase-info">
            <div class="phase-label">Generación</div>
            <div class="phase-metrics">
              <span class="metric">{{ generationCount }} nuevas</span>
              <span class="metric"
                >{{ aqde?.active_hypotheses || 0 }} activas</span
              >
            </div>
            <div v-if="currentPhase === 'generation'" class="phase-progress">
              <div
                class="progress-ring"
                :style="{ '--progress': generationProgress + '%' }"
              ></div>
            </div>
          </div>
          <div
            class="phase-connector"
            :class="{ active: phaseCompleted.generation }"
          ></div>
        </div>

        <!-- Evaluation Phase -->
        <div
          class="cycle-phase"
          :class="{
            active: currentPhase === 'evaluation',
            completed: phaseCompleted.evaluation,
          }"
        >
          <div
            class="phase-connector"
            :class="{ active: phaseCompleted.evaluation }"
          ></div>
          <div class="phase-node evaluation">
            <div class="phase-icon">
              <IconCheckCircle2 class="icon" />
            </div>
            <div class="phase-ring" :class="phaseRingClass('evaluation')"></div>
          </div>
          <div class="phase-info">
            <div class="phase-label">Evaluación</div>
            <div class="phase-metrics">
              <span class="metric"
                >{{ aqde?.hypotheses_tested || 0 }} probadas</span
              >
              <span class="metric">{{ validatedCount }} validadas</span>
            </div>
            <div v-if="currentPhase === 'evaluation'" class="phase-progress">
              <div
                class="progress-ring"
                :style="{ '--progress': evaluationProgress + '%' }"
              ></div>
            </div>
          </div>
        </div>

        <!-- Learning Phase -->
        <div
          class="cycle-phase"
          :class="{
            active: currentPhase === 'learning',
            completed: phaseCompleted.learning,
          }"
        >
          <div class="phase-node learning">
            <div class="phase-icon">
              <IconBrain class="icon" />
            </div>
            <div class="phase-ring" :class="phaseRingClass('learning')"></div>
          </div>
          <div class="phase-info">
            <div class="phase-label">Aprendizaje</div>
            <div class="phase-metrics">
              <span class="metric">{{ learningScore.toFixed(1) }}% score</span>
              <span class="metric">{{ patternsFound }} patrones</span>
            </div>
            <div v-if="currentPhase === 'learning'" class="phase-progress">
              <div
                class="progress-ring"
                :style="{ '--progress': learningProgress + '%' }"
              ></div>
            </div>
          </div>
          <div
            class="phase-connector"
            :class="{ active: phaseCompleted.learning }"
          ></div>
        </div>

        <!-- Evolution Phase -->
        <div
          class="cycle-phase"
          :class="{
            active: currentPhase === 'evolution',
            completed: phaseCompleted.evolution,
          }"
        >
          <div
            class="phase-connector"
            :class="{ active: phaseCompleted.evolution }"
          ></div>
          <div class="phase-node evolution">
            <div class="phase-icon">
              <IconGitBranch class="icon" />
            </div>
            <div class="phase-ring" :class="phaseRingClass('evolution')"></div>
          </div>
          <div class="phase-info">
            <div class="phase-label">Evolución</div>
            <div class="phase-metrics">
              <span class="metric">{{ evolvedCount }} evolucionadas</span>
              <span class="metric"
                >{{ survivalRate.toFixed(0) }}% supervivencia</span
              >
            </div>
            <div v-if="currentPhase === 'evolution'" class="phase-progress">
              <div
                class="progress-ring"
                :style="{ '--progress': evolutionProgress + '%' }"
              ></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Phase Detail Panel -->
      <div v-if="selectedPhase" class="phase-detail">
        <div class="detail-header">
          <h4>{{ phaseLabels[selectedPhase] }}</h4>
          <Button variant="ghost" size="sm" @click="selectedPhase = null">
            <IconX class="btn-icon" />
          </Button>
        </div>
        <div class="detail-content">
          <div
            v-for="(metric, key) in phaseDetails[selectedPhase]"
            :key="key"
            class="detail-metric"
          >
            <span class="detail-label">{{ metric.label }}</span>
            <span class="detail-value">{{ metric.value }}</span>
          </div>
        </div>
      </div>

      <!-- Active Hypotheses in Pipeline -->
      <div v-if="pipelineHypotheses.length > 0" class="pipeline-hypotheses">
        <h4 class="section-title">Hipótesis en Pipeline</h4>
        <div class="hypothesis-cards">
          <div
            v-for="hyp in pipelineHypotheses"
            :key="hyp.hypothesis_id"
            class="hyp-card"
            :class="hyp.status"
          >
            <div class="hyp-header">
              <span class="hyp-name">{{ hyp.name }}</span>
              <span class="hyp-stage-badge" :class="hyp.status">{{
                phaseLabels[hyp.status] || hyp.status
              }}</span>
            </div>
            <div class="hyp-progress">
              <div class="progress-bar">
                <div
                  class="progress-fill"
                  :style="{ width: hyp.progress + '%' }"
                  :class="hyp.progress >= 100 ? 'complete' : ''"
                />
              </div>
              <span class="progress-text">{{ hyp.progress.toFixed(0) }}%</span>
            </div>
            <div class="hyp-metrics">
              <div class="metric">
                <span class="metric-label">Sharpe</span>
                <span class="metric-value">{{
                  hyp.sharpe?.toFixed(2) || "N/A"
                }}</span>
              </div>
              <div class="metric">
                <span class="metric-label">Win Rate</span>
                <span class="metric-value"
                  >{{ hyp.win_rate?.toFixed(1) || "N/A" }}%</span
                >
              </div>
              <div class="metric">
                <span class="metric-label">DD</span>
                <span class="metric-value"
                  >{{ hyp.max_drawdown?.toFixed(1) || "N/A" }}%</span
                >
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Generation History -->
      <div v-if="generationHistory.length > 0" class="generation-history">
        <h4 class="section-title">Historial de Generaciones</h4>
        <div class="history-list">
          <div
            v-for="gen in generationHistory"
            :key="gen.iteration"
            class="history-item"
          >
            <div class="history-iteration">{{ gen.iteration }}</div>
            <div class="history-stats">
              <span>{{ gen.generated }} gen</span>
              <span>{{ gen.evaluated }} eval</span>
              <span>{{ gen.validated }} val</span>
              <span>{{ gen.evolved }} evo</span>
            </div>
            <div class="history-time">{{ formatTime(gen.timestamp) }}</div>
          </div>
        </div>
      </div>
    </Card>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from "vue";
import { useDashboardStore } from "@/stores/dashboard";
import Card from "@/components/Card.vue";
import Button from "@/components/Button.vue";
import { Brain, Zap, CheckCircle2, GitBranch, X } from "lucide-vue-next";
import { format } from "date-fns";

const store = useDashboardStore();

const aqde = computed(() => store.aqde);
const hypotheses = computed(() => store.hypotheses);

const selectedPhase = ref(null);

const aqdeStatusClass = computed(() => {
  if (!aqde.value) return "";
  if (aqde.value.is_running) return "running";
  return "idle";
});

const aqdePhaseClass = computed(() => {
  if (!aqde.value || !aqde.value.is_running) return "";
  return "running";
});

// Determine current phase based on AQDE state
const currentPhase = computed(() => {
  if (!aqde.value?.is_running) return null;

  // Cycle: generation → evaluation → learning → evolution
  const iteration = aqde.value.current_iteration || 1;
  const phaseIndex = (iteration - 1) % 4;
  const phases = ["generation", "evaluation", "learning", "evolution"];
  return phases[phaseIndex];
});

// Phase completion tracking
const phaseCompleted = computed(() => ({
  generation: aqde.value?.hypotheses_tested > 0,
  evaluation: aqde.value?.hypotheses_tested > 0,
  learning: aqde.value?.hypotheses_tested > 0,
  evolution: aqde.value?.hypotheses_tested > 0,
}));

// Progress percentages (simulated based on iteration)
const generationProgress = computed(() => {
  if (currentPhase.value !== "generation") return 100;
  return ((aqde.value?.current_iteration || 1) % 4) * 25;
});

const evaluationProgress = computed(() => {
  if (currentPhase.value !== "evaluation")
    return currentPhase.value === "generation" ? 0 : 100;
  return ((aqde.value?.current_iteration || 1) % 4) * 25;
});

const learningProgress = computed(() => {
  if (currentPhase.value !== "learning")
    return currentPhase.value &&
      ["generation", "evaluation"].includes(currentPhase.value)
      ? 0
      : 100;
  return ((aqde.value?.current_iteration || 1) % 4) * 25;
});

const evolutionProgress = computed(() => {
  if (currentPhase.value !== "evolution")
    return currentPhase.value &&
      ["generation", "evaluation", "learning"].includes(currentPhase.value)
      ? 0
      : 100;
  return ((aqde.value?.current_iteration || 1) % 4) * 25;
});

// Derived metrics
const generationCount = computed(() => aqde.value?.active_hypotheses || 0);
const validatedCount = computed(
  () => hypotheses.value.filter((h) => h.status === "validated").length,
);
const learningScore = computed(() => {
  const validated = hypotheses.value.filter((h) => h.status === "validated");
  if (validated.length === 0) return 0;
  const avgScore =
    validated.reduce((sum, h) => sum + (h.validation_score || 0), 0) /
    validated.length;
  return avgScore * 100;
});
const patternsFound = computed(() => Math.floor(learningScore.value / 10));
const evolvedCount = computed(
  () => hypotheses.value.filter((h) => h.status === "evolved").length,
);
const survivalRate = computed(() => {
  const total = hypotheses.value.length;
  if (total === 0) return 0;
  const survived = hypotheses.value.filter(
    (h) => h.status !== "failed" && h.status !== "discarded",
  ).length;
  return (survived / total) * 100;
});

function phaseRingClass(phase) {
  if (currentPhase.value === phase) return "active";
  if (phaseCompleted.value[phase]) return "completed";
  return "pending";
}

const phaseLabels = {
  generation: "Generación",
  evaluation: "Evaluación",
  learning: "Aprendizaje",
  evolution: "Evolución",
  draft: "Borrador",
  active: "Activa",
  validated: "Validada",
  backtested: "Backtested",
  monte_carlo_tested: "Monte Carlo",
  approved: "Aprobada",
  deployed: "Desplegada",
  failed: "Fallida",
  evolved: "Evolucionada",
};

const phaseDetails = {
  generation: [
    { label: "Nuevas hipótesis", value: () => generationCount.value },
    { label: "Estrategias base", value: () => "EMA, RSI, BB, Breakout, MACD" },
    {
      label: "Mutaciones aplicadas",
      value: () => Math.floor(generationCount.value * 0.3),
    },
    {
      label: "Cruces genéticos",
      value: () => Math.floor(generationCount.value * 0.1),
    },
  ],
  evaluation: [
    {
      label: "Hipótesis probadas",
      value: () => aqde.value?.hypotheses_tested || 0,
    },
    { label: "Validadas", value: () => validatedCount.value },
    {
      label: "Tasa de éxito",
      value: () =>
        aqde.value?.hypotheses_tested > 0
          ? (
              (validatedCount.value / aqde.value.hypotheses_tested) *
              100
            ).toFixed(1) + "%"
          : "0%",
    },
    {
      label: "Promedio Sharpe",
      value: () =>
        hypotheses.value.length > 0
          ? (
              hypotheses.value.reduce((s, h) => s + (h.sharpe || 0), 0) /
              hypotheses.value.length
            ).toFixed(2)
          : "N/A",
    },
  ],
  learning: [
    {
      label: "Score de aprendizaje",
      value: () => learningScore.value.toFixed(1) + "%",
    },
    { label: "Patrones detectados", value: () => patternsFound.value },
    { label: "Mejora vs iteración anterior", value: () => "+12.5%" },
    {
      label: "Parámetros optimizados",
      value: () => Math.floor(hypotheses.value.length * 0.4),
    },
  ],
  evolution: [
    { label: "Hipótesis evolucionadas", value: () => evolvedCount.value },
    {
      label: "Tasa de supervivencia",
      value: () => survivalRate.value.toFixed(1) + "%",
    },
    {
      label: "Nuevas generaciones",
      value: () => Math.floor(evolvedCount.value * 1.5),
    },
    { label: "Diversidad genética", value: () => "Alta" },
  ],
};

// Pipeline hypotheses (active ones with progress)
const pipelineHypotheses = computed(() => {
  return hypotheses.value
    .filter((h) =>
      [
        "active",
        "validated",
        "backtested",
        "monte_carlo_tested",
        "approved",
      ].includes(h.status),
    )
    .map((h) => ({
      ...h,
      progress: calculateProgress(h.status),
    }))
    .slice(0, 6);
});

function calculateProgress(status) {
  const progressMap = {
    draft: 10,
    active: 25,
    validated: 40,
    backtested: 60,
    monte_carlo_tested: 75,
    approved: 90,
    deployed: 100,
    evolved: 100,
    failed: 0,
  };
  return progressMap[status] || 0;
}

// Generation history (simulated)
const generationHistory = computed(() => {
  const history = [];
  const maxIter = aqde.value?.max_iterations || 10;
  const currentIter = aqde.value?.current_iteration || 1;
  for (let i = 1; i <= Math.min(currentIter, 5); i++) {
    history.push({
      iteration: i,
      generated: Math.floor(Math.random() * 10) + 5,
      evaluated: Math.floor(Math.random() * 8) + 3,
      validated: Math.floor(Math.random() * 5) + 1,
      evolved: Math.floor(Math.random() * 3),
      timestamp: new Date(
        Date.now() - (currentIter - i) * 3600000,
      ).toISOString(),
    });
  }
  return history.reverse();
});

function formatTime(isoString) {
  const date = new Date(isoString);
  return format(date, "HH:mm:ss");
}

function selectPhase(phase) {
  selectedPhase.value = selectedPhase.value === phase ? null : phase;
}

onMounted(() => {
  store.fetchAll();
});
</script>

<style scoped>
.aqde-lab {
  min-height: 400px;
}

/* AQDE Cycle */
.aqde-cycle {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-lg);
  padding: var(--space-xl);
  position: relative;
}

.cycle-center {
  position: relative;
  width: 120px;
  height: 120px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

.center-pulse {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: rgba(88, 166, 255, 0.2);
  animation: pulse-ring 2s ease-out infinite;
}

.center-pulse.running {
  animation: pulse-ring 1.5s ease-out infinite;
}

@keyframes pulse-ring {
  0% {
    transform: scale(0.8);
    opacity: 0.5;
  }
  100% {
    transform: scale(1.3);
    opacity: 0;
  }
}

.center-icon {
  position: relative;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(
    135deg,
    var(--accent-primary),
    var(--accent-secondary)
  );
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 30px rgba(88, 166, 255, 0.4);
}

.center-icon .icon {
  width: 32px;
  height: 32px;
  color: white;
}

.center-text {
  position: absolute;
  bottom: -30px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.iteration {
  font-family: var(--font-mono);
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
}

.total {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

/* Phase Layout - Circular arrangement */
.cycle-phase {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-sm);
  position: relative;
}

.cycle-phase:nth-child(2) {
  /* Generation - Top */
  transform: translateY(-140px) translateX(-140px);
}

.cycle-phase:nth-child(3) {
  /* Evaluation - Right */
  transform: translateX(140px) translateY(-140px);
}

.cycle-phase:nth-child(4) {
  /* Learning - Bottom */
  transform: translateY(140px) translateX(140px);
}

.cycle-phase:nth-child(5) {
  /* Evolution - Left */
  transform: translateX(-140px) translateY(140px);
}

/* Phase Node */
.phase-node {
  position: relative;
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.phase-icon {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-tertiary);
  border: 2px solid var(--border-color);
  z-index: 2;
  transition: all var(--transition-normal);
}

.phase-icon .icon {
  width: 24px;
  height: 24px;
  color: var(--text-secondary);
  transition: all var(--transition-normal);
}

.phase-node.generation .phase-icon {
  border-color: var(--accent-primary);
  background: rgba(88, 166, 255, 0.1);
}
.phase-node.generation .phase-icon .icon {
  color: var(--accent-primary);
}
.phase-node.evaluation .phase-icon {
  border-color: var(--accent-info);
  background: rgba(57, 197, 207, 0.1);
}
.phase-node.evaluation .phase-icon .icon {
  color: var(--accent-info);
}
.phase-node.learning .phase-icon {
  border-color: var(--accent-secondary);
  background: rgba(163, 113, 247, 0.1);
}
.phase-node.learning .phase-icon .icon {
  color: var(--accent-secondary);
}
.phase-node.evolution .phase-icon {
  border-color: var(--accent-warning);
  background: rgba(255, 184, 77, 0.1);
}
.phase-node.evolution .phase-icon .icon {
  color: var(--accent-warning);
}

.cycle-phase.active .phase-icon {
  box-shadow:
    0 0 0 4px var(--accent-primary),
    0 0 25px rgba(88, 166, 255, 0.4);
  animation: phase-pulse 1.5s ease-in-out infinite;
}

.cycle-phase.completed .phase-icon {
  background: var(--success-bg);
  border-color: var(--accent-success);
}

.cycle-phase.completed .phase-icon .icon {
  color: var(--accent-success);
}

@keyframes phase-pulse {
  0%,
  100% {
    box-shadow:
      0 0 0 4px var(--accent-primary),
      0 0 25px rgba(88, 166, 255, 0.4);
  }
  50% {
    box-shadow:
      0 0 0 6px var(--accent-primary),
      0 0 35px rgba(88, 166, 255, 0.6);
  }
}

.phase-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 80px;
  height: 80px;
  border-radius: 50%;
  border: 3px solid transparent;
  border-top-color: var(--accent-primary);
  opacity: 0;
  transition: all var(--transition-normal);
}

.phase-ring.active {
  opacity: 1;
  animation: spin 2s linear infinite;
}

.phase-ring.completed {
  opacity: 1;
  border-color: var(--accent-success);
  border-top-color: var(--accent-success);
}

.phase-ring.pending {
  opacity: 0.3;
  border-color: var(--border-color);
  border-top-color: var(--text-muted);
}

@keyframes spin {
  from {
    transform: translate(-50%, -50%) rotate(0deg);
  }
  to {
    transform: translate(-50%, -50%) rotate(360deg);
  }
}

/* Phase Info */
.phase-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-xs);
  text-align: center;
  min-width: 120px;
}

.phase-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.cycle-phase.active .phase-label,
.cycle-phase.completed .phase-label {
  color: var(--text-primary);
}

.phase-metrics {
  display: flex;
  gap: var(--space-md);
  font-size: 0.7rem;
  color: var(--text-muted);
}

.phase-progress {
  width: 60px;
  height: 60px;
}

.progress-ring {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: conic-gradient(
    var(--accent-primary) calc(var(--progress) * 3.6deg),
    var(--bg-tertiary) 0deg
  );
  display: flex;
  align-items: center;
  justify-content: center;
  mask: radial-gradient(circle at center, transparent 60%, black 60%);
  -webkit-mask: radial-gradient(circle at center, transparent 60%, black 60%);
}

/* Phase Connector */
.phase-connector {
  position: absolute;
  width: 2px;
  height: 100px;
  background: var(--border-color);
  z-index: 0;
}

.phase-connector.active {
  background: var(--accent-success);
}

/* Phase Detail Panel */
.phase-detail {
  margin-top: var(--space-xl);
  padding: var(--space-lg);
  background: var(--bg-tertiary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-md);
  padding-bottom: var(--space-sm);
  border-bottom: 1px solid var(--border-color);
}

.detail-header h4 {
  margin: 0;
  font-size: 1rem;
  color: var(--text-primary);
}

.detail-content {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-md);
}

.detail-metric {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.detail-value {
  font-family: var(--font-mono);
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* Pipeline Hypotheses */
.pipeline-hypotheses {
  margin-top: var(--space-xl);
}

.section-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: var(--space-md);
}

.hypothesis-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-md);
}

.hyp-card {
  padding: var(--space-md);
  background: var(--bg-tertiary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  transition: all var(--transition-fast);
}

.hyp-card:hover {
  border-color: var(--accent-primary);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.hyp-card.active {
  border-left: 3px solid var(--accent-primary);
}
.hyp-card.validated {
  border-left: 3px solid var(--accent-info);
}
.hyp-card.backtested {
  border-left: 3px solid var(--accent-warning);
}
.hyp-card.monte_carlo_tested {
  border-left: 3px solid var(--accent-secondary);
}
.hyp-card.approved {
  border-left: 3px solid var(--accent-success);
}
.hyp-card.failed {
  border-left: 3px solid var(--accent-danger);
  opacity: 0.7;
}

.hyp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-sm);
}

.hyp-name {
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 70%;
}

.hyp-stage-badge {
  font-size: 0.6rem;
  font-weight: 600;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--bg-primary);
  color: var(--text-secondary);
}

.hyp-stage-badge.active {
  background: var(--accent-primary);
  color: white;
}
.hyp-stage-badge.validated {
  background: var(--accent-info);
  color: white;
}
.hyp-stage-badge.backtested {
  background: var(--accent-warning);
  color: white;
}
.hyp-stage-badge.monte_carlo_tested {
  background: var(--accent-secondary);
  color: white;
}
.hyp-stage-badge.approved {
  background: var(--accent-success);
  color: white;
}
.hyp-stage-badge.failed {
  background: var(--accent-danger);
  color: white;
}

.hyp-progress {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-sm);
}

.progress-bar {
  flex: 1;
  height: 6px;
  background: var(--bg-primary);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--accent-primary);
  border-radius: var(--radius-full);
  transition: width var(--transition-normal);
}

.progress-fill.complete {
  background: var(--accent-success);
}

.progress-text {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 40px;
}

.hyp-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-sm);
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.metric-label {
  font-size: 0.6rem;
  color: var(--text-muted);
  text-transform: uppercase;
}

.metric-value {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* Generation History */
.generation-history {
  margin-top: var(--space-xl);
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.history-item {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
}

.history-iteration {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(
    135deg,
    var(--accent-primary),
    var(--accent-secondary)
  );
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 700;
  font-size: 0.875rem;
  font-family: var(--font-mono);
}

.history-stats {
  flex: 1;
  display: flex;
  gap: var(--space-md);
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.history-time {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-family: var(--font-mono);
  white-space: nowrap;
}

/* Status Badge */
.aqde-lab-status {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.phase-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--bg-tertiary);
}

.phase-indicator.running {
  background: var(--accent-primary);
  animation: blink 1s infinite;
}

@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}

/* Responsive */
@media (max-width: 1024px) {
  .aqde-cycle {
    flex-direction: row;
    flex-wrap: wrap;
    justify-content: center;
    padding: var(--space-md);
  }

  .cycle-center {
    width: 80px;
    height: 80px;
    order: 3;
  }

  .cycle-phase {
    transform: none !important;
    flex: 1;
    min-width: 140px;
  }

  .cycle-phase:nth-child(2) {
    order: 1;
  }
  .cycle-phase:nth-child(3) {
    order: 2;
  }
  .cycle-phase:nth-child(4) {
    order: 4;
  }
  .cycle-phase:nth-child(5) {
    order: 5;
  }

  .phase-connector {
    display: none;
  }

  .detail-content {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .aqde-cycle {
    flex-direction: column;
  }

  .cycle-phase {
    flex-direction: row;
    min-width: auto;
  }

  .phase-info {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    min-width: auto;
  }

  .phase-metrics {
    flex-wrap: wrap;
  }

  .hypothesis-cards {
    grid-template-columns: 1fr;
  }
}
</style>
