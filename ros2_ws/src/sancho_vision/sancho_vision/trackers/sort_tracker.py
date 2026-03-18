from .base_tracker import BaseTracker
import numpy as np

from .external.sort import Sort, associate_detections_to_trackers 

class SortTracker(BaseTracker):
    def __init__(self):
        self.tracker = Sort(
            max_age=30,
            min_hits=3,
            iou_threshold=0.3
        )

    def update(self, positions, confidences, image = None):
        # Construir array esperado por SORT: [[x1,y1,x2,y2,score], ...]
        dets = []
        for (x, y, w, h), score in zip(positions, confidences):
            dets.append([float(x), float(y), float(x + w), float(y + h), float(score)])

        if len(dets) == 0:
            return np.empty((0, 6))

        detections = np.array(dets)

        # Ejecutar SORT: tracker.update espera array [[x1,y1,x2,y2,score],...]
        tracker_outputs = self.tracker.update(detections)

        if len(tracker_outputs) == 0:
            return np.empty((0, 6))

        # Re-asociar para recuperar el Score
        matches, unmatched_dets, unmatched_trks = associate_detections_to_trackers(
            detections,
            tracker_outputs,
            iou_threshold=0.3
        )

        results = []
        for match in matches:
            det_idx = int(match[0])
            trk_idx = int(match[1])

            track_data = tracker_outputs[trk_idx]  # [x1,y1,x2,y2,tid]
            score = detections[det_idx, 4]

            track_with_score = np.append(track_data, score)
            results.append(track_with_score)

        if len(results) == 0:
            return np.empty((0, 6))

        return np.array(results)