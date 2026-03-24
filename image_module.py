import cv2
import numpy as np
from PIL import Image
import imagehash
import io
from datetime import datetime

def get_hash(img_bytes):
    img = Image.open(io.BytesIO(img_bytes))
    return str(imagehash.phash(img))

def compare_images(img1_bytes, img2_bytes):
    img1 = cv2.imdecode(np.frombuffer(img1_bytes, np.uint8), 1)
    img2 = cv2.imdecode(np.frombuffer(img2_bytes, np.uint8), 1)

    img1 = cv2.resize(img1, (400, 400))
    img2 = cv2.resize(img2, (400, 400))

    diff = cv2.absdiff(img1, img2)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

    return float(np.mean(gray))

def process_images(before_file, after_file, activity_time):
    before_bytes = before_file.read()
    after_bytes = after_file.read()

    before_hash = get_hash(before_bytes)
    after_hash = get_hash(after_bytes)

    diff_score = compare_images(before_bytes, after_bytes)

    now = datetime.now()
    time_diff = abs((now - activity_time).total_seconds() / 60)

    status = "VALID"
    if diff_score < 10 or time_diff > 60:
        status = "INVALID"

    return {
        "difference": diff_score,
        "time_diff": time_diff,
        "status": status,
        "before_hash": before_hash,
        "after_hash": after_hash
    }
