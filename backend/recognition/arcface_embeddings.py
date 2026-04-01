import numpy as np
import cv2

from scipy.datasets import face

from recognition.model_loader import get_face_app


def generate_embedding_from_images(images):
    face_app = get_face_app()

    embeddings = []

    for img_bytes in images:

        # convert bytes -> numpy image
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img is None:
            continue

        faces = face_app.get(img)

        if len(faces) == 1:
            face = faces[0]

            # filter small faces
            if face.bbox[2] - face.bbox[0] < 80:
                continue

            embeddings.append(face.normed_embedding)

    if len(embeddings) == 0:
        return None

    # average embeddings
    avg_embedding = np.mean(embeddings, axis=0)
    avg_embedding = avg_embedding / np.linalg.norm(avg_embedding)

    return avg_embedding.tolist()