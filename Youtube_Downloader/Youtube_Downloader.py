import os
import sys
import glob
from pathlib import Path
import re
import traceback
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from pytubefix import YouTube
from imageio_ffmpeg import get_ffmpeg_exe
import threading

# --- 설정 및 변수 ---
# PyInstaller로 실행 중일 때만 ffmpeg 경로를 강제 설정
if getattr(sys, 'frozen', False):
    # 실행 파일 내부의 임시 경로에서 ffmpeg 실행 파일을 찾음
    base_path = os.path.join(sys._MEIPASS, 'imageio_ffmpeg', 'binaries')
    
    # ffmpeg로 시작하는 모든 .exe 파일을 찾음
    files = glob.glob(os.path.join(base_path, 'ffmpeg*.exe'))
    if files:
        os.environ["IMAGEIO_FFMPEG_EXE"] = files[0]

DEFAULT_DOWNLOAD_PATH = Path("./Youtube_Downloads")

def resource_path(relative_path):
    try:
        # PyInstaller로 실행 시 임시 폴더 경로를 생성합니다.
        # sys._MEIPASS는 PyInstaller가 파일을 압축 해제하는 임시 경로입니다.
        base_path = sys._MEIPASS
    except Exception:
        # PyInstaller로 실행하지 않을 때(일반 파이썬 실행)는 현재 폴더를 사용합니다.
        base_path = os.path.abspath(".")
    
    # 합쳐진 최종 경로를 반환합니다.
    return os.path.join(base_path, relative_path)

# --- 유틸리티 함수 ---
def sanitize_filename(title):
    """파일 이름에서 Windows 허용 불가 문자를 모두 제거합니다."""
    # 윈도우 파일명 금지 문자: \ / : * ? " < > |
    # 정규식으로 위 문자들을 모두 '_'로 대체
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', title)
    
    # 추가로 파일명 앞뒤의 공백이나 마침표(.) 제거 (Windows에서 오류 유발 가능)
    sanitized = sanitized.strip('. ')
    
    # 파일명이 너무 길 경우(Windows 경로 제한) 대비하여 적절히 자르기
    return sanitized[:100]

# --- GUI 액션 함수 ---
def toggle_resolution_state():
    """다운로드 타입에 따라 해상도 콤보박스의 활성화 상태를 변경합니다."""
    selected_type = type_var.get()
    
    # if selected_type == "Video":
    #     resolution_combobox.config(state="readonly")
    # else:
    #     resolution_combobox.config(state="disabled")

def browse_path():
    """파일 탐색기를 열어 저장할 폴더를 선택하고 경로를 업데이트합니다."""
    folder_selected = filedialog.askdirectory(initialdir=Path.cwd().as_posix())
    if folder_selected:
        path_var.set(Path(folder_selected).as_posix())

def show_silent_info(title, message):
    """알림음 없이 메시지를 표시합니다."""
    root = tk.Toplevel()
    root.withdraw() # 메인 창은 숨김
    
    # 알림음 없이 메시지만 표시
    try:
        messagebox.showinfo(title, message, parent=root)
    finally:
        root.destroy()

def start_download():
    """메인 다운로드 함수를 별도의 스레드에서 실행합니다."""
    download_button.config(state=tk.DISABLED)
    download_thread = threading.Thread(target=download_process)
    download_thread.start()

