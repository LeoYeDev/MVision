# 定义了CameraParam类，用于管理相机参数和操作
import sys
import os

# 导入路径设置 - 相对于项目根目录
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_project_root, "lib", "MvImport"))
sys.path.insert(0, os.path.join(_project_root, "config"))

from param import *
from MvCameraControl_class import *
from cam_operation import CameraOperation


class CameraParam:
    def __init__(self):
        # 设备列表
        self.deviceList = MV_CC_DEVICE_INFO_LIST()
        # 相机类型
        self.tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE
        # 相机实例
        self.cam = MvCamera()
        # 在deviceList中选择的相机索引
        self.nSelCamIndex = 0
        # 相机操作
        self.obj_cam_operation = 0
        # 判断相机是否在运行
        self.b_is_run = False
