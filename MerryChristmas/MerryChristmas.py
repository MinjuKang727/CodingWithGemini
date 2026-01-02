import sys
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QLineEdit, QPushButton, QFileDialog, QFrame, QHBoxLayout)
from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtGui import QPixmap, QFont, QColor, QPalette

class MarqueeLabel(QLabel):
    """글자 수 제한 없이 아주 긴 메세지도 처리 가능한 LED 라벨"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.px = 0
        self.text_content = ""
        
        # 타이머 설정 (글자 움직임 속도 조절)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_position)
        self.timer.start(30)  # 30ms마다 갱신
        
        # 스타일 설정 (전광판 느낌)
        self.setStyleSheet("""
            color: #00FF00; 
            background-color: black; 
            font-weight: bold; 
            font-size: 16px; 
            border-radius: 5px;
        """)
        self.setAlignment(Qt.AlignVCenter)
        self.setFixedHeight(35)

    def set_marquee_text(self, text):
        # 문장 끝에 공백을 넉넉히 주어 다시 시작할 때 앞부분과 겹치지 않게 함
        self.text_content = text + "          " 
        self.setText(self.text_content)
        
        # 텍스트의 실제 길이에 맞춰 라벨 크기를 충분히 늘려줌 (잘림 방지)
        font_metrics = self.fontMetrics()
        text_width = font_metrics.horizontalAdvance(self.text_content)
        self.setFixedWidth(text_width + 1000) # 여유 공간 확보
        
        # 시작 위치를 위젯의 원래 컨테이너 오른쪽 끝으로 설정
        if self.parent():
            self.px = self.parent().width()
        else:
            self.px = 400
            
        self.update()

    def update_position(self):
        if not self.text_content:
            return
            
        font_metrics = self.fontMetrics()
        # 현재 텍스트의 전체 픽셀 너비 계산
        text_width = font_metrics.horizontalAdvance(self.text_content)
        
        # 위치 이동 (왼쪽으로 2픽셀씩)
        self.px -= 2  
        
        # 글자가 왼쪽 끝으로 완전히 사라지면(너비만큼 이동하면) 다시 오른쪽 끝에서 나타남
        if self.px < -text_width:
            if self.parent():
                self.px = self.parent().width()
            else:
                self.px = 400
            
        self.move(self.px, 0)

class DesktopWidget(QWidget):
    """화면 맨 위에 떠 있는 이미지+전광판 위젯"""
    def __init__(self):
        super().__init__()
        
        # 1. 윈도우 설정 (투명 배경, 항상 위, 테두리 없음, 작업표시줄 제외)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 2. 레이아웃 구성
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)
        self.setLayout(self.layout)
        
        # 3. 이미지 영역
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.image_label)
        
        # 4. 전광판 영역 컨테이너 (여기가 '창' 역할을 하여 글자가 이 안에서만 보임)
        self.marquee_container = QWidget()
        self.marquee_container.setStyleSheet("background-color: black; border-radius: 8px;")
        self.marquee_container.setFixedHeight(40)
        self.marquee_container.setFixedWidth(250) # 기본 너비
        
        # 실제 움직이는 라벨 생성 (컨테이너를 부모로 설정)
        self.marquee_label = MarqueeLabel(self.marquee_container)
        
        self.layout.addWidget(self.marquee_container, alignment=Qt.AlignCenter)
        
        self.old_pos = None

    def update_content(self, image_path, text):
        if image_path:
            pixmap = QPixmap(image_path)
            # 이미지 크기 조절
            pixmap = pixmap.scaled(250, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(pixmap)
            
            # 전광판 너비를 이미지 너비와 맞춤 (최소 200px)
            new_width = max(pixmap.width(), 200)
            self.marquee_container.setFixedWidth(new_width)
            
        # 텍스트 설정 (MarqueeLabel 내부에서 길이 계산 처리됨)
        self.marquee_label.set_marquee_text(text)
        self.show()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = QPoint(event.globalPos() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

class ControlPanel(QWidget):
    """설정을 위한 GUI 창"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("전광판 위젯 설정")
        self.setGeometry(100, 100, 400, 200) # 입력창을 위해 너비를 조금 늘림
        
        self.widget_instance = DesktopWidget()
        self.image_path = None

        layout = QVBoxLayout()

        # 이미지 선택
        self.btn_image = QPushButton("1. 이미지 선택 (배경 없는 PNG 추천)")
        self.btn_image.clicked.connect(self.select_image)
        layout.addWidget(self.btn_image)
        
        self.lbl_path = QLabel("선택된 파일 없음")
        self.lbl_path.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_path)

        # 텍스트 입력 (글자 수 제한 없음)
        self.input_text = QLineEdit()
        self.input_text.setPlaceholderText("2. 전광판에 띄울 문구를 입력하세요.")
        layout.addWidget(self.input_text)

        # 실행 버튼
        self.btn_run = QPushButton("3. 위젯 실행 / 업데이트")
        self.btn_run.clicked.connect(self.run_widget)
        self.btn_run.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; font-size: 14px;")
        layout.addWidget(self.btn_run)
        
        layout.addWidget(QLabel("※ 위젯을 드래그하여 위치를 옮길 수 있습니다.\n※ 설정창을 닫으면 위젯도 종료됩니다."))

        self.setLayout(layout)

    def select_image(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "이미지 열기", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if file_name:
            self.image_path = file_name
            self.lbl_path.setText(f"선택됨: {file_name.split('/')[-1]}")

    def run_widget(self):
        text = self.input_text.text()
        if not text:
            text = "메세지를 입력해주세요!"
            
        if not self.image_path:
            self.lbl_path.setText("⚠️ 이미지를 먼저 선택해주세요!")
            return
        
        self.widget_instance.update_content(self.image_path, text)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # 폰트 설정 (한글 깨짐 방지 및 깔끔한 출력)
    app.setFont(QFont("Malgun Gothic", 10))
    
    control_panel = ControlPanel()
    control_panel.show()
    sys.exit(app.exec_())