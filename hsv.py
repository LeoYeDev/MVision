import cv2
 
def mouse_callback(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:      # 鼠标左击按下
        # 获取鼠标按下位置的hsv值
        h, s, v = hsv[y, x]
        print(f'H:{h}, S:{s}, V:{v}')
 
img = cv2.imread('Y1.jpg')      # 加载图片
image_resize = cv2.resize(img, (0, 0), fx=0.4, fy=0.4)
hsv = cv2.cvtColor(image_resize, cv2.COLOR_BGR2HSV)      # 将图片转为hsv
 
img_name = 'image'
cv2.namedWindow(img_name)
cv2.setMouseCallback(img_name, mouse_callback)       # 设置鼠标回调
 
cv2.imshow(img_name, image_resize)        # 展示图片
cv2.waitKey(0)