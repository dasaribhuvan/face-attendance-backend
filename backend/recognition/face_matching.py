import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

THRESHOLD = 0.45


def recognize_face(query_embedding, database):

    best_match = None
    best_score = -1

    for student_id, stored_embedding in database.items():

        stored_embedding = np.array(stored_embedding).reshape(1, -1)

        score = cosine_similarity(query_embedding, stored_embedding)[0][0]

        if score > best_score:
            best_score = score
            best_match = student_id

    if best_score >= THRESHOLD:
        return best_match, best_score
    else:
        return None, best_score