from abc import ABC, abstractmethod
import numpy as np

class BaseTracker(ABC):

    @abstractmethod
    def update(self, positions, confidences, image = None):
        '''
        Update tracker state given detector results and return tracked detections.

        Args:
            positions (list or ndarray): Iterable of bounding boxes in the detector format
                [(x, y, w, h), ...] where x,y are corner coordinates and w,h are width/height.
            confidences (list or ndarray): Iterable of confidence scores matching `positions`.
            image (ndarray): (Optional) Actual image, in case of visual tracker (like DeepSORT).

        Returns:
            tracked_faces (ndarray): Numpy array in the format [[x1, y1, x2, y2, tid, score], ...]
        '''
        pass