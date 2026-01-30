# MVision 配置文件
import os

# 获取项目根目录
_config_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_config_dir)

# ==================== PLC 服务器配置 ====================
PLC_SERVER_HOST = "0.0.0.0"  # 监听所有网络接口
PLC_SERVER_PORT = 2000       # TCP 端口

# ==================== 文件路径配置 ====================
# 标定文件路径
CALIBRATION_FILE_PATH = os.path.join(_project_root, "assets", "calibration", "affine_matrix.txt")

# 扫描区域配置文件
SCAN_AREA_FILES = [
    os.path.join(_project_root, "config", "scan_areas", "area_A.txt"),
    os.path.join(_project_root, "config", "scan_areas", "area_B.txt"),
    os.path.join(_project_root, "config", "scan_areas", "area_C.txt"),
    os.path.join(_project_root, "config", "scan_areas", "area_D.txt"),
]

# ==================== 角度校正参数 ====================
# PLC中角度行程不一样需要微调
angle_deg_judge = 5.88

# ==================== HSV 颜色阈值配置 ====================
hsv_range = {
    'yellow': ((5, 60, 13), (30, 255, 255)),
    'red1': ((0, 100, 20), (100, 255, 255)),
    'red2': ((156, 100, 20), (180, 255, 255)),
    'green': ((40, 50, 10), (90, 255, 255)),
    'blue': ((90, 85, 13), (160, 255, 255)),
}