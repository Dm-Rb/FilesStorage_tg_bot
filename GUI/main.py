from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QFileDialog, QVBoxLayout, QTextEdit
)
from PyQt6.QtCore import Qt
import re
import sys
import os
import shutil
import csv
from datetime import datetime


"""
Окно для более удобного создания каталогов с договорами. Имя каталога содержит данные, используемые поисковым сккриптом
Так же создаёт в новых каталогах файл .csv, содержаний инфу, которая была указана в полях окна
"""


class DropArea(QLabel):
    def __init__(self):
        super().__init__("Перетащите файлы сюда")
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(160)  # Увеличение высоты в 2 раза
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #aaa;
                padding: 30px;
                background: #f9f9f9;
            }
        """)
        self.files = []

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                self.files.append(path)

        self.setText(f"Файлов добавлено: {len(self.files)}")


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Создание каталога с данными")
        self.resize(520, 650)

        self.output_dir = ""

        layout = QVBoxLayout()
        layout.setSpacing(8)  # уменьшили расстояние между элементами
        layout.setContentsMargins(10, 10, 10, 10)  # убрали лишние отступы

        # Выбор папки
        self.folder_btn = QPushButton("Выбрать папку для сохранения")
        self.folder_btn.clicked.connect(self.choose_folder)
        layout.addWidget(self.folder_btn)

        self.folder_label = QLabel("Папка для сохранения не выбрана")
        self.folder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.folder_label)

        # Поля ввода
        self.contract_input = QLineEdit()
        self.contract_input.setPlaceholderText("Номер договора")

        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("Адрес")

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Номер телефона")

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("ФИО клиента")

        self.margin_input = QLineEdit()
        self.margin_input.setPlaceholderText("Маржа")

        layout.addWidget(self.contract_input)
        layout.addWidget(self.address_input)
        layout.addWidget(self.phone_input)
        layout.addWidget(self.name_input)
        layout.addWidget(self.margin_input)

        # Drag & Drop (увеличен)
        self.drop_area = DropArea()
        layout.addWidget(self.drop_area)

        # Кнопка
        self.create_btn = QPushButton("Создать")
        self.create_btn.clicked.connect(self.create_result)
        layout.addWidget(self.create_btn)

        # Консоль (уменьшена)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFixedHeight(120)  # В 2 раза меньше
        self.console.setStyleSheet("""
            QTextEdit {
                background: #e6e6e6;
                color: #222;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)
        self.console.setPlaceholderText("История операций...")
        layout.addWidget(self.console)

        self.setLayout(layout)

    def log(self, message):
        time = datetime.now().strftime("%H:%M:%S")
        self.console.append(f"[{time}] {message}")

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if folder:
            self.output_dir = folder
            self.folder_label.setText(folder)
            self.log(f"Выбрана папка вывода: {folder}")

    @staticmethod
    def sanitize_filename(string):
        cleaned = re.sub(r'[\\/:*?"<>|+%!@]', '', string)
        return cleaned

    def create_result(self):
        """
        Создаёт папку с именем которое является конкатенацией строк из полей окна. В папку копируются указанные файлы
        и создаётся файл <info.csv> с данными
        """
        if not self.output_dir:
            self.log("❗ Папка для сохранения не выбрана")
            return

        fields = [
            self.contract_input.text().replace('/', ' ').replace('\\', ' ').strip(),
            self.address_input.text().replace('\\', ' ').strip(),
            self.phone_input.text().replace('\\', ' ').strip(),
            self.name_input.text().replace('\\', ' ').strip(),
            self.margin_input.text().replace('\\', ' ').strip()
        ]

        filled_fields = [self.sanitize_filename(f) for f in fields if f]

        if not filled_fields:
            self.log("❗ Не заполнено ни одного поля")
            return

        if not self.drop_area.files:
            self.log("❗ Не добавлены файлы")
            return

        folder_name = "_".join(filled_fields)
        target_folder = os.path.join(self.output_dir, folder_name)

        os.makedirs(target_folder, exist_ok=True)

        for file_path in self.drop_area.files:
            shutil.copy(file_path, target_folder)

        csv_path = os.path.join(target_folder, "info.csv")
        with open(csv_path, "w", newline="",  encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow([
                "Номер договора", "Адрес", "Телефон", "ФИО клиента", "Маржа"
            ])
            writer.writerow(fields)

        self.log(f"Создан новый каталог: {folder_name}")
        self.clear_form()

    def clear_form(self):
        self.contract_input.clear()
        self.address_input.clear()
        self.phone_input.clear()
        self.name_input.clear()
        self.margin_input.clear()

        self.drop_area.files.clear()
        self.drop_area.setText("Перетащите файлы сюда")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
