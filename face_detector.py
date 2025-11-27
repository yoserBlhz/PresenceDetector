import cv2
import numpy as np
import os
from datetime import datetime
from threading import Thread
import time


class FaceDetector:
    def __init__(self, tolerance=0.55):
        self.tolerance = tolerance
        self.known_encodings = []
        self.known_students = []
        self.marked_students = set()
        self.running = False
        self.stats = None
        
        # Détecteur Haar Cascade d'OpenCV
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        
        # Charger le modèle de reconnaissance faciale DNN d'OpenCV
        # Utilise le modèle ResNet pour les embeddings
        self.face_recognizer = None
        self._load_face_recognition_model()

    def _load_face_recognition_model(self):
        """Charge le modèle de reconnaissance faciale OpenCV (alternative à dlib)"""
        try:
            # Télécharger ces fichiers si nécessaire:
            # https://github.com/pyannote/pyannote-data/raw/master/openface.nn4.small2.v1.t7
            model_path = "openface.nn4.small2.v1.t7"
            
            if os.path.exists(model_path):
                self.face_recognizer = cv2.dnn.readNetFromTorch(model_path)
                print("✓ Modèle OpenFace chargé")
            else:
                print("⚠️ Modèle OpenFace non trouvé, utilisation de comparaison d'histogrammes")
                self.face_recognizer = None
        except Exception as e:
            print(f"⚠️ Erreur chargement modèle: {e}, utilisation de comparaison d'histogrammes")
            self.face_recognizer = None

    def load_encodings_from_database(self, database):
        """Charge les encodages depuis la base de données"""
        self.known_encodings, self.known_students = database.get_student_encodings()
        
        # Convertir les encodages en numpy arrays
        if self.known_encodings and len(self.known_encodings) > 0:
            if isinstance(self.known_encodings[0], (list, tuple)):
                self.known_encodings = [np.array(enc, dtype=np.float64) for enc in self.known_encodings]
        
        print(f"✓ {len(self.known_encodings)} encodage(s) chargé(s)")

    def _extract_face_encoding(self, face_image):
        """Extrait l'encodage d'un visage avec OpenCV DNN ou histogramme"""
        if face_image.size == 0 or face_image.shape[0] < 20 or face_image.shape[1] < 20:
            return None
        
        try:
            if self.face_recognizer is not None:
                # Utiliser le modèle OpenFace
                blob = cv2.dnn.blobFromImage(face_image, 1.0/255, (96, 96), (0, 0, 0), swapRB=True, crop=False)
                self.face_recognizer.setInput(blob)
                encoding = self.face_recognizer.forward()
                return encoding.flatten()
            else:
                # Fallback: utiliser des features d'histogramme
                gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY) if len(face_image.shape) == 3 else face_image
                resized = cv2.resize(gray, (100, 100))
                
                # Créer un vecteur de features combiné
                hist = cv2.calcHist([resized], [0], None, [256], [0, 256]).flatten()
                hist = hist / (hist.sum() + 1e-7)  # Normalisation
                
                # Ajouter des features LBP (Local Binary Patterns)
                lbp = self._compute_lbp(resized)
                
                # Combiner les features
                encoding = np.concatenate([hist, lbp])
                return encoding
        except Exception as e:
            print(f"⚠️ Erreur extraction encoding: {e}")
            return None

    def _compute_lbp(self, image):
        """Calcule les Local Binary Patterns (alternative simple aux deep features)"""
        h, w = image.shape
        lbp = np.zeros((h-2, w-2), dtype=np.uint8)
        
        for i in range(1, h-1):
            for j in range(1, w-1):
                center = image[i, j]
                code = 0
                code |= (image[i-1, j-1] >= center) << 7
                code |= (image[i-1, j] >= center) << 6
                code |= (image[i-1, j+1] >= center) << 5
                code |= (image[i, j+1] >= center) << 4
                code |= (image[i+1, j+1] >= center) << 3
                code |= (image[i+1, j] >= center) << 2
                code |= (image[i+1, j-1] >= center) << 1
                code |= (image[i, j-1] >= center) << 0
                lbp[i-1, j-1] = code
        
        # Histogramme LBP
        hist_lbp = cv2.calcHist([lbp], [0], None, [256], [0, 256]).flatten()
        return hist_lbp / (hist_lbp.sum() + 1e-7)

    def _compare_faces(self, known_encodings, face_encoding):
        """Compare un visage avec les visages connus (alternative à face_recognition.face_distance)"""
        if face_encoding is None or not known_encodings:
            return []
        
        distances = []
        for known_encoding in known_encodings:
            # Distance euclidienne
            distance = np.linalg.norm(known_encoding - face_encoding)
            distances.append(distance)
        
        return np.array(distances)

    def detect_faces_in_frame(self, frame, return_all_faces=False):
        """Détection complète avec OpenCV (sans dlib)"""
        if frame is None or frame.size == 0:
            return []

        try:
            # Détection des visages avec Haar Cascade
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            if len(faces) == 0:
                return []
            
            results = []
            
            for (x, y, w, h) in faces:
                # Extraire la région du visage
                face_image = frame[y:y+h, x:x+w]
                
                # Convertir en RGB si nécessaire
                if len(face_image.shape) == 2:
                    face_image = cv2.cvtColor(face_image, cv2.COLOR_GRAY2BGR)
                
                # Extraire l'encodage
                encoding = self._extract_face_encoding(face_image)
                
                if encoding is None:
                    if return_all_faces:
                        results.append({
                            "student": {"id": -1, "name": "Erreur encodage"},
                            "location": (y, x+w, y+h, x),
                            "confidence": 0
                        })
                    continue
                
                # Comparer avec les visages connus
                if self.known_encodings:
                    distances = self._compare_faces(self.known_encodings, encoding)
                    best_idx = np.argmin(distances)
                    dist = distances[best_idx]
                    
                    # Ajuster le seuil selon le type d'encodage
                    threshold = self.tolerance if self.face_recognizer else 0.4
                    
                    if dist < threshold:
                        student = self.known_students[best_idx]
                        results.append({
                            "student": student,
                            "location": (y, x+w, y+h, x),
                            "confidence": round(max(0, (1 - dist / threshold) * 100), 1)
                        })
                    elif return_all_faces:
                        results.append({
                            "student": {"id": -1, "name": f"Inconnu ({dist:.2f})"},
                            "location": (y, x+w, y+h, x),
                            "confidence": 0
                        })
                elif return_all_faces:
                    results.append({
                        "student": {"id": -1, "name": "Inconnu"},
                        "location": (y, x+w, y+h, x),
                        "confidence": 0
                    })
            
            return results
            
        except Exception as e:
            print(f"✗ Erreur détection : {e}")
            return []

    def draw_faces_on_frame(self, frame, faces):
        """Dessine les rectangles et labels sur les visages détectés"""
        for f in faces:
            t, r, b, l = f["location"]
            name = f["student"]["name"]
            conf = f.get("confidence", 0)
            
            # Couleur selon l'état
            if f["student"].get("id", 0) == -1:
                color = (0, 0, 255)  # Rouge pour inconnus
            elif f["student"].get("id", -1) in self.marked_students:
                color = (0, 255, 0)  # Vert pour présents
            else:
                color = (0, 165, 255)  # Orange pour détectés non marqués

            # Rectangle du visage
            cv2.rectangle(frame, (l, t), (r, b), color, 2)
            
            # Rectangle du label
            cv2.rectangle(frame, (l, b - 35), (r, b), color, cv2.FILLED)
            
            # Texte du nom et confiance
            label = f"{name} ({conf}%)" if conf else name
            cv2.putText(frame, label, (l + 6, b - 6), 
                       cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255), 2)
        
        return frame

    def _attendance_loop(self, database, session_id):
        """Boucle principale de détection de présence"""
        self.running = True
        self.marked_students.clear()
        
        if not self.known_encodings:
            self.load_encodings_from_database(database)

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("✗ Webcam inaccessible")
            self.running = False
            return

        print(f"✓ Session démarrée - {len(self.known_encodings)} étudiants | Appuyez sur Q pour quitter")
        print("ℹ️ Utilisation d'OpenCV pur (sans dlib)")

        frame_count = 0
        while self.running:
            ret, frame = cap.read()
            if not ret:
                print("✗ Erreur lecture webcam")
                break

            display = frame.copy()
            frame_count += 1

            # Détection tous les 5 frames
            if frame_count % 5 == 0:
                faces = self.detect_faces_in_frame(frame, return_all_faces=True)
                display = self.draw_faces_on_frame(display, faces)

                # Marquer la présence
                for face in faces:
                    sid = face["student"].get("id", -1)
                    if sid != -1 and sid not in self.marked_students:
                        if database.mark_attendance(session_id, sid):
                            self.marked_students.add(sid)
                            print(f"✓ {face['student']['name']} marqué présent ({face['confidence']}%)")

            # Affichage des informations
            cv2.putText(display, f"Session: {session_id}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(display, f"Presents: {len(self.marked_students)}", (10, 70), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            
            cv2.imshow("Presence Faciale", display)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("✓ Arrêt demandé par l'utilisateur")
                break

        cap.release()
        cv2.destroyAllWindows()
        self.running = False
        print(f"✓ Session terminée - {len(self.marked_students)} présents")

    def start_attendance_session(self, database, session_id):
        """Démarre la session de prise de présence en arrière-plan"""
        Thread(target=self._attendance_loop, args=(database, session_id), daemon=True).start()
        return {"status": "started", "session_id": session_id}

    def stop_attendance_session(self):
        """Arrête la session en cours"""
        self.running = False
        time.sleep(1)
        stats = {
            "marked_count": len(self.marked_students),
            "marked_ids": list(self.marked_students)
        }
        return stats

