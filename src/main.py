import tkinter as tk

from camera import CameraParam
from ui import AppUI
from processimg import *

if __name__ == "__main__":
    cam_ctrl = CameraParam()
    #界面设计代码
    window = tk.Tk()
    app = AppUI(window, cam_ctrl)
    window.mainloop()