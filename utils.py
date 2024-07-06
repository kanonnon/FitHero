import base64
import io
from PIL import Image


def encode_image(image_data):
    """
    Encode image data to base64
    """
    return base64.b64encode(image_data).decode("utf-8")


def resize_image(image_path, new_size=(512, 512)):
    """
    Resize image to new size
    """
    with Image.open(image_path) as img:
        resized_img = img.resize(new_size)
        img_byte_arr = io.BytesIO()
        resized_img.save(img_byte_arr, format=img.format)
        img_byte_arr = img_byte_arr.getvalue()
    return img_byte_arr


def extract_text_between(text, start, end):
    """
    Extract text between two markers
    """
    start_idx = text.find(start)
    if start_idx == -1:
        return ""
    
    start_idx += len(start)
    end_idx = text.find(end, start_idx)
    
    if end_idx == -1:
        return ""
    
    return text[start_idx:end_idx].strip()