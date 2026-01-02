import tkinter as tk
from tkinter import ttk, colorchooser, messagebox
from datetime import datetime, timedelta
import csv
import os

# tkcalendar 확인
try:
    from tkcalendar import DateEntry
except ImportError:
    messagebox.showerror("오류", "tkcalendar 라이브러리가 필요합니다.\n'pip install tkcalendar'를 실행해주세요.")

class StudyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("순공 PRO")
        
        self.db_file = "study_logs.csv"
        self.running = False
        self.seconds = 0
        self.current_color = "#3498db"
        self.after_id = None
        
        self.logs = self.load_and_fix_data()
        
        self.setup_ui()
        self.adjust_window_size()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_and_fix_data(self):
        logs = []
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        fixed_row = {
                            'full_date': row.get('full_date', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                            'date_only': row.get('date_only', datetime.now().strftime("%Y-%m-%d")),
                            'duration': int(row.get('duration', 0)),
                            'duration_str': row.get('duration_str', "0h, 0m, 0s"),
                            'memo': row.get('memo', ""),
                            'color': row.get('color', "#3498db")
                        }
                        logs.append(fixed_row)
            except Exception:
                return []
        return logs

    def save_data(self):
        with open(self.db_file, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['full_date', 'date_only', 'duration', 'duration_str', 'memo', 'color']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.logs)

    def adjust_window_size(self):
        self.root.update_idletasks()
        width = 500  # 가로폭 500으로 고정
        height = self.root.winfo_reqheight()
        self.root.geometry(f"{width}x{height}")

    def setup_ui(self):
        self.main_frame = tk.Frame(self.root, pady=10)
        self.main_frame.pack(fill="x")

        self.lbl_timer = tk.Label(self.main_frame, text="00:00:00", font=("Consolas", 40, "bold"), fg="#2c3e50")
        self.lbl_timer.pack()

        btn_timer_frame = tk.Frame(self.main_frame)
        btn_timer_frame.pack(pady=5)
        ttk.Button(btn_timer_frame, text="시작", command=self.start_timer).grid(row=0, column=0, padx=2)
        ttk.Button(btn_timer_frame, text="정지", command=self.stop_timer).grid(row=0, column=1, padx=2)
        ttk.Button(btn_timer_frame, text="리셋", command=self.reset_timer).grid(row=0, column=2, padx=2)

        input_container = tk.Frame(self.main_frame)
        input_container.pack(pady=5)
        tk.Label(input_container, text="비고:").grid(row=0, column=0)
        self.ent_memo = ttk.Entry(input_container, width=25)
        self.ent_memo.grid(row=0, column=1, padx=5)
        self.btn_color_pick = tk.Button(input_container, bg=self.current_color, width=2, relief="ridge", command=self.pick_color)
        self.btn_color_pick.grid(row=0, column=2)

        toggle_btn_frame = tk.Frame(self.main_frame)
        toggle_btn_frame.pack(pady=5)
        self.btn_toggle_logs = ttk.Button(toggle_btn_frame, text="로그 조회 ▼", command=self.toggle_logs)
        self.btn_toggle_logs.grid(row=0, column=0, padx=5)
        self.btn_toggle_stats = ttk.Button(toggle_btn_frame, text="통계 그래프 ▼", command=self.toggle_stats)
        self.btn_toggle_stats.grid(row=0, column=1, padx=5)

        # 4. 로그 조회 섹션
        self.log_container = tk.LabelFrame(self.root, text="공부 로그 리스트")
        search_ctrl = tk.Frame(self.log_container)
        search_ctrl.pack(fill="x", padx=5, pady=5)
        
        self.log_view_mode = tk.StringVar(value="일별")
        tk.Radiobutton(search_ctrl, text="일별", variable=self.log_view_mode, value="일별", command=self.on_view_mode_change).pack(side="left")
        tk.Radiobutton(search_ctrl, text="기간별", variable=self.log_view_mode, value="기간별", command=self.on_view_mode_change).pack(side="left")
        
        self.cal_start = DateEntry(search_ctrl, width=10, date_pattern='yyyy-mm-dd')
        self.cal_start.pack(side="left", padx=2)
        self.lbl_tilde = tk.Label(search_ctrl, text="~")
        self.cal_end = DateEntry(search_ctrl, width=10, date_pattern='yyyy-mm-dd')
        
        # 초기 상태는 일별이므로 종료 날짜 숨김
        self.lbl_tilde.pack_forget()
        self.cal_end.pack_forget()

        ttk.Button(search_ctrl, text="조회", command=self.update_log_list).pack(side="left", padx=5)

        self.tree = ttk.Treeview(self.log_container, columns=("c1", "c2", "c3"), show="headings", height=5)
        self.tree.heading("c1", text="일시"); self.tree.heading("c2", text="시간"); self.tree.heading("c3", text="비고")
        self.tree.column("c1", width=140); self.tree.column("c2", width=90); self.tree.column("c3", width=180)
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)

        # 5. 통계 섹션
        self.stats_container = tk.LabelFrame(self.root, text="최근 7일 통계")
        self.canvas = tk.Canvas(self.stats_container, bg="white", height=220, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)

    def on_view_mode_change(self):
        """라디오 버튼 변경 시 UI 동적 조절"""
        if self.log_view_mode.get() == "일별":
            self.lbl_tilde.pack_forget()
            self.cal_end.pack_forget()
        else:
            # 조회 버튼 앞으로 물결표와 달력 재배치
            self.lbl_tilde.pack(side="left")
            self.cal_end.pack(side="left", padx=2)
        self.adjust_window_size()

    def toggle_logs(self):
        if self.log_container.winfo_viewable():
            self.log_container.pack_forget()
            self.btn_toggle_logs.config(text="로그 조회 ▼")
        else:
            self.log_container.pack(fill="both", expand=True, padx=10, pady=5)
            self.btn_toggle_logs.config(text="로그 조회 ▲")
            self.update_log_list()
        self.adjust_window_size()

    def toggle_stats(self):
        if self.stats_container.winfo_viewable():
            self.stats_container.pack_forget()
            self.btn_toggle_stats.config(text="통계 그래프 ▼")
        else:
            self.stats_container.pack(fill="both", expand=True, padx=10, pady=5)
            self.btn_toggle_stats.config(text="통계 그래프 ▲")
            self.draw_graph()
        self.adjust_window_size()

    def pick_color(self):
        color = colorchooser.askcolor(initialcolor=self.current_color)[1]
        if color:
            self.current_color = color
            self.btn_color_pick.config(bg=color)

    def format_time(self, seconds):
        h, r = divmod(seconds, 3600); m, s = divmod(r, 60)
        return f"{h}h, {m}m, {s}s"

    def start_timer(self):
        if not self.running:
            self.running = True
            self.update_clock()

    def stop_timer(self):
        self.running = False

    def update_clock(self):
        if self.running:
            self.seconds += 1
            h, r = divmod(self.seconds, 3600); m, s = divmod(r, 60)
            self.lbl_timer.config(text=f"{h:02d}:{m:02d}:{s:02d}")
            self.after_id = self.root.after(1000, self.update_clock)

    def reset_timer(self):
        if self.seconds > 0:
            now = datetime.now()
            self.logs.insert(0, {
                'full_date': now.strftime("%Y-%m-%d %H:%M:%S"),
                'date_only': now.strftime("%Y-%m-%d"),
                'duration': self.seconds,
                'duration_str': self.format_time(self.seconds),
                'memo': self.ent_memo.get() or "기록 없음",
                'color': self.current_color
            })
            self.save_data()
            if self.log_container.winfo_viewable(): self.update_log_list()
            if self.stats_container.winfo_viewable(): self.draw_graph()
        self.stop_timer(); self.seconds = 0
        self.lbl_timer.config(text="00:00:00")
        self.ent_memo.delete(0, tk.END)

    def update_log_list(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        target_start = self.cal_start.get_date()
        target_end = target_start if self.log_view_mode.get() == "일별" else self.cal_end.get_date()

        for log in self.logs:
            try:
                log_date = datetime.strptime(log['date_only'], "%Y-%m-%d").date()
                if target_start <= log_date <= target_end:
                    self.tree.insert("", "end", values=(log['full_date'], log['duration_str'], log['memo']), tags=(log['color'],))
                    self.tree.tag_configure(log['color'], background=log['color'])
            except: continue

    def draw_graph(self):
        self.canvas.delete("all")
        self.root.update_idletasks()
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        margin_l, margin_b, margin_t = 40, 30, 20
        graph_h = h - margin_b - margin_t

        end_d = datetime.now().date()
        start_d = end_d - timedelta(days=6)
        date_list = [(start_d + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

        for i in range(0, 13, 4):
            y = (h - margin_b) - (i/12 * graph_h)
            self.canvas.create_text(margin_l-10, y, text=f"{i}h", anchor="e", font=("Arial", 7))
            self.canvas.create_line(margin_l, y, w-10, y, fill="#f0f0f0")

        bar_w = (w - margin_l - 10) / 7
        for i, d_str in enumerate(date_list):
            day_logs = [l for l in self.logs if l['date_only'] == d_str]
            day_total_sec = sum(l['duration'] for l in day_logs)
            x0 = margin_l + (i * bar_w) + (bar_w * 0.1)
            x1 = x0 + (bar_w * 0.8)
            curr_y = h - margin_b
            
            for log in day_logs:
                block_h = (log['duration'] / (12 * 3600)) * graph_h
                y0 = curr_y - block_h
                rect = self.canvas.create_rectangle(x0, y0, x1, curr_y, fill=log['color'], outline="white")
                info = f"{d_str}\n{log['memo']}\n{log['duration_str']}\n총: {self.format_time(day_total_sec)}"
                self.canvas.tag_bind(rect, "<Enter>", lambda e, msg=info: self.show_tooltip(e, msg))
                self.canvas.tag_bind(rect, "<Leave>", lambda e: self.hide_tooltip())
                curr_y = y0
            self.canvas.create_text((x0+x1)/2, h-margin_b+15, text=d_str[5:], font=("Arial", 7))

    def show_tooltip(self, event, msg):
        self.tip = tk.Toplevel(self.root)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{event.x_root+15}+{event.y_root+15}")
        tk.Label(self.tip, text=msg, bg="#2c3e50", fg="white", relief="solid", borderwidth=1, justify="left", padx=8, pady=5, font=("맑은 고딕", 8)).pack()

    def hide_tooltip(self):
        if hasattr(self, 'tip'): self.tip.destroy()

    def on_closing(self):
        if self.after_id: self.root.after_cancel(self.after_id)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = StudyApp(root)
    root.mainloop()