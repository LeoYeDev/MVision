import cv2
import numpy as np
import time
import sys

sys.path.append("./src")
from process_math import *

class Processor:
    def __init__(self, img):
        self.img = img 

        # 定义几种常见颜色在 HSV 空间的阈值范围（示例）
        self.hsv_ranges = {
            'red1': ((0, 100, 20),   (10, 255, 255)),
            'red2': ((156, 100, 20), (180, 255, 255)),  # 红色有两个区间
            'green': ((40,  50,  10),  (90,  255, 255)),
            'blue': ((90, 85,  13),  (160, 255, 255)),
            'yellow': ((10, 60, 13), (30, 255, 255)),
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

    def process(self):
        img_display = self.img.copy()
        hsv = cv2.cvtColor(self.img, cv2.COLOR_BGR2HSV) # 使用 self.img 进行转换
        
        # 合并所有颜色掩膜
        mask = None
        for lo, hi in self.hsv_ranges.values():
            m = cv2.inRange(hsv, np.array(lo), np.array(hi))
            mask = m if mask is None else cv2.bitwise_or(mask, m)
        
        if mask is None:
            return self.img

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
        
        for cnt in contours:
            area_cnt = cv2.contourArea(cnt) # 原始轮廓的面积
            if area_cnt < self.min_area:    
                continue

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
            
            # --- 基于凸包 `hull` 进行形状分析 ---
            hull = cv2.convexHull(cnt) # 计算原始轮廓的凸包
            perimeter_hull = cv2.arcLength(hull, True) # 凸包的周长
            area_hull = cv2.contourArea(hull)          # 凸包的面积

            # 对凸包进行多边形逼近
            approx_hull = cv2.approxPolyDP(hull, self.eps_factor * perimeter_hull, True)
            num_vertices_hull = len(approx_hull)
            # 绘制原始轮廓 (蓝色)
            # cv2.drawContours(img_display, [cnt], -1, (255,0，0), self.line_thickness1)
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

            cv2.circle(img_display, (cx_rect_int, cy_rect_int), self.dot_radius, (0,0,255), -1) 

            cv2.putText(img_display, f"C:{color_label}", (text_base_x, text_base_y),
                        cv2.FONT_HERSHEY_SIMPLEX, self.font_scale, (24,240,240), self.text_thickness, cv2.LINE_AA)
            cv2.putText(img_display, f"S:{shape_label}", (text_base_x, text_base_y + line_spacing),
                        cv2.FONT_HERSHEY_SIMPLEX, self.font_scale, (24,240,240), self.text_thickness, cv2.LINE_AA)
            
            if shape_label != 'circle':
                cv2.putText(img_display, f"A:{display_angle_text}", (text_base_x, text_base_y + 2*line_spacing),
                            cv2.FONT_HERSHEY_SIMPLEX, self.font_scale, (24,240,240), self.text_thickness, cv2.LINE_AA)

        return img_display


if __name__ == "__main__":
    img_path = 'Y1.jpg'           
    img_main = cv2.imread(img_path)

    
    if img_main.shape[2] == 4: # 处理PNG等带Alpha通道的图像
        img_main = cv2.cvtColor(img_main, cv2.COLOR_BGRA2BGR)

    starttime = time.time()
    processor = Processor(img_main) 
    result_img = processor.process()
    endtime = time.time()
    print(f"处理时间: {endtime - starttime:.4f} 秒")

    display_max_h, display_max_w = 800, 900 
    res_h, res_w = result_img.shape[:2]
    if res_h > display_max_h or res_w > display_max_w:
        scale = min(display_max_h/res_h, display_max_w/res_w, 1.0) 
        result_img_display = cv2.resize(result_img, None, fx=scale, fy=scale)
    else:
        result_img_display = result_img

    cv2.imshow("out", result_img_display)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
