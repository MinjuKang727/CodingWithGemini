import os
import io
import json
import re
import threading
import pickle
import gc
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, Toplevel, Label, Button, Canvas, Scrollbar, ttk
from PIL import Image, ImageTk

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from pdf2image import convert_from_path

SCOPES = ['https://www.googleapis.com/auth/drive.file']

class GoogleQuizExtractor:
    def __init__(self, root):
        self.root = root
        self.root.title("방송대 기출 PDF 추출 시스템 (v4.4)")
        self.root.geometry("900x800")
        
        self.current_photo = None 
        self.thumbnail_photos = [] # 썸네일 참조 보관용

        self.btn_select = tk.Button(root, text="PDF 파일 선택 및 분석 시작", command=self.start_thread, 
                                   width=40, height=2, bg="#4285F4", fg="white", font=("맑은 고딕", 10, "bold"))
        self.btn_select.pack(pady=20)

        self.log_area = scrolledtext.ScrolledText(root, width=110, height=40, bg="#1e1e1e", fg="#ffffff", font=("Consolas", 10))
        self.log_area.pack(pady=10, padx=10)
        
        self.poppler_path = r'C:\Users\minju\Programming\Small_Project\Qbank\poppler-24.08.0\Library\bin' 

    def log(self, message):
        self.log_area.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_area.see(tk.END)
        self.root.update_idletasks()

    def get_drive_service(self):
        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token: creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            with open('token.pickle', 'wb') as token: pickle.dump(creds, token)
        return build('drive', 'v3', credentials=creds)

    def start_thread(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF 파일", "*.pdf")])
        if not files: return
        self.log_area.delete(1.0, tk.END)
        threading.Thread(target=self.main_process, args=(files,), daemon=True).start()

    def main_process(self, files):
        service = self.get_drive_service()
        for f_path in files:
            temp_images = []
            self.log(f"🎬 분석 시작: {os.path.basename(f_path)}")
            
            try:
                poppler_path = r'C:\Users\minju\Programming\Small_Project\Qbank\poppler-24.08.0\Library\bin' 
                pages = convert_from_path(f_path, 300, poppler_path=poppler_path)
                for i, page in enumerate(pages):
                    p = f"temp_{int(time.time())}_{i}.png"
                    page.save(p, "PNG")
                    temp_images.append(p)
                
                u_in = self.select_pages_and_info(temp_images)
                if u_in["cancel"]: continue

                full_text = ""
                for idx in u_in["indices"]:
                    img_p = temp_images[idx]
                    self.log(f"⏳ [{idx+1}p] Google OCR 처리 중...")
                    media = MediaFileUpload(img_p, mimetype='image/png')
                    file_id = service.files().create(body={'name': 'ocr_t', 'mimeType': 'application/vnd.google-apps.document'}, media_body=media, fields='id').execute().get('id')
                    
                    fh = io.BytesIO()
                    downloader = MediaIoBaseDownload(fh, service.files().export_media(fileId=file_id, mimeType='text/plain'))
                    done = False
                    while not done: _, done = downloader.next_chunk()
                    
                    # OCR 텍스트 추출 확인
                    content = fh.getvalue().decode('utf-8').strip()
                    if content:
                        full_text += content + "\n"
                    else:
                        self.log(f"⚠️ [{idx+1}p] 텍스트를 감지하지 못했습니다.")
                    
                    service.files().delete(fileId=file_id).execute()

                if not full_text.strip():
                    self.log("❌ 추출된 텍스트가 없어 분석을 중단합니다.")
                    continue

                qs = self.parse_text(full_text)
                result = self.review_and_edit_data(u_in["subject"], u_in["year"], u_in["type"], qs, temp_images, u_in["indices"])
                
                if result["confirm"]:
                    self.merge_quiz_data(u_in["subject"], u_in["year"], u_in["type"], result["data"])
                    self.log(f"✅ 저장 완료: {u_in['subject']}")

            except Exception as e:
                self.log(f"❌ 오류 발생: {e}")
            finally:
                self.cleanup(temp_images)

        messagebox.showinfo("완료", "모든 PDF 처리가 완료되었습니다.")

    def select_pages_and_info(self, image_paths):
        result = {"indices": [], "subject": "", "year": "", "type": "", "cancel": True}
        dialog = Toplevel(self.root)
        dialog.title("정보 입력 및 페이지 선택")
        dialog.geometry("950x850")

        info_frame = tk.Frame(dialog, pady=15); info_frame.pack(side="top", fill="x")
        tk.Label(info_frame, text="과목명:").grid(row=0, column=0, padx=5)
        ent_sub = tk.Entry(info_frame, width=20); ent_sub.grid(row=0, column=1, padx=5)
        tk.Label(info_frame, text="연도:").grid(row=0, column=2, padx=5)
        ent_year = tk.Entry(info_frame, width=10); ent_year.insert(0, "2024"); ent_year.grid(row=0, column=3, padx=5)
        cb_type = ttk.Combobox(info_frame, values=["1학기 기말", "2학기 기말", "1학기 중간", "2학기 중간", "출석 대체"]); cb_type.set("1학기 기말"); cb_type.grid(row=0, column=5, padx=5)
        
        canvas = Canvas(dialog)
        scroll_frame = tk.Frame(canvas)
        scrollbar = Scrollbar(dialog, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y"); canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        self.thumbnail_photos = [] # 썸네일 리스트 초기화
        vars = []
        for i, path in enumerate(image_paths):
            f = tk.Frame(scroll_frame, bd=1, relief="sunken", padx=5, pady=5)
            f.grid(row=i//3, column=i%3, padx=10, pady=10)
            
            with Image.open(path) as raw:
                raw.thumbnail((220, 280))
                photo = ImageTk.PhotoImage(raw)
                self.thumbnail_photos.append(photo) # 참조 유지
                Label(f, image=photo).pack()
            
            v = tk.BooleanVar(value=True)
            tk.Checkbutton(f, text=f"{i+1}p 선택", variable=v).pack()
            vars.append(v)
        
        def confirm():
            if not ent_sub.get():
                messagebox.showwarning("입력 누락", "과목명을 입력해주세요.")
                return
            result.update({"indices": [idx for idx, v in enumerate(vars) if v.get()], "subject": ent_sub.get(), "year": ent_year.get(), "type": cb_type.get(), "cancel": False})
            self.thumbnail_photos = [] # 참조 해제
            dialog.destroy()
        
        Button(dialog, text="OCR 분석 시작", command=confirm, bg="#28a745", fg="white", height=2, font=("맑은 고딕", 10, "bold")).pack(side="bottom", fill="x")
        
        dialog.grab_set(); self.root.wait_window(dialog)
        return result

    def review_and_edit_data(self, subject, year, test_type, quiz_list, image_paths, selected_indices):
        final_data = {"confirm": False, "data": quiz_list}
        dialog = Toplevel(self.root)
        dialog.title(f"데이터 검토: {subject}")
        dialog.state('zoomed') 

        self.img_list = [image_paths[i] for i in selected_indices]; self.curr_idx = 0; self.zoom = 1.0
        
        main_container = tk.Frame(dialog); main_container.pack(fill="both", expand=True)
        paned = tk.PanedWindow(main_container, orient=tk.HORIZONTAL, sashwidth=4, bg="#666"); paned.pack(fill="both", expand=True)

        left_frame = tk.Frame(paned, bg="#444")
        tool_bar = tk.Frame(left_frame, bg="#222", pady=8); tool_bar.pack(side="top", fill="x")
        nav_f = tk.Frame(tool_bar, bg="#222"); nav_f.pack(side="left", padx=10)
        Button(nav_f, text="◀ 이전", width=10, command=lambda: self.move_page(-1)).pack(side="left", padx=5)
        self.lbl_page = Label(nav_f, text="", bg="#222", fg="white", width=20, font=("맑은 고딕", 10)); self.lbl_page.pack(side="left")
        Button(nav_f, text="다음 ▶", width=10, command=lambda: self.move_page(1)).pack(side="left", padx=5)

        zoom_f = tk.Frame(tool_bar, bg="#222"); zoom_f.pack(side="right", padx=10)
        Button(zoom_f, text="확대(+)", width=8, command=lambda: self.change_zoom(0.2)).pack(side="right", padx=2)
        Button(zoom_f, text="축소(-)", width=8, command=lambda: self.change_zoom(-0.2)).pack(side="right", padx=2)

        self.canvas = Canvas(left_frame, bg="#333", cursor="fleur", highlightthickness=0); self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_drag_start); self.canvas.bind("<B1-Motion>", self.on_drag_move); self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        paned.add(left_frame)

        right_frame = tk.Frame(paned)
        edit_area = scrolledtext.ScrolledText(right_frame, font=("Consolas", 12))
        edit_area.insert(tk.END, json.dumps(quiz_list, ensure_ascii=False, indent=4)); edit_area.pack(fill="both", expand=True, padx=5, pady=5)
        paned.add(right_frame)

        bottom_bar = tk.Frame(dialog, pady=10); bottom_bar.pack(side="bottom", fill="x")
        
        def on_ok():
            try:
                final_data["data"] = json.loads(edit_area.get(1.0, tk.END))
                final_data["confirm"] = True; dialog.destroy()
            except: messagebox.showerror("JSON 오류", "JSON 형식이 올바르지 않습니다.")

        Button(bottom_bar, text="💾 이 기출 데이터 최종 저장 및 병합", command=on_ok, bg="#4285F4", fg="white", height=2, font=("맑은 고딕", 11, "bold")).pack(fill="x", padx=20)

        self.update_viewer()
        
        def close_review():
            self.current_photo = None; self.canvas.delete("all"); dialog.destroy()
        dialog.protocol("WM_DELETE_WINDOW", close_review)
        
        dialog.grab_set(); self.root.wait_window(dialog)
        return final_data

    def update_viewer(self):
        try:
            with Image.open(self.img_list[self.curr_idx]) as img:
                w, h = img.size
                new_size = (int(w * self.zoom * 0.65), int(h * self.zoom * 0.65))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                self.current_photo = ImageTk.PhotoImage(img)
                self.canvas.delete("all")
                self.canvas.create_image(0, 0, anchor="nw", image=self.current_photo)
                self.canvas.config(scrollregion=self.canvas.bbox("all"))
                self.lbl_page.config(text=f"{self.curr_idx+1} / {len(self.img_list)} ({int(self.zoom*100)}%)")
        except: pass

    def move_page(self, d):
        if 0 <= self.curr_idx + d < len(self.img_list): self.curr_idx += d; self.update_viewer()
    def change_zoom(self, d):
        if 0.1 <= self.zoom + d <= 4.0: self.zoom += d; self.update_viewer()
    def on_mouse_wheel(self, e):
        if e.state & 0x0004: self.change_zoom(0.1 if e.delta > 0 else -0.1)
        else: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units")
    def on_drag_start(self, e): self.canvas.scan_mark(e.x, e.y)
    def on_drag_move(self, e): self.canvas.scan_dragto(e.x, e.y, gain=1)

    def parse_text(self, t):
        quiz_list = []
        chunks = re.split(r'\n\s*(?=\d{1,2}\.)', t)
        for c in chunks:
            match = re.match(r'^(\d{1,2})\.\s*(.*)', c.strip(), re.DOTALL)
            if match:
                q_id = match.group(1); body = match.group(2)
                options = re.findall(r'(?<=\s)[1-4]\s+([^\n1-4①-④]+)', " " + body)
                question = re.split(r'\s[1-4]\s', body)[0].strip()
                quiz_list.append({"id": q_id, "question": question, "options": [o.strip() for o in options[:4]], "answer": None})
        return quiz_list

    def merge_quiz_data(self, s, y, t, q):
        db_path = 'quiz_db.json'
        db = {}
        if os.path.exists(db_path):
            try:
                with open(db_path, 'r', encoding='utf-8') as f:
                    db = json.load(f)
            except: db = {}
            
        if s not in db: db[s] = {}
        if y not in db[s]: db[s][y] = {}
        db[s][y][t] = q
        
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=4)

    def cleanup(self, l):
        self.current_photo = None
        self.thumbnail_photos = [] # 썸네일 참조 완전 해제
        gc.collect()
        time.sleep(1.0) # 삭제 안정성을 위해 대기 시간 연장
        for p in l:
            try:
                if os.path.exists(p): os.remove(p)
            except:
                self.log(f"⚠️ 파일 잠금 해제 지연: {os.path.basename(p)}")

if __name__ == "__main__":
    root = tk.Tk(); app = GoogleQuizExtractor(root); root.mainloop()