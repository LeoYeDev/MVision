# -- coding: utf-8 --
import sys

sys.path.append("./lib/MvImport")
sys.path.append("./lib/Own")
sys.path.append("./config")
from param import *
from MvCameraControl_class import *
from CamOperation_class import *


class CameraParam:
    def __init__(self):
        # 设备列表
        self.deviceList = MV_CC_DEVICE_INFO_LIST()
        # 相机类型
        self.tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE
        #相机实例
        self.cam = MvCamera()
        #在deviceList中选择的相机索引
        self.nSelCamIndex = 0
        #相机操作
        self.obj_cam_operation = 0
        #判断相机是否在运行
        self.b_is_run = False
