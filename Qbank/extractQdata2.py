import os
import json
import re
import tkinter as tk
from tkinter import filedialog, messagebox, Canvas
from PIL import Image, ImageTk, ImageEnhance
import numpy as np
from pdf2image import convert_from_path
try:
    # 코드 상단에 추가
    import pytesseract

    # 설치 경로를 직접 지정 (본인의 설치 경로 확인 필수)
    # 보통 C:/Program Files/Tesseract-OCR/tesseract.exe 에 있습니다.
    pytesseract.pytesseract.tesseract_cmd = r'"C:\Program Files\Tesseract-OCR\tesseract.exe"'
except ImportError:
    print("pytesseract가 설치되지 않았습니다. 'pip install pytesseract'가 필요합니다.")



class OcrQuizMapper:
    def __init__(self, root):
        self.root = root
        self.root.title("OCR 번호 인식 2단 분할기 v5.9")
        self.root.state('zoomed')
        
        # 설정 (본인 환경에 맞게 수정)
        self.poppler_path = r'C:\Users\minju\Programming\Small_Project\Qbank\poppler-24.08.0\Library\bin'
        # Tesseract 설치 경로 (Windows의 경우 필수)
        # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        
        self.raw_images = []
        self.page_idx = 0
        self.scale = 0.5
        self.quiz_data = [] 
        self.image_folder = "quiz_images" 
        
        if not os.path.exists(self.image_folder):
            os.makedirs(self.image_folder)

        self.setup_ui()

    def setup_ui(self):
        top_bar = tk.Frame(self.root, bg="#2c3e50", height=50)
        top_bar.pack(side="top", fill="x")
        
        tk.Button(top_bar, text="PDF 로드", command=self.load_pdf).pack(side="left", padx=10)
        tk.Button(top_bar, text="🔍 OCR 번호 인식 분할", command=self.auto_segment_ocr, 
                  bg="#9b59b6", fg="white", font=("맑은 고딕", 9, "bold")).pack(side="left", padx=10)
        
        page_frame = tk.Frame(top_bar, bg="#2c3e50")
        page_frame.pack(side="left", padx=20)
        tk.Button(page_frame, text="◀", command=lambda: self.move_page(-1)).pack(side="left")
        self.lbl_page = tk.Label(page_frame, text="0 / 0", fg="white", bg="#2c3e50", width=10)
        self.lbl_page.pack(side="left")
        tk.Button(page_frame, text="▶", command=lambda: self.move_page(1)).pack(side="left")

        tk.Button(top_bar, text="💾 저장", command=self.save_for_web, bg="#27ae60", fg="white").pack(side="right", padx=10)

        self.canvas = Canvas(self.root, bg="gray")
        self.canvas.pack(fill="both", expand=True)

    def auto_segment_ocr(self):
        if not self.raw_images: return
        
        img = self.raw_images[self.page_idx]
        w, h = img.size
        mid = w // 2
        
        # 왼쪽/오른쪽 단 나누기
        columns = [(0, mid), (mid, w)]
        
        for x_offset, x_end in columns:
            col_img = img.crop((x_offset, 0, x_end, h))
            # OCR 데이터 추출 (단어별 좌표 포함)
            data = pytesseract.image_to_data(col_img, output_type=pytesseract.Output.DICT, lang='kor+eng')
            
            num_positions = []
            for i in range(len(data['text'])):
                text = data['text'][i].strip()
                # "1.", "20.", "3)" 같은 문항 번호 패턴 매칭
                if re.match(r'^\d+[\.|\)]', text):
                    num_positions.append(data['top'][i])
            
            # 번호 위치를 기준으로 영역 생성
            for j in range(len(num_positions)):
                y_start = num_positions[j] - 15 # 번호보다 살짝 위를 자름
                y_end = num_positions[j+1] - 20 if j+1 < len(num_positions) else h
                
                new_id = max([q["id"] for q in self.quiz_data], default=0) + 1
                self.quiz_data.append({
                    "id": new_id,
                    "img_src": f"page_{self.page_idx+1}.png",
                    "x": x_offset + 20,
                    "y": max(0, y_start),
                    "w": (x_end - x_offset) - 40,
                    "h": y_end - y_start
                })
        
        self.show_page()
        messagebox.showinfo("완료", "번호 인식 기반 분할이 완료되었습니다.")

    def load_pdf(self):
        f = filedialog.askopenfilename()
        if f:
            self.raw_images = convert_from_path(f, 200, poppler_path=self.poppler_path)
            for i, img in enumerate(self.raw_images):
                img.save(f"{self.image_folder}/page_{i+1}.png", "PNG")
            self.show_page()

    def show_page(self):
        img = self.raw_images[self.page_idx]
        sw, sh = int(img.width * self.scale), int(img.height * self.scale)
        self.photo = ImageTk.PhotoImage(img.resize((sw, sh), Image.Resampling.LANCZOS))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        self.lbl_page.config(text=f"{self.page_idx+1} / {len(self.raw_images)}")
        
        for q in self.quiz_data:
            if q["img_src"] == f"page_{self.page_idx+1}.png":
                x, y, qw, qh = q['x']*self.scale, q['y']*self.scale, q['w']*self.scale, q['h']*self.scale
                self.canvas.create_rectangle(x, y, x+qw, y+qh, outline="#4285F4", width=2)

    def move_page(self, d):
        if 0 <= self.page_idx + d < len(self.raw_images):
            self.page_idx += d; self.show_page()

    def save_for_web(self):
        with open("web_quiz_data.json", "w", encoding="utf-8") as f:
            json.dump(self.quiz_data, f, indent=4, ensure_ascii=False)
        messagebox.showinfo("완료", "데이터가 저장되었습니다.")

if __name__ == "__main__":
    root = tk.Tk(); app = OcrQuizMapper(root); root.mainloop()