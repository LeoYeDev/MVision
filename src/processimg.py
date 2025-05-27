import cv2
import numpy as np

class Processor:
    def __init__(self, img):
        self.img = img

    def process(self):
        after_process = self.img
        return after_process
    
if __name__ == "__main__":
    img = cv2.imread('test.jpg')
    image_resize = dst = cv2.resize(img, (0, 0), fx=0.4, fy=0.4)
    processtest = Processor(image_resize)
    reslut = processtest.process()
    cv2.imshow("result", reslut)
    cv2.waitKey(0)
    cv2.destroyAllWindows()