def download_process():
    """pytubefix를 사용하여 다운로드 옵션에 따라 영상을 다운로드합니다."""
    url = url_entry.get()
    download_type = type_var.get()
    # resolution = resolution_var.get()  # 해상도
    save_path = Path(path_var.get())
    user_filename_input = filename_entry.get()

    if not url or not save_path:
        status_label.config(text="⚠️ URL 또는 저장 경로를 입력/선택해주세요.", fg="orange")
        download_button.config(state=tk.NORMAL)
        return
    
    # if download_type == "Video" and (resolution == "선택" or not resolution):
    #     status_label.config(text="⚠️ 비디오 다운로드 시 해상도를 선택해주세요.", fg="orange")
    #     download_button.config(state=tk.NORMAL)
    #     return

    save_path.mkdir(parents=True, exist_ok=True)
    status_label.config(text="⏳ 다운로드 준비 중...", fg="blue")
    
    try:
        yt = YouTube(url)
        
        # 1. 파일 이름 설정 (생략)
        if user_filename_input:
            base_filename = sanitize_filename(user_filename_input)
        else:
            base_filename = sanitize_filename(yt.title)
        
        # 2. 다운로드 유형에 따른 스트림 선택 및 다운로드
        if download_type == "Video":
            
            final_filename = f"{base_filename}.mp4"
            final_filepath = save_path / final_filename
            # print(f"DEBUG: Attempting to save to: {final_filepath}") # 콘솔에서 확인 가능
            # status_label.config(text=f"⬇️ '{base_filename}' 비디오 다운로드 시작 ({resolution})...", fg="blue")
            status_label.config(text=f"⬇️ '{base_filename}' 비디오 다운로드 시작...", fg="blue")

            # 🚀 해상도 선택 로직 개선: 선택한 해상도의 progressive stream을 정확히 찾습니다.
            # stream = yt.streams.filter(res=resolution, file_extension='mp4', progressive=True).first()
            # Progressive stream 중 가장 높은 해상도로 대체
            stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
            
            if stream is None:
                # 최종적으로도 찾지 못하면 에러 발생
                raise Exception("다운로드 가능한 통합 스트림(progressive stream)이 없습니다. 다른 URL을 시도해 보세요.")

            # 파일명 지정하여 다운로드
            stream.download(output_path=save_path, filename=final_filename)

            # if stream is None:
            #     # 선택한 해상도의 통합 스트림이 없는 경우 (주로 1080p 또는 특정 해상도 미지원 시)
            #     # 현재 가능한 통합 스트림 중 최고 해상도로 대체합니다.
            #     status_label.config(text="🔍 요청 해상도 스트림을 찾을 수 없어, 최고 화질 통합 스트림으로 대체합니다.", fg="darkblue")
                
            #     # Progressive stream 중 가장 높은 해상도로 대체
            #     stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
                
            #     if stream is None:
            #         # 최종적으로도 찾지 못하면 에러 발생
            #         raise Exception("다운로드 가능한 통합 스트림(progressive stream)이 없습니다. 다른 URL을 시도해 보세요.")

            #     # 파일명 지정하여 다운로드
            #     stream.download(output_path=save_path, filename=final_filename)
            final_message = f"✅ 비디오(MP4) 다운로드 완료! 실제 해상도: {stream.resolution}\n(저장 경로:{final_filepath})"
            
        elif download_type == "Audio":
            # 1. 오디오 스트림 중 가장 품질이 좋은 것을 선택
            audio_stream = yt.streams.filter(only_audio=True).first()
            
            # 2. 스트림의 기본 확장자(mp4, webm 등)를 확인하여 저장
            # 대부분 m4a 또는 webm으로 저장됩니다.
            ext = ".m4a" if audio_stream.mime_type == "audio/mp4" else ".webm"
            final_filename = f"{base_filename}{ext}"
            final_filepath = save_path / final_filename
            
            status_label.config(text=f"🎶 '{base_filename}' 오디오 다운로드 중...", fg="blue")
            
            # 3. 별도의 변환 없이 스트림 그대로 저장 (가장 안정적)
            audio_stream.download(output_path=save_path, filename=final_filename)
            
            final_message = f"✅ 오디오({ext.upper()}) 다운로드 완료! 저장 위치: {final_filepath}"
        
        status_label.config(text=final_message, fg="green")
        app.after(0, lambda: show_silent_info("완료", final_message)) # 🔔 알림음 없이 메시지 표시

    except Exception as e:
        # error_message = f"❌ 다운로드 오류가 발생했습니다: {e}"
        # status_label.config(text=error_message, fg="red")
        # app.after(0, lambda: show_silent_info("오류", error_message)) # 🔔 알림음 없이 메시지 표시
        # 오류의 상세 정보를 가져옵니다.
        error_trace = traceback.format_exc()
        error_message = f"❌ 다운로드 오류 발생가 발생했습니다.\n\n [원인]: {str(e)}\n\n[상세 내용]:\n{error_trace}"
        
        # 상태 레이블과 메시지 박스에 표시
        status_label.config(text="❌ 오류 발생 (상세 내용 참조)", fg="red")
        
        # 메인 스레드에서 메시지 박스 띄우기
        app.after(0, lambda: show_silent_info("상세 오류", error_message))
    finally:
        download_button.config(state=tk.NORMAL)


