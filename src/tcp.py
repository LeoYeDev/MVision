# src/tcp_server.py
import socket
import threading
import time
import queue

# --- 数据格式化函数 (参照C#代码中的格式) ---
def format_object_data_for_plc(detected_object_info):
    """
    参数:detected_object_info (dict): 包含 "shape", "color", "robot_x", "robot_y", "angle_deg"。
    返回:str: 格式化后的字符串，准备发送给PLC。
    """
    prefix = "0xU,"  # U for Unknown, 默认前缀
    shape = detected_object_info.get("shape", "unknown")
    color_code = detected_object_info.get("color", "N/A")[0].upper() if detected_object_info.get("color") != "N/A" else "U"
    # processimg.py 返回的 robot_x, robot_y 已经是带正负号和两位小数的字符串
    robot_x = detected_object_info.get("robot_x", "+000.00")
    robot_y = detected_object_info.get("robot_y", "+000.00")
    #手动加上相应的偏移值
    robot_x = float(robot_x) + 0.001  # 假设偏移值为0.01
    robot_y = float(robot_y) + 0.001  # 假设偏移值为0.01
    robot_x_str = f"{robot_x:+07.2f}"
    robot_y_str = f"{robot_y:+07.2f}"

    angle_str_formatted = ""
    angle_deg = detected_object_info.get("angle_deg", 0.0)
    #手动加上相应的偏移值
    if 0<= angle_deg <= 180:
        angle_deg = -angle_deg  # C#逻辑：0-180度为负角度
    else:
        angle_deg = 360 - angle_deg # C#逻辑：180-360度为正角度
    angle_deg = float(angle_deg) + 0.001  # 假设偏移值为0.01
    angle_deg_judge = 5
    # 根据C#代码中的格式调整角度和前缀
    if shape in ["square", "rectangle", "diamond", "trapezoid"]: # 假设这些都用 S，梯形也用S处理角度
        prefix = "0xS"
        #匹配PLC中的行程
        if 0 <= angle_deg <= 90:
            angle_deg = angle_deg -180
        elif 90 < angle_deg <= 180:
            angle_deg = angle_deg - 270
        elif -90 < angle_deg <= 0:
            angle_deg = angle_deg - 90
        angle_deg = angle_deg * angle_deg_judge
        angle_str_formatted = f"{angle_deg:+07.2f}" # 例如 +045.00, +270.00

    elif shape == "circle":
        prefix = "0xC"
        angle_str_formatted = "+000.00"

    elif shape == "hexagon":
        prefix = "0xH"
        angle_deg = angle_deg * angle_deg_judge
        angle_str_formatted = f"{angle_deg:+07.2f}" # 同方形处理
    
    print(f"格式化对象: {shape}, 位置: ({robot_x_str}, {robot_y_str}), 角度: {angle_str_formatted}, 颜色: {color_code}")
    # 最终字符串拼接
    return f"{prefix},{robot_x_str},{robot_y_str},{angle_str_formatted},{color_code}"

def format_error_for_plc(area_identifier_char):
    """
    格式化错误信息。格式: "0xError,Pos" + Workpiece_Area[SortIndex]; (Workpiece_Area是 'A', 'B', 'C', 'D')
    """
    return f"0xError,Pos{area_identifier_char}"

def format_over_for_plc():
    """
    格式化 "Over" 信息。格式: "0xOver" (当工件在纠偏时未移动或符合要求时发送)
    """
    return "0xOver"

