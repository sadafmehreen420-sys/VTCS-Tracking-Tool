"""
Image Processing Module for VTCS
--------------------------------
Features:
- Image Hashing (Duplicate Detection Ready)
- Before vs After Comparison (OpenCV)
- Time Validation
- EXIF Timestamp Extraction (if available)
"""

import cv2
import numpy as np
from PIL import Image, ExifTags
import imagehash
import io
from datetime import datetime


# ---------------- IMAGE HASH ----------------
def get_image_hash(image_bytes):
    """
    Generate perceptual hash of image
    Used for duplicate detection
    """
    image = Image.open(io.BytesIO(image_bytes))
    return str(imagehash.phash(image))


# ---------------- IMAGE COMPARISON ----------------
def compare_images(before_bytes, after_bytes):
    """
    Compare two images and return difference score
    Higher score = more difference (good for activity)
    """
    img1 = cv2.imdecode(np.frombuffer(before_bytes, np.uint8), cv2.IMREAD_COLOR)
    img2 = cv2.imdecode(np.frombuffer(after_bytes, np.uint8), cv2.IMREAD_COLOR)

    # Resize for uniform comparison
    img1 = cv2.resize(img1, (500, 500))
    img2 = cv2.resize(img2, (500, 500))

    # Absolute difference
    diff = cv2.absdiff(img1, img2)

    # Convert to grayscale
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

    # Mean difference score
    score = np.mean(gray)

    return float(score)


# ---------------- EXIF TIME EXTRACTION ----------------
def extract_image_time(image_bytes):
    """
    Extract timestamp from image metadata (if available)
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        exif = image._getexif()

        if exif is not None:
            for tag, value in exif.items():
                decoded = ExifTags.TAGS.get(tag, tag)

                if decoded == "DateTimeOriginal":
                    return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")

    except:
        return None

    return None


# ---------------- MAIN PROCESS FUNCTION ----------------
def process_images(before_file, after_file, activity_time):
    """
    Main function used in Streamlit app
    """

    before_bytes = before_file.read()
    after_bytes = after_file.read()

    # HASHES
    before_hash = get_image_hash(before_bytes)
    after_hash = get_image_hash(after_bytes)

    # IMAGE DIFFERENCE
    diff_score = compare_images(before_bytes, after_bytes)

    # SYSTEM TIME CHECK
    current_time = datetime.now()
    time_diff = abs((current_time - activity_time).total_seconds() / 60)

    # EXIF TIME CHECK (optional)
    before_img_time = extract_image_time(before_bytes)
    after_img_time = extract_image_time(after_bytes)

    # STATUS LOGIC
    status = "VALID"

    if diff_score < 10:
        status = "INVALID (No Activity Detected)"

    elif time_diff > 60:
        status = "INVALID (Time Mismatch)"

    # RETURN RESULTS
    return {
        "status": status,
        "difference_score": diff_score,
        "time_difference_minutes": time_diff,
        "before_hash": before_hash,
        "after_hash": after_hash,
        "before_image_time": before_img_time,
        "after_image_time": after_img_time
    }
