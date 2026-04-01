from insightface.app import FaceAnalysis

face_app = None

def get_face_app():
    global face_app

    if face_app is None:
        print("Loading face model...")

        face_app = FaceAnalysis(
            name="buffalo_l",
            providers=["CPUExecutionProvider"]
        )

        face_app.prepare(ctx_id=-1)

        print("Face model loaded")

    return face_app