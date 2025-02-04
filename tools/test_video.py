# 模块导入
import numpy as np
import cv2 as cv
# 相机捕获
cap = cv.VideoCapture(0,cv.CAP_DSHOW)
#更改默认参数
cap.set(6,cv.VideoWriter.fourcc('M','J','P','G'))# 视频流格式
cap.set(5, 30);# 帧率
cap.set(3, 1280)# 帧宽
cap.set(4, 720)# 帧高
# 获取相机宽高以及帧率
width = cap.get(3)
height  = cap.get(4)
frame = cap.get(5) #帧率只对视频有效，因此返回值为0
#打印信息
print(width ,height)
# 循环
while(True):
    # 获取一帧图片
    ret, img = cap.read()
    # 显示图片
    cv.imshow('img', img)
    # 等待键盘事件
    k = cv.waitKey(1) & 0xFF
    if k == 27:
        break
#资源释放
cap.release()
cv.destroyAllWindows() 