import cv2
import numpy as np
import time

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
        self.min_area = 2000
        # 轮廓逼近精度
        self.eps_factor = 0.02

    def _is_trapezoid(self, approx):
        # 判断四边形中是否有一对近似平行的边
        if len(approx) != 4:
            return False
        # 计算每条边的方向向量
        pts = approx.reshape(4,2)
        vecs = [pts[(i+1)%4]-pts[i] for i in range(4)]
        # 计算相邻边与对边的夹角
        def is_parallel(v1, v2):
            ang = abs(np.degrees(np.arctan2(v1[1],v1[0]) - np.arctan2(v2[1],v2[0])))
            return ang<10 or abs(ang-180)<10
        # 检查是否存在一对平行边但非所有边都平行（排除矩形/菱形）
        parallels = [(i,(i+2)%4) for i in range(2) if is_parallel(vecs[i], vecs[i+2])]
        return len(parallels)==1

    def process(self):
        img = self.img.copy()
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        # 合并所有颜色掩膜
        mask = None
        for lo, hi in self.hsv_ranges.values():
            m = cv2.inRange(hsv, np.array(lo), np.array(hi))
            mask = m if mask is None else cv2.bitwise_or(mask, m)
        # 中值滤波 + 闭运算
        mask = cv2.medianBlur(mask, 5)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT,(7,7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
         
        # 边缘检测 & 轮廓提取
        edges, contours, _ = cv2.Canny(mask,50,150), *cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        h, w = img.shape[:2]
        img_area = h * w

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_area:
                continue
            
            # 计算最小外接矩形长宽以及边缘的周长面积
            x,y,bw,bh = cv2.boundingRect(cnt)
            aspect = max(bw/bh, bh/bw)
            area = cv2.contourArea(cnt)
            peri = cv2.arcLength(cnt, True)
            ca_ratio = (peri * peri) / (area + 1e-6)
            # print(f"Contour area: {area}, Perimeter: {peri}, CA ratio: {ca_ratio:.2f} , Aspect: {aspect:.2f}")
            # # 画一个绿色的外接矩形（普通轴对齐矩形）
            # cv2.rectangle(
            #     img, 
            #     pt1=(x,   y), 
            #     pt2=(x+bw, y+bh), 
            #     color=(0, 255, 0),   # BGR：绿色
            #     thickness=2
            # )

            # 长宽比过大可能就是边框
            # 面积占比过大可能就是边框
            if aspect > 8 and area > 0.6 * img_area:
                continue
            
            # 周长–面积比过大可能就是边框
            if ca_ratio > 500:   # 门槛可调
                continue
                

            # 轮廓中心
            M = cv2.moments(cnt)
            cx = M['m10']/M['m00']; cy = M['m01']/M['m00']
            print(f"Contour center: ({cx:.2f}, {cy:.2f})")

            # PCA 主方向
            pts = cnt.reshape(-1,2).astype(np.float32)
            _, eigenvectors = cv2.PCACompute(pts, mean=None)
            vx, vy = eigenvectors[0]

            # 0–360° 角度
            angle = (np.degrees(np.arctan2(vy, vx)) + 360) % 360

            # 可视化：从中心沿主方向画一条线
            length = 50
            x2 = int(cx + length * vx)
            y2 = int(cy + length * vy)
            cv2.arrowedLine(img, (int(cx),int(cy)), (x2,y2), (0,255,255), 2)

            # 标注文本
            cv2.putText(img, f"degree:{angle:.1f}", (int(cx)+10, int(cy)+10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,0), 1)
    

            # 轮廓拟合 (粗绿色)
            cv2.drawContours(img, [cnt], -1, (0,255,0), 2)
            
            # 多边形逼近
            peri   = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, self.eps_factor*peri, True)
            v      = len(approx)

            # 最小外接矩形 (紫色)
            rect = cv2.minAreaRect(cnt)
            # print (f"Rect: {rect}")
            box  = cv2.boxPoints(rect).astype(int)
            cv2.drawContours(img, [box], -1, (50,90,255), 1)

            # 形状判断
            if v == 3:
                shape = 'triangle'
            elif v == 4:
                # 判断菱形 vs 梯形 vs 正方形/矩形
                if self._is_trapezoid(approx):
                    shape = 'trapezoid'
                else:
                    # 判断菱形：四边等长
                    dists = [cv2.norm(approx[i]-approx[(i+1)%4]) for i in range(4)]
                    if max(dists)-min(dists) < 0.1*max(dists):
                        shape = 'diamond'
                    else:
                        # 长宽比区分正方形/矩形
                        (x,y,w,h) = cv2.boundingRect(approx)
                        shape = 'square' if abs(w-h)<0.1*max(w,h) else 'rectangle'
            else:
                # 顶点数很多且圆度高判定为圆形
                circularity = 4*np.pi*area/(peri*peri) if peri>0 else 0
                shape = 'circle' if circularity>0.7 else 'polygon'

            # 中心与角度
            (cx,cy),(_, _), angle = rect
            cx, cy = map(int, (cx,cy))

            # 获取中心颜色标签
            hsv_val = hsv[cy, cx]
            color_label = 'unknown'
            for name, (lo,hi) in self.hsv_ranges.items():
                lo,hi = np.array(lo), np.array(hi)
                if np.all(hsv_val>=lo) and np.all(hsv_val<=hi):
                    color_label = name
                    break

            # # 绘制中心点 & 文本
            # cv2.circle(img, (cx,cy), 4, (0,0,255), -1)
            # cv2.putText(img, f"c{color_label}", (cx-30, cy-10),
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
            # cv2.putText(img, f"{shape}", (cx-30, cy+10),
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
            # cv2.putText(img, f"degree:{angle:.2f}", (cx-30, cy+30),
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,0), 1)
            
        return img


if __name__ == "__main__":
    img = cv2.imread('150.jpg')
    image_resize = cv2.resize(img, (0, 0), fx=0.5, fy=0.5)

    starttime = time.time()
    processtest = Processor(image_resize)
    result_img = processtest.process()
    endtime = time.time()
    print(f"Processing time: {endtime - starttime:.4f} seconds")

    cv2.imshow("Processed", result_img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
