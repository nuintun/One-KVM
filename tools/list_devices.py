import cv2
import serial.tools.list_ports
import os
import sys

# 隐藏 OpenCV 的错误输出
def suppress_opencv_warnings():
    #cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
    pass

def list_video_devices():
    """列出可用的视频设备及其名称"""
    video_devices = []
    for i in range(10):  # 假设最多有10个视频设备
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            device_name = cap.getBackendName()  # 获取设备名称
            video_devices.append((i, device_name))
            cap.release()
    return video_devices

def list_serial_ports():
    """列出可用的串口设备"""
    return [port.device for port in serial.tools.list_ports.comports()]

def main():
    suppress_opencv_warnings()  # 调用函数以隐藏 OpenCV 的错误输出

    print("可用的视频设备索引及名称:")
    video_devices = list_video_devices()
    if video_devices:
        for index, name in video_devices:
            print(f"视频设备索引: {index}, 名称: {name}")
    else:
        print("未找到视频设备。")

    print("\n可用的串口设备:")
    serial_ports = list_serial_ports()
    if serial_ports:
        for port in serial_ports:
            print(f"串口设备: {port}")
    else:
        print("未找到串口设备。")

if __name__ == "__main__":
    main()
