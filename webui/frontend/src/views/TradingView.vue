<template>
  <div class="trading-view">
    <div class="page-header">
      <div class="header-content">
        <h1 class="page-title">
          <IconAlertTriangle class="title-icon warning" />
          Trading Real (Bybit)
        </h1>
        <p class="page-subtitle">
          Conexión con exchange real - FUNCIÓN EXPERIMENTAL
        </p>
      </div>
    </div>

    <!-- Warning Banner -->
    <div class="warning-banner">
      <div class="warning-icon">
        <IconAlertTriangle class="icon" />
      </div>
      <div class="warning-content">
        <h3 class="warning-title">⚠️ ADVERTENCIA CRÍTICA</h3>
        <ul class="warning-list">
          <li>
            Esta funcionalidad está <strong>DESHABILITADA POR DEFECTO</strong>
          </li>
          <li>
            El trading real implica <strong>RIESGO FINANCIERO REAL</strong>
          </li>
          <li>
            Solo habilite después de <strong>PRUEBAS EXHAUSTIVAS</strong> en
            paper trading
          </li>
          <li>
            El sistema <strong>NO GARANTIZA BENEFICIOS</strong> - puede perder
            capital
          </li>
          <li>Uso bajo su <strong>PROPIA RESPONSABILIDAD EXCLUSIVA</strong></li>
        </ul>
      </div>
    </div>

    <!-- Status Card -->
    <Card title="Estado de Conexión">
      <div class="status-grid">
        <div class="status-item">
          <span class="status-label">Estado</span>
          <span
            class="status-value"
            :class="tradingStatus.enabled ? 'enabled' : 'disabled'"
          >
            {{ tradingStatus.enabled ? "HABILITADO" : "DESHABILITADO" }}
          </span>
        </div>
        <div class="status-item">
          <span class="status-label">Exchange</span>
          <span class="status-value">{{ tradingStatus.exchange }}</span>
        </div>
        <div class="status-item">
          <span class="status-label">Modo</span>
          <span v-if="tradingStatus.sandbox_mode" class="status-value sandbox"
            >Sandbox</span
          >
          <span v-else class="status-value live">LIVE</span>
        </div>
        <div class="status-item">
          <span class="status-label">Balance Paper</span>
          <span class="status-value">{{
            formatCurrency(tradingStatus.paper_balance)
          }}</span>
        </div>
        <div class="status-item">
          <span class="status-label">Balance Real</span>
          <span class="status-value real">{{
            formatCurrency(tradingStatus.real_balance)
          }}</span>
        </div>
        <div class="status-item">
          <span class="status-label">Órdenes Abiertas</span>
          <span class="status-value">{{ tradingStatus.open_orders }}</span>
        </div>
        <div class="status-item">
          <span class="status-label">PnL Hoy</span>
          <span
            class="status-value"
            :class="tradingStatus.today_pnl >= 0 ? 'positive' : 'negative'"
          >
            {{ tradingStatus.today_pnl >= 0 ? "+" : ""
            }}{{ formatCurrency(tradingStatus.today_pnl) }}
          </span>
        </div>
      </div>
    </Card>

    <!-- Enable Form -->
    <Card v-if="!tradingStatus.enabled" title="Habilitar Trading Real">
      <div class="enable-form">
        <p class="enable-warning">
          Para habilitar el trading real, debe confirmar explícitamente que
          entiende los riesgos.
        </p>

        <div class="checkbox-group">
          <label class="checkbox-label">
            <input
              v-model="confirmations.understood_risks"
              type="checkbox"
              class="checkbox-input"
            />
            <span class="checkbox-text"
              >Entiendo que puedo perder dinero real</span
            >
          </label>
          <label class="checkbox-label">
            <input
              v-model="confirmations.tested_paper"
              type="checkbox"
              class="checkbox-input"
            />
            <span class="checkbox-text"
              >He probado exhaustivamente en paper trading</span
            >
          </label>
          <label class="checkbox-label">
            <input
              v-model="confirmations.api_configured"
              type="checkbox"
              class="checkbox-input"
            />
            <span class="checkbox-text"
              >Mis API keys de Bybit están configuradas correctamente</span
            >
          </label>
          <label class="checkbox-label">
            <input
              v-model="confirmations.accept_responsibility"
              type="checkbox"
              class="checkbox-input"
            />
            <span class="checkbox-text"
              >Acepto responsabilidad total por mis decisiones de trading</span
            >
          </label>
        </div>

        <div class="api-config">
          <h4>Configuración Bybit API</h4>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">API Key</label>
              <input
                v-model="apiConfig.api_key"
                type="password"
                class="form-input"
                placeholder="Ingrese API Key"
              />
            </div>
            <div class="form-group">
              <label class="form-label">API Secret</label>
              <input
                v-model="apiConfig.api_secret"
                type="password"
                class="form-input"
                placeholder="Ingrese API Secret"
              />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Testnet / Sandbox</label>
            <div class="param-toggle">
              <input
                id="testnet-toggle"
                v-model="apiConfig.testnet"
                type="checkbox"
                class="toggle-input"
              />
              <label for="testnet-toggle" class="toggle-switch">
                <span class="toggle-thumb" />
              </label>
              <span class="toggle-label"
                >Usar Testnet (Recomendado para pruebas)</span
              >
            </div>
          </div>
        </div>

        <Button
          variant="danger"
          :loading="enabling"
          :disabled="
            !allConfirmed || !apiConfig.api_key || !apiConfig.api_secret
          "
          class="w-full"
          @click="enableTrading"
        >
          <IconUnlock class="btn-icon" /> Habilitar Trading Real
        </Button>
      </div>
    </Card>

    <!-- Active Trading Panel -->
    <Card v-if="tradingStatus.enabled" title="Panel de Trading Activo">
      <div class="active-trading">
        <div class="trading-controls">
          <Button variant="danger" @click="disableTrading">
            <IconLock class="btn-icon" /> Deshabilitar Trading Real
          </Button>
          <Button variant="ghost" class="emergency-btn" @click="emergencyStop">
            <IconX class="btn-icon" /> PARADA DE EMERGENCIA
          </Button>
        </div>

        <div v-if="positions.length > 0" class="positions-table">
          <table class="monitor-table">
            <thead>
              <tr>
                <th>Símbolo</th>
                <th>Lado</th>
                <th>Tamaño</th>
                <th>Entrada</th>
                <th>Actual</th>
                <th>PnL</th>
                <th>PnL %</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="pos in positions" :key="pos.symbol">
                <td>{{ pos.symbol }}</td>
                <td>
                  <span class="trade-side" :class="pos.side">{{
                    pos.side.toUpperCase()
                  }}</span>
                </td>
                <td>{{ pos.size }}</td>
                <td>{{ pos.entry_price.toFixed(2) }}</td>
                <td>{{ pos.current_price.toFixed(2) }}</td>
                <td :class="pos.pnl >= 0 ? 'positive' : 'negative'">
                  {{ pos.pnl >= 0 ? "+" : "" }}{{ pos.pnl.toFixed(2) }}
                </td>
                <td :class="pos.pnl_pct >= 0 ? 'positive' : 'negative'">
                  {{ pos.pnl_pct >= 0 ? "+" : "" }}{{ pos.pnl_pct.toFixed(2) }}%
                </td>
                <td>
                  <Button
                    size="sm"
                    variant="ghost"
                    @click="closePosition(pos.symbol)"
                  >
                    <IconX class="btn-icon" /> Cerrar
                  </Button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty-state">
          <IconPackage class="empty-icon" />
          <p>No hay posiciones abiertas</p>
        </div>
      </div>
    </Card>

    <!-- Risk Limits -->
    <Card title="Límites de Riesgo (Configurables)">
      <div class="risk-limits">
        <div class="limit-item">
          <span class="limit-label">Max Posición (%)</span>
          <input
            v-model.number="riskLimits.max_position_pct"
            type="number"
            class="form-input"
            min="1"
            max="100"
            step="1"
          />
        </div>
        <div class="limit-item">
          <span class="limit-label">Max Drawdown Diario (%)</span>
          <input
            v-model.number="riskLimits.max_daily_drawdown"
            type="number"
            class="form-input"
            min="1"
            max="50"
            step="1"
          />
        </div>
        <div class="limit-item">
          <span class="limit-label">Max Operaciones/Día</span>
          <input
            v-model.number="riskLimits.max_trades_per_day"
            type="number"
            class="form-input"
            min="1"
            max="100"
            step="1"
          />
        </div>
        <div class="limit-item">
          <span class="limit-label">Stop Loss Global (%)</span>
          <input
            v-model.number="riskLimits.global_stop_loss"
            type="number"
            class="form-input"
            min="1"
            max="100"
            step="1"
          />
        </div>
      </div>
    </Card>

    <!-- Toast -->
    <div v-show="showToast" class="toast" :class="toastType">
      <IconCheckCircle v-if="toastType === 'success'" class="toast-icon" />
      <IconAlertCircle v-else class="toast-icon" />
      <span>{{ toastMessage }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useTradingStore } from "@/stores/trading";
