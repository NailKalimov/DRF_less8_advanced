"""Обработка изображений библиотекой Pillow."""

from io import BytesIO
from pathlib import PurePath

from django.core.files.base import ContentFile
from PIL import Image

THUMBNAIL_SIZE = (300, 300)


def make_thumbnail(image_file) -> ContentFile:
    """Делает миниатюру обложки до 300×300 в формате JPEG.

    Миниатюра нужна клиентам для списков и превью: маленькую картинку
    грузить быстрее, чем оригинал.

    Отличия от кода методички:
      * convert("RGB"): в JPEG нет прозрачности, и PNG с альфа-каналом
        (режим RGBA) без конвертации падает с ошибкой
        «cannot write mode RGBA as JPEG»;
      * ContentFile вместо InMemoryUploadedFile: результат тот же, кода меньше.
    """
    with Image.open(image_file) as source:
        thumbnail = source.convert("RGB")

    # thumbnail() уменьшает картинку с сохранением пропорций.
    thumbnail.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

    # Сохраняем в BytesIO, то есть в память, а не на диск.
    buffer = BytesIO()
    thumbnail.save(buffer, format="JPEG", quality=85)

    # Pillow прочитал исходный файл. Возвращаем указатель в начало,
    # чтобы Django потом сохранил оригинал целиком.
    image_file.seek(0)

    name = f"thumb_{PurePath(image_file.name).stem}.jpg"
    return ContentFile(buffer.getvalue(), name=name)
