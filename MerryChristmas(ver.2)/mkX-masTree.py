import sys
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QPushButton, QFileDialog, QListWidget, QListWidgetItem,
                             QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsPathItem,
                             QSplitter, QMessageBox, QColorDialog, QSlider, QGroupBox, QTabWidget)
from PyQt5.QtCore import Qt, QTimer, QPoint, QSize, QMimeData, QByteArray, QDataStream, QIODevice, QLineF
from PyQt5.QtGui import (QPixmap, QDrag, QPainter, QImage, QTransform, QIcon, 
                         QPen, QPainterPath, QColor, QCursor)

# ==========================================
# 1. 바탕화면 위젯 (출력용) - 기존과 동일
# ==========================================
class MarqueeLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.px = 0
        self.text_content = ""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_position)
        self.timer.start(30)
        self.setStyleSheet("color: #00FF00; background-color: black; font-weight: bold; font-size: 14px; border-radius: 5px;")
        self.setAlignment(Qt.AlignVCenter)
        self.setFixedHeight(30)

    def set_marquee_text(self, text):
        self.text_content = text + "   "
        self.setText(self.text_content)
        self.px = self.width()
        self.update()

    def update_position(self):
        if not self.text_content: return
        font_metrics = self.fontMetrics()
        text_width = font_metrics.width(self.text_content)
        self.px -= 2
        if self.px < -text_width:
            self.px = self.width()
        self.move(self.px, 0)
        
    def resizeEvent(self, event):
        self.setFixedWidth(event.size().width())
        super().resizeEvent(event)

class DesktopWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.setLayout(self.layout)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.image_label)
        self.marquee_container = QWidget()
        self.marquee_container.setStyleSheet("background-color: black; border-radius: 5px;")
        self.marquee_container.setFixedHeight(30)
        self.marquee_label = MarqueeLabel(self.marquee_container)
        self.layout.addWidget(self.marquee_container, alignment=Qt.AlignCenter)
        self.old_pos = None

    def set_content(self, pixmap, text):
        if pixmap.width() > 500 or pixmap.height() > 800:
             pixmap = pixmap.scaled(500, 800, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(pixmap)
        target_width = max(200, pixmap.width())
        self.marquee_container.setFixedWidth(target_width)
        self.marquee_label.setFixedWidth(target_width)
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

# ==========================================
# 2. 꾸미기 에디터 (그리기 기능 추가)
# ==========================================

class DraggableItem(QGraphicsPixmapItem):
    """오너먼트 아이템"""
    def __init__(self, pixmap):
        super().__init__(pixmap)
        self.setFlags(QGraphicsPixmapItem.ItemIsMovable | 
                      QGraphicsPixmapItem.ItemIsSelectable | 
                      QGraphicsPixmapItem.ItemSendsGeometryChanges)
        self.setTransformOriginPoint(pixmap.width() / 2, pixmap.height() / 2)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        if self.isSelected():
            painter.setPen(Qt.DashLine)
            painter.drawRect(self.boundingRect())

class DraggablePathItem(QGraphicsPathItem):
    """그림 그리기 스트로크 아이템"""
    def __init__(self, path, pen):
        super().__init__(path)
        self.setPen(pen)
        # 그려진 선도 선택해서 옮기거나 지울 수 있게 설정
        self.setFlags(QGraphicsPathItem.ItemIsMovable | 
                      QGraphicsPathItem.ItemIsSelectable)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        if self.isSelected():
            # 선택 시 옅은 박스로 표시
            painter.setPen(Qt.DashLine)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect())