# --- GUI 설정 ---
app = tk.Tk()
try:
    # 'icon.ico'는 준비하신 아이콘 파일 이름으로 변경하세요
    app.iconbitmap(resource_path("Youtube_Downloader.ico") )
except Exception as e:
    print(f"아이콘을 불러올 수 없습니다: {e}")

app.title("유튜브 다운로더 (pytubefix)")
app.geometry("550x450")
app.resizable(False, False)

# 1. URL 섹션
url_label = tk.Label(app, text="1. 유튜브 영상 URL", font=("맑은 고딕", 10, "bold"))
url_label.pack(pady=(10, 0))
url_entry = tk.Entry(app, width=60, font=("맑은 고딕", 10))
url_entry.pack(pady=5, padx=20)

# 2. 파일 이름 섹션
filename_label = tk.Label(app, text="2. 파일 이름 (선택 사항: 미입력 시 유튜브 제목 사용)", font=("맑은 고딕", 10, "bold"))
filename_label.pack(pady=(5, 0))
filename_entry = tk.Entry(app, width=60, font=("맑은 고딕", 10))
filename_entry.pack(pady=5, padx=20)

# 3. 저장 경로 섹션
path_label = tk.Label(app, text="3. 저장 경로", font=("맑은 고딕", 10, "bold"))
path_label.pack(pady=(5, 0))

path_frame = tk.Frame(app)
path_frame.pack(pady=5, padx=20)

path_var = tk.StringVar(value=DEFAULT_DOWNLOAD_PATH.resolve().as_posix())
path_entry = tk.Entry(path_frame, textvariable=path_var, width=50, font=("맑은 고딕", 10), state="readonly")
path_entry.pack(side=tk.LEFT, padx=(0, 5))

browse_button = tk.Button(path_frame, text="폴더 선택", command=browse_path, font=("맑은 고딕", 9))
browse_button.pack(side=tk.LEFT)

# 4. 옵션 섹션 (해상도 및 타입)
options_label = tk.Label(app, text="4. 다운로드 옵션", font=("맑은 고딕", 10, "bold"))
options_label.pack(pady=(10, 0))

options_frame = tk.Frame(app)
options_frame.pack(pady=5)

### 4-1. 다운로드 타입 (라디오 버튼)
type_label = tk.Label(options_frame, text="타입:", font=("맑은 고딕", 10))
type_label.pack(side=tk.LEFT, padx=(0, 5))

type_var = tk.StringVar(value="Video")
video_radio = tk.Radiobutton(options_frame, text="비디오 (MP4, 360p)", variable=type_var, value="Video", 
                             command=toggle_resolution_state, font=("맑은 고딕", 10))
audio_radio = tk.Radiobutton(options_frame, text="오디오 (m4a, webm 등)", variable=type_var, value="Audio", 
                             command=toggle_resolution_state, font=("맑은 고딕", 10))
video_radio.pack(side=tk.LEFT, padx=5)
audio_radio.pack(side=tk.LEFT, padx=5)

# ### 4-2. 해상도 선택 (콤보박스)
# resolution_label = tk.Label(options_frame, text="| 해상도:", font=("맑은 고딕", 10))
# resolution_label.pack(side=tk.LEFT, padx=(15, 5))

# resolution_var = tk.StringVar(value="720p")
# resolutions = ["720p", "480p", "360p", "240p", "144p"]
# resolution_combobox = ttk.Combobox(options_frame, textvariable=resolution_var, values=resolutions, 
#                                    width=8, state="readonly", font=("맑은 고딕", 10))
# resolution_combobox.pack(side=tk.LEFT, padx=5)
# toggle_resolution_state() 

# 5. 다운로드 버튼
download_button = tk.Button(app, text="🚀 다운로드 시작", command=start_download, 
                            bg="#ff0000", fg="white", font=("맑은 고딕", 12, "bold"))
download_button.pack(pady=15)

# 6. 상태 표시 레이블
status_label = tk.Label(app, text="준비됨", fg="gray", font=("맑은 고딕", 10), 
                        wraplength=500, justify="center")
status_label.pack(pady=5, fill=tk.X)

# GUI 실행
app.mainloop()