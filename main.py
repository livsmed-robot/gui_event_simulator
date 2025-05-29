import tkinter as tk
from tkinter import ttk
import socket
import threading
import json
import struct
import queue
import time
import select
import random
from datetime import datetime

class Application:
    # 상태 옵션을 클래스 변수로 정의
    NUM_ARMS = 4  # Arm의 개수 정의
    state_options = {
        "is_connected": ["change", "random", "false", "true"],
        "is_selected": ["change", "random", "false", "true"],
        "is_tracking": ["change", "random", "false", "true"],
        "is_instrument": ["change", "random", "false", "true"],
        "instrument_type": ["change", "random", "none", "fene forceps", "mary dissector", "pre dissector", "clinch forceps", "clip applier", "needle holder", "pre needle", "suture needle", "mono hook", "mono spatular", "mono pre dissector", "mono scissors", "bi fene forceps", "bi mary dissector", "bi pre dissector", "bi blunt dissector"],
        "endoscope_type": ["change", "random", "none", "0 endoscope", "30 endoscope"],
        "homing_type": ["change", "random", "unknown", "done", "drape", "end effector", "slide"],
        "is_clutched": ["change", "random", "false", "true"],
        "esu_state": ["change", "random", "none", "coag", "cut"],
        "manual_type": ["change", "random", "none", "op", "su", "slide"],
        "is_drape": ["change", "random", "false", "true"],
        "is_trocar": ["change", "random", "false", "true"]
    }

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("simulaotr for GUI")
        self.root.geometry("1600x1200")  # 윈도우 크기 설정
        
        # 서버 상태
        self.is_server_running = False
        self.server_socket = None
        self.is_auto_sending = False  # 자동 전송 상태
        self.auto_send_thread = None  # 자동 전송 스레드
        self.is_swap_pedal_auto = False  # 스왑페달 자동 시작 상태
        self.swap_pedal_auto_thread = None  # 스왑페달 자동 시작 스레드
        
        # 메시지 큐 생성
        self.message_queue = queue.Queue()
        
        # 현재 연결된 클라이언트 소켓 저장
        self.current_client = None
        self.client_lock = threading.Lock()
        
        # 상단 컨트롤 프레임
        control_frame = ttk.Frame(self.root)
        control_frame.pack(pady=(10,0))  # 위쪽만 패딩 적용
        
        # 서버 설정 프레임
        server_config_frame = ttk.Frame(control_frame)
        server_config_frame.pack(side=tk.LEFT, padx=5)
        
        # IP 주소 입력
        ip_label = ttk.Label(server_config_frame, text="IP:")
        ip_label.pack(side=tk.LEFT, padx=(0,2))
        self.ip_var = tk.StringVar(value="127.0.0.1")
        self.ip_entry = ttk.Entry(server_config_frame, textvariable=self.ip_var, width=15)
        self.ip_entry.pack(side=tk.LEFT, padx=(0,5))
        
        # 포트 번호 입력
        port_label = ttk.Label(server_config_frame, text="Port:")
        port_label.pack(side=tk.LEFT, padx=(0,2))
        self.port_var = tk.StringVar(value="19738")
        self.port_entry = ttk.Entry(server_config_frame, textvariable=self.port_var, width=6)
        self.port_entry.pack(side=tk.LEFT, padx=(0,5))
        
        # 버튼을 담을 프레임
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(side=tk.LEFT)
        
        # 레이블 생성
        self.label = ttk.Label(button_frame, text="서버 대기중...")
        self.label.pack(side=tk.LEFT, pady=(0,2), padx=5)  # 왼쪽 정렬
        
        # 시작/중지 버튼 생성
        self.button = ttk.Button(button_frame, text="서버 시작", command=self.toggle_server)
        self.button.pack(side=tk.LEFT, padx=5)
        
        # 자동 전송 버튼 생성
        self.auto_send_button = ttk.Button(button_frame, text="메시지 자동전송", command=self.toggle_auto_send)
        self.auto_send_button.pack(side=tk.LEFT, padx=5)
        
        # 스왑페달 버튼 생성
        self.swap_pedal_button = ttk.Button(button_frame, text="스왑페달", command=self.swap_pedal)
        self.swap_pedal_button.pack(side=tk.LEFT, padx=5)
        
        # 스왑페달 자동 시작 버튼 생성
        self.swap_pedal_auto_button = ttk.Button(button_frame, text="스왑페달자동시작", command=self.toggle_swap_pedal_auto)
        self.swap_pedal_auto_button.pack(side=tk.LEFT, padx=5)
        
        # Interval 입력 프레임
        interval_frame = ttk.Frame(button_frame)
        interval_frame.pack(side=tk.LEFT, padx=5)
        
        # Interval 레이블
        interval_label = ttk.Label(interval_frame, text="Interval (ms):")
        interval_label.pack(side=tk.LEFT, padx=(0,5))
        
        # Interval 입력 필드
        self.interval_var = tk.StringVar(value="1000")  # 기본값 1000ms
        self.interval_entry = ttk.Entry(interval_frame, textvariable=self.interval_var, width=8)
        self.interval_entry.pack(side=tk.LEFT)
        
        # 상태 표시를 위한 프레임
        state_frame = ttk.Frame(self.root)
        state_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 4개의 Arm을 위한 컨테이너 프레임
        arms_container = ttk.Frame(state_frame)
        arms_container.pack(fill=tk.BOTH, expand=True)
        
        # weight를 1로 설정하여 4개의 열을 동일한 너비로 설정
        for i in range(4):
            arms_container.grid_columnconfigure(i, weight=1)
        
        # 상태 레이블 생성
        self.state_vars = {}  # 라디오 버튼 변수들을 저장할 딕셔너리
        self.previous_states = {}  # 각 Arm의 이전 상태를 저장할 딕셔너리
        self.state_enabled = {}  # 각 상태의 활성화 여부를 저장할 딕셔너리
        self.state_expanded = {}  # 각 상태의 확장 여부를 저장할 딕셔너리
        
        # 스타일 설정
        style = ttk.Style()
        style.configure('Tray.TButton', padding=0)
        style.configure('StateHeader.TFrame', relief='raised', borderwidth=1)
        
        # 4개의 Arm 생성
        for arm_idx in range(4):
            # Arm을 위한 LabelFrame 생성
            arm_frame = ttk.LabelFrame(arms_container, text=f"Arm {arm_idx + 1}")
            arm_frame.grid(row=0, column=arm_idx, padx=5, pady=5, sticky='nsew')
            
            # 각 Arm의 상태 변수 저장을 위한 중첩 딕셔너리 생성
            self.state_vars[f"Arm {arm_idx + 1}"] = {}
            self.previous_states[f"Arm {arm_idx + 1}"] = {}
            self.state_enabled[f"Arm {arm_idx + 1}"] = {}
            self.state_expanded[f"Arm {arm_idx + 1}"] = {}
            
            # 각 상태 옵션에 대한 라디오 버튼 그룹 생성
            for state_name, options in self.state_options.items():
                # 상태 컨테이너 프레임
                state_container = ttk.Frame(arm_frame)
                state_container.pack(pady=(0,2), padx=5, fill='x')
                
                # 상태 헤더 프레임 (스타일 적용)
                state_header = ttk.Frame(state_container, style='StateHeader.TFrame')
                state_header.pack(fill='x')
                
                # 트레이 아이콘 버튼 (활성화/비활성화 상태도 함께 표시)
                self.state_enabled[f"Arm {arm_idx + 1}"][state_name] = tk.BooleanVar(value=False)  # 초기값 False로 변경
                self.state_expanded[f"Arm {arm_idx + 1}"][state_name] = tk.BooleanVar(value=False)  # 초기값 False로 변경
                tray_button = ttk.Button(
                    state_header,
                    text="[+]",  # 초기 상태는 접혀있으므로 "[+]"로 표시
                    width=3,
                    style='Tray.TButton',
                    command=lambda a=f"Arm {arm_idx + 1}", s=state_name, c=state_container: 
                        self.toggle_state_expansion(a, s, c)
                )
                tray_button.pack(side=tk.LEFT, padx=(5,0))
                
                # 상태 레이블
                label = ttk.Label(state_header, text=state_name)
                label.pack(side=tk.LEFT, padx=5)
                
                # 라디오 버튼을 포함할 컨텐츠 프레임
                content_frame = ttk.Frame(state_container)
                # 초기 상태에서는 pack하지 않음 (접힌 상태로 시작)
                
                # 라디오 버튼용 변수 생성 - 'random'을 기본값으로 설정
                self.state_vars[f"Arm {arm_idx + 1}"][state_name] = tk.StringVar(value="random")
                self.previous_states[f"Arm {arm_idx + 1}"][state_name] = None
                
                # 라디오 버튼 생성
                for i, option in enumerate(options):
                    radio = ttk.Radiobutton(
                        content_frame,
                        text=option,
                        value=option,
                        variable=self.state_vars[f"Arm {arm_idx + 1}"][state_name]
                    )
                    radio.grid(row=i//3, column=i%3, padx=5, sticky='w')
                    # 초기 상태는 비활성화
                    radio.state(['disabled'])
                
                # content_frame을 state_name으로 태그
                content_frame.radio_buttons = content_frame.winfo_children()
            
            # 메시지 전송 버튼 추가
            send_button = ttk.Button(
                arm_frame,
                text="메시지 전송",
                command=lambda arm=f"Arm {arm_idx + 1}": self.send_arm_state(arm)
            )
            send_button.pack(pady=10)
        
        # 하단 메시지 영역 프레임 (전체 높이의 1/3)
        text_frame = ttk.Frame(self.root)
        text_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=10)
        
        # 텍스트 영역을 감싸는 컨테이너 프레임
        text_container = ttk.Frame(text_frame)
        text_container.pack(fill=tk.BOTH, expand=True)
        
        # weight를 1로 설정하여 두 열의 너비를 동일하게 설정
        text_container.grid_columnconfigure(0, weight=1)
        text_container.grid_columnconfigure(1, weight=1)
        
        # 송신 메시지 영역
        send_frame = ttk.LabelFrame(text_container, text="송신 메시지")
        send_frame.grid(row=0, column=0, sticky='nsew', padx=5)
        
        # 송신 텍스트 영역의 높이를 창 높이의 1/3로 설정
        self.sent_text = tk.Text(send_frame, height=10)
        self.sent_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        sent_scrollbar = ttk.Scrollbar(send_frame, command=self.sent_text.yview)
        sent_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.sent_text.config(yscrollcommand=sent_scrollbar.set)
        
        # 수신 메시지 영역
        recv_frame = ttk.LabelFrame(text_container, text="수신 메시지")
        recv_frame.grid(row=0, column=1, sticky='nsew', padx=5)
        
        # 수신 텍스트 영역의 높이를 창 높이의 1/3로 설정
        self.received_text = tk.Text(recv_frame, height=10)
        self.received_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        recv_scrollbar = ttk.Scrollbar(recv_frame, command=self.received_text.yview)
        recv_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.received_text.config(yscrollcommand=recv_scrollbar.set)

        # 창 크기 변경 시 텍스트 영역 높이 조정
        self.root.bind('<Configure>', self.on_window_configure)
    
    def on_window_configure(self, event):
        if event.widget == self.root:
            # 창 높이의 1/3을 텍스트 영역의 높이로 설정
            window_height = event.height
            text_height = int(window_height / 3 / 20)  # 대략적인 라인 수로 변환
            self.sent_text.config(height=text_height)
            self.received_text.config(height=text_height)
    
    def get_current_time(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    def update_label(self, text):
        # GUI 업데이트는 메인 스레드에서 실행
        self.root.after(0, lambda: self.label.config(text=text))
    
    def update_received_text(self, text):
        timestamp = self.get_current_time()
        self.root.after(0, lambda: self.received_text.insert(tk.END, f"[{timestamp}] {text}\n"))
        self.root.after(0, lambda: self.received_text.see(tk.END))
    
    def update_sent_text(self, text):
        timestamp = self.get_current_time()
        self.root.after(0, lambda: self.sent_text.insert(tk.END, f"[{timestamp}] {text}\n"))
        self.root.after(0, lambda: self.sent_text.see(tk.END))
    
    def read_message_with_header(self, sock):
        # 헤더 읽기 (5바이트)
        header_data = sock.recv(5)
        if not header_data or len(header_data) < 5:
            return None
        
        # 헤더에서 메시지 길이 추출 (첫 4바이트)
        message_length = struct.unpack('<I', header_data[:4])[0]
        
        # 메시지 읽기
        message_data = sock.recv(message_length)
        if not message_data or len(message_data) < message_length:
            return None
        
        return message_data.decode('utf-8')
    
    def message_receiver_thread(self):
        while self.is_server_running:
            try:
                with self.client_lock:
                    if not self.current_client:
                        time.sleep(0.01)  # 클라이언트가 없으면 10ms 대기
                        continue
                    
                    # select를 사용하여 데이터 있는지 확인 (10ms 타임아웃)
                    readable, _, _ = select.select([self.current_client], [], [], 0.01)
                    
                    if readable:
                        # 데이터가 있는 동안 계속 읽기
                        while True:
                            try:
                                # 소켓을 non-blocking 모드로 설정
                                self.current_client.setblocking(False)
                                json_str = self.read_message_with_header(self.current_client)
                                
                                if json_str:
                                    try:
                                        # JSON 파싱 및 처리
                                        json_data = json.loads(json_str)
                                        self.update_received_text(f"{json_str}")
                                    except json.JSONDecodeError as e:
                                        self.update_received_text(f"잘못된 JSON 형식: {json_str}")
                                else:
                                    break
                                    
                            except BlockingIOError:
                                # 더 이상 읽을 데이터가 없음
                                break
                            except Exception as e:
                                self.update_label(f"메시지 수신 중 오류: {str(e)}")
                                break
                        
                        # 소켓을 다시 blocking 모드로 설정
                        self.current_client.setblocking(True)
                
            except Exception as e:
                self.update_label(f"수신 스레드 오류: {str(e)}")
                time.sleep(0.01)  # 에러 발생 시 10ms 대기
    
    def create_message_with_header(self, json_data):
        # JSON 데이터를 UTF-8로 인코딩
        json_bytes = json_data.encode('utf-8')
        # 데이터 길이 계산
        data_length = len(json_bytes)
        # 헤더 생성: 4바이트 길이 + 1바이트 0
        # '<I' 는 리틀 엔디안 부호없는 정수(4바이트)
        # 'B' 는 부호없는 char(1바이트)
        header = struct.pack('<IB', data_length, 0)
        # 헤더와 데이터 합치기
        return header + json_bytes
    
    def message_sender_thread(self):
        while self.is_server_running:
            try:
                try:
                    json_message = self.message_queue.get(timeout=0.01)
                    
                    with self.client_lock:
                        if self.current_client:
                            full_message = self.create_message_with_header(json_message)
                            self.current_client.send(full_message)
                            self.update_sent_text(f"{json_message}")
                            self.update_label(f"메시지 전송 완료 (크기: {len(json_message.encode('utf-8'))} 바이트)")
                
                except queue.Empty:
                    continue
                    
            except Exception as e:
                self.update_label(f"메시지 전송 중 오류 발생: {str(e)}")
                with self.client_lock:
                    if self.current_client:
                        self.current_client.close()
                        self.current_client = None
    
    def handle_client(self, client_socket, addr):
        try:
            with self.client_lock:
                self.current_client = client_socket
            
            message = {
                "SOCKET_ENABLE": True
            }
            json_message = json.dumps(message)
            self.message_queue.put(json_message)
            
            while self.is_server_running:
                time.sleep(0.1)
                
        except Exception as e:
            self.update_label(f"클라이언트 처리 중 오류 발생: {str(e)}")
        finally:
            with self.client_lock:
                if self.current_client == client_socket:
                    self.current_client = None
            client_socket.close()
    
    def start_server(self):
        try:
            # IP와 포트 번호 가져오기
            ip = self.ip_var.get()
            try:
                port = int(self.port_var.get())
            except ValueError:
                self.update_label("잘못된 포트 번호입니다.")
                return

            # 이전 연결 정리
            try:
                temp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                temp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                temp_socket.bind((ip, port))
                temp_socket.close()
            except Exception as e:
                self.update_label(f"이전 연결 정리 중 오류: {str(e)}")

            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # 소켓 재사용 옵션 추가
            self.server_socket.bind((ip, port))
            self.server_socket.listen(1)
            self.is_server_running = True
            self.update_label(f"서버가 시작되었습니다. ({ip}:{port}) 연결 대기중...")
            
            # 메시지 송수신 스레드 시작
            sender_thread = threading.Thread(target=self.message_sender_thread)
            sender_thread.daemon = True
            sender_thread.start()
            
            receiver_thread = threading.Thread(target=self.message_receiver_thread)
            receiver_thread.daemon = True
            receiver_thread.start()
            
            while self.is_server_running:
                try:
                    self.server_socket.settimeout(1.0)
                    client_socket, addr = self.server_socket.accept()
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, addr)
                    )
                    client_thread.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.is_server_running:
                        self.update_label(f"연결 처리 중 오류 발생: {str(e)}")
                    break
            
        except Exception as e:
            self.update_label(f"서버 시작 실패: {str(e)}")
            self.is_server_running = False
    
    def toggle_server(self):
        if not self.is_server_running:
            self.button.config(text="서버 중지")
            server_thread = threading.Thread(target=self.start_server)
            server_thread.daemon = True
            server_thread.start()
        else:
            self.is_server_running = False
            if self.server_socket:
                self.server_socket.close()
            self.button.config(text="서버 시작")
            self.update_label("서버가 중지되었습니다.")
    
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)  # 창 닫기 이벤트 처리
        self.root.mainloop()
   
    def on_closing(self):
        self.is_auto_sending = False  # 자동 전송 중지
        if self.auto_send_thread:
            self.auto_send_thread.join(timeout=1.1)
        
        self.is_swap_pedal_auto = False  # 스왑페달 자동 시작 중지
        if self.swap_pedal_auto_thread:
            self.swap_pedal_auto_thread.join(timeout=1.1)
        
        self.is_server_running = False
        if self.server_socket:
            self.server_socket.close()
        self.root.destroy()

    def toggle_state_expansion(self, arm, state_name, container):
        """상태 영역 확장/축소 및 활성화/비활성화 토글"""
        is_expanded = self.state_expanded[arm][state_name].get()
        self.state_expanded[arm][state_name].set(not is_expanded)
        self.state_enabled[arm][state_name].set(not is_expanded)
        
        # 컨테이너의 모든 자식 위젯 중 content_frame 찾기
        content_frame = None
        for child in container.winfo_children():
            if isinstance(child, ttk.Frame) and child.winfo_children() and \
               isinstance(child.winfo_children()[0], ttk.Radiobutton):
                content_frame = child
                break
        
        if content_frame:
            if not is_expanded:  # 현재 접혀있으면 펼치기
                content_frame.pack(fill='x', padx=20)
                # 트레이 아이콘 업데이트
                for child in container.winfo_children()[0].winfo_children():  # header frame의 자식들
                    if isinstance(child, ttk.Button):
                        child.configure(text="[-]")
                        break
                # 라디오 버튼 활성화
                for radio in content_frame.winfo_children():
                    radio.state(['!disabled'])
            else:  # 현재 펼쳐있으면 접기
                content_frame.pack_forget()
                # 트레이 아이콘 업데이트
                for child in container.winfo_children()[0].winfo_children():  # header frame의 자식들
                    if isinstance(child, ttk.Button):
                        child.configure(text="[+]")
                        break
                # 라디오 버튼 비활성화
                for radio in content_frame.winfo_children():
                    radio.state(['disabled'])

    def send_arm_state(self, arm):
        """특정 Arm의 변경된 상태만 전송하는 메서드"""
        changed_states = {}
        arm_index = int(arm.split()[-1]) - 1

        for state_name in self.state_options.keys():
            # 상태가 비활성화되어 있으면 건너뛰기
            if not self.state_expanded[arm][state_name].get():
                continue
                
            current_value = self.state_vars[arm][state_name].get()
            options = self.state_options[state_name]
            
            if current_value == "change":
                # 이전 상태와 다른 값을 선택하기 위해 가능한 값들의 리스트 생성
                possible_values = list(range(len(options[2:])))  # change와 random을 제외한 실제 값들의 인덱스 리스트
                
                # 이전 상태가 있으면 해당 값 제외
                if self.previous_states[arm].get(state_name) is not None:
                    try:
                        possible_values.remove(self.previous_states[arm][state_name])
                    except ValueError:
                        pass
                
                # 남은 값들 중에서 무작위 선택
                if possible_values:
                    value = random.choice(possible_values)
                else:
                    # 가능한 값이 하나밖에 없는 경우 (이전 상태가 유일한 값이었을 경우)
                    value = 0
                
                changed_states[state_name.lower()] = value
                self.previous_states[arm][state_name] = value
                
            elif current_value == "random":
                value = random.randint(0, len(options[2:]) - 1)  # change와 random을 제외한 값들 중에서 선택
                
                # 이전 상태와 비교하여 변경된 경우에만 추가
                if value != self.previous_states[arm].get(state_name):
                    changed_states[state_name.lower()] = value
                    self.previous_states[arm][state_name] = value
                    
            else:
                # change와 random을 제외한 실제 값들 중에서 인덱스 찾기
                value = options[2:].index(current_value)
                
                # 이전 상태와 비교하여 변경된 경우에만 추가
                if value != self.previous_states[arm].get(state_name):
                    changed_states[state_name.lower()] = value
                    self.previous_states[arm][state_name] = value

        # 변경된 상태가 있는 경우에만 메시지 전송
        if changed_states:
            message = {
                "REPORT_TO_GUI": 0,
                "arm_index": arm_index,
                **changed_states
            }
            
            json_message = json.dumps(message)
            self.message_queue.put(json_message)

    def toggle_auto_send(self):
        """자동 전송 시작/중지 토글"""
        if not self.is_auto_sending:
            self.is_auto_sending = True
            self.auto_send_button.config(text="자동전송 중지")
            
            # 자동 전송 스레드 시작
            self.auto_send_thread = threading.Thread(target=self.auto_send_messages)
            self.auto_send_thread.daemon = True
            self.auto_send_thread.start()
        else:
            self.is_auto_sending = False
            self.auto_send_button.config(text="메시지 자동전송")
            if self.auto_send_thread:
                self.auto_send_thread.join(timeout=1.1)  # 스레드가 완전히 종료될 때까지 대기
                self.auto_send_thread = None

    def auto_send_messages(self):
        """자동으로 각 Arm의 메시지 전송 버튼을 무작위로 클릭"""
        try:
            # interval 값 가져오기 (ms 단위를 초 단위로 변환)
            interval = float(self.interval_var.get()) / 1000.0
        except ValueError:
            # interval 값이 잘못된 경우 기본값(1초) 사용
            self.interval_var.set("1000")
            interval = 1.0

        # 활성화된 상태가 있는 Arm들 찾기
        active_arms = []
        for arm_idx in range(1, self.NUM_ARMS + 1):  # 1부터 NUM_ARMS까지
            arm = f"Arm {arm_idx}"
            # 해당 Arm의 활성화된 상태가 있는지 확인
            if any(self.state_expanded[arm][state_name].get() 
                  for state_name in self.state_options.keys()):
                active_arms.append(arm)
        
        if not active_arms:
            self.is_auto_sending = False
            self.auto_send_button.config(text="메시지 자동전송")
            return

        while self.is_auto_sending:
            # 활성화된 Arm들 중에서 무작위로 선택
            arm = random.choice(active_arms)
            
            # 선택된 Arm의 상태 전송
            self.send_arm_state(arm)
            
            # interval 시간만큼 대기
            time.sleep(interval)

    def swap_pedal(self):
        """Arm1과 Arm2의 is_selected 상태를 서로 교환하고 메시지 전송"""
        # Arm1과 Arm2의 is_selected 상태 가져오기
        arm1_selected = self.state_vars["Arm 1"]["is_selected"].get()
        arm2_selected = self.state_vars["Arm 2"]["is_selected"].get()
        
        # 상태 교환
        self.state_vars["Arm 1"]["is_selected"].set(arm2_selected)
        self.state_vars["Arm 2"]["is_selected"].set(arm1_selected)
        
        # Arm1 메시지 전송
        self.send_arm_state("Arm 1")
        
        # Arm3 메시지 전송
        self.send_arm_state("Arm 2")

    def toggle_swap_pedal_auto(self):
        """스왑페달 자동 시작/중지 토글"""
        if not self.is_swap_pedal_auto:
            self.is_swap_pedal_auto = True
            self.swap_pedal_auto_button.config(text="스왑페달자동중지")
            
            # 스왑페달 자동 시작 스레드 시작
            self.swap_pedal_auto_thread = threading.Thread(target=self.auto_swap_pedal)
            self.swap_pedal_auto_thread.daemon = True
            self.swap_pedal_auto_thread.start()
        else:
            self.is_swap_pedal_auto = False
            self.swap_pedal_auto_button.config(text="스왑페달자동시작")
            if self.swap_pedal_auto_thread:
                self.swap_pedal_auto_thread.join(timeout=1.1)
                self.swap_pedal_auto_thread = None

    def auto_swap_pedal(self):
        """자동으로 스왑페달 동작을 반복"""
        try:
            # interval 값 가져오기 (ms 단위를 초 단위로 변환)
            interval = float(self.interval_var.get()) / 1000.0
        except ValueError:
            # interval 값이 잘못된 경우 기본값(1초) 사용
            self.interval_var.set("1000")
            interval = 1.0

        while self.is_swap_pedal_auto:
            # 스왑페달 동작 실행
            self.swap_pedal()
            
            # interval 시간만큼 대기
            time.sleep(interval)

if __name__ == "__main__":
    app = Application()
    app.run()