import Card from "@/components/Card.vue";
import Button from "@/components/Button.vue";
import {
  AlertTriangle,
  Unlock,
  Lock,
  X,
  CheckCircle,
  AlertCircle,
  Package,
} from "lucide-vue-next";

const store = useTradingStore();

const tradingStatus = computed(() => store.status);
const positions = computed(() => store.positions);
const riskLimits = computed(() => store.riskLimits);
const enabling = computed(() => store.enabling);

const confirmations = ref({
  understood_risks: false,
  tested_paper: false,
  api_configured: false,
  accept_responsibility: false,
});

const apiConfig = ref({
  api_key: "",
  api_secret: "",
  testnet: true,
});

const showToast = ref(false);
const toastMessage = ref("");
const toastType = ref("success");

const allConfirmed = computed(() =>
  Object.values(confirmations.value).every((v) => v),
);

function formatCurrency(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

async function enableTrading() {
  try {
    const success = await store.enableTrading({
      ...apiConfig.value,
      confirmations: confirmations.value,
    });

    if (success) {
      showToastNotification(
        "Trading real habilitado. ¡EXTREMA PRECAUCIÓN!",
        "warning",
      );
      confirmations.value = {
        understood_risks: false,
        tested_paper: false,
        api_configured: false,
        accept_responsibility: false,
      };
    } else {
      showToastNotification(
        store.error || "Error al habilitar trading real",
        "error",
      );
    }
  } catch (error) {
    showToastNotification("Error de conexión", "error");
  }
}

async function disableTrading() {
  try {
    await store.disableTrading();
    showToastNotification("Trading real deshabilitado", "success");
  } catch (error) {
    showToastNotification("Error al deshabilitar", "error");
  }
}

async function emergencyStop() {
  if (
    confirm(
      "¿CONFIRMA PARADA DE EMERGENCIA? Se cerrarán TODAS las posiciones inmediatamente.",
    )
  ) {
    try {
      await store.emergencyStop();
      showToastNotification("Parada de emergencia ejecutada", "success");
    } catch (error) {
      showToastNotification("Error en parada de emergencia", "error");
    }
  }
}

async function closePosition(symbol) {
  if (confirm(`¿Cerrar posición en ${symbol}?`)) {
    try {
      await store.closePosition(symbol);
      showToastNotification(`Posición ${symbol} cerrada`, "success");
    } catch (error) {
      showToastNotification("Error al cerrar posición", "error");
    }
  }
}

function showToastNotification(message, type) {
  toastMessage.value = message;
  toastType.value = type;
  showToast.value = true;
  setTimeout(() => {
    showToast.value = false;
  }, 5000);
}

onMounted(() => {
  store.loadStatus();
});
</script>

<style scoped>
.trading-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.page-header {
  margin-bottom: var(--space-md);
}

.page-title {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 var(--space-xs);
}

.title-icon.warning {
  color: var(--accent-warning);
}

.page-subtitle {
  font-size: 0.875rem;
  color: var(--accent-warning);
  margin: 0;
}

/* Warning Banner */
.warning-banner {
  display: flex;
  gap: var(--space-md);
  padding: var(--space-lg);
  background: var(--danger-bg);
  border: 2px solid var(--danger-border);
  border-radius: var(--radius-lg);
}

.warning-icon {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  background: var(--accent-danger);
  display: flex;
  align-items: center;
  justify-content: center;
}

.warning-icon .icon {
  width: 24px;
  height: 24px;
  color: white;
}

.warning-content {
  flex: 1;
}

.warning-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--accent-danger);
  margin: 0 0 var(--space-sm);
}

