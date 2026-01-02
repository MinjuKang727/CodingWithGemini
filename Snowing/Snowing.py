# 프로그램 실행 시 필요한 라이브러리 설치 명령어
# 화면 캡처 및 영상 처리 관련
# pip install opencv-python numpy mss
# 시스템 소리(루프백) 캡처 관련 (중요: PyAudio 대신 이걸 설치해야 합니다)
# pip install PyAudioWPatch
# FFmpeg 제어 관련
# pip install ffmpeg-python
import tkinter as tk
import random
import threading
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item
import sys

class Snowfall:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Snowing")
        
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "black")
        self.root.geometry(f"{self.screen_width}x{self.screen_height}+0+0")

        try:
            import ctypes
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
        except:
            pass

        self.canvas = tk.Canvas(self.root, width=self.screen_width, height=self.screen_height, 
                               bg='black', highlightthickness=0)
        self.canvas.pack()

        self.root.bind("<Escape>", lambda e: self.quit_window())

        self.snowflakes = []
        # 눈송이 개수를 80개로 조절 (방해되지 않는 선에서 적당히)
        for _ in range(80):
            self.add_snowflake(initial=True)

        self.animate()
        
        self.tray_thread = threading.Thread(target=self.setup_tray, daemon=True)
        self.tray_thread.start()

        self.root.mainloop()

    def add_snowflake(self, initial=False):
        # 눈송이 크기를 2~4픽셀 사이로 아주 작게 제한
        size = random.randint(2, 4)
        x = random.randint(0, self.screen_width)
        # 처음 생성 시에는 화면 전체에 뿌리고, 재생성 시에는 화면 위쪽에서 생성
        y = random.randint(0, self.screen_height) if initial else random.randint(-50, -10)
        
        speed = random.uniform(0.7, 2.0) # 눈 속도도 조금 더 차분하게 조절
        
        flake = self.canvas.create_oval(x, y, x + size, y + size, fill="white", outline="white")
        self.snowflakes.append({'id': flake, 'speed': speed, 'size': size})

    def animate(self):
        for flake_data in self.snowflakes:
            flake_id = flake_data['id']
            speed = flake_data['speed']
            size = flake_data['size']
            
            # 아래로 이동
            self.canvas.move(flake_id, 0, speed)
            pos = self.canvas.coords(flake_id)

            # 화면 아래로 완전히 사라지면 위로 재배치
            if pos[1] > self.screen_height:
                new_x = random.randint(0, self.screen_width)
                new_y = random.randint(-20, -5)
                # 좌표를 다시 설정할 때 크기(size)가 유지되도록 x+size, y+size를 정확히 지정
                self.canvas.coords(flake_id, new_x, new_y, new_x + size, new_y + size)
                
        self.root.after(30, self.animate)

    def create_image(self):
        image = Image.new('RGB', (64, 64), color=(255, 255, 255))
        dc = ImageDraw.Draw(image)
        dc.rectangle((16, 16, 48, 48), fill=(0, 150, 255))
        return image

    def setup_tray(self):
        menu = (item('종료(Exit)', self.quit_window),)
        self.icon = pystray.Icon("Snowfall", self.create_image(), "Snowing", menu)
        self.icon.run()

    def quit_window(self):
        if hasattr(self, 'icon'):
            self.icon.stop()
        self.root.quit()
        sys.exit()

if __name__ == "__main__":
    Snowfall()