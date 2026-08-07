import { ref } from "vue";
import axios from "axios";

export function useApi(baseUrl = "/api/v1") {
  const loading = ref(false);
  const error = ref(null);

  async function get(endpoint, params = {}) {
    loading.value = true;
    error.value = null;
    try {
      const response = await axios.get(`${baseUrl}${endpoint}`, { params });
      return response.data;
    } catch (err) {
      error.value =
        err.response?.data?.detail || err.message || "Error de conexión";
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function post(endpoint, data = {}, options = {}) {
    loading.value = true;
    error.value = null;
    try {
      const response = await axios.post(`${baseUrl}${endpoint}`, data, options);
      return response.data;
    } catch (err) {
      error.value =
        err.response?.data?.detail || err.message || "Error de conexión";
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function put(endpoint, data = {}) {
    loading.value = true;
    error.value = null;
    try {
      const response = await axios.put(`${baseUrl}${endpoint}`, data);
      return response.data;
    } catch (err) {
      error.value =
        err.response?.data?.detail || err.message || "Error de conexión";
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function del(endpoint) {
    loading.value = true;
    error.value = null;
    try {
      const response = await axios.delete(`${baseUrl}${endpoint}`);
      return response.data;
    } catch (err) {
      error.value =
        err.response?.data?.detail || err.message || "Error de conexión";
      throw err;
    } finally {
      loading.value = false;
    }
  }

  function clearError() {
    error.value = null;
  }

  return {
    loading,
    error,
    get,
    post,
    put,
    delete: del,
    clearError,
  };
}

export function useConfigApi() {
  return useApi("/api/v1/config");
}

export function useBacktestApi() {
  return useApi("/api/v1/backtest");
}

export function useAutonomousApi() {
  return useApi("/api/v1/autonomous");
}

export function useMonitoringApi() {
  return useApi("/api/v1/monitoring");
}

export function useDashboardApi() {
  return useApi("/api/v1/dashboard");
}

export function useTradingApi() {
  return useApi("/api/v1/trading");
}
