<template>
  <div class="control-buttons">
    <Button
      variant="primary"
      size="sm"
      :loading="starting"
      @click="$emit('start')"
    >
      <IconPlay class="btn-icon" /> Iniciar Quant-Math
    </Button>
    <Button
      variant="danger"
      size="sm"
      :disabled="!running"
      :loading="stopping"
      @click="$emit('stop')"
    >
      <IconSquare class="btn-icon" /> Detener
    </Button>
    <Button
      variant="secondary"
      size="sm"
      :disabled="!running"
      :loading="restarting"
      @click="$emit('restart')"
    >
      <IconRotateCw class="btn-icon" /> Reiniciar
    </Button>
    <Button
      variant="primary"
      size="sm"
      :loading="autonomousLoading"
      @click="$emit('autonomous')"
    >
      <IconBrain class="btn-icon" />
      {{ autonomousRunning ? "Modo Autónomo: ACTIVO" : "Modo Autónomo" }}
    </Button>
    <Button
      variant="secondary"
      size="sm"
      :disabled="running"
      @click="$emit('backtest')"
    >
      <IconBarChart2 class="btn-icon" /> Backtest
    </Button>
    <Button variant="outline" size="sm" disabled @click="$emit('real-trading')">
      <IconServer class="btn-icon" /> Trading Real (Bybit) - Deshabilitado
    </Button>
  </div>
</template>

<script setup>
import { ref } from "vue";
import {
  Play,
  Square,
  RotateCw,
  Brain,
  BarChart2,
  Server,
} from "lucide-vue-next";

const props = defineProps({
  running: Boolean,
  autonomousRunning: Boolean,
});

const emit = defineEmits([
  "start",
  "stop",
  "restart",
  "autonomous",
  "backtest",
  "real-trading",
]);

const starting = ref(false);
const stopping = ref(false);
const restarting = ref(false);
const autonomousLoading = ref(false);

async function emitStart() {
  starting.value = true;
  emit("start");
  setTimeout(() => (starting.value = false), 1000);
}

async function emitStop() {
  stopping.value = true;
  emit("stop");
  setTimeout(() => (stopping.value = false), 1000);
}

async function emitRestart() {
  restarting.value = true;
  emit("restart");
  setTimeout(() => (restarting.value = false), 1000);
}

async function emitAutonomous() {
  autonomousLoading.value = true;
  emit("autonomous");
  setTimeout(() => (autonomousLoading.value = false), 1000);
}

async function emitBacktest() {
  emit("backtest");
}

async function emitRealTrading() {
  emit("real-trading");
}
</script>

<style scoped>
.control-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-sm);
}

@media (max-width: 768px) {
  .control-buttons {
    flex-direction: column;
  }

  .control-buttons .btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
