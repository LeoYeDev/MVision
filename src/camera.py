# -- coding: utf-8 --
import sys

sys.path.append("./lib/MvImport")
sys.path.append("./lib/Own")
sys.path.append("./config")
from param import *
from MvCameraControl_class import *
from CamOperation_class import *


class CameraController:
    def __init__(self):
        global deviceList 
        deviceList = MV_CC_DEVICE_INFO_LIST()
        global tlayerType
        tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE
        global cam
        cam = MvCamera()
        global nSelCamIndex
        nSelCamIndex = 0
        global obj_cam_operation
        obj_cam_operation = 0
        global b_is_run
        b_is_run = False
    

