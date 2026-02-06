import importlib
from .base_tracker import BaseTracker

def load_tracker(tracker_name: str) -> BaseTracker:
    tracker_map = {
        "sort": "sort_tracker.SortTracker",
    }

    try:
        module_class = tracker_map[tracker_name]
        module_name, class_name = module_class.rsplit(".", 1)
        module = importlib.import_module(f".{module_name}", package="sancho_vision.trackers")
        tracker_class = getattr(module, class_name)
        return tracker_class()
    except KeyError:
        raise ValueError(f"Tracker '{tracker_name}' no reconocido")
    except Exception as e:
        raise RuntimeError(f"No se pudo cargar el tracker '{tracker_name}': {e}")