import tkinter as tk

from camera import CameraController
from ui import AppUI
from processimg import *

parm = {'lower_hsv':10,
        'upper_hsv': 20,
        'min_area': 500}

if __name__ == "__main__":
    cam_ctrl = CameraController()
    processor = Processor(parm)
    #界面设计代码
    window = tk.Tk()
    app = AppUI(window, cam_ctrl,processor)
    window.mainloop()