import os, io, json, re, threading, pickle, gc, time, base64
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, Toplevel, Label, Button, Canvas, Scrollbar, ttk
from PIL import Image, ImageTk
import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from pdf2image import convert_from_path
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db as firebase_db

# .env 파일 로드 및 환경 변수 설정
load_dotenv()
GH_TOKEN = os.getenv("GH_TOKEN")
GH_REPO = os.getenv("GH_REPO")
GH_BRANCH = os.getenv("GH_BRANCH", "main")

SCOPES = ['https://www.googleapis.com/auth/drive.file']

class GoogleQuizExtractor:
    def __init__(self, root):
        self.root = root
        self.root.title("방송대 기출 추출 v5.5")
        self.root.geometry("900x800")
        
        self.current_photo = None 
        self.thumbnail_photos = [] 
        # 사용자의 환경에 맞는 poppler 경로 (본인 경로에 맞게 수정 확인)
        self.poppler_path = r'C:\Users\minju\Programming\Small_Project\Qbank\poppler-24.08.0\Library\bin' 

        self.btn_select = tk.Button(root, text="PDF 파일 선택 및 분석 시작", command=self.start_thread, 
                                   width=40, height=2, bg="#4285F4", fg="white", font=("맑은 고딕", 10, "bold"))
        self.btn_select.pack(pady=20)

        self.log_area = scrolledtext.ScrolledText(root, width=110, height=40, bg="#1e1e1e", fg="#ffffff", font=("Consolas", 10))
        self.log_area.pack(pady=10, padx=10)

        if not GH_TOKEN or not GH_REPO:
            self.log("⚠️ 경고: .env 파일에서 GitHub 설정을 읽어오지 못했습니다.")
        
        self.init_firebase()

    def log(self, message):
        self.log_area.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_area.see(tk.END)
        self.root.update_idletasks()

    # --- GitHub 업로드 로직 ---
    def upload_to_github(self, img_bytes, subject, year, test_type, tid):
        def clean_path(text):
            return re.sub(r'[\\/:*?"<>| ]', '_', text)

        safe_subject = clean_path(subject)
        safe_type = clean_path(test_type)
        
        folder_path = f"Qbank/images/{safe_subject}_{year}_{safe_type}"
        filename = f"{tid}.png"  # 타임스탬프 제거, ID로 고정
        full_path = f"{folder_path}/{filename}"
        
        url = f"https://api.github.com/repos/{GH_REPO}/contents/{full_path}"
        headers = {
            "Authorization": f"token {GH_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

        # 1. 기존 파일의 sha 값 확인 (덮어쓰기 필수 단계)
        sha = None
        try:
            res_get = requests.get(url, headers=headers)
            if res_get.status_code == 200:
                sha = res_get.json().get("sha")
        except: pass

        # 2. 업로드 또는 업데이트
        encoded_content = base64.b64encode(img_bytes).decode("utf-8")
        data = {
            "message": f"Upload/Update quiz {tid} for {safe_subject}",
            "content": encoded_content,
            "branch": GH_BRANCH
        }
        if sha: data["sha"] = sha  # sha가 있으면 업데이트(덮어쓰기) 모드로 동작

        try:
            response = requests.put(url, headers=headers, json=data)
            if response.status_code in [200, 201]:
                return f"https://raw.githubusercontent.com/{GH_REPO}/{GH_BRANCH}/{full_path}"
            else:
                self.log(f"❌ GH 업로드 실패: {response.json().get('message')}")
                return None
        except Exception as e:
            self.log(f"❌ GH 네트워크 오류: {e}")
            return None

    # --- Google Drive & OCR 로직 ---
    def get_drive_service(self):
        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token: creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token: creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            with open('token.pickle', 'wb') as token: pickle.dump(creds, token)
        return build('drive', 'v3', credentials=creds)

    def start_thread(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF 파일", "*.pdf")])
        if files: threading.Thread(target=self.main_process, args=(files,), daemon=True).start()

    def main_process(self, files):
        service = self.get_drive_service()
        for f_path in files:
            temp_images = []
            self.log(f"🎬 분석 시작: {os.path.basename(f_path)}")
            try:
                pages = convert_from_path(f_path, 300, poppler_path=self.poppler_path)
                for i, page in enumerate(pages):
                    p = f"temp_{int(time.time())}_{i}.png"
                    page.save(p, "PNG")
                    temp_images.append(p)
                
                u_in = self.select_pages_and_info(temp_images)
                if not u_in or u_in.get("cancel"): continue

                full_text = ""
                for idx in u_in["indices"]:
                    img_p = temp_images[idx]
                    self.log(f"⏳ [{idx+1}p] OCR 처리 중...")
                    media = MediaFileUpload(img_p, mimetype='image/png')
                    file_id = service.files().create(body={'name': 'ocr_t', 'mimeType': 'application/vnd.google-apps.document'}, media_body=media, fields='id').execute().get('id')
                    
                    fh = io.BytesIO()
                    downloader = MediaIoBaseDownload(fh, service.files().export_media(fileId=file_id, mimeType='text/plain'))
                    done = False
                    while not done: _, done = downloader.next_chunk()
                    
                    full_text += fh.getvalue().decode('utf-8').strip() + "\n"
                    service.files().delete(fileId=file_id).execute()

                qs = self.parse_answer_only(full_text) if u_in.get("mode") == "ans" else self.parse_text(full_text)
                result = self.review_and_edit_data(u_in["subject"], u_in["year"], u_in["type"], qs, temp_images, u_in["indices"])
                
                if result["confirm"]:
                    self.merge_quiz_data(u_in["subject"], u_in["year"], u_in["type"], result["data"])
                    self.log(f"✅ 모든 작업 완료 및 저장됨")
            except Exception as e: self.log(f"❌ 오류: {e}")
            finally: self.cleanup(temp_images)
        messagebox.showinfo("완료", "처리가 끝났습니다.")

    def select_pages_and_info(self, image_paths):
        res = {"indices": [], "subject": "", "year": "2024", "type": "", "mode": "quiz", "cancel": True}
        dialog = Toplevel(self.root); dialog.title("정보 입력"); dialog.geometry("950x850")

        f_top = tk.Frame(dialog, pady=10); f_top.pack(fill="x")
        tk.Label(f_top, text="과목:").pack(side="left", padx=5)
        e_sub = tk.Entry(f_top, width=15); e_sub.pack(side="left", padx=5)
        tk.Label(f_top, text="연도:").pack(side="left", padx=5)
        e_yr = tk.Entry(f_top, width=8); e_yr.insert(0, "2024"); e_yr.pack(side="left", padx=5)
        cb = ttk.Combobox(f_top, values=["1학기 중간", "1학기 기말", "2학기 중간", "2학기 기말", "출석 대체", "하계 계절수업", "동계 계절수업"]); cb.set("1학기 기말"); cb.pack(side="left", padx=5)
        
        m_var = tk.StringVar(value="quiz")
        tk.Radiobutton(f_top, text="문제", variable=m_var, value="quiz").pack(side="left")
        tk.Radiobutton(f_top, text="정답", variable=m_var, value="ans").pack(side="left")

        def go():
            if not e_sub.get(): return messagebox.showwarning("누락", "과목명 입력 필수")
            res.update({"indices": [i for i, v in enumerate(vars) if v.get()], "subject": e_sub.get(), "year": e_yr.get(), "type": cb.get(), "mode": m_var.get(), "cancel": False})
            dialog.destroy()

        tk.Button(f_top, text="시작", command=go, bg="#28a745", fg="white", width=10).pack(side="right", padx=10)

        canvas = Canvas(dialog); scroll_f = tk.Frame(canvas)
        sb = Scrollbar(dialog, command=canvas.yview); canvas.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0,0), window=scroll_f, anchor="nw")
        scroll_f.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        self.thumbnail_photos = []; vars = []
        for i, p in enumerate(image_paths):
            f = tk.Frame(scroll_f, bd=1, relief="sunken"); f.grid(row=i//3, column=i%3, padx=5, pady=5)
            with Image.open(p) as raw:
                raw.thumbnail((200, 250)); photo = ImageTk.PhotoImage(raw)
                self.thumbnail_photos.append(photo); Label(f, image=photo).pack()
            v = tk.BooleanVar(value=True); tk.Checkbutton(f, text=f"{i+1}p", variable=v).pack(); vars.append(v)
        
        dialog.grab_set(); self.root.wait_window(dialog)
        return res

    # --- 데이터 편집 및 이미지 뷰어 ---
    def review_and_edit_data(self, subject, year, test_type, quiz_list, image_paths, selected_indices):
        final = {"confirm": False, "data": quiz_list}
        win = Toplevel(self.root); win.title(f"편집: {subject}"); win.state('zoomed')
        
        self.img_list = [image_paths[i] for i in selected_indices]; self.curr_idx = 0; self.zoom_scale = 0.6; self.temp_img_bytes = None; self.rect = None

        paned = tk.PanedWindow(win, orient=tk.HORIZONTAL, bg="#444"); paned.pack(fill="both", expand=True)
        
        # --- 왼쪽: 뷰어 프레임 ---
        l_f = tk.Frame(paned, bg="#333")
        tool = tk.Frame(l_f, bg="#222"); tool.pack(fill="x")
        Button(tool, text="◀ 이전", command=lambda: self.move_page(-1)).pack(side="left", padx=5)
        self.lbl_page = Label(tool, text="", bg="#222", fg="white"); self.lbl_page.pack(side="left", padx=10)
        Button(tool, text="다음 ▶", command=lambda: self.move_page(1)).pack(side="left", padx=5)
        self.canvas = Canvas(l_f, bg="#333", cursor="cross"); self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_crop_start); self.canvas.bind("<B1-Motion>", self.on_crop_move); self.canvas.bind("<ButtonRelease-1>", self.on_crop_end)
        self.canvas.bind("<MouseWheel>", self.on_zoom); self.canvas.bind("<ButtonPress-3>", self.on_drag_start); self.canvas.bind("<B3-Motion>", self.on_drag_move)
        paned.add(l_f)

        # --- 오른쪽: 에디터 및 기능 프레임 ---
        r_f = tk.Frame(paned); paned.add(r_f)
        
        func1 = tk.Frame(r_f, bg="#f8f9fa", pady=5); func1.pack(fill="x")
        tk.Label(func1, text="대상 ID:").pack(side="left", padx=5)
        e_tid = tk.Entry(func1, width=5); e_tid.pack(side="left", padx=5)
        
        func2 = tk.Frame(r_f, bg="#e9ecef", pady=5); func2.pack(fill="x")
        tk.Label(func2, text="공통지문:").pack(side="left", padx=5)
        e_ctx = tk.Entry(func2, width=30); e_ctx.pack(side="left", padx=5)
        tk.Label(func2, text="범위(예:1-5):").pack(side="left", padx=5)
        e_rng = tk.Entry(func2, width=8); e_rng.pack(side="left", padx=5)

        # --- 줄 번호 기능을 포함한 에디터 영역 ---
        edit_frame = tk.Frame(r_f)
        edit_frame.pack(fill="both", expand=True)

        line_canvas = tk.Canvas(edit_frame, width=40, bg="#e0e0e0", highlightthickness=0)
        line_canvas.pack(side="left", fill="y")

        # 기존 scrolledtext 대신 Text 위젯 사용 (줄번호 연동을 위해)
        area = tk.Text(edit_frame, font=("Consolas", 10), undo=True, wrap="none")
        area.pack(side="left", fill="both", expand=True)
        
        v_scroll = tk.Scrollbar(edit_frame, command=area.yview)
        v_scroll.pack(side="right", fill="y")
        area.config(yscrollcommand=v_scroll.set)

        area.insert(tk.END, json.dumps(quiz_list, ensure_ascii=False, indent=4))

        # 줄 번호 갱신 로직
        def update_line_numbers(event=None):
            line_canvas.delete("all")
            i = area.index("@0,0")
            while True:
                dline = area.dlineinfo(i)
                if dline is None: break
                y = dline[1]
                linenum = str(i).split(".")[0]
                line_canvas.create_text(35, y, anchor="ne", text=linenum, fill="#666", font=("Consolas", 10))
                i = area.index(f"{i}+1line")

        area.bind("<KeyRelease>", update_line_numbers)
        area.bind("<MouseWheel>", update_line_numbers)
        area.bind("<Configure>", update_line_numbers)

        # --- 내부 로직 함수들 (JSON 에러 핸들링 보강) ---
        def get_current_json():
            raw_text = area.get(1.0, tk.END).strip()
            try: 
                return json.loads(raw_text)
            except json.JSONDecodeError as e:
                # 문법 에러 시 위치와 내용 표시
                error_msg = f"📍 위치: {e.lineno}행 {e.colno}열\n📝 에러: {e.msg}"
                lines = raw_text.splitlines()
                if 0 <= e.lineno - 1 < len(lines):
                    error_msg += f"\n\n해당 라인: {lines[e.lineno-1].strip()}"
                messagebox.showerror("JSON 문법 오류", error_msg)
                
                # 에러 위치로 커서 이동
                area.mark_set("insert", f"{e.lineno}.{e.colno-1}")
                area.see(f"{e.lineno}.{e.colno-1}")
                area.focus_set()
                return None

        def update_area(data):
            area.delete(1.0, tk.END)
            area.insert(tk.END, json.dumps(data, ensure_ascii=False, indent=4))
            win.after(10, update_line_numbers)

        def apply_capture_gh():
            tid = e_tid.get().strip()
            if not tid or not self.temp_img_bytes: return messagebox.showwarning("알림", "ID 입력 및 영역 드래그 필수")
            img_url = self.upload_to_github(self.temp_img_bytes, subject, year, test_type, tid)
            if img_url:
                data = get_current_json()
                if not data: return
                for item in data:
                    if str(item.get('id')) == tid:
                        item['image_url'] = img_url; break
                update_area(data); self.log(f"✅ {tid}번 이미지 반영 완료")

        def apply_answer():
            tid = e_tid.get().strip()
            if not tid: return messagebox.showwarning("알림", "대상 ID를 입력하세요.")
            ans_win = Toplevel(win); ans_win.title("정답 입력"); ans_win.geometry("200x100")
            ans_e = tk.Entry(ans_win); ans_e.pack(pady=10); ans_e.focus_set()
            def set_ans():
                data = get_current_json()
                if not data: return
                for item in data:
                    if str(item.get('id')) == tid: item['answer'] = ans_e.get(); break
                update_area(data); ans_win.destroy()
            Button(ans_win, text="확인", command=set_ans).pack()

        def apply_context():
            ctx_text = e_ctx.get().strip()
            rng_text = e_rng.get().strip()
            if not ctx_text or not rng_text: return messagebox.showwarning("알림", "지문과 범위를 입력하세요.")
            try:
                start, end = map(int, rng_text.split('-'))
                target_ids = [str(i) for i in range(start, end + 1)]
                data = get_current_json()
                if not data: return
                for item in data:
                    if str(item.get('id')) in target_ids: item['context'] = ctx_text
                update_area(data); self.log(f"📝 공통지문 반영 완료 (ID: {rng_text})")
            except: messagebox.showerror("오류", "범위 형식이 잘못되었습니다. (예: 1-5)")

        # 버튼 배치
        Button(func1, text="📸 캡처&GH업로드", command=apply_capture_gh, bg="#3498db", fg="white").pack(side="left", padx=5)
        Button(func1, text="🎯 정답 입력", command=apply_answer, bg="#9b59b6", fg="white").pack(side="left", padx=5)
        Button(func2, text="➕ 지문 적용", command=apply_context, bg="#e67e22", fg="white").pack(side="left", padx=5)

        def save_final_action():
            data = get_current_json()
            if data:
                final["data"] = data; final["confirm"] = True; win.destroy()

        Button(win, text="💾 최종 저장 (Firebase 동기화)", command=save_final_action, bg="#2ecc71", height=2, font=("맑은 고딕", 11, "bold")).pack(fill="x")
        
        # 초기 줄번호 출력
        win.after(100, update_line_numbers)
        self.update_viewer(); win.grab_set(); self.root.wait_window(win)
        return final

    # --- 뷰어 상세 기능 핸들러 ---
    def update_viewer(self):
        with Image.open(self.img_list[self.curr_idx]) as img:
            new_w, new_h = int(img.width * self.zoom_scale), int(img.height * self.zoom_scale)
            resized = img.resize((new_w, new_h), Image.LANCZOS)
            self.current_photo = ImageTk.PhotoImage(resized)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.current_photo)
            self.canvas.config(scrollregion=(0, 0, new_w, new_h))
            self.lbl_page.config(text=f"{self.curr_idx+1}/{len(self.img_list)} ({int(self.zoom_scale*100)}%)")

    def on_zoom(self, e):
        if e.delta > 0: self.zoom_scale *= 1.1
        else: self.zoom_scale /= 1.1
        self.zoom_scale = max(0.2, min(self.zoom_scale, 3.0))
        self.update_viewer()

    def on_drag_start(self, e): self.canvas.scan_mark(e.x, e.y)
    def on_drag_move(self, e): self.canvas.scan_dragto(e.x, e.y, gain=1)

    def on_crop_start(self, e):
        self.start_x, self.start_y = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        if self.rect: self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2)

    def on_crop_move(self, e):
        cur_x, cur_y = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_crop_end(self, e):
        end_x, end_y = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        x1 = min(self.start_x, end_x) / self.zoom_scale
        y1 = min(self.start_y, end_y) / self.zoom_scale
        x2 = max(self.start_x, end_x) / self.zoom_scale
        y2 = max(self.start_y, end_y) / self.zoom_scale
        
        with Image.open(self.img_list[self.curr_idx]) as img:
            buf = io.BytesIO()
            img.crop((x1, y1, x2, y2)).save(buf, format="PNG")
            self.temp_img_bytes = buf.getvalue()

    def move_page(self, d):
        if 0 <= self.curr_idx + d < len(self.img_list):
            self.curr_idx += d; self.update_viewer()

    # --- 텍스트 파싱 및 데이터 병합 ---
    def parse_text(self, t):
        res = []
        for c in re.split(r'\n\s*(?=\d{1,2}\.)', t):
            if not c.strip(): continue
            score_m = re.search(r"\((\d+\.?\d*)점\)", c)
            score = float(score_m.group(1)) if score_m else 0
            match = re.match(r'^(\d{1,2})\.\s*(.*)', c.strip(), re.DOTALL)
            if match:
                q_id, body = match.group(1), match.group(2)
                opts = re.findall(r'(?<=\s)[1-4]\s+([^\n1-4]+)', " " + body)
                res.append({"type":"quiz","id":q_id,"question":re.split(r'\s[1-4]\s', body)[0].strip(),"options":[o.strip() for o in opts[:4]],"answer":None,"score":score,"image_url":""})
        return res

    def parse_answer_only(self, text):
        found = re.findall(r'[1-4]', re.sub(r'\d+~\d+', '', text))
        return [{"id": str(i + 1), "answer": val} for i, val in enumerate(found)]
    
    def init_firebase(self):
        """Firebase Admin SDK 초기화"""
        try:
            # 이미 초기화되어 있는지 확인 (중복 초기화 방지)
            if not firebase_admin._apps:
                cred = credentials.Certificate("serviceAccountKey.json")
                firebase_admin.initialize_app(cred, {
                    'databaseURL': 'https://qbank-f4821-default-rtdb.asia-southeast1.firebasedatabase.app/'
                })
            self.log("📡 Firebase Admin SDK 초기화 성공")
        except Exception as e:
            self.log(f"❌ Firebase 초기화 실패: {e}")

    def merge_quiz_data(self, s, y, t, q):
        # 1. 로컬 저장 (동일)
        local_db = {}
        if os.path.exists('quiz_db.json'):
            with open('quiz_db.json', 'r', encoding='utf-8') as f:
                try: local_db = json.load(f)
                except: pass
        local_db.setdefault(s, {}).setdefault(y, {})[t] = q
        
        with open('quiz_db.json', 'w', encoding='utf-8') as f:
            json.dump(local_db, f, ensure_ascii=False, indent=4)
            
        # 2. Firebase Admin SDK로 저장 (가장 안전)
        try: 
            # 'quizzes' 노드에 직접 접근하여 업데이트
            ref = firebase_db.reference('quizzes')
            ref.set(local_db)  # 전체 데이터를 덮어쓰거나, ref.child(s).set(...)으로 부분 업데이트 가능
            self.log("📡 Firebase 관리자 권한 동기화 성공")
        except Exception as e:
            self.log(f"📡 Firebase 동기화 에러: {e}")

    def cleanup(self, l):
        """작업 완료 후 모든 임시 이미지 파일을 삭제합니다."""
        self.current_photo = None
        self.thumbnail_photos = []
        
        # 1. 분석 과정에서 생성된 temp_... 파일들 삭제
        for p in l:
            try:
                if os.path.exists(p):
                    os.remove(p)
                    # self.log(f"🗑️ 임시 파일 삭제됨: {p}") # 로그가 너무 많으면 생략 가능
            except Exception as e:
                print(f"파일 삭제 오류 ({p}): {e}")

        # 2. 혹시 남아있을지 모르는 모든 temp_*.png 파일 추가 강제 청소
        try:
            for file in os.listdir("."):
                if file.startswith("temp_") and file.endswith(".png"):
                    os.remove(file)
        except:
            pass
            
        self.log("🧹 모든 임시 이미지 파일 정리 완료")

if __name__ == "__main__":
    root = tk.Tk(); app = GoogleQuizExtractor(root); root.mainloop()