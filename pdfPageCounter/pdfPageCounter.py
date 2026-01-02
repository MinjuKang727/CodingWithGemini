import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path 

# PDF 라이브러리
from PyPDF2 import PdfReader

# --- PDF 파일 페이지 카운터 함수 ---

def count_pdf_pages(file_path: Path) -> int:
    """PDF 파일의 페이지 수를 반환합니다."""
    try:
        with open(file_path, 'rb') as file:
            reader = PdfReader(file)
            return len(reader.pages)
    except Exception: 
        return 0

# --- GUI 애플리케이션 클래스 ---
class PageCounterApp:
    def __init__(self, master):
        self.master = master
        master.title("📄 PDF 파일/폴더 페이지 카운터 (PDF 전용)")
        master.geometry("600x600")

        self.selected_items = set() 
        self.total_page_count = 0

        style = ttk.Style()
        style.configure('TButton', font=('Helvetica', 10), padding=10)
        style.configure('TLabel', font=('Helvetica', 10), padding=5)

        # 1. 안내 메시지
        ttk.Label(master, 
                  text="[✅ PDF 전용 모드]\n선택된 파일/폴더 내의 PDF 파일만 카운트합니다.",
                  foreground='darkgreen',
                  font=('Helvetica', 10, 'bold')).pack(pady=10)

        # 2. 항목 선택 버튼 프레임
        frame_select = ttk.Frame(master)
        frame_select.pack(pady=5)
        
        self.select_file_button = ttk.Button(frame_select, text="📃 PDF 파일 선택", command=self.select_files)
        self.select_file_button.pack(side=tk.LEFT, padx=10)
        
        self.select_folder_button = ttk.Button(frame_select, text="📁 폴더 선택", command=self.select_folders)
        self.select_folder_button.pack(side=tk.LEFT, padx=10)
        
        self.clear_button = ttk.Button(frame_select, text="초기화", command=self.clear_selection)
        self.clear_button.pack(side=tk.LEFT, padx=10)


        # 3. 선택된 항목 목록 (Listbox)
        ttk.Label(master, text="선택된 항목 목록 (파일 및 폴더):", font=('Helvetica', 10, 'bold')).pack(pady=(10, 0))
        
        frame_list = ttk.Frame(master)
        frame_list.pack(fill='x', padx=15)
        
        scrollbar = ttk.Scrollbar(frame_list, orient=tk.VERTICAL)
        self.listbox = tk.Listbox(frame_list, height=8, width=70, yscrollcommand=scrollbar.set)
        
        scrollbar.config(command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Separator(master, orient='horizontal').pack(fill='x', padx=10, pady=10)


        # 4. 페이지 카운트 실행 버튼
        self.count_button = ttk.Button(master, text="🔢 페이지 카운트 시작", command=self.start_counting)
        self.count_button.pack(pady=5)

        # 5. 결과 표시 영역 (총합 표시)
        self.result_label = ttk.Label(master, text="결과: 카운트 전", font=('Helvetica', 14, 'bold'))
        self.result_label.pack(pady=5)
        
        # 6. 상세 로그 영역
        self.log_text = tk.Text(master, height=12, width=70, state='disabled')
        self.log_text.pack(pady=10)
        
    def log(self, message):
        """로그 메시지를 텍스트 위젯에 추가합니다."""
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def select_files(self):
        """PDF 파일 선택 대화상자를 열고 선택된 파일을 목록에 추가합니다."""
        new_files = filedialog.askopenfilenames(
            title="페이지 카운트할 PDF 파일을 선택하세요",
            filetypes=[("PDF 파일", "*.pdf"), ("모든 파일", "*.*")]
        )
        for item in new_files:
            self.selected_items.add(item)
        self.update_listbox()

    def select_folders(self):
        """폴더 선택 대화상자를 열고 선택된 폴더를 목록에 추가합니다."""
        new_folder = filedialog.askdirectory(title="PDF 파일이 포함된 폴더를 선택하세요")
        if new_folder:
            self.selected_items.add(new_folder)
        self.update_listbox()
        
    def clear_selection(self):
        """선택된 항목 목록을 초기화합니다."""
        self.selected_items.clear()
        self.update_listbox()

    def update_listbox(self):
        """선택된 항목 목록을 Listbox에 업데이트합니다."""
        self.listbox.delete(0, tk.END) 
        
        for item in sorted(list(self.selected_items)):
            path_obj = Path(item)
            item_type = "📁" if path_obj.is_dir() else "📃"
            self.listbox.insert(tk.END, f"{item_type} {path_obj.name}")
            
        self.result_label.config(text=f"결과: {len(self.selected_items)}개 항목 선택 완료")

    def start_counting(self):
        if not self.selected_items:
            self.result_label.config(text="❌ 파일이나 폴더를 먼저 선택해 주세요.", foreground='red')
            return

        self.total_page_count = 0
        self.log_text.config(state='normal'); self.log_text.delete(1.0, tk.END); self.log_text.config(state='disabled')
        self.result_label.config(text="⏳ 카운트 중...", foreground='blue')
        self.master.update()

        self.log("페이지 계산 시작. 대상: PDF 파일")

        file_count = 0
        
        # 선택된 모든 항목 순회
        for item_path_str in self.selected_items:
            path_obj = Path(item_path_str)
            
            # 1. 폴더인 경우: 재귀적으로 PDF 파일 검색
            if path_obj.is_dir():
                self.log(f"\n--- 폴더 검색: {path_obj.name} ---")
                
                # PDF 파일 검색 및 카운트
                for file_path in path_obj.rglob(f"*.pdf"):
                    page_count = count_pdf_pages(file_path)
                    
                    self.total_page_count += page_count
                    file_count += 1
                    self.log_file_result(file_path.name, ".pdf", page_count)
                        
            # 2. 파일인 경우: PDF 파일인지 확인 후 카운트
            elif path_obj.is_file():
                ext = path_obj.suffix.lower()
                
                if ext == ".pdf":
                    page_count = count_pdf_pages(path_obj)
                    
                    self.total_page_count += page_count
                    file_count += 1
                    self.log_file_result(path_obj.name, ext, page_count)
                else:
                    self.log(f"※ 건너뛰기: {path_obj.name} (PDF 파일이 아닙니다.)")
                    continue
                    
        # 최종 결과 표시
        final_result_text = f"✅ 총 PDF 파일 수: {file_count}개 | 총 페이지 수: {self.total_page_count}장"
        self.result_label.config(
            text=final_result_text, 
            foreground='green'
        )
        
        # 로그 영역에 총합을 명확하게 한 번 더 출력 
        self.log("\n--- 작업 완료 ---")
        self.log("="*60)
        self.log(f"*** 최종 합계: 총 PDF 파일 {file_count}개, 총 페이지 {self.total_page_count}장 ***")
        self.log("="*60)

    def log_file_result(self, file_name, ext, page_count):
        """
        로그 출력을 위한 헬퍼 함수
        출력 형식: [파일형식] 파일명\n  페이지 수 (페이지)
        """
        
        # 첫 번째 줄: [파일형식] 파일명
        log_msg = f"[{ext.upper().ljust(4)}] {file_name}"
        self.log(log_msg)
        
        # 두 번째 줄: 공백 2칸 + 페이지 수
        page_line = f"  {page_count} 페이지"
        
        if page_count == 0:
            page_line += " (※ 카운트 실패 또는 0 페이지)"
            
        self.log(page_line)


# --- 메인 실행 ---
if __name__ == "__main__":
    root = tk.Tk()
    app = PageCounterApp(root)
    root.mainloop()