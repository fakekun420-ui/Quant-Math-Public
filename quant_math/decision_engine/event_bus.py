import logging
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)

class EventBus:
    """Lightweight Pub/Sub Event Bus for Quant-Math."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[..., Any]]] = {}

    def subscribe(self, event_type: str, callback: Callable[..., Any]) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)

    def publish(self, event_type: str, *args, **kwargs) -> None:
        callbacks = self._subscribers.get(event_type, [])
        for callback in callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error executing callback {callback.__name__} for event {event_type}: {e}")

# Global Event Bus instance
bus = EventBus()
