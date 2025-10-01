from PIL import Image
from typing import Tuple

def get_image_size(image_file) -> Tuple[int,int]:
    image_file.seek(0)
    with Image.open(image_file) as img:
        return img.width, img.height
