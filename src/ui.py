# -- coding: utf-8 --
import sys
import tkinter as tk

from tkinter import * 
from tkinter.messagebox import *
from tkinter import ttk

sys.path.append("./lib/MvImport")
sys.path.append("./lib/Own")
from MvCameraControl_class import *
from CamOperation_class import *

#获取选取设备信息的索引，通过[]之间的字符去解析
def TxtWrapBy(start_str, end, all):
    start = all.find(start_str)
    if start >= 0:
        start += len(start_str)
        end = all.find(end, start)
        if end >= 0:
            return all[start:end].strip()

#将返回的错误码转换为十六进制显示
def ToHexStr(num):
    chaDic = {10: 'a', 11: 'b', 12: 'c', 13: 'd', 14: 'e', 15: 'f'}
    hexStr = ""
    if num < 0:
        num = num + 2**32
    while num >= 16:
        digit = num % 16
        hexStr = chaDic.get(digit, str(digit)) + hexStr
        num //= 16
    hexStr = chaDic.get(num, str(num)) + hexStr   
    return hexStr

class AppUI:
    def __init__(self,window,camera):
        self.window = window
        self.camera = camera
        self.build()

    def build(self):
        #界面设计代码
        self.window.title('BasicDemo')
        self.window.geometry('1150x650')
        self.model_val = tk.StringVar()
        self.triggercheck_val = tk.IntVar()
        self.page = Frame(self.window,height=400,width=60,relief=GROOVE,bd=5,borderwidth=4)
        self.page.pack(expand=True, fill=BOTH)
        self.panel = Label(self.page)
        self.panel.place(x=190, y=10,height=600,width=1000)

        self.xVariable = tkinter.StringVar()
        self.device_list = ttk.Combobox(self.window, textvariable=self.xVariable,width=30)
        self.device_list.place(x=20, y=20)
        self.device_list.bind("<<ComboboxSelected>>", self.xFunc)

        self.label_exposure_time = tk.Label(self.window, text='Exposure Time',width=15, height=1)
        self.label_exposure_time.place(x=20, y=350)
        self.text_exposure_time = tk.Text(self.window,width=15, height=1)
        self.text_exposure_time.place(x=160, y=350)

        self.label_gain = tk.Label(self.window, text='Gain', width=15, height=1)
        self.label_gain.place(x=20, y=400)
        self.text_gain = tk.Text(self.window,width=15, height=1)
        self.text_gain.place(x=160, y=400)

        self.label_frame_rate = tk.Label(self.window, text='Frame Rate', width=15, height=1)
        self.label_frame_rate.place(x=20, y=450)
        self.text_frame_rate  = tk.Text(self.window,width=15, height=1)
        self.text_frame_rate.place(x=160, y=450)

        self.btn_enum_devices = tk.Button(self.window, text='Enum Devices', width=35, height=1, command = self.enum_devices )
        self.btn_enum_devices.place(x=20, y=50)
        self.btn_open_device = tk.Button(self.window, text='Open Device', width=15, height=1, command = self.open_device)
        self.btn_open_device.place(x=20, y=100)
        self.btn_close_device = tk.Button(self.window, text='Close Device', width=15, height=1, command = self.close_device)
        self.btn_close_device.place(x=160, y=100)

        self.radio_continuous = tk.Radiobutton(self.window, text='Continuous',variable=self.model_val, value='continuous',width=15, height=1,command=self.set_triggermode)
        self.radio_continuous.place(x=20,y=150)
        self.radio_trigger = tk.Radiobutton(self.window, text='Trigger Mode',variable=self.model_val, value='triggermode',width=15, height=1,command=self.set_triggermode)
        self.radio_trigger.place(x=160,y=150)
        self.model_val.set(1)

        self.btn_start_grabbing = tk.Button(self.window, text='Start Grabbing', width=15, height=1, command = self.start_grabbing )
        self.btn_start_grabbing.place(x=20, y=200)
        self.btn_stop_grabbing = tk.Button(self.window, text='Stop Grabbing', width=15, height=1, command = self.stop_grabbing)
        self.btn_stop_grabbing.place(x=160, y=200)

        self.checkbtn_trigger_software = tk.Checkbutton(self.window, text='Tigger by Software', variable=self.triggercheck_val, onvalue=1, offvalue=0)
        self.checkbtn_trigger_software.place(x=20,y=250)
        self.btn_trigger_once = tk.Button(self.window, text='Trigger Once', width=15, height=1, command = self.trigger_once)
        self.btn_trigger_once.place(x=160, y=250)

        self.btn_save_bmp = tk.Button(self.window, text='Save as BMP', width=15, height=1, command = self.bmp_save )
        self.btn_save_bmp.place(x=20, y=300)
        self.btn_save_jpg = tk.Button(self.window, text='Save as JPG', width=15, height=1, command = self.jpg_save)
        self.btn_save_jpg.place(x=160, y=300)

        self.btn_get_parameter = tk.Button(self.window, text='Get Parameter', width=15, height=1, command = self.get_parameter)
        self.btn_get_parameter.place(x=20, y=500)
        self.btn_set_parameter = tk.Button(self.window, text='Set Parameter', width=15, height=1, command = self.set_parameter)
        self.btn_set_parameter.place(x=160, y=500)
    
    #ch:设置触发模式 | en:set trigger mode
    def set_triggermode(self):
        strMode = self.model_val.get()
        self.camera.obj_cam_operation.Set_trigger_mode(strMode)

    #ch:设置触发命令 | en:set trigger software
    def trigger_once(self):
        nCommand = self.triggercheck_val.get()
        self.camera.obj_cam_operation.Trigger_once(nCommand)

    #ch:枚举相机 | en:enum devices
    def enum_devices(self):
        self.camera.deviceList = MV_CC_DEVICE_INFO_LIST()
        tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE
        ret = MvCamera.MV_CC_EnumDevices(tlayerType, self.camera.deviceList)
        if ret != 0:
            tkinter.messagebox.showerror('show error','enum devices fail! ret = '+ ToHexStr(ret))

        if self.camera.deviceList.nDeviceNum == 0:
            tkinter.messagebox.showinfo('show info','find no device!')

        print ("Find %d devices!" % self.camera.deviceList.nDeviceNum)

        devList = []
        for i in range(0, self.camera.deviceList.nDeviceNum):
            mvcc_dev_info = cast(self.camera.deviceList.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
            if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE:
                print ("\ngige device: [%d]" % i)
                chUserDefinedName = ""
                for per in mvcc_dev_info.SpecialInfo.stGigEInfo.chUserDefinedName:
                    if 0 == per:
                        break
                    chUserDefinedName = chUserDefinedName + chr(per)
                print ("device model name: %s" % chUserDefinedName)

                nip1 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0xff000000) >> 24)
                nip2 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x00ff0000) >> 16)
                nip3 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x0000ff00) >> 8)
                nip4 = (mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x000000ff)
                print ("current ip: %d.%d.%d.%d\n" % (nip1, nip2, nip3, nip4))
                devList.append("["+str(i)+"]GigE: "+ chUserDefinedName +"("+ str(nip1)+"."+str(nip2)+"."+str(nip3)+"."+str(nip4) +")")
            elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
                print ("\nu3v device: [%d]" % i)
                chUserDefinedName = ""
                for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chUserDefinedName:
                    if per == 0:
                        break
                    chUserDefinedName = chUserDefinedName + chr(per)
                print ("device model name: %s" % chUserDefinedName)

                strSerialNumber = ""
                for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber:
                    if per == 0:
                        break
                    strSerialNumber = strSerialNumber + chr(per)
                print ("user serial number: %s" % strSerialNumber)
                devList.append("["+str(i)+"]USB: "+ chUserDefinedName +"(" + str(strSerialNumber) + ")")
        self.device_list["value"] = devList
        self.device_list.current(0)
    
        #ch:打开相机 | en:open device
    def open_device(self):
        if True == self.camera.b_is_run:
            tkinter.messagebox.showinfo('show info','Camera is Running!')
            return
        self.camera.obj_cam_operation = CameraOperation(self.camera.cam,self.camera.deviceList,self.camera.nSelCamIndex)
        ret = self.camera.obj_cam_operation.Open_device()
        if  0!= ret:
            self.camera.b_is_run = False
        else:
            self.model_val.set('continuous')
            self.camera.b_is_run = True

    # ch:开始取流 | en:Start grab image
    def start_grabbing(self):
        self.camera.obj_cam_operation.Start_grabbing(self.window,self.panel)
        
    # ch:停止取流 | en:Stop grab image
    def stop_grabbing(self):
        self.camera.obj_cam_operation.Stop_grabbing()    

    # ch:关闭设备 | Close device   
    def close_device(self):
        self.camera.obj_cam_operation.Close_device()
        self.camera.b_is_run = False 
        #清除文本框的数值
        self.text_frame_rate.delete(1.0, tk.END)
        self.text_exposure_time.delete(1.0, tk.END)
        self.text_gain.delete(1.0, tk.END)


    #绑定下拉列表至设备信息索引
    def xFunc(event,self):
        self.camera.nSelCamIndex = TxtWrapBy("[","]",self.device_list.get())

    #ch:保存bmp图片 | en:save bmp image
    def bmp_save(self):
        self.camera.obj_cam_operation.b_save_bmp = True

    #ch:保存jpg图片 | en:save jpg image
    def jpg_save(self):
        self.camera.obj_cam_operation.b_save_jpg = True

    def get_parameter(self):
        self.camera.obj_cam_operation.Get_parameter()
        self.text_frame_rate.delete(1.0, tk.END)
        self.text_frame_rate.insert(1.0,self.camera.obj_cam_operation.frame_rate)
        self.text_exposure_time.delete(1.0, tk.END)
        self.text_exposure_time.insert(1.0,self.camera.obj_cam_operation.exposure_time)
        self.text_gain.delete(1.0, tk.END)
        self.text_gain.insert(1.0, self.camera.obj_cam_operation.gain)

    def set_parameter(self):
        self.camera.obj_cam_operation.exposure_time = self.text_exposure_time.get(1.0,tk.END)
        self.camera.obj_cam_operation.exposure_time = self.camera.obj_cam_operation.exposure_time.rstrip("\n")
        self.camera.obj_cam_operation.gain = self.text_gain.get(1.0,tk.END)
        self.camera.obj_cam_operation.gain = self.camera.obj_cam_operation.gain.rstrip("\n")
        self.camera.obj_cam_operation.frame_rate = self.text_frame_rate.get(1.0,tk.END)
        self.camera.obj_cam_operation.frame_rate = self.camera.obj_cam_operation.frame_rate.rstrip("\n")
        self.camera.obj_cam_operation.Set_parameter(self.camera.obj_cam_operation.frame_rate,self.camera.obj_cam_operation.exposure_time,self.camera.obj_cam_operation.gain)

        #ch:设置触发模式 | en:set trigger mode
    def set_triggermode(self):
        strMode = self.model_val.get()
        self.camera.obj_cam_operation.Set_trigger_mode(strMode)

    #ch:设置触发命令 | en:set trigger software
    def trigger_once(self):
        nCommand = self.triggercheck_val.get()
        self.camera.obj_cam_operation.Trigger_once(nCommand)
