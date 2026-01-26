from config import config_
import os
from slugify import slugify
from PIL import Image
from pathlib import Path
from io import BytesIO
import pillow_heif  # extension for PIL to read iPhone files
import csv
from collections import defaultdict
from typing import Dict, List, TypedDict


pillow_heif.register_heif_opener()  # it is important to call it right after the imports.


class FolderData(TypedDict):
    # annotation for FileManager.folders_by_id
    folder_name: str
    slug: str
    folder_id: int


class FolderDataByKey(TypedDict):
    # annotation for FileManager.folders_by_order\folders_by_phone\folders_by_address
    folder_name: str
    folder_id: int | str


class FileManager:
    """
    A class for working with files and directories. During initialization, it saves all existing directories into its
    attributes. These records are used as a search cache.
    The self.folders_by_id attribute is used for partial match searches.
    The self.folders_by_order, self.folders_by_phone, and self.folders_by_address attributes are used for instant O(1)
    lookup by key name.
    It contains methods for reading and processing images and .csv files.
    """

    SUPPORTED_IMAGES = {'.jpg', '.jpeg', '.png', '.webp'}
    HEIC_IMAGES = {'.heic', '.heif'}

    def __init__(self):
        #
        self.folders_by_id: Dict[int, FolderData] = {}  # annotation in class FolderData
        self.folders_by_order: Dict[str, List[FolderDataByKey]] = {}  # annotation in class FolderDataByKey
        self.folders_by_phone: Dict[str, List[Dict]] = {}  # annotation in class FolderDataByKey
        self.folders_by_address: Dict[str, List[Dict]] = {}  # annotation in class FolderDataByKey
        self.total_folders: int = len(os.listdir(config_.STORAGE_DIR))
        self.__build_indexes()

    @staticmethod
    def __normalize_string(string: str):
        string = slugify(string)
        return string.replace('-', '')

    def __build_indexes(self) -> None:
        """
        It creates objects for the attribute <self.folders_by_id>. It also calls the method
        <self.__index_folder_metadata> inside itself.
        This method creates objects for the attributes <self.folders_by_order>,
         <self.folders_by_phone>, <self.folders_by_address>.
        """
        if not os.listdir(config_.STORAGE_DIR):
            return None
        for num, folder_name in enumerate(os.listdir(config_.STORAGE_DIR)):
            self.folders_by_id[num] = {'folder_name': folder_name,
                                       'slug': self.__normalize_string(folder_name),
                                       'folder_id': num}
            self.__index_folder_metadata(folder_id=num, folder_name=folder_name)

        return

    def __index_folder_metadata(self, folder_id: str | int, folder_name: str) -> None:
        """
        This method creates objects for the attributes <self.folders_by_order>,
         <self.folders_by_phone>, <self.folders_by_address>
        """
        info: dict | None = self.get_data_from_info_file(folder_id)
        if not info:
            return
        order = info.get('Номер договора', None)
        phone_number = info.get('Телефон', None)
        address = info.get('Адрес', None)
        if order:
            values = self.folders_by_order.setdefault(self.__normalize_string(order), [])
            values.append({'folder_name': folder_name, 'folder_id': folder_id})
            self.folders_by_order[self.__normalize_string(order)] = values

        if phone_number:
            values = self.folders_by_phone.setdefault(self.__normalize_string(phone_number), [])
            values.append({'folder_name': folder_name, 'folder_id': folder_id})

            self.folders_by_phone[self.__normalize_string(phone_number)] = values

        if address:
            values = self.folders_by_address.setdefault(self.__normalize_string(address), [])
            values.append({'folder_name': folder_name, 'folder_id': folder_id})
            self.folders_by_address[self.__normalize_string(address)] = values

        return

    def remove_folder(self, folder_name: str) -> None:
        # it removes an object from <self.folders_by_id> by the argument.
        for id_key, item_value in self.folders_by_id.items():
            if item_value['folder_name'] == folder_name:
                del self.folders_by_id[id_key]
                return

    def add_folder(self, folder_name: str) -> None:
        # It adds new objects to <self.folders_by_id> and <self.folders_by_order/folders_by_phone/folders_by_address>
        # by the argument.
        self.folders_by_id[self.total_folders] = {'folder_name': folder_name,
                                                  'slug': self.__normalize_string(folder_name),
                                                  'folder_id': self.total_folders,
                                                  }
        self.__index_folder_metadata(self.total_folders, folder_name)
        self.total_folders += 1
        return

    def search_folders_by_partial(self, query: str) -> list[dict]:
        """
        Search by partial match. We iterate through self.folders_by_id and compare the normalized argument with the 'slug'.
        If there is a match, we add it to the result list.
        """
        result_array = []
        query = self.__normalize_string(query)
        # folders_by_id = {int: {'folder_name': str, 'slug': str}, ...}
        for item in self.folders_by_id.values():
            if query in item['slug']:
                result_array.append({'folder_id': item['folder_id'], 'folder_name': item['folder_name']})

        return result_array

    def search_folders_by_key(self, query: str, search_type: str) -> list[dict]:
        """
        Search by exact key match. The search_type argument specifies which dictionary to search in.
        """
        result_array = []
        query = self.__normalize_string(query)

        index_data = {}
        if search_type == "by_contract":
            index_data = self.folders_by_order
        elif search_type == "by_phone":
            index_data = self.folders_by_phone
        elif search_type == "by_address":
            index_data = self.folders_by_address
        else:
            pass

        if index_data.get(query, None):
            for i in range(len(index_data[query])):
                item = index_data[query][i]
                result_array.append(item)

        return result_array

    def __get_full_path_folder_by_id(self, folder_id: str | int) -> str | None:
        folder_item = self.folders_by_id.get(int(folder_id), None)
        if not folder_item:
            return None
        folder_name = folder_item.get('folder_name', None)
        if not folder_name:
            return None
        folder_path = os.path.join(config_.STORAGE_DIR, folder_name)

        return folder_path

    def get_files_from_folder(self, folder_id: str | int) -> List[str] | None:
        """It searches for and returns files inside a directory."""
        folder_path = self.__get_full_path_folder_by_id(folder_id)
        if not os.listdir(folder_path):
            return None
        # Возвращаем список абсолютных путей к файлам из родительского каталога
        try:
            return [os.path.join(folder_path, file_name) for file_name in os.listdir(folder_path)]
        except TypeError:
            return None

    def prepare_images(self, folder_id: str | int) -> List[bytes] | None:
        """A wrapper method for sending image files to a Telegram bot."""
        files_paths = self.get_files_from_folder(folder_id)
        if not files_paths:
            return None

        result = []
        for p in files_paths:
            path = Path(p)
            data = self.__image_to_bytes(path)
            if data is not None:
                result.append(data)

        return result

    def __image_to_bytes(self, path: Path) -> bytes | None:
        """
        It returns binary image data.
        HEIC is converted to JPEG.
        Not an image -> None
        """
        if not path.exists() or not path.is_file():
            return None

        suffix = path.suffix.lower()

        try:
            # regular images read as is
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
            print(f'Processing error {path}: {e}')
            return None

        return None

    def get_data_from_info_file(self, folder_id: str | int) -> Dict[str, str] | None:
        print(folder_id)
        """A wrapper method for reading the contents of a CSV file."""
        folder_path = self.__get_full_path_folder_by_id(folder_id)
        print(folder_path)

        if not os.listdir(folder_path):
            return None

        csv_file_path = os.path.join(folder_path, 'info.csv')
        if os.path.exists(csv_file_path):
            info: dict | None = self.__read_csv(csv_file_path)
            return info
        return None

    @staticmethod
    def __read_csv(file_path: str, delimiter: str = ';') -> Dict[str, str] | None:
        """It reads the contents of a .csv file and returns it."""
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
