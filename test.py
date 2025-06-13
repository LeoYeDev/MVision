#梦开始的地方，OpenCV入门
import cv2 #opencv读取的格式是BGR
import matplotlib.pyplot as plt
import numpy as np 

#matplotlib inline 
img=cv2.imread('cat.jpg')
cv2.imshow("img",img)
cv2.waitKey(2000)
cv2.destroyAllWindows()

blur = cv2.blur(img, (3, 3))# 均值滤波
box1 = cv2.boxFilter(img,-1,(3,3), normalize=True)  # 方框滤波
box2 = cv2.boxFilter(img,-1,(3,3), normalize=False) # 方框滤波
aussian = cv2.GaussianBlur(img, (5, 5), 1)  # 高斯滤波
median = cv2.medianBlur(img, 5)  # 中值滤波

titles = ['Original Image', 'Blur', 'BoxFilter1', 'BoxFilter2', 'Gaussian', 'Median']
images = [img, blur, box1, box2, aussian, median]
for i in range(6):
    plt.subplot(2, 3, i + 1), plt.imshow(images[i], 'gray')
    plt.title(titles[i])
    plt.xticks([]), plt.yticks([])
plt.show()

img_gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)

ret, thresh1 = cv2.threshold(img_gray, 127, 255, cv2.THRESH_BINARY)
ret, thresh2 = cv2.threshold(img_gray, 127, 255, cv2.THRESH_BINARY_INV)
ret, thresh3 = cv2.threshold(img_gray, 127, 255, cv2.THRESH_TRUNC)
ret, thresh4 = cv2.threshold(img_gray, 127, 255, cv2.THRESH_TOZERO)
ret, thresh5 = cv2.threshold(img_gray, 127, 255, cv2.THRESH_TOZERO_INV)

titles = ['Original Image', 'BINARY', 'BINARY_INV', 'TRUNC', 'TOZERO', 'TOZERO_INV']
images = [img, thresh1, thresh2, thresh3, thresh4, thresh5]

for i in range(6):
    plt.subplot(2, 3, i + 1), plt.imshow(images[i], 'gray')
    plt.title(titles[i])
    plt.xticks([]), plt.yticks([])
plt.show()

#读取视频流，本机的摄像头  控制台Ctrl+C退出
# import cv2
# import sys

# def CatchUsbVideo(window_name, camera_idx):
#     cv2.namedWindow(window_name)#写入打开时视频框的名称
#     # 捕捉摄像头
#     cap = cv2.VideoCapture(camera_idx)#camera_idx 的参数是0代表是打开笔记本的内置摄像头，也可以写上自己录制的视频路径
#     while cap.isOpened():#判断摄像头是否打开，打开的话就是返回的是True
#         #读取图像
#         ok, frame = cap.read()#读取一帧图像，该方法返回两个参数，ok true 成功 flase失败，frame一帧的图像，是个三维矩阵，当输入的是一个是视频文件，读完ok==flase
#         if not ok:#如果读取帧数不是正确的则ok就是Flase则该语句就会执行
#             break
            
#         # 显示图像
#         cv2.imshow(window_name, frame)#显示视频到窗口
#         c = cv2.waitKey(10)
#         if c & 0xFF == ord('q'):#键盘按q退出视频
#             break
            
#     cap.release()# 释放摄像头
#     cv2.destroyAllWindows()#销毁所有窗口
    
# if __name__ == '__main__':
#     CatchUsbVideo("camera", 0)
