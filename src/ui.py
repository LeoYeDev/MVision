# -- coding: utf-8 --
import sys
import tkinter as tk

from tkinter import scrolledtext, messagebox, ttk, Frame, Label, Button, Radiobutton, Checkbutton, Entry, LabelFrame,StringVar, IntVar
from tkinter.messagebox import *

sys.path.append("./lib/MvImport")
sys.path.append("./lib/Own")
sys.path.append("./config")
from MvCameraControl_class import *
from CamOperation_class import *
from tcp import PLCServer
from processimg import Processor
from param import PLC_SERVER_HOST, PLC_SERVER_PORT, CALIBRATION_FILE_PATH, SCAN_AREA_FILES
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
        self.image_processor = None
        # TCP 服务器实例
        # PLC_SERVER_HOST = "0.0.0.0" # 监听所有接口
        # PLC_SERVER_PORT = 2000      # 与C#代码一致的端口
        # -- 从配置文件读取IP和端口，或在此硬编码 --
        # 假设 param.py 定义了 PLC_SERVER_HOST 和 PLC_SERVER_PORT
        self.SCAN_AREAS = self._load_scan_areas_from_files(SCAN_AREA_FILES)
        try:
            from param import PLC_SERVER_HOST, PLC_SERVER_PORT
            self.log_message(f"成功导入配置: PLC_SERVER_HOST={PLC_SERVER_HOST}, PLC_SERVER_PORT={PLC_SERVER_PORT}")
        except ImportError:
            self.log_message("警告: 无法从 config/param.py 加载服务器配置，使用默认值。")
            PLC_SERVER_HOST = "10.23.149.2"
            PLC_SERVER_PORT = 5000
        # TCP 服务器实例
        self.plc_server = PLCServer(
            host=PLC_SERVER_HOST,
            port=PLC_SERVER_PORT,
            ui_update_callback=self.log_message, # GUI日志回调
            request_process_callback=self.handle_plc_request # PLC请求处理回调
        )

        self.build()
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

    def build(self):
        self.window.title('视觉检测与PLC通信系统 v2')
        # 估算窗口大小：左侧控制区宽度约320-350px，右侧图像800px + 边距，总宽约1180-1200
        # 高度：图像600px + 日志区 (比如200px) + 边距，总高约830-850
        self.window.geometry('1180x830')

        # --- 主框架 ---
        main_frame = Frame(self.window, padx=5, pady=5)
        main_frame.pack(expand=True, fill=tk.BOTH)

        # --- 左侧控制区 ---
        left_controls_frame = Frame(main_frame, width=330, relief=tk.RIDGE, bd=1, padx=10, pady=10)
        left_controls_frame.pack(side=tk.LEFT, fill=tk.Y)
        left_controls_frame.pack_propagate(False)

        # --- 右侧显示区 (图像 + 日志) ---
        right_display_frame = Frame(main_frame, bd=1, relief=tk.SUNKEN)
        right_display_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=(5,0))

        # --- 右侧 - 图像显示区域 ---
        image_view_frame = Frame(right_display_frame, width=800, height=600, bd=1, relief=tk.SOLID) # 固定图像区域大小
        image_view_frame.pack(side=tk.TOP, pady=(0,5))
        image_view_frame.pack_propagate(False) # 防止Label改变Frame大小
        self.panel = Label(image_view_frame, bg="gray") # 初始灰色背景
        self.panel.pack(expand=True, fill=tk.BOTH)

        # --- 右侧 - 日志显示区域 ---
        log_display_frame = LabelFrame(right_display_frame, text="系统与通信日志", padx=5, pady=5, height=200) # 显著减小高度
        log_display_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5,0))
        log_display_frame.pack_propagate(False)
        self.log_text = scrolledtext.ScrolledText(log_display_frame, wrap=tk.WORD, state=tk.DISABLED, height=5) # height控制行数
        self.log_text.pack(expand=True, fill=tk.BOTH)


        # --- 左侧控制区内容 ---

        # 设备操作组
        device_group = LabelFrame(left_controls_frame, text="设备连接与状态", padx=10, pady=10)
        device_group.pack(pady=(0,10), fill=tk.X)

        self.xVariable = StringVar()
        self.device_list = ttk.Combobox(device_group, textvariable=self.xVariable, width=28, state="readonly") # 宽度调整
        self.device_list.pack(pady=(0,5), fill=tk.X)
        self.device_list.bind("<<ComboboxSelected>>", self.on_device_select)

        self.btn_enum_devices = Button(device_group, text='枚举设备', command=self.enum_devices)
        self.btn_enum_devices.pack(pady=5, fill=tk.X)

        device_op_frame = Frame(device_group)
        device_op_frame.pack(pady=5, fill=tk.X)
        self.btn_open_device = Button(device_op_frame, text='打开设备', command=self.open_device)
        self.btn_open_device.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,3))
        self.btn_close_device = Button(device_op_frame, text='关闭设备', command=self.close_device)
        self.btn_close_device.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(3,0))
 
        # 采集控制组
        grabbing_group = LabelFrame(left_controls_frame, text="采集控制", padx=10, pady=10)
        grabbing_group.pack(pady=10, fill=tk.X)

        self.model_val = StringVar(value='continuous')
        trigger_mode_frame = Frame(grabbing_group) # 不再是独立的Frame，直接pack到grabbing_group
        trigger_mode_frame.pack(pady=5, fill=tk.X)
        self.radio_continuous = Radiobutton(trigger_mode_frame, text='连续模式', variable=self.model_val, value='continuous', command=self.set_triggermode)
        self.radio_continuous.pack(side=tk.LEFT, expand=True, anchor='w', padx=(0,5))
        self.radio_trigger = Radiobutton(trigger_mode_frame, text='触发模式', variable=self.model_val, value='triggermode', command=self.set_triggermode)
        self.radio_trigger.pack(side=tk.LEFT, expand=True, anchor='w', padx=(5,0))

        grabbing_buttons_frame = Frame(grabbing_group)
        grabbing_buttons_frame.pack(pady=5, fill=tk.X)
        self.btn_start_grabbing = Button(grabbing_buttons_frame, text='开始采集', command=self.start_grabbing)
        self.btn_start_grabbing.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,3))
        self.btn_stop_grabbing = Button(grabbing_buttons_frame, text='停止采集', command=self.stop_grabbing)
        self.btn_stop_grabbing.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(3,0))

        self.triggercheck_val = IntVar()
        soft_trigger_frame = Frame(grabbing_group)
        soft_trigger_frame.pack(pady=5, fill=tk.X)
        self.checkbtn_trigger_software = Checkbutton(soft_trigger_frame, text='软触发', variable=self.triggercheck_val, onvalue=1, offvalue=0)
        self.checkbtn_trigger_software.pack(side=tk.LEFT, anchor='w')
        self.btn_trigger_once = Button(soft_trigger_frame, text='触发一次', command=self.trigger_once, width=10) #固定宽度
        self.btn_trigger_once.pack(side=tk.RIGHT, padx=(10,0))

        save_image_frame = Frame(grabbing_group)
        save_image_frame.pack(pady=(5,0), fill=tk.X)
        self.btn_save_bmp = Button(save_image_frame, text='保存BMP', command=self.bmp_save)
        self.btn_save_bmp.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,3))
        self.btn_save_jpg = Button(save_image_frame, text='保存JPG', command=self.jpg_save)
        self.btn_save_jpg.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(3,0))


        # 相机参数组
        params_input_frame = LabelFrame(left_controls_frame, text="相机参数", padx=10, pady=10)
        params_input_frame.pack(pady=10, fill=tk.X)

        Label(params_input_frame, text='曝光时间:').grid(row=0, column=0, sticky='w', pady=3)
        self.text_exposure_time = Entry(params_input_frame, width=15)
        self.text_exposure_time.grid(row=0, column=1, sticky='ew', pady=3, padx=5)

        Label(params_input_frame, text='增益:').grid(row=1, column=0, sticky='w', pady=3)
        self.text_gain = Entry(params_input_frame, width=15)
        self.text_gain.grid(row=1, column=1, sticky='ew', pady=3, padx=5)

        Label(params_input_frame, text='帧率:').grid(row=2, column=0, sticky='w', pady=3)
        self.text_frame_rate = Entry(params_input_frame, width=15)
        self.text_frame_rate.grid(row=2, column=1, sticky='ew', pady=3, padx=5)
        params_input_frame.grid_columnconfigure(1, weight=1)

        param_buttons_frame = Frame(params_input_frame) # 按钮放在参数框内部
        param_buttons_frame.grid(row=3, column=0, columnspan=2, pady=(8,0), sticky='ew')
        self.btn_get_parameter = Button(param_buttons_frame, text='获取参数', command=self.get_parameter)
        self.btn_get_parameter.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,3))
        self.btn_set_parameter = Button(param_buttons_frame, text='设置参数', command=self.set_parameter)
        self.btn_set_parameter.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(3,0))

        # PLC 通信组
        plc_frame = LabelFrame(left_controls_frame, text="PLC通信", padx=10, pady=10)
        plc_frame.pack(pady=(10,0), fill=tk.X, side=tk.BOTTOM) # 调整到最下方

        self.btn_start_server = Button(plc_frame, text="启动PLC服务", command=self.start_plc_server)
        self.btn_start_server.pack(fill=tk.X, pady=3)
        self.btn_stop_server = Button(plc_frame, text="停止PLC服务", command=self.stop_plc_server, state=tk.DISABLED)
        self.btn_stop_server.pack(fill=tk.X, pady=3)

    
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
        # 【修复】使用 tk.Entry 的正确方法 (delete 0, END; insert 0, ...)
        self.text_exposure_time.delete(0, tk.END)
        self.text_exposure_time.insert(0, str(self.camera.obj_cam_operation.exposure_time))
        
        self.text_gain.delete(0, tk.END)
        self.text_gain.insert(0, str(self.camera.obj_cam_operation.gain))

        self.text_frame_rate.delete(0, tk.END)
        self.text_frame_rate.insert(0, str(self.camera.obj_cam_operation.frame_rate))
        self.log_message("参数获取成功。")

    def set_parameter(self):
        # 【修复】使用 tk.Entry 的正确方法 get()
        exposure_time_str = self.text_exposure_time.get()
        gain_str = self.text_gain.get()
        frame_rate_str = self.text_frame_rate.get()
        if not all([exposure_time_str, gain_str, frame_rate_str]):
            messagebox.showerror('输入错误', '所有参数框都不能为空。')
            return
        # 传递给相机操作对象
        self.camera.obj_cam_operation.exposure_time = exposure_time_str
        self.camera.obj_cam_operation.gain = gain_str
        self.camera.obj_cam_operation.frame_rate = frame_rate_str
        self.camera.obj_cam_operation.Set_parameter()
        self.log_message("参数设置成功。")

    # --- PLC 请求处理回调 ---
    def handle_plc_request(self, client_socket, command, area_num=0, sort_payload=None):
        self.log_message(f"收到PLC请求: command='{command}', area_num={area_num}, sort_payload={sort_payload}")

        if not self.camera.b_is_run or \
           not hasattr(self.camera, 'obj_cam_operation') or \
           not self.camera.obj_cam_operation:
            self.log_message("错误: 相机未打开或运行，无法响应PLC。")
            return

        detected_objects = []
        detected_objects.clear() # 清除检测到的物体列表
        if command == "START" or command == "SORT":
            self.log_message(f"PLC请求 '{command}', 正在准备图像...")
            # 从 CamOperation 获取最新的信息
            # **重要**: CamOperation_class.py 中的 Work_thread 需要更新 self.latest_info
            time.sleep(0.05)
            detected_objects = getattr(self.camera.obj_cam_operation, 'latest_info', None)
            print(f"获取到信息 ")
            
            if detected_objects is None:
                self.log_message("错误: 未能从相机操作模块获取最新数据以响应PLC。")
                return

            self.log_message(f"图像处理完成。检测到 {len(detected_objects)} 个物体。")

            # --- 发送结果给PLCServer ---
            self.plc_server.send_results_to_plc(client_socket, detected_objects, area_num)
            print(f"已将检测结果发送到PLC: (detected_objects) 个物体。")

            # --- SORT 指令的额外逻辑 (发送 Error 或 Over) ---
            if command == "SORT" and sort_payload:
                area_char_sort = chr(ord('A') + area_num - 1) if 1 <= area_num <= 4 else 'X'
                handler_thread = self.plc_server.client_handlers.get(client_socket)
                is_movement_detection_mode = sort_payload.get("detection_mode") == "REALIGNMENT_MOVEMENT_DETECTION"
                
                if is_movement_detection_mode:
                    self.log_message(f"SORT指令代码未编写。")
                    self.plc_server.send_specific_message_to_plc(client_socket, "OVER")
                    if handler_thread: handler_thread.movement_flag = False # 标记未发生移动/错误

                if handler_thread: # 更新SortIndex (C#中在发送Over前或处理AllWorkpieceInfo时)
                    handler_thread.sort_index = (handler_thread.sort_index + 1) 

        elif command == "STOP":
            self.log_message("PLC请求停止操作，正在执行清理/状态重置...")
            # self.camera.obj_cam_operation.Stop_grabbing() # 可选：是否真的停止相机物理采集
            
            # 重置PLC会话相关的状态 (在对应的ClientHandlerThread中)
            handler = self.plc_server.client_handlers.get(client_socket)
            if handler:
                handler.current_area_num = 0
                handler.sort_index = 0
                handler.workpiece_information_to_send = []
                handler.current_send_index = 0
                handler.movement_flag = False
            self.log_message("已响应PLC的STOP指令，相关状态已重置。")

    def _load_scan_areas_from_files(self, file_paths):
        """
        从一系列文本文件中加载扫描区域(ROI)坐标。每个文件应包含两行，每行两个由空格或逗号分隔的整数:
        第一行: x1 y1 (左上角) 第二行: x2 y2 (右下角)
        """
        loaded_areas = []
        for file_path in file_paths:
            try:
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                    if len(lines) < 2:
                        self.log_message(f"  错误: 文件 '{file_path}' 内容不足两行。")
                        continue
                    # 解析第一行 (x1, y1)
                    parts1 = lines[0].replace(',', ' ').strip().split()
                    # 解析第二行 (x2, y2)
                    parts2 = lines[1].replace(',', ' ').strip().split()
                    
                    if len(parts1) == 2 and len(parts2) == 2:
                        x1, y1 = map(int, parts1)
                        x2, y2 = map(int, parts2)
                        # 计算程序内部使用的 (x, y, width, height) 格式
                        x, y = x1, y1
                        w, h = x2 - x1, y2 - y1
                        loaded_areas.append((x, y, w, h))
                        self.log_message(f"  成功加载区域 '{file_path}': (x={x}, y={y}, w={w}, h={h})")
                    else:
                        self.log_message(f"  错误: 文件 '{file_path}' 格式不正确，每行应包含2个数字。")
            except FileNotFoundError:
                self.log_message(f"  警告: 扫描区域文件 '{file_path}' 未找到。")
            except (ValueError, TypeError):
                self.log_message(f"  错误: 文件 '{file_path}' 中包含非数字内容。")
            except Exception as e:
                self.log_message(f"  加载 '{file_path}' 时发生未知错误: {e}")

        if not loaded_areas:
             self.log_message("警告: 未能从文件加载任何扫描区域，将使用默认全图区域。")
             # 提供一个默认值，例如 800x600，或根据您的相机分辨率调整
             return [(0, 0, 800, 600)]
        return loaded_areas

    def log_message(self, message):
        """线程安全地将消息追加到日志文本区域。"""
        def append_log():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        self.window.after(0, append_log) # 使用 after 确保从主GUI线程更新

    def start_plc_server(self):
        if self.plc_server.start():
            self.btn_start_server.config(state=tk.DISABLED)
            self.btn_stop_server.config(state=tk.NORMAL)
            # self.log_message("PLC服务器已启动。") # PLCServer内部会调用log
        else:
            pass # PLCServer内部会调用log记录失败

    def stop_plc_server(self):
        self.plc_server.stop()
        self.btn_start_server.config(state=tk.NORMAL)
        self.btn_stop_server.config(state=tk.DISABLED)
        # self.log_message("PLC服务器已停止。") # PLCServer内部会调用log

    def on_device_select(self, event=None):
        selection = self.xVariable.get() # 使用self.xVariable
        if selection:
            idx_str = TxtWrapBy("[", "]", selection)
            if idx_str is not None:
                try:
                    self.camera.nSelCamIndex = int(idx_str)
                    self.log_message(f"已选择设备索引: {self.camera.nSelCamIndex}")
                except ValueError:
                    self.log_message(f"错误: 无法从 '{selection}' 解析设备索引。")
                    self.camera.nSelCamIndex = 0
            else:
                 self.log_message(f"错误: 设备名称格式不正确 '{selection}'")
                 self.camera.nSelCamIndex = 0
        else:
            self.camera.nSelCamIndex = 0
    
    def on_closing(self):
        """处理窗口关闭事件，确保资源被正确释放。"""
        if messagebox.askokcancel("退出", "确定要退出程序吗?"):
            self.log_message("正在关闭应用程序...")
            # 停止PLC服务
            if self.plc_server and self.plc_server.running:
                self.stop_plc_server()
            # 关闭相机
            if self.camera and self.camera.b_is_run:
                self.close_device()
            
            self.window.destroy()