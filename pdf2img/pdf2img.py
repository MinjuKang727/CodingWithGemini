from tkinter import Tk, filedialog, Button, Label, Entry, Text, Scrollbar, END, StringVar, messagebox
from tkinter import ttk
import os
import threading
from pathlib import Path
from pdf2image import convert_from_path, exceptions as pdf2image_exceptions
from PIL import Image # 이미지 저장 형식의 유연성을 위해 PIL을 사용

class PDFtoImageConverter(Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF to Image Converter (Poppler 기반)")
        self.geometry("700x650")
        
        self.pdf_paths = []  # 여러 파일 경로를 저장할 리스트
        # 기본 저장 경로: 현재 폴더의 converted_images
        self.output_dir = os.path.join(os.getcwd(), "converted_images") 
        # Poppler 경로를 환경 변수에서 가져오거나 비워둠
        self.poppler_path = self.get_poppler_path()
        
        self.create_widgets()
        
    def get_poppler_path(self):
        """환경 변수에서 Poppler 경로를 찾아 반환합니다."""
        # 이 부분은 Poppler 설치 위치에 따라 사용자가 수동으로 설정해야 할 수도 있습니다.
        # 일반적으로 poppler의 bin 폴더 경로입니다.
        # 예: "C:\\Program Files\\poppler-0.68.0\\bin"
        return "" # 사용자가 직접 설정하도록 유도

    def create_widgets(self):
        # --- PDF 파일 및 경로 설정 ---
        main_frame = ttk.Frame(self, padding="10 10 10 10")
        main_frame.pack(fill='both', expand=True)

        # 0. Poppler 경로 안내 및 입력
        Label(main_frame, text="0. Poppler Path (필수):", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(5, 0))
        Label(main_frame, text="Poppler bin 폴더 경로를 입력하거나 비워두세요 (PATH에 등록된 경우).", font=('Arial', 8)).pack(anchor='w')
        
        frame_poppler = ttk.Frame(main_frame)
        frame_poppler.pack(pady=5, fill='x')
        
        self.poppler_entry = Entry(frame_poppler, width=60)
        self.poppler_entry.insert(0, self.poppler_path)
        self.poppler_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        Button(frame_poppler, text="경로 선택", command=self.select_poppler_path).pack(side='right')

        # 1. PDF 파일 선택
        Label(main_frame, text="\n1. 변환할 PDF 파일 선택 (다중 선택 가능):", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(5, 0))
        Button(main_frame, text="PDF 파일 선택", command=self.select_pdf_files).pack(pady=5)
        
        self.path_listbox = Text(main_frame, height=5, wrap='word', bg='white', relief='sunken')
        self.path_listbox.pack(pady=5, fill='x')

        # 2. 저장 경로 설정
        Label(main_frame, text="2. 이미지 저장 경로 설정:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 0))
        
        frame_output = ttk.Frame(main_frame)
        frame_output.pack(pady=5, fill='x')
        
        self.output_label = Label(frame_output, text=f"{self.output_dir}", bg='white', relief='sunken', anchor='w')
        self.output_label.pack(side='left', fill='x', expand=True, padx=(0, 10))
        Button(frame_output, text="경로 선택", command=self.select_output_directory).pack(side='right')

        # 3. DPI (해상도) 설정
        Label(main_frame, text="3. 해상도 및 형식 설정:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 0))
        
        frame_options = ttk.Frame(main_frame)
        frame_options.pack(pady=5, fill='x')
        
        Label(frame_options, text="DPI 설정:").pack(side='left', padx=5)
        self.dpi_entry = Entry(frame_options, width=5)
        self.dpi_entry.insert(0, "300") # DPI 사용이 일반적임
        self.dpi_entry.pack(side='left', padx=10)
        
        Label(frame_options, text="파일 형식:").pack(side='left', padx=5)
        self.format_var = StringVar(self)
        self.format_combo = ttk.Combobox(frame_options, textvariable=self.format_var, values=["png", "jpeg", "tiff", "ppm"], width=5)
        self.format_combo.current(0) # 기본값 png
        self.format_combo.pack(side='left', padx=10)
        
        
        # 4. 변환 버튼
        self.convert_button = Button(main_frame, text="PDF 변환 시작", command=self.start_conversion_thread, bg='light blue', fg='black', font=('Arial', 12, 'bold'))
        self.convert_button.pack(pady=20, fill='x')

        # 5. 상태 표시 텍스트 영역
        Label(main_frame, text="--- 변환 상태 로그 ---").pack(anchor='w', pady=(5, 0))
        
        frame_log = ttk.Frame(main_frame)
        frame_log.pack(pady=5, fill='both', expand=True)
        
        self.log_text = Text(frame_log, wrap='word', height=8)
        self.log_text.pack(side='left', fill='both', expand=True)
        
        scrollbar = Scrollbar(frame_log, command=self.log_text.yview)
        scrollbar.pack(side='right', fill='y')
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # 초기 메시지
        self.log(f"기본 저장 경로: {self.output_dir}")
        self.log("PDF 파일을 선택하고 '변환 시작' 버튼을 누르세요.")
        self.log("Poppler 경로를 확인해 주세요. (없으면 실행 불가)")


    def log(self, message):
        """텍스트 영역에 메시지를 추가하고 스크롤합니다."""
        self.log_text.insert(END, message + "\n")
        self.log_text.see(END)

    def select_poppler_path(self):
        """Poppler 경로 디렉토리 대화 상자를 열어 경로를 설정합니다."""
        directory = filedialog.askdirectory(title="Poppler 'bin' 폴더를 선택하세요")
        if directory:
            self.poppler_path = directory
            self.poppler_entry.delete(0, END)
            self.poppler_entry.insert(0, directory)
            self.log(f"Poppler 경로가 설정되었습니다: {self.poppler_path}")
            
    def select_pdf_files(self):
        """파일 대화 상자를 열어 여러 PDF 파일을 선택합니다."""
        self.pdf_paths = filedialog.askopenfilenames(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="변환할 PDF 파일을 선택하세요"
        )
        self.path_listbox.delete(1.0, END) # 기존 목록 삭제
        
        if self.pdf_paths:
            for path in self.pdf_paths:
                self.path_listbox.insert(END, os.path.basename(path) + "\n")
            self.log(f"{len(self.pdf_paths)}개의 PDF 파일이 선택되었습니다.")
        else:
            self.log("선택된 파일이 없습니다.")
            self.pdf_paths = []

    def select_output_directory(self):
        """저장 경로 디렉토리 대화 상자를 열어 경로를 설정합니다."""
        directory = filedialog.askdirectory(title="이미지를 저장할 폴더를 선택하세요")
        if directory:
            self.output_dir = directory
            self.output_label.config(text=self.output_dir)
            self.log(f"저장 경로가 다음으로 설정되었습니다: {self.output_dir}")

    def start_conversion_thread(self):
        """UI가 멈추지 않도록 별도의 스레드에서 변환을 시작합니다."""
        if not self.pdf_paths:
            messagebox.showerror("오류", "변환할 PDF 파일을 먼저 선택하세요.")
            return

        # Poppler 경로 확인
        poppler_path_input = self.poppler_entry.get().strip()
        if not poppler_path_input and not os.environ.get('PATH_TO_POPPLER_BIN'):
            # PATH에 등록되어 있지 않고, 입력도 안 된 경우
            messagebox.showerror("오류", "Poppler bin 폴더 경로를 입력하거나 PATH에 등록해야 합니다.")
            return

        try:
            dpi = int(self.dpi_entry.get())
            if dpi <= 0:
                 raise ValueError
        except ValueError:
            messagebox.showerror("오류", "DPI 값은 0보다 큰 정수여야 합니다.")
            return

        # 버튼 비활성화
        self.convert_button.config(state='disabled', text="변환 중...")
        self.log("--- 변환 스레드 시작 ---")

        # 스레드 생성 및 실행
        threading.Thread(target=self.convert_all_pdfs, args=(self.pdf_paths, dpi, self.output_dir, self.format_var.get(), poppler_path_input)).start()

    def convert_all_pdfs(self, pdf_paths, dpi, output_dir, file_format, poppler_path):
        """선택된 모든 PDF 파일을 순차적으로 변환합니다."""
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        total_files = len(pdf_paths)
        
        for index, pdf_path in enumerate(pdf_paths):
            pdf_base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            self.log(f"\n[파일 {index + 1}/{total_files}] 변환 시작: {os.path.basename(pdf_path)}")
            
            try:
                # convert_from_path 호출 (Poppler 경로 사용)
                images = convert_from_path(
                    pdf_path, 
                    dpi=dpi, 
                    output_folder=output_dir, 
                    fmt=file_format,
                    poppler_path=poppler_path if poppler_path else None # 경로가 입력되면 사용
                )
                
                self.log(f"  -> 총 {len(images)} 페이지 변환 완료. 이미지 저장 중...")
                
                # convert_from_path는 이미지 객체 리스트를 반환합니다.
                for page_number, image in enumerate(images):
                    # 파일 이름 설정 (출력 폴더/원본파일명_페이지번호.확장자)
                    output_filename = f"{pdf_base_name}_page_{page_number + 1}.{file_format}"
                    output_path = os.path.join(output_dir, output_filename)
                    
                    # Pillow 객체를 사용하여 저장
                    try:
                        # JPEG는 품질 설정이 필요할 수 있지만, 여기서는 기본 저장
                        image.save(output_path, file_format.upper() if file_format != 'jpg' else 'JPEG') 
                        self.log(f"    -> 저장됨: {output_filename}")
                        
                    except Exception as e:
                        self.log(f"    -> 페이지 저장 오류 (페이지 {page_number + 1}): {e}")

            except pdf2image_exceptions.PDFInfoNotInstalledError as e:
                self.log(f"  -> 오류: Poppler 실행 파일(pdfinfo)을 찾을 수 없습니다. Poppler 경로를 확인하세요.")
                break # 다음 파일로 넘어가지 않고 중단
                
            except Exception as e:
                self.log(f"[파일 {index + 1}/{total_files}] 처리 중 치명적인 오류 발생: {e}")
                
        self.log("\n*** 모든 PDF 파일 변환 프로세스 완료 ***")
        messagebox.showinfo("완료", f"모든 파일 변환이 완료되었습니다.\n결과는 '{output_dir}' 폴더에서 확인하세요.")
        
        # 버튼 다시 활성화
        self.convert_button.config(state='normal', text="PDF 변환 시작")

if __name__ == "__main__":
    app = PDFtoImageConverter()
    app.mainloop()