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

        # 마우스 클릭 통과 (Windows API)
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

        # 하단 배경 그리기 (트리 및 집) - 시야 방해 없는 회색조
        self.draw_background()

        self.root.bind("<Escape>", lambda e: self.quit_window())

        self.snowflakes = []
        for _ in range(70):
            self.add_snowflake(initial=True)

        self.animate()
        
        self.tray_thread = threading.Thread(target=self.setup_tray, daemon=True)
        self.tray_thread.start()
        self.root.mainloop()

    def draw_background(self):
        h = self.screen_height
        w = self.screen_width
        color = "#444444" # 어두운 회색으로 투명하게 보임 (배경이 블랙이므로)

        # 트리 1 (왼쪽)
        self.canvas.create_polygon(100, h-20, 150, h-120, 200, h-20, fill="", outline=color, width=2)
        # 트리 2 (오른쪽)
        self.canvas.create_polygon(w-250, h-20, w-200, h-150, w-150, h-20, fill="", outline=color, width=2)
        # 집 (오른쪽 구석)
        self.canvas.create_rectangle(w-400, h-100, w-300, h-20, outline=color, width=2)
        self.canvas.create_polygon(w-410, h-100, w-350, h-150, w-290, h-100, outline=color, width=2)

    def add_snowflake(self, initial=False):
        size = random.randint(2, 4)
        x = random.randint(0, self.screen_width)
        y = random.randint(0, self.screen_height) if initial else random.randint(-50, -10)
        speed = random.uniform(0.8, 1.8)
        flake = self.canvas.create_oval(x, y, x + size, y + size, fill="white", outline="white")
        self.snowflakes.append({'id': flake, 'speed': speed, 'size': size})

    def animate(self):
        for flake in self.snowflakes:
            self.canvas.move(flake['id'], 0, flake['speed'])
            pos = self.canvas.coords(flake['id'])
            if pos[1] > self.screen_height:
                new_x = random.randint(0, self.screen_width)
                new_y = random.randint(-20, -5)
                self.canvas.coords(flake['id'], new_x, new_y, new_x + flake['size'], new_y + flake['size'])
        self.root.after(30, self.animate)

    def create_image(self):
        # 트레이에 표시될 아이콘 이미지 (단순 생성)
        image = Image.new('RGB', (64, 64), color=(255, 255, 255))
        dc = ImageDraw.Draw(image)
        dc.rectangle((16, 16, 48, 48), fill=(0, 150, 255))
        return image

    def setup_tray(self):
        menu = (item('종료(Exit)', self.quit_window),)
        self.icon = pystray.Icon("Snowfall", self.create_image(), "눈 내리는 중", menu)
        self.icon.run()

    def quit_window(self):
        if hasattr(self, 'icon'): self.icon.stop()
        self.root.destroy()
        sys.exit()

if __name__ == "__main__":
    Snowfall()