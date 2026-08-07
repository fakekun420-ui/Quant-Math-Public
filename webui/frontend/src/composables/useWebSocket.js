import { ref, onUnmounted } from "vue";

export function useWebSocket(url, options = {}) {
  const connected = ref(false);
  const error = ref(null);
  const lastMessage = ref(null);
  let ws = null;
  let reconnectTimer = null;
  let heartbeatTimer = null;

  const {
    onOpen,
    onMessage,
    onClose,
    onError,
    autoReconnect = true,
    reconnectInterval = 5000,
    heartbeatInterval = 30000,
    protocols = [],
  } = options;

  function connect() {
    if (ws?.readyState === WebSocket.OPEN) return;

    try {
      ws = new WebSocket(url, protocols);

      ws.onopen = (event) => {
        connected.value = true;
        error.value = null;
        onOpen?.(event);

        if (heartbeatInterval > 0) {
          heartbeatTimer = setInterval(() => {
            if (ws?.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: "ping" }));
            }
          }, heartbeatInterval);
        }
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          lastMessage.value = message;
          onMessage?.(message);
        } catch (err) {
          console.error("Failed to parse WS message:", err);
        }
      };

      ws.onclose = (event) => {
        connected.value = false;
        clearTimers();
        onClose?.(event);

        if (autoReconnect) {
          scheduleReconnect();
        }
      };

      ws.onerror = (event) => {
        error.value = event;
        onError?.(event);
      };
    } catch (err) {
      error.value = err;
      if (autoReconnect) {
        scheduleReconnect();
      }
    }
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, reconnectInterval);
  }

  function clearTimers() {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer);
      heartbeatTimer = null;
    }
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  }

  function send(data) {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
      return true;
    }
    return false;
  }

  function disconnect() {
    clearTimers();
    if (ws) {
      ws.close();
      ws = null;
    }
    connected.value = false;
  }

  onUnmounted(() => {
    disconnect();
  });

  return {
    connected,
    error,
    lastMessage,
    connect,
    disconnect,
    send,
  };
}
