import json

from backend.database.db import SessionLocal
from backend.database.models import Embedding, Student
from backend.recognition.face_matching import recognize_face
from backend.recognition.model_loader import get_face_app


# cache embeddings in memory
embedding_cache = None


def load_embeddings_from_db():
    import numpy as np

    global embedding_cache

    if embedding_cache is not None:
        return embedding_cache

    db = SessionLocal()

    records = db.query(Embedding).all()
    print("Embeddings loaded:", len(records))

    database = {}

    for r in records:
        database[r.student_id] = np.array(
            json.loads(r.embedding_vector),
            dtype=np.float32
        )

    embedding_cache = database
    db.close()

    return embedding_cache


def get_all_students():
    db = SessionLocal()
    students = db.query(Student).all()
    db.close()
    return students


def process_group_images(image_list):
    import cv2
    import numpy as np

    face_app = get_face_app()

    database = load_embeddings_from_db()
    print("Embeddings loaded:", len(database))

    recognized = {}

    # Loop through multiple images
    for image_bytes in image_list:

        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img is None:
            continue

        # resize while keeping aspect ratio
        h, w = img.shape[:2]

        if w > 800:
            scale = 800 / w
            img = cv2.resize(img, (int(w * scale), int(h * scale)))

        faces = face_app.get(img)
        print("Faces detected:", len(faces))

        for face in faces:

            embedding = face.normed_embedding.reshape(1, -1)

            student_id, score = recognize_face(embedding, database)
            print("Matching score:", score)

            if student_id is not None:

                # Keep best score if duplicate detected
                if student_id not in recognized or score > recognized[student_id]:
                    recognized[student_id] = float(score)

    students = get_all_students()

    attendance_list = []

    for student in students:

        if student.id in recognized:
            status = "Present"
        else:
            status = "Absent"

        attendance_list.append({
            "student_id": student.id,
            "roll_no": student.roll_no,
            "name": student.name,
            "status": status
        })

    return attendance_list