class DecorationScene(QGraphicsScene):
    """그리기 및 드래그 앤 드롭 통합 씬"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.background_item = None
        
        # 그리기 관련 변수
        self.is_drawing_mode = False
        self.current_color = Qt.red
        self.pen_width = 5
        self.current_path_item = None
        self.current_path = None

    def set_background(self, pixmap):
        # 기존 아이템들은 유지하고 배경만 교체
        if self.background_item:
            self.removeItem(self.background_item)
        
        self.background_item = self.addPixmap(pixmap)
        self.background_item.setZValue(-100) # 맨 뒤로
        self.background_item.setFlag(QGraphicsPixmapItem.ItemIsSelectable, False)
        self.background_item.setFlag(QGraphicsPixmapItem.ItemIsMovable, False)
        self.setSceneRect(0, 0, pixmap.width(), pixmap.height())

    def mousePressEvent(self, event):
        if self.is_drawing_mode and event.button() == Qt.LeftButton:
            # 그리기 시작
            self.current_path = QPainterPath(event.scenePos())
            pen = QPen(self.current_color, self.pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            self.current_path_item = DraggablePathItem(self.current_path, pen)
            self.addItem(self.current_path_item)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_drawing_mode and self.current_path_item:
            # 선 이어 그리기
            self.current_path.lineTo(event.scenePos())
            self.current_path_item.setPath(self.current_path)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.is_drawing_mode:
            self.current_path_item = None
            self.current_path = None
        else:
            super().mouseReleaseEvent(event)

class DecorationView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setAcceptDrops(True)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setStyleSheet("background-color: #333; border: 1px solid #555;")

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-item-data"):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-item-data"):
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-item-data"):
            data = event.mimeData().data("application/x-item-data")
            stream = QDataStream(data, QIODevice.ReadOnly)
            pixmap = QPixmap()
            stream >> pixmap
            item = DraggableItem(pixmap)
            item.setPos(self.mapToScene(event.pos()))
            self.scene().addItem(item)
            item.setSelected(True)
            event.accept()

    def wheelEvent(self, event):
        items = self.scene().selectedItems()
        if not items: return
        for item in items:
            if isinstance(item, DraggableItem) or isinstance(item, DraggablePathItem):
                delta = event.angleDelta().y()
                if QApplication.keyboardModifiers() == Qt.ControlModifier:
                    rotation = item.rotation() + (5 if delta > 0 else -5)
                    item.setRotation(rotation)
                else:
                    scale = item.scale() + (0.1 if delta > 0 else -0.1)
                    if scale > 0.1: item.setScale(scale)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.RightButton:
            items = self.scene().selectedItems()
            for item in items:
                current_transform = item.transform()
                item.setTransform(current_transform.scale(-1, 1))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            items = self.scene().selectedItems()
            for item in items:
                self.scene().removeItem(item)
        else:
            super().keyPressEvent(event)

class ImageListWidget(QListWidget):
    """이미지 썸네일 리스트 (트리용, 오너먼트용 공용)"""
    def __init__(self, size=80):
        super().__init__()
        self.setIconSize(QSize(size, size))
        self.setViewMode(QListWidget.IconMode)
        self.setSpacing(10)
        self.setDragEnabled(False) # 기본은 끄고 필요시 켬

    def add_image(self, path):
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            icon = QIcon(pixmap.scaled(100, 100, Qt.KeepAspectRatio))
            item = QListWidgetItem(icon, os.path.basename(path))
            item.setData(Qt.UserRole, path) # 전체 경로 저장
            self.addItem(item)

# ==========================================
# 3. 메인 에디터 창
# ==========================================
class EditorWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("나만의 크리스마스 트리 만들기 V2")
        self.setGeometry(100, 100, 1200, 750)
        
        # 폴더 생성
        os.makedirs("trees", exist_ok=True)
        os.makedirs("ornaments", exist_ok=True)

        main_layout = QHBoxLayout(self)
        
        # --- 왼쪽: 캔버스 ---
        canvas_layout = QVBoxLayout()
        self.scene = DecorationScene()
        self.view = DecorationView(self.scene)
        self.lbl_info = QLabel("▼ 휠: 크기 | Ctrl+휠: 회전 | 우클릭: 반전 | Del: 삭제")
        canvas_layout.addWidget(self.lbl_info)
        canvas_layout.addWidget(self.view)

        # --- 오른쪽: 도구 패널 ---
        panel_layout = QVBoxLayout()
        
        # 1. 탭 위젯 (트리 선택 / 오너먼트 꾸미기)
        self.tabs = QTabWidget()
        
        # Tab 1: 트리(배경) 선택
        self.tab_tree = QWidget()
        tree_layout = QVBoxLayout()
        self.tree_list = ImageListWidget(size=100)
        self.tree_list.itemClicked.connect(self.change_tree_background)
        btn_add_tree = QPushButton("📂 트리 이미지 폴더에서 불러오기 (새로고침)")
        btn_add_tree.clicked.connect(lambda: self.load_images_from_folder("trees", self.tree_list))
        btn_upload_tree = QPushButton("➕ 트리 파일 직접 추가")
        btn_upload_tree.clicked.connect(self.upload_tree_file)
        
        tree_layout.addWidget(QLabel("<b>트리 선택 (클릭하여 변경)</b>"))
        tree_layout.addWidget(self.tree_list)
        tree_layout.addWidget(btn_add_tree)
        tree_layout.addWidget(btn_upload_tree)
        self.tab_tree.setLayout(tree_layout)
        
        # Tab 2: 오너먼트
        self.tab_ornament = QWidget()
        ornament_layout = QVBoxLayout()
        self.ornament_list = ImageListWidget(size=60)
        self.ornament_list.setDragEnabled(True) # 드래그 가능하게 설정
        # 드래그 로직 오버라이드
        self.ornament_list.startDrag = self.start_ornament_drag
        
        btn_add_orn = QPushButton("📂 오너먼트 폴더 새로고침")
        btn_add_orn.clicked.connect(lambda: self.load_images_from_folder("ornaments", self.ornament_list))
        btn_upload_orn = QPushButton("➕ 오너먼트 파일 추가")
        btn_upload_orn.clicked.connect(self.upload_ornament_file)
        
        ornament_layout.addWidget(QLabel("<b>오너먼트 (드래그 앤 드롭)</b>"))
        ornament_layout.addWidget(self.ornament_list)
        ornament_layout.addWidget(btn_add_orn)
        ornament_layout.addWidget(btn_upload_orn)
        self.tab_ornament.setLayout(ornament_layout)
        
        self.tabs.addTab(self.tab_tree, "🎄 트리 선택")
        self.tabs.addTab(self.tab_ornament, "⭐ 오너먼트")
        
        panel_layout.addWidget(self.tabs)

        # 2. 펜 도구 (Drawing Tool)
        group_pen = QGroupBox("🎨 그림 그리기 펜")
        pen_layout = QVBoxLayout()
        
        hbox_pen_ctrl = QHBoxLayout()
        self.btn_toggle_pen = QPushButton("펜 켜기")
        self.btn_toggle_pen.setCheckable(True)
        self.btn_toggle_pen.clicked.connect(self.toggle_drawing_mode)
        
        self.btn_color = QPushButton("■")
        self.btn_color.setStyleSheet("background-color: red; color: red; font-weight: bold;")
        self.btn_color.clicked.connect(self.choose_color)
        
        hbox_pen_ctrl.addWidget(self.btn_toggle_pen)
        hbox_pen_ctrl.addWidget(QLabel("색상:"))
        hbox_pen_ctrl.addWidget(self.btn_color)
        
        hbox_width = QHBoxLayout()
        self.slider_width = QSlider(Qt.Horizontal)
        self.slider_width.setRange(1, 20)
        self.slider_width.setValue(5)
        self.slider_width.valueChanged.connect(self.change_pen_width)
        hbox_width.addWidget(QLabel("두께:"))
        hbox_width.addWidget(self.slider_width)
        
        pen_layout.addLayout(hbox_pen_ctrl)
        pen_layout.addLayout(hbox_width)
        group_pen.setLayout(pen_layout)
        
        panel_layout.addWidget(group_pen)

        # 3. 완료 섹션
        self.input_text = QLineEdit()
        self.input_text.setPlaceholderText("전광판 문구 입력...")
        
        btn_finish = QPushButton("✨ 완성! 바탕화면에 띄우기")
        btn_finish.setStyleSheet("background-color: #ff4757; color: white; font-size: 16px; font-weight: bold; padding: 12px;")
        btn_finish.clicked.connect(self.finish_editing)
        
        panel_layout.addWidget(QLabel("<b>최종 설정</b>"))
        panel_layout.addWidget(self.input_text)
        panel_layout.addWidget(btn_finish)

        # 스플리터 구성
        splitter = QSplitter(Qt.Horizontal)
        left_widget = QWidget()
        left_widget.setLayout(canvas_layout)
        right_widget = QWidget()
        right_widget.setLayout(panel_layout)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([800, 350])
        
        main_layout.addWidget(splitter)

        # 초기 데이터 로드
        self.load_images_from_folder("trees", self.tree_list)
        self.load_images_from_folder("ornaments", self.ornament_list)
        
        # 기본 트리 로드 (없으면 생성)
        if self.tree_list.count() > 0:
            first_tree = self.tree_list.item(0).data(Qt.UserRole)
            self.scene.set_background(QPixmap(first_tree))
        else:
            self.create_dummy_tree()

        self.desktop_widget = DesktopWidget()

    # --- 유틸리티 메서드 ---
    def load_images_from_folder(self, folder_name, list_widget):
        list_widget.clear()
        if not os.path.exists(folder_name): return
        for file in os.listdir(folder_name):
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                list_widget.add_image(os.path.join(folder_name, file))

    def create_dummy_tree(self):
        pix = QPixmap(600, 800)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setBrush(QColor(34, 139, 34))
        painter.drawPolygon(QPoint(300, 50), QPoint(50, 750), QPoint(550, 750))
        painter.end()
        self.scene.set_background(pix)

    # --- 트리 변경 로직 ---
    def change_tree_background(self, item):
        path = item.data(Qt.UserRole)
        self.scene.set_background(QPixmap(path))

    def upload_tree_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "트리 추가", "", "Images (*.png *.jpg)")
        if fname:
            # 파일을 trees 폴더로 복사하지는 않고 그냥 리스트에만 임시 추가 (원하면 복사 로직 추가 가능)
            self.tree_list.add_image(fname)

    # --- 오너먼트 드래그 로직 (메서드 바인딩용) ---
    def start_ornament_drag(self, supportedActions):
        item = self.ornament_list.currentItem()
        if not item: return
        path = item.data(Qt.UserRole)
        pixmap = QPixmap(path)
        
        item_data = QByteArray()
        data_stream = QDataStream(item_data, QIODevice.WriteOnly)
        data_stream << pixmap

        mime_data = QMimeData()
        mime_data.setData("application/x-item-data", item_data)

        drag = QDrag(self.ornament_list)
        drag.setMimeData(mime_data)
        drag.setPixmap(pixmap.scaled(50, 50, Qt.KeepAspectRatio))
        drag.exec_(Qt.CopyAction)

    def upload_ornament_file(self):
        fnames, _ = QFileDialog.getOpenFileNames(self, "오너먼트 추가", "", "Images (*.png *.jpg *.gif)")
        for fname in fnames:
            self.ornament_list.add_image(fname)

    # --- 펜 그리기 로직 ---
    def toggle_drawing_mode(self):
        is_drawing = self.btn_toggle_pen.isChecked()
        self.scene.is_drawing_mode = is_drawing
        
        if is_drawing:
            self.btn_toggle_pen.setText("펜 끄기 (그리기 중...)")
            self.btn_toggle_pen.setStyleSheet("background-color: #FFA500; font-weight: bold;")
            self.view.setCursor(QCursor(Qt.CrossCursor))
            self.view.setDragMode(QGraphicsView.NoDrag)
            self.lbl_info.setText("🖌 그리기 모드! 마우스로 그림을 그리세요.")
        else:
            self.btn_toggle_pen.setText("펜 켜기")
            self.btn_toggle_pen.setStyleSheet("")
            self.view.setCursor(QCursor(Qt.ArrowCursor))
            self.lbl_info.setText("▼ 휠: 크기 | Ctrl+휠: 회전 | 우클릭: 반전 | Del: 삭제")

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.scene.current_color = color
            self.btn_color.setStyleSheet(f"background-color: {color.name()}; color: {color.name()};")

    def change_pen_width(self):
        self.scene.pen_width = self.slider_width.value()

    # --- 완료 로직 ---
    def finish_editing(self):
        # 펜 모드 종료
        if self.btn_toggle_pen.isChecked():
            self.btn_toggle_pen.click() 
            
        text = self.input_text.text() or "Happy Holidays!"
        self.scene.clearSelection()
        
        # 렌더링
        rect = self.scene.itemsBoundingRect()
        rect = rect.united(self.scene.sceneRect())
        image = QImage(rect.size().toSize(), QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        
        painter = QPainter(image)
        self.scene.render(painter, target=rect, source=rect)
        painter.end()
        
        self.desktop_widget.set_content(QPixmap.fromImage(image), text)
        self.hide()
        QMessageBox.information(self, "완성", "바탕화면에 트리가 생성되었습니다!")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    editor = EditorWindow()
    editor.show()
    sys.exit(app.exec_())