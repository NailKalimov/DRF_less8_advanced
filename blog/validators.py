"""Валидаторы загружаемых файлов."""

from django.core.exceptions import ValidationError

MAX_UPLOAD_SIZE_MB = 5


def validate_file_size(file):
    """Не даёт загрузить файл больше MAX_UPLOAD_SIZE_MB.

    Проверка размера защищает сервер от злоупотреблений: без неё клиент
    может забить диск огромными файлами.
    """
    if file.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"Размер файла не должен превышать {MAX_UPLOAD_SIZE_MB} МБ")
