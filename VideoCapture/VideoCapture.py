import cv2
import numpy as np
import mss
import threading
import time
import os
import sys
import wave
import subprocess
import configparser
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import pyaudiowpatch as pyaudio

def get_path(rel_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, rel_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)

class ToolTip:
    def __init__(self, widget, text, owner=None):
        self.widget = widget
        self.text = text
        self.owner = owner
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.owner and self.owner.is_recording and self.widget == self.owner.btn_audio:
            return
        if self.tip_window or not self.text: return
        x = self.widget.winfo_rootx() + 5
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_attributes("-topmost", True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, justify='left', background="#ffffe0", 
                 relief='solid', borderwidth=1, font=("Malgun Gothic", "8"), padx=3, pady=3).pack()

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw: tw.destroy()

class VideoRecorder:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Rec Pro Ultra")
        self.root.attributes("-topmost", True)
        self.root.geometry("320x200+50+50")
        self.root.resizable(False, False)
        
        self.exe_path = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(self.exe_path, "config.ini")
        
        self.is_recording = False
        self.is_paused = False
        self.video_real_started = False
        self.record_audio_enabled = True
        self.total_paused_duration = 0
        self.tmp_v = ""; self.tmp_a = ""

        self.load_images()
        self.setup_ui()
        self.load_settings()
        self.update_status_msg("wait")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_images(self):
        self.imgs = {}
        names = ["record", "mute", "sound", "stop", "pause", "cancel", "play", "video", "audio", "folder", "save", "delete", "info"]
        for name in names:
            p = get_path(os.path.join("images", f"{name}.png"))
            if os.path.exists(p):
                img = tk.PhotoImage(file=p)
                self.imgs[name] = img.subsample(2, 2) if name in ["save", "info"] else img
            else: self.imgs[name] = None

    def setup_ui(self):
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill='both', expand=True)
        self.rec_tab = tk.Frame(self.tabs); self.tabs.add(self.rec_tab, text="녹화")
        self.rec_mid_f = tk.Frame(self.rec_tab); self.rec_mid_f.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        btn_opt = {"width": 45, "height": 45, "relief": "raised", "borderwidth": 2}
        self.btn_main = tk.Button(self.rec_mid_f, image=self.imgs.get("record"), command=self.handle_main, **btn_opt)
        self.btn_main.pack(side=tk.LEFT, padx=3, pady=5); self.tt_main = ToolTip(self.btn_main, "녹화", self)
        self.btn_pause = tk.Button(self.rec_mid_f, image=self.imgs.get("pause"), command=self.handle_pause, **btn_opt)
        self.tt_pause = ToolTip(self.btn_pause, "녹화 일시 정지", self)
        self.btn_delete = tk.Button(self.rec_mid_f, image=self.imgs.get("cancel"), command=self.handle_del, **btn_opt)
        ToolTip(self.btn_delete, "녹화 취소(삭제)", self)
        self.btn_audio = tk.Button(self.rec_mid_f, image=self.imgs.get("sound"), command=self.toggle_audio, **btn_opt)
        self.btn_audio.pack(side=tk.LEFT, padx=3, pady=5); self.tt_audio = ToolTip(self.btn_audio, "음소거로 변경", self)

        self.sync_tab = tk.Frame(self.tabs); self.tabs.add(self.sync_tab, text="저장/싱크")
        path_configs = [("video", "비디오 경로", "v"), ("audio", "오디오 경로", "a"), ("folder", "저장 경로", "o")]
        for img_name, tt_text, var in path_configs:
            f = tk.Frame(self.sync_tab); f.pack(fill="x", padx=5, pady=0)
            l = tk.Label(f, image=self.imgs.get(img_name), width=25, height=22); l.pack(side=tk.LEFT); ToolTip(l, tt_text, self)
            e = tk.Entry(f, font=("Malgun Gothic", 8)); e.pack(side=tk.LEFT, fill="x", expand=True, padx=2)
            cmd = self.br_v if var=="v" else (self.br_a if var=="a" else self.br_o)
            tk.Button(f, text="..", command=cmd, width=2, font=("Malgun Gothic", 7), pady=0).pack(side=tk.RIGHT)
            if var=="v": self.ent_v=e 
            elif var=="a": self.ent_a=e
            else: self.ent_o=e

        f_sync = tk.Frame(self.sync_tab); f_sync.pack(fill="x", padx=5, pady=0)
        self.ent_s = tk.Entry(f_sync, width=5, font=("Malgun Gothic", 8)); tk.Label(f_sync, text="싱크:", font=("Malgun Gothic", 8)).pack(side=tk.LEFT); self.ent_s.pack(side=tk.LEFT, padx=2)
        info_lbl = tk.Label(f_sync, image=self.imgs.get("info"), cursor="question_arrow"); info_lbl.pack(side=tk.LEFT, padx=2); ToolTip(info_lbl, "1000ms = 1초", self)
        self.opt_ap = tk.BooleanVar(value=True); self.chk_ap = tk.Checkbutton(f_sync, text="자동재생", variable=self.opt_ap, font=("Malgun Gothic", 8)); self.chk_ap.pack(side=tk.RIGHT); ToolTip(self.chk_ap, "싱크 조정 후 자동 재생", self)

        f_bottom = tk.Frame(self.sync_tab); f_bottom.pack(pady=2)
        self.btn_save = tk.Button(f_bottom, image=self.imgs.get("save"), command=self.handle_sync_save, width=35, height=35, relief="raised", borderwidth=2); self.btn_save.pack(side=tk.LEFT, padx=10)
        self.btn_cln = tk.Button(f_bottom, image=self.imgs.get("delete"), command=self.clean, width=35, height=35, relief="raised", borderwidth=2); self.btn_cln.pack(side=tk.LEFT, padx=10); ToolTip(self.btn_cln, "비디오, 오디오 raw 파일 삭제", self)
        self.st_lbl = tk.Label(self.root, text="", bd=1, relief="sunken", anchor="w", font=("Malgun Gothic", 8)); self.st_lbl.pack(side=tk.BOTTOM, fill="x")

    def load_settings(self):
        config = configparser.ConfigParser()
        if os.path.exists(self.config_file):
            config.read(self.config_file); self.ent_s.insert(0, config.get("Settings", "sync_ms", fallback="-200"))
        else: self.ent_s.insert(0, "-200")

    def on_closing(self):
        config = configparser.ConfigParser(); config["Settings"] = {"sync_ms": self.ent_s.get()}
        try:
            with open(self.config_file, "w") as f: config.write(f)
        except: pass
        self.root.destroy()

    def update_status_msg(self, state):
        m = {"wait": "대기", "recording": "녹화중", "paused": "정지", "merging": "변환중"}
        self.root.after(0, lambda: self.st_lbl.config(text=f"상태: {m.get(state, '대기')}"))

    def toggle_audio(self):
        if not self.is_recording:
            self.record_audio_enabled = not self.record_audio_enabled
            self.btn_audio.config(image=self.imgs.get("sound" if self.record_audio_enabled else "mute"))

    def handle_main(self):
        if not self.is_recording:
            self.is_recording, self.is_paused, self.total_paused_duration, self.video_real_started = True, False, 0, False
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.tmp_v = os.path.join(self.exe_path, f"v_{ts}.avi")
            self.tmp_a = os.path.join(self.exe_path, f"a_{ts}.wav") if self.record_audio_enabled else ""
            self.auto_o = os.path.join(self.exe_path, f"REC_{ts}.mp4")
            for w in self.rec_mid_f.winfo_children(): w.pack_forget()
            self.btn_main.config(image=self.imgs.get("stop")); self.btn_main.pack(side=tk.LEFT, padx=3, pady=5); self.btn_pause.pack(side=tk.LEFT, padx=3, pady=5); self.btn_delete.pack(side=tk.LEFT, padx=3, pady=5); self.btn_audio.config(state="disabled"); self.btn_audio.pack(side=tk.LEFT, padx=3, pady=5)
            self.update_status_msg("recording")
            threading.Thread(target=self.rec_v, args=(self.tmp_v,), daemon=True).start()
            if self.record_audio_enabled: threading.Thread(target=self.rec_a, args=(self.tmp_a,), daemon=True).start()
        else:
            self.is_recording = False; time.sleep(0.5); audio_active = self.record_audio_enabled
            self.reset_ui_to_idle()
            self.ent_v.delete(0, tk.END); self.ent_v.insert(0, self.tmp_v)
            self.ent_o.delete(0, tk.END); self.ent_o.insert(0, self.auto_o)
            self.ent_a.delete(0, tk.END)
            if audio_active: self.ent_a.insert(0, self.tmp_a); self.tabs.select(1)
            else: self.start_merge(force_no_play=True, auto_clean=True)

    def handle_pause(self):
        if not self.is_paused:
            self.is_paused, self.p_st = True, time.perf_counter()
            self.btn_pause.config(image=self.imgs.get("play")); self.update_status_msg("paused")
        else:
            self.total_paused_duration += (time.perf_counter() - self.p_st)
            self.is_paused = False; self.btn_pause.config(image=self.imgs.get("pause")); self.update_status_msg("recording")

    def handle_del(self):
        if messagebox.askyesno("취소", "녹화 취소 및 임시 파일 삭제?"):
            self.is_recording = False; time.sleep(0.5)
            for f in [self.tmp_v, self.tmp_a]:
                if f and os.path.exists(f): 
                    try: os.remove(f)
                    except: pass
            self.reset_ui_to_idle(); self.update_status_msg("wait")

    def reset_ui_to_idle(self):
        for w in self.rec_mid_f.winfo_children(): w.pack_forget()
        self.btn_main.config(image=self.imgs.get("record")); self.btn_main.pack(side=tk.LEFT, padx=3, pady=5); self.btn_audio.config(state="normal"); self.btn_audio.pack(side=tk.LEFT, padx=3, pady=5); self.btn_pause.config(image=self.imgs.get("pause")); self.is_paused = False

    def handle_sync_save(self): self.start_merge(auto_clean=False)

    def start_merge(self, force_no_play=None, auto_clean=False):
        self.update_status_msg("merging")
        threading.Thread(target=self.merge, args=(force_no_play, auto_clean), daemon=True).start()

    def merge(self, force_no_play, auto_clean):
        try:
            v, a, o, s_str = self.ent_v.get(), self.ent_a.get(), self.ent_o.get(), self.ent_s.get()
            ff = get_path("ffmpeg.exe")
            if a and os.path.exists(a):
                s = int(s_str) if s_str.lstrip('-').isdigit() else -200
                filt = f"adelay={s}|{s},aresample=async=1" if s>=0 else f"atrim={abs(s)/1000},asetpts=PTS-STARTPTS,aresample=async=1"
                cmd = [ff, '-y', '-i', v, '-i', a, '-filter_complex', f"[1:a]{filt}[ao]", '-map', '0:v', '-map', '[ao]', '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', '-b:a', '192k', o]
            else:
                cmd = [ff, '-y', '-i', v, '-c:v', 'copy', '-an', o]
            
            if subprocess.run(cmd, creationflags=0x08000000).returncode == 0:
                # auto_clean이 True(음소거 즉시 저장)인 경우에만 raw 파일 삭제
                if auto_clean:
                    for temp_f in [v, a]:
                        if temp_f and os.path.exists(temp_f):
                            try: os.remove(temp_f)
                            except: pass
                messagebox.showinfo("완료", "저장되었습니다.")
                if not force_no_play and self.opt_ap.get(): os.startfile(o)
        finally: self.update_status_msg("wait")

    def rec_v(self, p):
        with mss.mss() as sct:
            m = sct.monitors[1]; out = cv2.VideoWriter(p, cv2.VideoWriter_fourcc(*'XVID'), 30.0, (m["width"], m["height"]))
            self.video_real_started, st, f_w = True, time.perf_counter(), 0
            while self.is_recording:
                if not self.is_paused:
                    img = np.array(sct.grab(m)); out.write(cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)); f_w += 1
                    while f_w < int((time.perf_counter() - st - self.total_paused_duration) * 30.0):
                        out.write(cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)); f_w += 1
                time.sleep(0.01)
            out.release()

    def rec_a(self, p):
        if not p: return
        pa = pyaudio.PyAudio()
        try:
            while self.is_recording and not self.video_real_started: time.sleep(0.1)
            wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            dev = pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
            lb = next(d for d in pa.get_loopback_device_info_generator() if dev["name"] in d["name"])
            sr = 44100
            try: stream = pa.open(format=pyaudio.paInt16, channels=lb["maxInputChannels"], rate=sr, input=True, input_device_index=lb["index"], frames_per_buffer=1024)
            except: sr = int(lb["defaultSampleRate"]); stream = pa.open(format=pyaudio.paInt16, channels=lb["maxInputChannels"], rate=sr, input=True, input_device_index=lb["index"], frames_per_buffer=1024)
            f = []
            while self.is_recording:
                if not self.is_paused:
                    try: f.append(stream.read(1024, exception_on_overflow=False))
                    except: continue
                else: time.sleep(0.1)
            stream.stop_stream(); stream.close()
            with wave.open(p, 'wb') as wf: wf.setnchannels(lb["maxInputChannels"]); wf.setsampwidth(pa.get_sample_size(pyaudio.paInt16)); wf.setframerate(sr); wf.writeframes(b''.join(f))
        finally: pa.terminate()

    def clean(self):
        # [수정] 현재 입력창에 있는 파일만 삭제하도록 변경 (보안성 강화)
        v_path = self.ent_v.get()
        a_path = self.ent_a.get()
        c = 0
        for f in [v_path, a_path]:
            if f and os.path.exists(f):
                try: 
                    os.remove(f)
                    c += 1
                except: pass
        
        # 추가로 폴더 내 남아있을 수 있는 v_, a_ 임시 파일들도 정리
        for f_name in os.listdir(self.exe_path):
            if (f_name.startswith("v_") or f_name.startswith("a_")) and (f_name.endswith(".avi") or f_name.endswith(".wav")):
                try: 
                    os.remove(os.path.join(self.exe_path, f_name))
                    c += 1
                except: pass
        messagebox.showinfo("정리", f"{c}개의 캐시 파일이 삭제되었습니다.")

    def br_v(self): p=filedialog.askopenfilename(); self.ent_v.delete(0, tk.END); self.ent_v.insert(0,p) if p else None
    def br_a(self): p=filedialog.askopenfilename(); self.ent_a.delete(0, tk.END); self.ent_a.insert(0,p) if p else None
    def br_o(self): p=filedialog.asksaveasfilename(defaultextension=".mp4"); self.ent_o.delete(0, tk.END); self.ent_o.insert(0,p) if p else None

if __name__ == "__main__": app = VideoRecorder(); app.root.mainloop()