.warning-list {
  margin: 0;
  padding-left: var(--space-lg);
  color: var(--text-primary);
  font-size: 0.875rem;
  line-height: 1.8;
}

.warning-list li {
  margin-bottom: var(--space-xs);
}

.warning-list strong {
  color: var(--accent-danger);
}

/* Status Grid */
.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-md);
}

.status-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--space-md);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.status-label {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.status-value {
  font-family: var(--font-mono);
  font-size: 1rem;
  font-weight: 600;
}

.status-value.enabled {
  color: var(--accent-danger);
}
.status-value.disabled {
  color: var(--accent-success);
}
.status-value.sandbox {
  color: var(--accent-info);
}
.status-value.live {
  color: var(--accent-danger);
  font-weight: 700;
}
.status-value.real {
  color: var(--accent-warning);
}
.status-value.positive {
  color: var(--accent-success);
}
.status-value.negative {
  color: var(--accent-danger);
}

/* Enable Form */
.enable-form {
  padding: var(--space-sm) 0;
}

.enable-warning {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin-bottom: var(--space-lg);
  padding: var(--space-md);
  background: var(--warning-bg);
  border: 1px solid var(--warning-border);
  border-radius: var(--radius-md);
}

.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  margin-bottom: var(--space-lg);
}

.checkbox-label {
  display: flex;
  align-items: flex-start;
  gap: var(--space-sm);
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary);
  padding: var(--space-sm);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  transition: background var(--transition-fast);
}