class PLCServer:
    def __init__(self, host, port, ui_update_callback=None, request_process_callback=None):
        self.host = host
        self.port = port
        self.server_socket = None
        self.client_handlers = {} #  {client_socket: ClientHandlerThread}
        self.running = False
        self.ui_update_callback = ui_update_callback  # GUI日志更新回调
        self.request_process_callback = request_process_callback # 回调AppUI触发检测/相机操作

    def log(self, message):
        """记录日志，并通过回调更新UI。"""
        print(message) # 打印到控制台
        if self.ui_update_callback:
            try:
                self.ui_update_callback(message)
            except Exception as e:
                print(f"Error in ui_update_callback: {e}")

    def start(self):
        """启动TCP服务器并开始监听连接。"""
        if self.running:
            self.log("服务器已在运行中。")
            return True
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1) # C#中是listen(1)，通常可以更大，如5
            self.running = True
            self.log(f"TCP服务器启动，监听于 {self.host}:{self.port}")

            accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
            accept_thread.start()
            return True
        except Exception as e:
            self.log(f"启动服务器失败: {e}")
            self.running = False
            return False

    def stop(self):
        """停止TCP服务器，关闭所有连接。"""
        self.log("正在停止服务器...")
        self.running = False
        # 关闭所有客户端连接
        for client_socket, handler_thread in list(self.client_handlers.items()): # list() to avoid runtime dict change
            try:
                handler_thread.stop_flag = True # 通知线程停止
                if client_socket:
                    client_socket.shutdown(socket.SHUT_RDWR) # 尝试优雅关闭
                    client_socket.close()
                handler_thread.join(timeout=2.0) # 等待线程退出
            except Exception as e:
                self.log(f"关闭客户端 {handler_thread.client_address} 连接时出错: {e}")
        
        self.client_handlers.clear()

        if self.server_socket:
            try:
                self.server_socket.close() # 关闭服务器套接字
            except Exception as e:
                self.log(f"关闭服务器套接字时出错: {e}")
            self.server_socket = None
        self.log("服务器已停止。")

    def on_client_disconnected(self, client_socket):
        """当客户端处理线程检测到断开时调用。"""
        if client_socket in self.client_handlers:
            del self.client_handlers[client_socket]
            self.log(f"客户端 {client_socket.getpeername() if client_socket.fileno() != -1 else 'unknown'} 的处理器已移除。")


    def send_results_to_plc(self, client_socket, detected_objects_list, area_num_for_this_detection):
        """
        由AppUI调用，用于将一批检测到的工件信息发送给指定的PLC客户端。
        这个方法会找到对应的ClientHandlerThread实例并调用其方法来处理发送。
        """
        if client_socket in self.client_handlers:
            handler = self.client_handlers[client_socket]
            area_char = chr(ord('A') + area_num_for_this_detection - 1) if 1 <= area_num_for_this_detection <= 4 else 'X'
            
            formatted_results = []
            if detected_objects_list: # 如果有检测到物体
                for obj_info in detected_objects_list:
                    formatted_results.append(format_object_data_for_plc(obj_info))
            
            # 即使没有物体，也需要通知handler，它可能需要发送一个特定的空消息或不发送
            # C#中，若无物体，Workpiece_Deetection1 似乎不发送，等待下一个指令
            # 我们让 handler 自己决定如何处理空列表
            handler.set_workpiece_data_to_send(formatted_results)
        else:
            self.log(f"错误: 尝试发送结果给一个未知的或已断开的PLC客户端 ({client_socket})")

    def send_specific_message_to_plc(self, client_socket, message_type, area_char=None):
        """
        由AppUI调用，用于发送特定控制消息，如 "0xError,PosA" 或 "0xOver"。
        """
        if client_socket in self.client_handlers:
            handler = self.client_handlers[client_socket]
            if message_type == "ERROR_POS":
                if area_char:
                    error_msg = format_error_for_plc(area_char)
                    handler.send_message(error_msg)
                    handler.movement_flag = True # C#逻辑：发送Error后设置MovementFlag
                else:
                    self.log("错误：发送ERROR_POS时未提供区域标识。")
            elif message_type == "OVER":
                # C#逻辑：发送Over前会递增SortIndex，这里SortIndex由handler内部管理
                handler.send_message(format_over_for_plc())
            # 可以扩展其他特定消息
        else:
            self.log(f"错误: 尝试发送特定消息给一个未知的或已断开的PLC客户端 ({client_socket})")

    def _accept_connections(self):
        """在单独线程中接受新的客户端连接。"""
        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                if not self.running: # 解决停止服务器时accept可能引发的问题
                    client_socket.close()
                    break
                
                self.log(f"PLC {client_address} 已连接。")
                
                handler_thread = ClientHandlerThread(client_socket, client_address, self)
                self.client_handlers[client_socket] = handler_thread
                handler_thread.start()

            except socket.timeout: # 如果设置了超时
                continue
            except OSError as e: # 服务器套接字已关闭时会发生
                if self.running: # 只有在服务器应该还在运行时才记录为错误
                    self.log(f"接受连接时发生OSError: {e}")
                break # 服务器套接字可能已关闭，退出循环
            except Exception as e:
                if self.running:
                    self.log(f"接受连接时发生未知错误: {e}")
                break
        self.log("服务器监听线程已停止。")


