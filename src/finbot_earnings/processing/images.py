"""Bounded supporting raster inputs; visual evidence always requires human review."""

from io import BytesIO
import warnings

IMAGE_FORMATS = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif"}
MAX_IMAGES = 20
MAX_IMAGE_BYTES = 3_750_000
MAX_IMAGE_TOTAL_BYTES = 12 * 1024 * 1024


def image_format(filename):
    return IMAGE_FORMATS.get(filename.rsplit(".", 1)[-1].lower())


def valid_image(body, format):
    from PIL import Image, UnidentifiedImageError

    if not body or len(body) > MAX_IMAGE_BYTES:
        return False
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(body)) as image:
                if (image.format.lower() != format or not 1 <= image.width <= 8000
                        or not 1 <= image.height <= 8000 or getattr(image, "n_frames", 1) != 1):
                    return False
                image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        return False
    return True
