import tkinter as tk
import time

class StudyTimer:
    def __init__(self, root):
        self.root = root
        self.root.title("순공 타이머")
        self.root.geometry("250x150")
        
        # 핵심 설정: 항상 위에 오게 함
        self.root.attributes("-topmost", True)
        
        self.running = False
        self.seconds = 0
        
        # 시간 표시 레이블
        self.label = tk.Label(root, text="00:00:00", font=("Helvetica", 30))
        self.label.pack(expand=True)
        
        # 버튼 프레임
        btn_frame = tk.Frame(root)
        btn_frame.pack(expand=True, fill="x")
        
        self.start_btn = tk.Button(btn_frame, text="시작", command=self.start)
        self.start_btn.pack(side="left", expand=True)
        
        self.stop_btn = tk.Button(btn_frame, text="정지", command=self.stop)
        self.stop_btn.pack(side="left", expand=True)
        
        self.reset_btn = tk.Button(btn_frame, text="리셋", command=self.reset)
        self.reset_btn.pack(side="left", expand=True)
        
        self.update_timer()

    def update_timer(self):
        if self.running:
            self.seconds += 1
            mins, secs = divmod(self.seconds, 60)
            hours, mins = divmod(mins, 60)
            time_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
            self.label.config(text=time_str)
        
        # 1초마다 자기 자신을 호출 (1000ms)
        self.root.after(1000, self.update_timer)

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def reset(self):
        self.running = False
        self.seconds = 0
        self.label.config(text="00:00:00")

if __name__ == "__main__":
    root = tk.Tk()
    timer = StudyTimer(root)
    root.mainloop()