.checkbox-label:hover {
  background: var(--bg-elevated);
}

.checkbox-input {
  width: 18px;
  height: 18px;
  margin-top: 2px;
  accent-color: var(--accent-primary);
  flex-shrink: 0;
}

.checkbox-text {
  line-height: 1.5;
}

/* API Config */
.api-config {
  padding: var(--space-lg);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.api-config h4 {
  font-size: 0.875rem;
  font-weight: 600;
  margin: 0 0 var(--space-md);
  color: var(--text-primary);
}

.api-config .form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-md);
}

.api-config .form-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.api-config .form-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.api-config .form-input {
  padding: 0.5rem 0.75rem;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 0.875rem;
}

.api-config .form-input:focus {
  outline: none;
  border-color: var(--accent-primary);
}

.param-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.toggle-input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-switch {
  position: relative;
  width: 44px;
  height: 24px;
  background: var(--border-color);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.toggle-switch::before {
  content: "";
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  background: white;
  border-radius: var(--radius-full);
  transition: transform var(--transition-fast);
}

.toggle-input:checked + .toggle-switch {
  background: var(--accent-primary);
}

.toggle-input:checked + .toggle-switch::before {
  transform: translateX(20px);
}

.toggle-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

/* Active Trading */
.active-trading {
  padding: var(--space-sm) 0;
}

.trading-controls {
  display: flex;
  gap: var(--space-sm);
  margin-bottom: var(--space-lg);
  padding-bottom: var(--space-lg);
  border-bottom: 1px solid var(--border-color);
}

.emergency-btn {
  color: var(--accent-danger);
  border-color: var(--accent-danger);
}

.emergency-btn:hover {
  background: var(--danger-bg);
  color: white;
}

/* Positions Table */
.positions-table {
  overflow-x: auto;
}

/* Risk Limits */
.risk-limits {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-md);
}

.limit-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.limit-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.limit-item .form-input {
  padding: 0.5rem 0.75rem;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.875rem;
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

.toast.warning {
  background: var(--warning-bg);
  color: var(--accent-warning);
  border: 1px solid var(--warning-border);
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

/* Responsive */
@media (max-width: 768px) {
  .status-grid {
    grid-template-columns: 1fr 1fr;
  }

  .api-config .form-row {
    grid-template-columns: 1fr;
  }

  .trading-controls {
    flex-direction: column;
  }

  .risk-limits {
    grid-template-columns: 1fr;
  }
}
</style>
