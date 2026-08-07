import { createRouter, createWebHistory } from "vue-router";
import DashboardView from "@/views/DashboardView.vue";
import ConfigView from "@/views/ConfigView.vue";
import BacktestView from "@/views/BacktestView.vue";
import AutonomousView from "@/views/AutonomousView.vue";
import MonitoringView from "@/views/MonitoringView.vue";
import TradingView from "@/views/TradingView.vue";

const routes = [
  {
    path: "/",
    name: "Dashboard",
    component: DashboardView,
    meta: { title: "Dashboard" },
  },
  {
    path: "/config",
    name: "Config",
    component: ConfigView,
    meta: { title: "Configuración" },
  },
  {
    path: "/backtest",
    name: "Backtest",
    component: BacktestView,
    meta: { title: "Backtesting" },
  },
  {
    path: "/autonomous",
    name: "Autonomous",
    component: AutonomousView,
    meta: { title: "Modo Autónomo" },
  },
  {
    path: "/monitoring",
    name: "Monitoring",
    component: MonitoringView,
    meta: { title: "Panel de Monitoreo" },
  },
  {
    path: "/trading",
    name: "Trading",
    component: TradingView,
    meta: { title: "Trading Real" },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to, from, next) => {
  document.title = `Quant-Math | ${to.meta.title || "Dashboard"}`;
  next();
});

export default router;
