import base64
import numpy as np
import cv2

def base64_to_image(base64_string):

    img_data = base64.b64decode(base64_string.split(",")[1])

    np_arr = np.frombuffer(img_data, np.uint8)

    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    return img