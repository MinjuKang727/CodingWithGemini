import sys
import os

# DPI 설정 에러(액세스 거부) 방지
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

import time
import win32com.client as win32
import pyautogui
import pyperclip
import pythoncom
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QListWidget, QFileDialog, QCheckBox, 
                             QLineEdit, QLabel, QMessageBox)
from PyPDF2 import PdfMerger

class FinalRetryConverter(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('PDF Merge Master (Auto Retry Mode)')
        self.setFixedWidth(500) 
        
        main_vbox = QVBoxLayout()
        main_vbox.setContentsMargins(15, 15, 15, 15)
        main_vbox.setSpacing(10)

        main_vbox.addWidget(QLabel('변환 및 병합 파일 목록:'))

        top_hbox = QHBoxLayout()
        top_hbox.setSpacing(8)
        self.file_list = QListWidget()
        self.file_list.setFixedWidth(400) 
        self.file_list.setFixedHeight(250)
        top_hbox.addWidget(self.file_list)

        side_vbox = QVBoxLayout()
        side_vbox.setSpacing(5)
        btn_width = 50
        self.btn_up = QPushButton('▲')
        self.btn_down = QPushButton('▼')
        self.btn_delete = QPushButton('삭제')
        for btn in [self.btn_up, self.btn_down, self.btn_delete]:
            btn.setFixedWidth(btn_width)
        
        side_vbox.addStretch(1)
        side_vbox.addWidget(self.btn_up)
        side_vbox.addWidget(self.btn_down)
        side_vbox.addWidget(self.btn_delete)
        side_vbox.addStretch(1)
        top_hbox.addLayout(side_vbox)
        main_vbox.addLayout(top_hbox)

        manage_hbox = QHBoxLayout()
        manage_hbox.setContentsMargins(0, 0, 70, 0)
        self.btn_add = QPushButton('파일 추가')
        self.btn_clear = QPushButton('목록 초기화')
        self.btn_add.clicked.connect(self.add_files)
        self.btn_clear.clicked.connect(self.file_list.clear)
        manage_hbox.addWidget(self.btn_add)
        manage_hbox.addWidget(self.btn_clear)
        main_vbox.addLayout(manage_hbox)

        options_vbox = QVBoxLayout()
        options_vbox.setContentsMargins(0, 0, 70, 0)
        self.cb_del_orig = QCheckBox('성공 시 원본 문서(HWP/Word) 삭제')
        merge_hbox = QHBoxLayout()
        self.cb_merge = QCheckBox('PDF 병합 (이름:')
        self.merge_name = QLineEdit("최종결과_합본")
        self.merge_name.setFixedWidth(150)
        merge_hbox.addWidget(self.cb_merge)
        merge_hbox.addWidget(self.merge_name)
        merge_hbox.addWidget(QLabel(')'))
        merge_hbox.addStretch(1)
        self.cb_del_temp_pdf = QCheckBox('병합 후 사용된 모든 개별 PDF 삭제')
        options_vbox.addWidget(self.cb_del_orig)
        options_vbox.addLayout(merge_hbox)
        options_vbox.addWidget(self.cb_del_temp_pdf)
        main_vbox.addLayout(options_vbox)

        self.status_label = QLabel('상태: 대기 중...')
        self.status_label.setStyleSheet("color: blue; font-weight: bold; padding: 8px; background: #f0f0f0;")
        main_vbox.addWidget(self.status_label)

        self.btn_run = QPushButton('작업 시작')
        self.btn_run.setStyleSheet("background-color: #1A73E8; color: white; font-weight: bold; height: 45px;")
        self.btn_run.clicked.connect(self.process_conversion)
        main_vbox.addWidget(self.btn_run)

        self.setLayout(main_vbox)
        self.btn_up.clicked.connect(self.move_item_up)
        self.btn_down.clicked.connect(self.move_item_down)
        self.btn_delete.clicked.connect(self.delete_selected)

    def set_status(self, text):
        self.status_label.setText(f"상태: {text}")
        QApplication.processEvents()

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "파일 선택", "", "Files (*.hwp *.hwpx *.doc *.docx *.pdf)")
        if files:
            current_items = [self.file_list.item(i).text() for i in range(self.file_list.count())]
            new_files = [os.path.normpath(f) for f in files if os.path.normpath(f) not in current_items]
            all_files = current_items + new_files
            all_files.sort(key=lambda x: os.path.basename(x).lower())
            self.file_list.clear()
            self.file_list.addItems(all_files)

    def move_item_up(self):
        curr_row = self.file_list.currentRow()
        if curr_row > 0:
            item = self.file_list.takeItem(curr_row)
            self.file_list.insertItem(curr_row - 1, item)
            self.file_list.setCurrentRow(curr_row - 1)

    def move_item_down(self):
        curr_row = self.file_list.currentRow()
        if curr_row < self.file_list.count() - 1 and curr_row != -1:
            item = self.file_list.takeItem(curr_row)
            self.file_list.insertItem(curr_row + 1, item)
            self.file_list.setCurrentRow(curr_row + 1)

    def delete_selected(self):
        curr_row = self.file_list.currentRow()
        if curr_row != -1: self.file_list.takeItem(curr_row)

    def process_conversion(self):
        if self.file_list.count() == 0: return
        self.set_status("작업 시작")
        all_pdfs_to_process = []
        hwp = None
        has_final_error = False 

        try:
            pythoncom.CoInitialize()
            out_name = self.merge_name.text().strip() or "최종결과_합본"
            
            while self.file_list.count() > 0:
                if has_final_error: break
                
                item = self.file_list.item(0)
                full_path = os.path.normpath(item.text())
                file_name = os.path.basename(full_path)
                ext = os.path.splitext(full_path)[1].lower()
                
                if file_name == f"{out_name}.pdf":
                    self.file_list.takeItem(0)
                    continue

                if ext == '.pdf':
                    if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                        all_pdfs_to_process.append(full_path)
                    self.file_list.takeItem(0)
                    continue

                # --- 변환 시도 루프 (최대 3회) ---
                retry_count = 0
                success = False
                while retry_count < 3 and not success:
                    if not hwp:
                        hwp = win32.DispatchEx("HWPFrame.HwpObject")
                        hwp.XHwpWindows.Item(0).Visible = True
                    
                    pdf_path = os.path.splitext(full_path)[0] + ".pdf"
                    self.set_status(f"변환 중({retry_count+1}/3): {file_name}")
                    
                    hwp.Open(full_path, None, None)
                    time.sleep(1.5)
                    pyautogui.hotkey('alt', 'p')
                    time.sleep(1.0)
                    pyautogui.press('enter')
                    time.sleep(2.5) 
                    pyperclip.copy(pdf_path)
                    pyautogui.hotkey('ctrl', 'v')
                    time.sleep(0.5)
                    pyautogui.press('enter')
                    time.sleep(1.5)
                    pyautogui.press('enter') 
                    
                    time.sleep(2.0) # 생성 대기 시간 충분히
                    if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                        success = True
                    else:
                        retry_count += 1
                        if hwp: hwp.Clear(1)
                        time.sleep(1.0) # 재시도 전 휴식

                if success:
                    all_pdfs_to_process.append(pdf_path)
                    if self.cb_del_orig.isChecked():
                        try:
                            hwp.Clear(1) 
                            os.remove(full_path)
                        except: pass
                    self.file_list.takeItem(0)
                else:
                    has_final_error = True
                    self.set_status(f"최종 실패: {file_name}")
                
                if hwp: hwp.Clear(1)
                QApplication.processEvents()

            if hwp: 
                hwp.Quit()
                time.sleep(1.5)

            if not has_final_error:
                if self.cb_merge.isChecked() and all_pdfs_to_process:
                    self.set_status("PDF 병합 중...")
                    merge_path = self.merge_all_pdfs(all_pdfs_to_process)
                    if merge_path and self.cb_del_temp_pdf.isChecked():
                        time.sleep(2.5)
                        for pdf in all_pdfs_to_process:
                            if os.path.normpath(pdf) == os.path.normpath(merge_path): continue
                            try: os.remove(pdf)
                            except: pass
                self.set_status("작업 종료")
                QMessageBox.information(self, "완료", "모든 작업이 성공적으로 완료되었습니다.")
            else:
                QMessageBox.critical(self, "중단", f"특정 파일 변환에 3회 실패하여 작업을 중단했습니다.\n파일이 다른 곳에서 열려있는지 확인하세요.")

        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))
        finally:
            if hwp: 
                try: hwp.Quit()
                except: pass
            pythoncom.CoUninitialize()

    def merge_all_pdfs(self, pdf_list):
        try:
            merger = PdfMerger()
            output_dir = os.path.dirname(pdf_list[0])
            name = self.merge_name.text().strip() or "최종결과_합본"
            final_path = os.path.normpath(os.path.join(output_dir, f"{name}.pdf"))
            for pdf in pdf_list:
                if os.path.exists(pdf) and os.path.getsize(pdf) > 0:
                    merger.append(pdf)
            with open(final_path, "wb") as fout:
                merger.write(fout)
            merger.close()
            return final_path
        except: return None

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = FinalRetryConverter()
    ex.show()
    sys.exit(app.exec())