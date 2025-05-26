import cv2
import numpy as np

class Processor:
    def __init__(self, params):
        self.lower_hsv = np.array(params['lower_hsv'])
        self.upper_hsv = np.array(params['upper_hsv'])
        self.min_area  = params.get('min_area', 500)
    
    def process(self, img_bgr):
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_hsv, self.upper_hsv)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                                cv2.getStructuringElement(cv2.MORPH_RECT,(5,5)))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        results = []
        for cnt in contours:
            if cv2.contourArea(cnt) < self.min_area:
                continue
            rect = cv2.minAreaRect(cnt)
            box  = cv2.boxPoints(rect).astype(int)
            cx, cy = map(int, rect[0])
            angle  = rect[2]
            results.append({'box': box, 'center': (cx,cy), 'angle': angle})
        return results