#图像处理中常用的数学计算函数
import numpy as np

def get_midpoint(p1, p2):
        """计算两点p1, p2的中点"""
        return np.array([int((p1[0] + p2[0]) / 2), int((p1[1] + p2[1]) / 2)])

def get_vector_angle_0_360(p_start, p_end):
    """计算从点p_start到点p_end的向量与x轴正方向的0-360度角"""
    vector_x = float(p_end[0] - p_start[0])
    vector_y = float(p_end[1] - p_start[1]) 
    angle_rad = np.arctan2(vector_y, vector_x)
    angle_deg_raw = np.degrees(angle_rad)
    return (angle_deg_raw + 360) % 360
def get_sides_sorted_by_length(approx_points):
    """获取逼近轮廓的各条边（顶点对）及其长度，按长度降序排序"""
    sides_info = [] 
    num_points = len(approx_points)
    if num_points < 2: return []
    for i in range(num_points):
        p1 = approx_points[i][0] 
        p2 = approx_points[(i + 1) % num_points][0]
        length = np.linalg.norm(p1 - p2)
        sides_info.append(((p1, p2), length))
    sides_info.sort(key=lambda x: x[1], reverse=True) 
    return sides_info 
def find_trapezoid_bases(approx_points_reshaped):
    """为梯形找到两条平行底边，并区分长短。"""
    if len(approx_points_reshaped) != 4: return None, None
    vecs = [approx_points_reshaped[(i + 1) % 4] - approx_points_reshaped[i] for i in range(4)]
    angles_deg = [np.degrees(np.arctan2(v[1], v[0])) if np.linalg.norm(v) > 1e-6 else 0 for v in vecs]
    parallel_pairs_indices = []
    diff_02 = abs(angles_deg[0] - angles_deg[2])
    if min(diff_02, abs(diff_02 - 180), abs(diff_02 + 180)) < 15: parallel_pairs_indices.append((0, 2))
    diff_13 = abs(angles_deg[1] - angles_deg[3])
    if min(diff_13, abs(diff_13 - 180), abs(diff_13 + 180)) < 15: parallel_pairs_indices.append((1, 3))
    if len(parallel_pairs_indices) != 1: return None, None
    idx1, idx2 = parallel_pairs_indices[0]
    
    base1_p1, base1_p2 = approx_points_reshaped[idx1], approx_points_reshaped[(idx1 + 1) % 4]
    base1_len = np.linalg.norm(base1_p1 - base1_p2)
    base2_p1, base2_p2 = approx_points_reshaped[idx2], approx_points_reshaped[(idx2 + 1) % 4]
    base2_len = np.linalg.norm(base2_p1 - base2_p2)
    if base1_len >= base2_len: return ((base1_p1, base1_p2), (base2_p1, base2_p2))
    else: return ((base2_p1, base2_p2), (base1_p1, base1_p2))
def is_trapezoid(approx): # approx 是 (N,1,2) 形状
    # 用户原始的 _is_trapezoid 判断逻辑
    if len(approx) != 4:
        return False
    pts = approx.reshape(4,2)
    vecs = [pts[(i+1)%4]-pts[i] for i in range(4)]
    def is_parallel_local(v1, v2): # 局部函数，保持与用户定义一致
        # 确保v1, v2是numpy array
        v1_np = np.array(v1)
        v2_np = np.array(v2)
        if np.linalg.norm(v1_np) < 1e-6 or np.linalg.norm(v2_np) < 1e-6: return False # 避免零向量
        ang = abs(np.degrees(np.arctan2(v1_np[1],v1_np[0]) - np.arctan2(v2_np[1],v2_np[0])))
        # 归一化角度差到 [0, 180]
        while ang > 180: ang -= 360
        ang = abs(ang)
        if ang > 90: ang = 180 - ang # 取最小夹角
        return ang < 10 # 平行容差为10度 (与0度或180度线的夹角小于10度)
    parallels = 0
    # 检查 vec[0]与vec[2] (对边1), vec[1]与vec[3] (对边2)
    if is_parallel_local(vecs[0], vecs[2]): parallels += 1
    if is_parallel_local(vecs[1], vecs[3]): parallels += 1
    return parallels == 1 # 梯形：有且仅有一组对边平行

def find_hexagon_parallel_side_pair(approx_points_reshaped):
    """为六边形找到一对平行边。approx_points_reshaped: 6x2 的顶点数组"""
    if len(approx_points_reshaped) != 6:
        return None
    vecs = [approx_points_reshaped[(i + 1) % 6] - approx_points_reshaped[i] for i in range(6)]
    angles_deg = [np.degrees(np.arctan2(v[1], v[0])) if np.linalg.norm(v) > 1e-6 else 0 for v in vecs]
    # 正六边形有三对平行边：(v0, v3), (v1, v4), (v2, v5)
    parallel_check_tolerance = 15 # 平行判断的角度容差
    
    # 检查第一对: 边0 (v0-v1) 与 边3 (v3-v4)
    diff_03 = abs(angles_deg[0] - angles_deg[3])
    if min(diff_03, abs(diff_03 - 180), abs(diff_03 + 180)) < parallel_check_tolerance:
        p1_pair1 = approx_points_reshaped[0]
        p2_pair1 = approx_points_reshaped[1]
        p1_pair2 = approx_points_reshaped[3]
        p2_pair2 = approx_points_reshaped[4]
        return ((p1_pair1, p2_pair1), (p1_pair2, p2_pair2))
    # 检查第二对: 边1 (v1-v2) 与 边4 (v4-v5)
    diff_14 = abs(angles_deg[1] - angles_deg[4])
    if min(diff_14, abs(diff_14 - 180), abs(diff_14 + 180)) < parallel_check_tolerance:
        p1_pair1 = approx_points_reshaped[1]
        p2_pair1 = approx_points_reshaped[2]
        p1_pair2 = approx_points_reshaped[4]
        p2_pair2 = approx_points_reshaped[5]
        return ((p1_pair1, p2_pair1), (p1_pair2, p2_pair2))
    # 检查第三对: 边2 (v2-v3) 与 边5 (v5-v0)
    diff_25 = abs(angles_deg[2] - angles_deg[5])
    if min(diff_25, abs(diff_25 - 180), abs(diff_25 + 180)) < parallel_check_tolerance:
        p1_pair1 = approx_points_reshaped[2]
        p2_pair1 = approx_points_reshaped[3]
        p1_pair2 = approx_points_reshaped[5]
        p2_pair2 = approx_points_reshaped[0]
        return ((p1_pair1, p2_pair1), (p1_pair2, p2_pair2))
        
    return None # 未找到平行对
def calculate_interior_angles(approx_points_reshaped):
    """计算多边形所有内角"""
    angles = []
    n = len(approx_points_reshaped)
    if n < 3: return []
    for i in range(n):
        p_prev = approx_points_reshaped[(i - 1 + n) % n]
        p_curr = approx_points_reshaped[i]
        p_next = approx_points_reshaped[(i + 1) % n]
        v1 = p_prev - p_curr 
        v2 = p_next - p_curr 
        dot_product = np.dot(v1, v2)
        mag_v1 = np.linalg.norm(v1)
        mag_v2 = np.linalg.norm(v2)
        if mag_v1 * mag_v2 < 1e-6: 
            angles.append(0) 
            continue
        cos_angle = np.clip(dot_product / (mag_v1 * mag_v2), -1.0, 1.0)
        angle = np.degrees(np.arccos(cos_angle))
        angles.append(angle)
    return angles