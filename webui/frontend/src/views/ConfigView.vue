<template>
  <div class="config-view">
    <div class="page-header">
      <h1 class="page-title">Configuración</h1>
      <p class="page-subtitle">Gestión de parámetros del sistema Quant-Math</p>
    </div>

    <div class="config-toolbar">
      <Button variant="secondary" :loading="loading" @click="loadConfig">
        <IconRefreshCw class="btn-icon" /> Recargar
      </Button>
      <Button variant="primary" :loading="saving" @click="saveConfig">
        <IconSave class="btn-icon" /> Guardar Cambios
      </Button>
      <Button variant="ghost" :disabled="saving" @click="resetConfig">
        <IconRotateCcw class="btn-icon" /> Restablecer
      </Button>
    </div>

    <div v-if="sections.length > 0" class="config-sections">
      <div
        v-for="section in sections"
        :key="section.name"
        class="config-section"
      >
        <Card :title="section.display_name">
          <div v-if="section.description" class="section-description">
            {{ section.description }}
          </div>

          <div class="parameters-grid">
            <ParameterField
              v-for="param in section.parameters"
              :key="param.key"
              :param="param"
              :section="section.name"
              :value="getValue(section.name, param.key)"
              @update="updateValue(section.name, param.key, $event)"
            />
          </div>
        </Card>
      </div>
    </div>

    <div v-else class="empty-state">
      <IconSettings class="empty-icon" />
      <p>No hay secciones de configuración disponibles</p>
    </div>

    <!-- Save confirmation toast -->
    <div v-show="showToast" class="toast" :class="toastType">
      <IconCheckCircle v-if="toastType === 'success'" class="toast-icon" />
      <IconAlertCircle v-else class="toast-icon" />
      <span>{{ toastMessage }}</span>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from "vue";
import { useConfigStore } from "@/stores/config";
import Card from "@/components/Card.vue";
import Button from "@/components/Button.vue";
import ParameterField from "@/components/ParameterField.vue";
import {
  RefreshCw,
  Save,
  RotateCcw,
  Settings,
  CheckCircle,
  AlertCircle,
} from "lucide-vue-next";

const store = useConfigStore();

const sections = computed(() => store.sections);
const loading = computed(() => store.loading);
const saving = computed(() => store.saving);
const config = computed(() => store.config);

const showToast = ref(false);
const toastMessage = ref("");
const toastType = ref("success");

function getValue(section, key) {
  return config.value[section]?.[key];
}

function updateValue(section, key, value) {
  store.updateValue(section, key, value);
}

async function loadConfig() {
  await store.loadConfig();
  showToastNotification("Configuración recargada", "success");
}

async function saveConfig() {
  const success = await store.saveConfig();
  if (success) {
    showToastNotification("Configuración guardada correctamente", "success");
  } else {
    showToastNotification("Error al guardar la configuración", "error");
  }
}

function resetConfig() {
  store.resetConfig();
  showToastNotification(
    "Configuración restablecida a valores por defecto",
    "success",
  );
}

function showToastNotification(message, type) {
  toastMessage.value = message;
  toastType.value = type;
  showToast.value = true;
  setTimeout(() => {
    showToast.value = false;
  }, 3000);
}

onMounted(() => {
  store.loadConfig();
});
</script>

<style scoped>
.config-view {
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

.config-toolbar {
  display: flex;
  gap: var(--space-sm);
  justify-content: flex-end;
}

.config-sections {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.section-description {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  margin-bottom: var(--space-md);
  padding-bottom: var(--space-sm);
  border-bottom: 1px solid var(--border-color);
}

.parameters-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-md);
}

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

.toast.success {
  background: var(--success-bg);
  color: var(--accent-success);
  border: 1px solid var(--success-border);
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

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-2xl);
  color: var(--text-muted);
  text-align: center;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}

.empty-icon {
  width: 64px;
  height: 64px;
  margin-bottom: var(--space-md);
  opacity: 0.5;
}

.empty-state p {
  font-size: 1rem;
  margin: 0;
}
</style>