class ClientHandlerThread(threading.Thread):
    def __init__(self, client_socket, client_address, server_instance):
        super().__init__(daemon=True)
        self.client_socket = client_socket
        self.client_address = client_address
        self.server = server_instance # 回调PLCServer的方法，如log, on_client_disconnected
        self.running = True
        self.stop_flag = False # 用于外部请求停止

        # 每个客户端独立的状态
        self.current_area_num = 0 # 由 "Start" 指令更新
        self.workpiece_information_to_send = [] # 存储当前批次待发送的格式化后的工件字符串
        self.current_send_index = 0
        self.movement_flag = False # 对应C#中的MovementFlag，用于纠偏逻辑
        self.sort_index = 0 # 对应C#中的SortIndex，与AllWorkpiece_Information相关，这里可能用途不同

    def log(self, message):
        """通过服务器实例记录日志。"""
        self.server.log(f"[PLC {self.client_address}] {message}")

    def send_message(self, message):
        """向连接的PLC发送消息。"""
        if not self.running or self.stop_flag:
            return False
        try:
            # C#代码中不加换行符，直接发送字节
            # self.client_socket.sendall((message + "\n").encode('utf-8'))
            self.client_socket.sendall(message.encode('utf-8'))
            self.log(f"已发送: {message}")
            return True
        except socket.error as e:
            self.log(f"发送数据失败: {e}")
            self.running = False # 发送失败通常意味着连接问题
            return False
        except Exception as e:
            self.log(f"发送数据时发生未知错误: {e}")
            self.running = False
            return False
            
    def set_workpiece_data_to_send(self, formatted_data_list):
        """由PLCServer调用，设置当前批次要发送的工件数据。"""
        self.workpiece_information_to_send = formatted_data_list
        self.current_send_index = 0
        if self.workpiece_information_to_send:
            # 发送第一条数据
            if self.send_message(self.workpiece_information_to_send[self.current_send_index]):
                self.current_send_index += 1
            else:
                # 发送失败，清除待发送列表
                self.workpiece_information_to_send = []
                self.current_send_index = 0
        else:
            self.log("没有检测到工件数据需要发送。")
            # 根据C#逻辑，若无工件，不主动发送，等待PLC指令

    def run(self):
        """处理来自单个PLC客户端的通信。"""
        self.log("客户端处理线程已启动。")
        try:
            while self.running and not self.stop_flag:
                try:
                    # C#代码中 buffer = new byte[1024 * 1024 * 2]; r = socketSend.Receive(buffer);
                    # string str = Encoding.UTF8.GetString(buffer, 2, r); // 跳过了前2字节
                    # Python中简单接收
                    data = self.client_socket.recv(1024) # 接收缓冲区大小
                    if not data:
                        self.log("PLC断开连接 (收到空数据)。")
                        self.running = False
                        break
        
                    # C#中跳过了前2字节。这里假设PLC发送的指令不包含那2字节，直接是命令字符串。
                    # 如果PLC确实发送了包含长度或其他信息的前缀字节，需要在此处处理。
                    # 假设直接是命令字符串
                    data = data[2:]  # C#中跳过了前2字节，这里假设PLC发送的指令包含那2字节
                    command = data.decode('utf-8').strip()
                    self.log(f"\n收到指令: '{command}'\n")

                    if not self.server.request_process_callback:
                        self.log("错误：未设置 request_process_callback，无法处理PLC指令。")
                        time.sleep(1)
                        continue

                    # --- 指令处理 ---
                    if command.startswith("Start"): # C# 是 GetString(buffer, 2, 5) == "Start"
                        # 假设"Start"后面可能跟参数，或就是"Start"
                        self.current_area_num = (self.current_area_num % 4) + 1 # 1,2,3,4 循环，同C#
                        self.workpiece_information_to_send = [] # 清空上一批次
                        self.current_send_index = 0
                        self.movement_flag = False # C#中Start会重置MovementFlag
                        self.log(f"-------处理'Start'指令，当前区域: {self.current_area_num}")
                        self.server.request_process_callback(
                            client_socket=self.client_socket,
                            command="START",
                            area_num=self.current_area_num
                        )
                        # 结果将通过 PLCServer.send_results_to_plc -> self.set_workpiece_data_to_send 来设置和发送第一条

                    elif command.startswith("Sort"): # C# 是 GetString(buffer, 2, 4) == "Sort"
                        self.log(f"------处理'Sort'指令，MovementFlag: {self.movement_flag}, SortIndex: {self.sort_index}")
                        self.workpiece_information_to_send = []
                        self.current_send_index = 0
                        
                        detection_mode_for_sort = "REALIGNMENT_RE_DETECTION" if self.movement_flag else "REALIGNMENT_MOVEMENT_DETECTION"
                        self.movement_flag = False # 重置

                        self.server.request_process_callback(
                            client_socket=self.client_socket,
                            command="SORT", # 或者更细分的指令类型
                            area_num=self.current_area_num, # Sort通常在当前区域
                            sort_payload = {"detection_mode": detection_mode_for_sort, "sort_index": self.sort_index}
                        )
                        # C#中SortIndex在发送Over前递增，这里也需要在AppUI回调后处理

                    elif command.startswith("Stop"): # C# 是 GetString(buffer, 2, 4) == "Stop"
                        self.log("------处理'Stop'指令。")
                        self.workpiece_information_to_send = [] # 清空
                        self.current_send_index = 0
                        # self.current_area_num = 0 # C# 中重置AreaNum
                        # self.sort_index = 0 # C# 中重置AllWorkpieceIndex/SortIndex
                        self.server.request_process_callback(client_socket=self.client_socket, command="STOP")
                        # C#中 IscontinueGrabing = false; ScanPointNum = 0; AllWorkpieceIndex = 0; AreaNum = 0;
                        # 这些状态的重置应在 AppUI 的回调中处理相机和应用状态

                    elif command.startswith("OK"): # C# 是 GetString(buffer, 2, 2) == "OK"
                        self.log("------处理'OK'指令。")
                        if self.current_send_index < len(self.workpiece_information_to_send):
                            next_data_to_send = self.workpiece_information_to_send[self.current_send_index]
                            if self.send_message(next_data_to_send):
                                self.current_send_index += 1
                            else:
                                self.workpiece_information_to_send = [] # 发送失败则清空
                                self.current_send_index = 0
                        else:
                            self.log("所有工件信息已发送完毕。")
                            self.workpiece_information_to_send = []
                            self.current_send_index = 0
                    else:
                        self.log(f"------未知指令: '{command}'")

                except socket.timeout:
                    if not self.running or self.stop_flag: break
                    continue # 继续等待数据
                except UnicodeDecodeError:
                    self.log("接收到无法解码为UTF-8的数据。")
                except ConnectionResetError:
                    self.log("PLC连接被重置。")
                    self.running = False
                    break
                except socket.error as e:
                    self.log(f"Socket通信错误: {e}")
                    self.running = False # 通常socket错误意味着连接已中断
                    break
        except Exception as e:
            self.log(f"客户端处理线程发生意外错误: {e}")
        finally:
            if self.client_socket.fileno() != -1 : # 检查socket是否还打开
                self.client_socket.close()
            self.server.on_client_disconnected(self.client_socket) # 通知服务器实例
            self.log("客户端处理线程已结束。")

