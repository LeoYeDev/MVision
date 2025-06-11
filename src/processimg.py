import cv2
import numpy as np
import time
import sys
import os

sys.path.append("./src")
sys.path.append("./config")
from process_math import *
from param import PLC_SERVER_HOST, PLC_SERVER_PORT, CALIBRATION_FILE_PATH, SCAN_AREA_FILES

class Processor:
    def __init__(self, img):
        self.img = img 

        # 定义几种常见颜色在 HSV 空间的阈值范围（示例）
        # self.hsv_ranges = {
        #     'red1': ((0, 100, 20),   (10, 255, 255)),
        #     'red2': ((156, 100, 20), (180, 255, 255)),  # 红色有两个区间
        #     'green': ((40,  50,  10),  (90,  255, 255)),
        #     'blue': ((90, 85,  13),  (160, 255, 255)),
        #     'yellow': ((10, 60, 13), (30, 255, 255)),
        # }

        self.hsv_ranges = {
            'yellow': ((5, 60, 13), (30, 255, 255)),
            'red1': ((0, 100, 20),   (100, 255, 255)),
            'red2': ((156, 100, 20), (180, 255, 255)),  # 红色有两个区间
            'green': ((40,  50,  10),  (90,  255, 255)),
            'blue': ((90, 85,  13),  (160, 255, 255)),
        }
        # 最小检测面积 
        self.min_area = 50000
        # 轮廓逼近精度
        self.eps_factor = 0.02
        # --- 用于控制绘制效果的参数 ---
        self.font_scale = 1.5       # 字体缩放比例
        self.text_thickness = 3     # 文本线条粗细
        self.dot_radius = 10        # 中心点半径
        self.line_thickness1 = 6    # 轮廓线的粗细 (例如原始轮廓)
        self.line_thickness2 = 3    # 标记线的粗细 (例如最小外接矩形、凸包)

        # --- 新增：从文件加载仿射变换矩阵 ---
        self.affine_transform_matrix = None # 初始化为None
        self._load_affine_matrix(CALIBRATION_FILE_PATH) # 调用加载方法
    
    def _load_affine_matrix(self, filepath):
        if not os.path.exists(filepath):
            print(f"错误：标定文件 '{filepath}' 未找到！")
            self.affine_transform_matrix = np.eye(3, dtype=np.float32)
            return
        try:
            self.affine_transform_matrix = np.loadtxt(filepath, delimiter=',')
            if self.affine_transform_matrix.shape != (3, 3):
                print(f"错误：从 '{filepath}' 读取的矩阵不是3x3形状！")
                self.affine_transform_matrix = np.eye(3, dtype=np.float32)
        except Exception as e:
            print(f"加载标定文件 '{filepath}' 时发生错误: {e}")
            self.affine_transform_matrix = np.eye(3, dtype=np.float32)

    def process(self, roi_rect=None):
        img_display = self.img.copy()# 用于绘制结果的图像
       # --- 【核心修改】应用ROI遮罩 ---
        roi_rect = [300, 200, 2000, 1500]
        if roi_rect is not None:
            # 创建一个半透明的浅色覆盖层
            overlay = img_display.copy()
            cv2.rectangle(overlay, (0, 0), (overlay.shape[1], overlay.shape[0]), (230, 230, 230), -1)
            # 将覆盖层与显示图像混合
            alpha = 0.6  # 透明度
            img_display = cv2.addWeighted(overlay, alpha, img_display, 1 - alpha, 0)
            # "擦亮" ROI 区域，恢复其原始内容
            x, y, w, h = roi_rect
            img_display[y:y+h, x:x+w] = self.img[y:y+h, x:x+w]
            # 绘制清晰的ROI边框
            cv2.rectangle(img_display, (x, y), (x+w, y+h), (255, 255, 0), 3)
        else:
            x,y,w,h= 0, 0, img_display.shape[1], img_display.shape[0] # 如果没有ROI，使用全图

        # --- 对原始、完整的图像进行颜色分割和轮廓提取 ---
        hsv = cv2.cvtColor(self.img, cv2.COLOR_BGR2HSV)
        
        # 合并所有颜色掩膜
        mask = None
        for lo, hi in self.hsv_ranges.values():
            m = cv2.inRange(hsv, np.array(lo), np.array(hi))
            mask = m if mask is None else cv2.bitwise_or(mask, m)
        
        if mask is None: return img_display, [] 

        # 形态学操作 (保持上一版本中的平滑处理)
        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_open, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close, iterations=1)
        mask = cv2.medianBlur(mask, 5)
         
        # 轮廓提取 (修正)
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        h_img, w_img = self.img.shape[:2] 
        img_total_area = h_img * w_img
        
        # --- 新增：用于存储所有检测到的物料信息，包括机械臂坐标 ---
        detected_objects_info = []
        detected_objects_info.clear() # 确保每次处理前清空
        
        for cnt in contours:
            area_cnt = cv2.contourArea(cnt) # 原始轮廓的面积
            if area_cnt < self.min_area: continue

            # --- 边框过滤逻辑 (保持不变) ---
            x_br, y_br, w_br, bh_br = cv2.boundingRect(cnt) 
            aspect_ratio = max(w_br/bh_br, bh_br/w_br) if bh_br != 0 and w_br != 0 else 0
            perimeter_cnt = cv2.arcLength(cnt, True) # 原始轮廓的周长
            compactness_ratio = (perimeter_cnt * perimeter_cnt) / (area_cnt + 1e-6) 
            if aspect_ratio > 7 and area_cnt > (0.7 * img_total_area): 
                continue
            if compactness_ratio > 550: 
                continue
                
            # --- 基于原始轮廓 `cnt` 计算实际物理特征 ---
            # 轮廓中心 (质心)
            M = cv2.moments(cnt)
            if M['m00'] == 0: continue 
            cx_centroid = M['m10']/M['m00'] # 原始轮廓的质心X
            cy_centroid = M['m01']/M['m00'] # 原始轮廓的质心Y

            # 最小外接矩形 (基于原始轮廓 `cnt`)
            rect = cv2.minAreaRect(cnt)
            (cx_rect_float, cy_rect_float), (w_rect, h_rect), angle_from_cv2 = rect 
            box_points = cv2.boxPoints(rect).astype(int) 
            cv2.drawContours(img_display, [box_points], -1, (128,0,128), self.line_thickness2 -1 if self.line_thickness2 > 1 else 1)
            
            # 【核心修改 2】根据中心点位置过滤物体
            if roi_rect is not None:
                x, y, w, h = roi_rect
                # 如果中心点不在ROI内部，则跳过此轮廓
                if not (x <= cx_rect_float < x + w and y <= cy_rect_float < y + h):
                    continue

            # --- 基于凸包 `hull` 进行形状分析 ---
            hull = cv2.convexHull(cnt) # 计算原始轮廓的凸包
            perimeter_hull = cv2.arcLength(hull, True) # 凸包的周长
            area_hull = cv2.contourArea(hull)          # 凸包的面积

            # 对凸包进行多边形逼近
            approx_hull = cv2.approxPolyDP(hull, self.eps_factor * perimeter_hull, True)
            num_vertices_hull = len(approx_hull)

            # 绘制凸包轮廓 (绿色)
            cv2.drawContours(img_display, [hull], -1, (0,255,0), self.line_thickness2)
            # 形状判断 (基于凸包的顶点数 `num_vertices_hull` 和 `approx_hull`)
            shape_label = 'unknown'
            approx_hull_reshaped = approx_hull.reshape(-1, 2) # 转换为 N x 2 形状

            if num_vertices_hull == 3: shape_label = 'triangle'
            elif num_vertices_hull == 4:
                # --- 四边形判断逻辑修改区域 ---
                side_lengths = [np.linalg.norm(approx_hull_reshaped[i] - approx_hull_reshaped[(i + 1) % 4]) for i in range(4)]
                interior_angles = calculate_interior_angles(approx_hull_reshaped)

                angle_tolerance = 15  # 内角与90度的容差（度）
                side_relative_tolerance = 0.15 # 边长相对容差 (15%)

                # 检查所有内角是否约等于90度
                all_angles_approx_90 = False
                if len(interior_angles) == 4: # 确保计算出4个角
                    all_angles_approx_90 = all(abs(angle - 90) < angle_tolerance for angle in interior_angles)
                
                # 检查所有边是否约等长
                all_sides_approx_equal = False
                if side_lengths: # 确保边长列表不为空
                    all_sides_approx_equal = (max(side_lengths) - min(side_lengths)) < side_relative_tolerance * (max(side_lengths) + 1e-6) # 加epsilon避免max为0

                # 检查对边是否约等长 (side0 vs side2, side1 vs side3)
                opposite_sides_approx_equal = False
                if len(side_lengths) == 4:
                    s0, s1, s2, s3 = side_lengths
                    # 比较时，分母使用两条比较边中的较大者，或加上一个极小值避免除零
                    cond1 = abs(s0 - s2) < side_relative_tolerance * max(s0, s2, 1e-6) 
                    cond2 = abs(s1 - s3) < side_relative_tolerance * max(s1, s3, 1e-6)
                    opposite_sides_approx_equal = cond1 and cond2

                if all_sides_approx_equal and all_angles_approx_90:
                    shape_label = 'square'  # 正方形：四边等长，四角相等且为90度
                elif all_sides_approx_equal: # 隐含条件: 角度不都为90 (已被正方形条件覆盖)
                    shape_label = 'diamond' # 菱形：四边等长
                elif opposite_sides_approx_equal and all_angles_approx_90: # 隐含条件: 四边不都等长 (已被正方形条件覆盖)
                    shape_label = 'rectangle' # 矩形：对边等长，四角相等且为90度
                elif is_trapezoid(approx_hull): # 使用用户定义的梯形判断
                    shape_label = 'trapezoid'
            
            elif num_vertices_hull == 6: 
                shape_label = 'hexagon'
            else: 
                circularity_hull = 4*np.pi*area_hull/(perimeter_hull**2) if perimeter_hull > 0 else 0
                shape_label = 'circle' if circularity_hull > 0.75 else f'polygon{num_vertices_hull}' 
            
            # --- 新的角度计算逻辑 ---
            display_angle_text = "N/A"
            calculated_angle_0_360 = -1.0 
            ref_vec_start_pt, ref_vec_end_pt = None, None 

            if shape_label != 'circle':
                approx_hull_reshaped = approx_hull.reshape(-1, 2)

                if shape_label == 'triangle':
                    if num_vertices_hull == 3:
                        # 计算三角形质心 (也可以用原始轮廓的质心 cx_centroid, cy_centroid)
                        # M_hull = cv2.moments(approx_hull) # 用凸包的顶点计算质心
                        # cx_triangle_center = M_hull['m10'] / (M_hull['m00'] + 1e-6)
                        # cy_triangle_center = M_hull['m01'] / (M_hull['m00'] + 1e-6)
                        triangle_center = np.array([cx_centroid, cy_centroid]) # 使用原始轮廓质心

                        vertices = approx_hull_reshaped
                        distances_to_center = [np.linalg.norm(v - triangle_center) for v in vertices]
                        
                        closest_vertex_idx = np.argmin(distances_to_center)
                        ref_vec_end_pt = vertices[closest_vertex_idx] # 终点：离中心最近的顶点

                        # 另外两个顶点构成一条边
                        other_vertices_indices = [i for i in range(3) if i != closest_vertex_idx]
                        p_side1 = vertices[other_vertices_indices[0]]
                        p_side2 = vertices[other_vertices_indices[1]]
                        ref_vec_start_pt = get_midpoint(p_side1, p_side2) # 起点：远边的中点
                
                elif shape_label == 'trapezoid':
                    bases = find_trapezoid_bases(approx_hull_reshaped)
                    if bases and bases[0] and bases[1]:
                        (long_base_p1, long_base_p2), (short_base_p1, short_base_p2) = bases
                        mid_long_base = get_midpoint(long_base_p1, long_base_p2)
                        mid_short_base = get_midpoint(short_base_p1, short_base_p2)
                        ref_vec_start_pt = mid_long_base
                        ref_vec_end_pt = mid_short_base
                
                elif shape_label == 'hexagon':
                    if num_vertices_hull == 6:
                        parallel_side_pair = find_hexagon_parallel_side_pair(approx_hull_reshaped)
                        if parallel_side_pair:
                            (side1_p1, side1_p2), (side2_p1, side2_p2) = parallel_side_pair
                            mid1 = get_midpoint(side1_p1, side1_p2)
                            mid2 = get_midpoint(side2_p1, side2_p2)
                            # 确保向量方向一致性，例如从y较小的中点指向y较大的中点
                            if mid1[1] < mid2[1] or (mid1[1] == mid2[1] and mid1[0] < mid2[0]):
                                ref_vec_start_pt = mid1
                                ref_vec_end_pt = mid2
                            else:
                                ref_vec_start_pt = mid2
                                ref_vec_end_pt = mid1
                
                elif shape_label in ['rectangle', 'square', 'diamond']:
                    if num_vertices_hull == 4:
                        mid1 = get_midpoint(approx_hull_reshaped[0], approx_hull_reshaped[1])
                        mid2 = get_midpoint(approx_hull_reshaped[2], approx_hull_reshaped[3])
                        if mid1[1] < mid2[1] or (mid1[1] == mid2[1] and mid1[0] < mid2[0]):
                             ref_vec_start_pt = mid1; ref_vec_end_pt = mid2
                        else: ref_vec_start_pt = mid2; ref_vec_end_pt = mid1
                
                if ref_vec_start_pt is not None and ref_vec_end_pt is not None:
                    calculated_angle_0_360 = get_vector_angle_0_360(ref_vec_start_pt, ref_vec_end_pt)
                    display_angle_text = f"{calculated_angle_0_360:.1f}"
                    cv2.arrowedLine(img_display, tuple(ref_vec_start_pt.astype(int)), tuple(ref_vec_end_pt.astype(int)), 
                                    (255, 100, 0), self.line_thickness2)

             # --- 坐标转换和显示 ---
            robot_x_str, robot_y_str = "N/A", "N/A" # 初始化为N/A
            pixel_x_to_transform = float(cx_rect_float) # 使用最小外接矩形中心作为待转换点
            pixel_y_to_transform = float(cy_rect_float)

            if self.affine_transform_matrix is not None:
                # 应用仿射变换:
                # X_robot = u*C[0,0] + v*C[1,0] + C[2,0]
                # Y_robot = u*C[0,1] + v*C[1,1] + C[2,1]
                # 注意C#数组和Python NumPy数组的索引方式可能不同，这里假设 self.affine_transform_matrix 
                # 的存储方式与C#代码中 transformation_array[row, col] 对应。
                # C# transformation_array[0,0] -> self.affine_transform_matrix[0,0] (u的X系数)
                # C# transformation_array[1,0] -> self.affine_transform_matrix[1,0] (v的X系数)
                # C# transformation_array[2,0] -> self.affine_transform_matrix[2,0] (X的平移)
                
                C = self.affine_transform_matrix
                robot_x = pixel_x_to_transform * C[0,0] + pixel_y_to_transform * C[1,0] + C[2,0]
                robot_y = pixel_x_to_transform * C[0,1] + pixel_y_to_transform * C[1,1] + C[2,1]
                robot_x = -robot_x # 注意：C#代码中Y轴方向是向下的，这里需要取反
                robot_y = -robot_y
                robot_x_str = f"{robot_x:.2f}"
                robot_y_str = f"{robot_y:.2f}"
            else:
                print("警告: 仿射变换矩阵未加载，无法进行坐标转换。")
                
            # --- 绘制文本和标记 (保持不变) ---
            cx_rect_int = int(cx_rect_float)
            cy_rect_int = int(cy_rect_float)
            color_label = 'N/A' 
            if 0 <= cy_rect_int < h_img and 0 <= cx_rect_int < w_img: 
                hsv_pixel_value = hsv[cy_rect_int, cx_rect_int]
                for name, (lo, hi) in self.hsv_ranges.items():
                    lo_np, hi_np = np.array(lo), np.array(hi)
                    if np.all(hsv_pixel_value >= lo_np) and np.all(hsv_pixel_value <= hi_np):
                        color_label = name.replace('1','').replace('2','') 
                        break
            
            text_base_x = cx_rect_int + 20  
            text_base_y = cy_rect_int - 20  
            line_spacing = int(40 * self.font_scale)

            cv2.rectangle(img_display, (x, y), (x + w, y + h), (0, 255, 255), 4) # 黄色，粗线条
            #(200,255,200)青色
            cv2.circle(img_display, (cx_rect_int, cy_rect_int), self.dot_radius, (0,0,255), -1) 

            cv2.putText(img_display, f"X-Y:({robot_x_str},{robot_y_str})", (text_base_x, text_base_y),
                        cv2.FONT_HERSHEY_SIMPLEX, self.font_scale * 0.9, (24,240,240), self.text_thickness, cv2.LINE_AA) # 稍小字体，不同颜色
            cv2.putText(img_display, f"C:{color_label}", (text_base_x, text_base_y + line_spacing),
                        cv2.FONT_HERSHEY_SIMPLEX, self.font_scale, (24,240,240), self.text_thickness, cv2.LINE_AA)
            cv2.putText(img_display, f"S:{shape_label}", (text_base_x, text_base_y + 2*line_spacing),
                        cv2.FONT_HERSHEY_SIMPLEX, self.font_scale, (24,240,240), self.text_thickness, cv2.LINE_AA)
            if shape_label != 'circle':
                cv2.putText(img_display, f"A:{display_angle_text}", (text_base_x, text_base_y + 3*line_spacing),
                            cv2.FONT_HERSHEY_SIMPLEX, self.font_scale, (24,240,240), self.text_thickness, cv2.LINE_AA)
                
            # 存储信息 (如果需要返回给调用者)
            current_object_data = {
                "shape": shape_label,
                "color": color_label,
                "angle_deg": calculated_angle_0_360 if shape_label != 'circle' else -1.0, # -1.0 表示圆形
                "robot_x": robot_x, 
                "robot_y": robot_y
            }
            detected_objects_info.append(current_object_data)
            # print(f"检测到物体: {current_object_data}")
        return img_display, detected_objects_info


if __name__ == "__main__":
    img_path = '1454.jpg'           
    img_main = cv2.imread(img_path)
    print(f"读取图像: {img_path}, 大小: {img_main.shape[1]}x{img_main.shape[0]}")
    
    if img_main.shape[2] == 4: # 处理PNG等带Alpha通道的图像
        img_main = cv2.cvtColor(img_main, cv2.COLOR_BGRA2BGR)

    starttime = time.time()
    processor = Processor(img_main) 
    result_img ,_ = processor.process()
    endtime = time.time()
    print(f"处理时间: {endtime - starttime:.4f} 秒")

    display_max_h, display_max_w = 600, 800 
    res_h, res_w = result_img.shape[:2]
    if res_h > display_max_h or res_w > display_max_w:
        scale = min(display_max_h/res_h, display_max_w/res_w, 1.0) 
        result_img_display = cv2.resize(result_img, None, fx=scale, fy=scale)
    else:
        result_img_display = result_img
    print(f"显示图像大小: {result_img_display.shape[1]}x{result_img_display.shape[0]}")
    cv2.imshow("out", result_img_display)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
