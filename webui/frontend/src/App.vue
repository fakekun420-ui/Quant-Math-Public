<template>
  <div id="app">
    <header class="app-header">
      <div class="header-left">
        <router-link to="/" class="logo">
          <IconBrain class="logo-icon" />
          <span class="logo-text">Quant-Math</span>
        </router-link>
        <nav v-if="$route.meta.requiresAuth !== false" class="main-nav">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="nav-link"
            :class="{ active: isActive(item.path) }"
          >
            <component :is="item.icon" class="nav-icon" />
            <span>{{ item.label }}</span>
          </router-link>
        </nav>
      </div>

      <div class="header-right">
        <ConnectionStatus />
        <div class="theme-toggle" title="Cambiar tema" @click="toggleTheme">
          <IconSun v-if="isDark" class="icon" />
          <IconMoon v-else class="icon" />
        </div>
        <div class="user-menu">
          <span class="user-name">Admin</span>
          <IconChevronDown class="icon" />
        </div>
      </div>
    </header>

    <main class="app-main">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <footer class="app-footer">
      <span>Quant-Math WebUI v1.0.0</span>
      <span class="footer-divider">|</span>
      <span>WebSocket: {{ wsStatus }}</span>
    </footer>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useDashboardStore } from "@/stores/dashboard";
import ConnectionStatus from "@/components/ConnectionStatus.vue";
import {
  Brain,
  LayoutDashboard,
  Settings,
  BarChart2,
  Play,
  Activity,
  Monitor,
  Server,
  Sun,
  Moon,
  ChevronDown,
} from "lucide-vue-next";

const route = useRoute();
const router = useRouter();
const store = useDashboardStore();

const isDark = ref(true);

const navItems = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/autonomous", label: "Autónomo", icon: Play },
  { path: "/backtest", label: "Backtesting", icon: BarChart2 },
  { path: "/monitoring", label: "Monitoreo", icon: Monitor },
  { path: "/config", label: "Configuración", icon: Settings },
  { path: "/trading", label: "Trading Real", icon: Server },
];

function isActive(path) {
  return route.path === path || (path !== "/" && route.path.startsWith(path));
}

function toggleTheme() {
  isDark.value = !isDark.value;
  document.documentElement.setAttribute(
    "data-theme",
    isDark.value ? "dark" : "light",
  );
  localStorage.setItem("theme", isDark.value ? "dark" : "light");
}

const wsStatus = computed(() =>
  store.wsConnected ? "Conectado" : "Desconectado",
);

onMounted(() => {
  const savedTheme = localStorage.getItem("theme") || "dark";
  isDark.value = savedTheme === "dark";
  document.documentElement.setAttribute("data-theme", savedTheme);

  store.connectWebSocket();
});

onUnmounted(() => {
  store.disconnectWebSocket();
});
</script>

<style scoped>
#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 100;
  height: var(--header-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-lg);
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  backdrop-filter: blur(8px);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-xl);
}

.logo {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  text-decoration: none;
  color: var(--text-primary);
}

.logo-icon {
  width: 28px;
  height: 28px;
  color: var(--accent-primary);
}

.logo-text {
  font-size: 1.125rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.main-nav {
  display: flex;
  gap: var(--space-xs);
}

.nav-link {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.875rem;
  font-weight: 500;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.nav-link:hover {
  color: var(--text-primary);
  background: var(--bg-tertiary);
}

.nav-link.active {
  color: var(--accent-primary);
  background: rgba(88, 166, 255, 0.1);
}

.nav-icon {
  width: 18px;
  height: 18px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.theme-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.theme-toggle:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
  border-color: var(--accent-primary);
}

.theme-toggle .icon {
  width: 18px;
  height: 18px;
}

.user-menu {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-xs) var(--space-md);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.user-menu .icon {
  width: 16px;
  height: 16px;
}

.app-main {
  flex: 1;
  padding: var(--space-lg);
  max-width: 1600px;
  width: 100%;
  margin: 0 auto;
}

.app-footer {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-md) var(--space-lg);
  background: var(--bg-secondary);
  border-top: 1px solid var(--border-color);
  font-size: 0.75rem;
  color: var(--text-muted);
}

.footer-divider {
  color: var(--border-color);
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--transition-normal);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Responsive */
@media (max-width: 1024px) {
  .main-nav {
    display: none;
  }

  .app-main {
    padding: var(--space-md);
  }
}
</style>
