from config import config_
import os
from slugify import slugify
from PIL import Image
from pathlib import Path
from io import BytesIO
import pillow_heif  # надстройка PIL для чтения блядских файлов айфон
import csv
from collections import defaultdict
from typing import Dict


pillow_heif.register_heif_opener()  # важно вызвать


class FileManager:

    SUPPORTED_IMAGES = {'.jpg', '.jpeg', '.png', '.webp'}
    HEIC_IMAGES = {'.heic', '.heif'}

    def __init__(self):

        self.folders_map: dict = {}  # {int: {"folder_name" : str, "slug": str}, int:{...}, ...}
        self.folders_len: int = len(os.listdir(config_.STORAGE_DIR))
        self.get_folders_map()

    @staticmethod
    def string_normalized(string):
        string = slugify(string)
        return string.replace('_', '')

    def get_folders_map(self) -> None:
        for num, folder_name in enumerate(os.listdir(config_.STORAGE_DIR)):
            self.folders_map[num] = {'folder_name': folder_name, 'slug': self.string_normalized(folder_name)}
        return

    def del_folder_from_folders_map(self, folder_name) -> None:
        for id_key, item_value in self.folders_map.items():
            if item_value['folder_name'] == folder_name:
                del self.folders_map[id_key]
                return

    def add_new_folder_in_folders_map(self, folder_name) -> None:
        self.folders_map[self.folders_len + 1] = {'folder_name': folder_name, 'slug': self.string_normalized(folder_name)}
        self.folders_len += 1
        return

    def match_search(self, query) -> list[dict]:  # keys ('path_dir', 'slug')
        result_array = []
        query = self.string_normalized(query)
        for id_key, item_value in self.folders_map.items():
            if query in item_value['slug']:
                result_array.append({'id': id_key, 'folder_name': item_value['folder_name']})

        return result_array

    def get_full_path_folder(self, folder_id: str):
        folder_item = self.folders_map.get(int(folder_id), None)
        if not folder_item:
            return None
        # Получаем имя родительского каталога
        folder_name = folder_item.get('folder_name', None)
        if not folder_name:
            return None
        # Джойним корневой каталог из конфига и имя родительского каталога и получаем полный путь к род. каталогу
        folder_path = os.path.join(config_.STORAGE_DIR, folder_name)

        return folder_path

    def get_files_from_folder(self, folder_id) -> list | None:
        folder_path = self.get_full_path_folder(folder_id)
        if not os.listdir(folder_path):
            return None
        # Возвращаем список абсолютных путей к файлам из родительского каталога
        try:
            return [os.path.join(folder_path, file_name) for file_name in os.listdir(folder_path)]
        except TypeError:
            return None

    def prepare_images(self, folder_id) -> list[bytes] | None:

        files_paths = self.get_files_from_folder(folder_id)
        if not files_paths:
            return None

        result = []
        for p in files_paths:
            path = Path(p)
            data = self.image_to_bytes(path)
            if data is not None:
                result.append(data)

        return result

    def image_to_bytes(self, path: Path) -> bytes | None:
        """
        Возвращает бинарные данные изображения.
        HEIC конвертируется в JPEG.
        Не изображение -> None
        """
        if not path.exists() or not path.is_file():
            return None

        suffix = path.suffix.lower()

        try:
            # обычные изображения — читаем как есть
            if suffix in self.SUPPORTED_IMAGES:
                return path.read_bytes()

            # HEIC → JPEG → bytes
            if suffix in self.HEIC_IMAGES:
                img = Image.open(path)
                img = img.convert("RGB")

                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=95)
                return buffer.getvalue()

        except Exception as e:
            print(f'Ошибка обработки {path}: {e}')
            return None

        return None

    def get_text_description(self, folder_id) -> dict | None:
        folder_path = self.get_full_path_folder(folder_id)
        if not os.listdir(folder_path):
            return None
        for file in os.listdir(folder_path):
            if str(file).startswith('info'):
                info: dict | None = self.read_csv_to_dict(os.path.join(folder_path, str(file)))
                return info
        return None

    @staticmethod
    def read_csv_to_dict(file_path: str, delimiter: str = ';') -> Dict[str, str] | None:
        result = defaultdict(str)

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file, delimiter=delimiter)

                for row in reader:
                    for key, value in row.items():
                        result[key] = value

        except FileNotFoundError:
            return None
        except Exception as e:
            return None

        return dict(result)


file_manager = FileManager()

