import socket
import threading
import time

class PLCCommunicator:
    def __init__(self, host, port, camera_trigger_callback):
        """
        初始化TCP服务器。
        :param host: 服务器主机IP (e.g., '0.0.0.0')
        :param port: 服务器端口 (e.g., 2000 from C# code)
        :param camera_trigger_callback: 接收到PLC的 "START" 或 "SORT" 等拍照指令时调用的函数。
                                       此回调应返回一个检测到的物料信息列表 (每个元素是已格式化的字符串)。
        """
        self.host = host
        self.port = port
        self.camera_trigger_callback = camera_trigger_callback
        self.server_socket = None
        self.client_connection = None # C#代码似乎只处理一个PLC连接
        self.client_address = None
        self.running = False
        self.receive_thread = None
        self.plc_expects_data = False # 标志位，表示是否已发送第一条数据，等待PLC的"OK"
        self.data_to_send_queue = [] # 存储待发送的物料信息
        self.data_send_lock = threading.Lock() # 保护 data_to_send_queue

    def _format_object_info_for_plc(self, detected_objects):
        """将Processor返回的结构化数据格式化为PLC期望的字符串列表。"""
        if not detected_objects:
            return []
        
        formatted_strings = []
        for obj_info in detected_objects:
            shape_char = 'P' # 默认多边形
            if obj_info['shape'] == 'square': shape_char = 'S'
            elif obj_info['shape'] == 'circle': shape_char = 'C'
            elif obj_info['shape'] == 'hexagon': shape_char = 'H'
            elif obj_info['shape'] == 'triangle': shape_char = 'T'
            elif obj_info['shape'] == 'rectangle': shape_char = 'R'
            elif obj_info['shape'] == 'diamond': shape_char = 'D'
            
            robot_x_str = obj_info.get('robot_x', "N/A")
            robot_y_str = obj_info.get('robot_y', "N/A")
            angle_val = obj_info.get('angle_deg', -1.0)
            color_simple = obj_info.get('color', "N/A").lower()

            # 坐标格式化: +/-XXX.XX (与C#代码的ToString("000.00")逻辑对应)
            try: rx = float(robot_x_str); robot_x_str = f"{rx:+07.2f}"
            except: pass # 如果是N/A或Err，保持原样
            try: ry = float(robot_y_str); robot_y_str = f"{ry:+07.2f}"
            except: pass

            angle_str = "+000.00" # 默认值，与C#中圆形的角度发送格式一致
            if shape_char != 'C' and angle_val != -1.0 and angle_val is not None :
                try: 
                    ang = float(angle_val)
                    # C#代码对角度正负处理: if (SAngle >= 0) strSAngle = "-" + SAngle.ToString("000.00"); else strSAngle = "+" + (0-SAngle).ToString("000.00");
                    # 这意味着正角度发送为"-", 负角度发送为"+". 这很不寻常，但我们遵循它。
                    # 我们的 calculated_angle_0_360 总是正的。
                    # 如果要完全匹配C#的奇怪逻辑，需要调整。
                    # 这里我们先用一种更标准的 +/- AAA.AA 格式，假设0-360度。
                    # angle_str = f"{ang:+07.2f}" # 例如 +090.00
                    # 按照C#逻辑 (SAngle是OpenCV的原始角度)
                    # 这里我们用的是0-360，假设PLC期望的是这个范围的带符号或特定格式
                    # C#的 SAgle 对于正方形，有一个特殊的调整逻辑。
                    # 我们用0-360度的calculated_angle_0_360，发送时统一格式
                    angle_str = f"{ang:+07.2f}" # 假设我们发送的是标准带符号的角度
                except: pass

            color_char_plc = 'U' # Unknown
            if 'red' in color_simple: color_char_plc = 'R'
            elif 'green' in color_simple: color_char_plc = 'G' # C#用Y代表黄色，B代表蓝色。绿色没有明确对应。
            elif 'blue' in color_simple: color_char_plc = 'B'
            elif 'yellow' in color_simple: color_char_plc = 'Y'
            
            # 格式: "0x{Shape},{RobotX},{RobotY},{Angle},{Color}"
            msg = f"0x{shape_char},{robot_x_str},{robot_y_str},{angle_str},{color_char_plc}"
            formatted_strings.append(msg)
        return formatted_strings

    def _handle_plc_communication(self):
        print(f"[TCP Comm] PLC {self.client_address} 通信线程已启动。")
        conn = self.client_connection
        try:
            while self.running and conn:
                try:
                    conn.settimeout(1.0)
                    data = conn.recv(1024)
                    if not data:
                        print(f"[TCP Comm] PLC {self.client_address} 已断开 (无数据)。")
                        break
                    
                    message = data.decode('utf-8').strip()
                    print(f"[TCP Comm] 从 PLC 收到: {message}")

                    if message.upper() == "START" or message.upper() == "SORT":
                        print("[TCP Comm] 收到 START/SORT 触发信号。")
                        if self.camera_trigger_callback:
                            detected_data_list = self.camera_trigger_callback() # 这应该返回字典列表
                            
                            formatted_strings_to_send = self._format_object_info_for_plc(detected_data_list)

                            with self.data_send_lock:
                                self.data_to_send_queue = formatted_strings_to_send
                                print(f"[TCP Comm] 准备发送 {len(self.data_to_send_queue)} 条物料信息。")

                            if self.data_to_send_queue:
                                first_message = self.data_to_send_queue.pop(0) # 取出第一条
                                print(f"[TCP Comm] 发送给 PLC: {first_message}")
                                conn.sendall((first_message + "\r\n").encode('utf-8'))
                                if not self.data_to_send_queue: # 如果只有一条，发送完就结束
                                    conn.sendall("END_OF_DATA\r\n".encode('utf-8'))
                                    print("[TCP Comm] END_OF_DATA 已发送 (单条数据)。")
                            else: # 没有检测到物料
                                conn.sendall("NO_DATA\r\n".encode('utf-8')) # 或其他PLC约定的空消息
                                print("[TCP Comm] 未检测到数据，已通知PLC。")
                    
                    elif message.upper() == "OK":
                        print("[TCP Comm] PLC 回复 OK。")
                        with self.data_send_lock:
                            if self.data_to_send_queue:
                                next_message = self.data_to_send_queue.pop(0)
                                print(f"[TCP Comm] 发送给 PLC: {next_message}")
                                conn.sendall((next_message + "\r\n").encode('utf-8'))
                                if not self.data_to_send_queue: # 如果这是最后一条
                                    conn.sendall("END_OF_DATA\r\n".encode('utf-8'))
                                    print("[TCP Comm] END_OF_DATA 已发送 (多条数据完毕)。")
                            else:
                                print("[TCP Comm] 收到OK，但没有更多数据待发送。")
                                # conn.sendall("END_OF_DATA\r\n".encode('utf-8')) # 也可再发一次结束

                    elif message.upper() == "STOP":
                        print("[TCP Comm] 收到 PLC 的 STOP 命令。")
                        # 此处可以添加停止相机采集等的逻辑，或通知主程序
                        # self.running = False # 如果STOP意味着服务器也停止

                    # 根据C#代码，视觉系统还可能发送 "0xOver" 或 "0xError,PosX"
                    # 这些通常是基于PLC的特定请求（如"Sort"后的偏移检测）或视觉系统自身的状态判断
                    # 这里我们主要处理由"START"触发的检测流程

                except socket.timeout:
                    continue
                except socket.error as e:
                    print(f"[TCP Comm] Socket 错误: {e}")
                    break
                except Exception as e:
                    print(f"[TCP Comm] 处理消息时发生错误: {e}")
                    break
        finally:
            print(f"[TCP Comm] 与 PLC {self.client_address} 的通信结束。")
            if conn:
                conn.close()
            self.client_connection = None # 清理连接

    def start_server(self):
        if self.running:
            print("[TCP Server] 服务器已在运行。")
            return
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            self.running = True
            print(f"[TCP Server] 服务器启动，监听 {self.host}:{self.port}...")
            # 主监听循环
            while self.running:
                try:
                    self.server_socket.settimeout(1.0)
                    if self.client_connection is None: # 只接受一个PLC连接
                        conn, addr = self.server_socket.accept()
                        print(f"[TCP Server] PLC {addr} 已连接。")
                        self.client_connection = conn
                        self.client_address = addr
                        # 为该连接启动通信处理线程
                        self.receive_thread = threading.Thread(target=self._handle_plc_communication)
                        self.receive_thread.daemon = True
                        self.receive_thread.start()
                    else:
                        time.sleep(0.5) # 如果已有连接，则短暂等待
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running: print(f"[TCP Server] 接受连接时出错: {e}")
                    break 
        except Exception as e:
            print(f"[TCP Server] 启动失败: {e}")
            self.running = False
        finally:
            self.stop_server() # 确保资源释放

    def stop_server(self):
        print("[TCP Server] 正在停止服务器...")
        self.running = False
        if self.client_connection:
            try: self.client_connection.close()
            except: pass
            self.client_connection = None
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=1.0)
        if self.server_socket:
            try: self.server_socket.close()
            except: pass
            self.server_socket = None
        print("[TCP Server] 服务器已停止。")

