
"""
FastAPI REST API pour le système de gestion de présence
par reconnaissance faciale
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional
import os
import numpy as np
import cv2
import sqlite3


from database import AttendanceDatabase
from face_detector import FaceDetector

# --- Initialisation FastAPI ---
app = FastAPI(
    title="Attendance System API",
    version="1.0.0",
    description="REST API pour le système de gestion de présence par reconnaissance faciale",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Base de données et détecteur ---
database = AttendanceDatabase()
detector = FaceDetector(tolerance=0.6)  # Tolérance plus stricte

# --- Pydantic Models ---
class ProfessorCreate(BaseModel):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    subject: str = Field(..., min_length=1)

class StudentCreate(BaseModel):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)

class SessionRequest(BaseModel):
    professor_id: int
    subject: Optional[str] = None

# --- Endpoints Health ---
@app.get("/health")
def health_check():
    return {"status": "ok"}

# --- Professors ---
@app.get("/professors")
def list_professors():
    professors = database.get_all_professors()
    return [
        {
            "id": prof[0],
            "first_name": prof[1],
            "last_name": prof[2],
            "subject": prof[3],
            "created_at": prof[4],
        }
        for prof in professors
    ]

@app.post("/professors", status_code=201)
def create_professor(payload: ProfessorCreate):
    professor_id = database.add_professor(
        payload.first_name.strip(),
        payload.last_name.strip(),
        payload.subject.strip(),
    )
    if not professor_id:
        raise HTTPException(status_code=500, detail="Impossible de créer le professeur")
    return {"id": professor_id}

# --- Students ---
@app.get("/students")
def list_students():
    students = database.get_all_students()
    return [
        {
            "id": student[0],
            "first_name": student[1],
            "last_name": student[2],
            "photo_path": student[3],
        }
        for student in students
    ]

@app.post("/students/capture-webcam", status_code=201)
def capture_student_from_webcam(
    first_name: str = Form(...),
    last_name: str = Form(...)
):
    """Capture une photo depuis la webcam avec OpenCV (fenêtre native)"""
    try:
        print(f"📸 Ouverture de la webcam pour capturer {first_name} {last_name}...")
        
        # Ouvrir la webcam
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise HTTPException(status_code=500, detail="Impossible d'accéder à la webcam")
        
        print("✓ Webcam ouverte - Appuyez sur ESPACE pour capturer, ESC pour annuler")
        
        captured_frame = None
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Détecter les visages en temps réel
            faces = detector.detect_faces_in_frame(frame, return_all_faces=True)
            
            # Dessiner les rectangles
            display = frame.copy()
            for face in faces:
                top, right, bottom, left = face["location"]
                color = (0, 255, 0) if len(faces) == 1 else (0, 0, 255)
                cv2.rectangle(display, (left, top), (right, bottom), color, 2)
            
            # Instructions
            cv2.putText(display, f"Capture: {first_name} {last_name}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(display, "ESPACE = Capturer | ESC = Annuler", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(display, f"Visages detectes: {len(faces)}", (10, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
            cv2.imshow("Capture Etudiant", display)
            
            key = cv2.waitKey(1) & 0xFF
            
            # ESPACE pour capturer
            if key == 32:  # Touche ESPACE
                if len(faces) == 1:
                    captured_frame = frame.copy()
                    print("✓ Photo capturée!")
                    break
                else:
                    print(f"⚠️ {len(faces)} visage(s) détecté(s) - Un seul requis")
            
            # ESC pour annuler
            elif key == 27:  # Touche ESC
                cap.release()
                cv2.destroyAllWindows()
                raise HTTPException(status_code=400, detail="Capture annulée par l'utilisateur")
        
        cap.release()
        cv2.destroyAllWindows()
        
        if captured_frame is None:
            raise HTTPException(status_code=400, detail="Aucune image capturée")
        
        # Traiter l'image capturée
        faces = detector.detect_faces_in_frame(captured_frame, return_all_faces=False)
        
        if not faces or len(faces) == 0:
            raise HTTPException(status_code=400, detail="Aucun visage détecté dans l'image capturée")
        
        if len(faces) > 1:
            raise HTTPException(status_code=400, detail=f"{len(faces)} visages détectés. Un seul requis.")
        
        # Extraire l'encodage
        face = faces[0]
        top, right, bottom, left = face["location"]
        face_image = captured_frame[top:bottom, left:right]
        
        encoding = detector._extract_face_encoding(face_image)
        if encoding is None:
            raise HTTPException(status_code=500, detail="Erreur extraction encodage")
        
        # Sauvegarder la photo
        save_dir = "students_photos"
        os.makedirs(save_dir, exist_ok=True)
        filename = f"{first_name.strip()}_{last_name.strip()}.jpg"
        photo_path = os.path.join(save_dir, filename)
        cv2.imwrite(photo_path, captured_frame)
        
        # Ajouter à la base
        student_id = database.add_student(
            first_name.strip(),
            last_name.strip(),
            photo_path,
            encoding.tolist(),
        )
        
        detector.load_encodings_from_database(database)
        
        return {
            "id": student_id,
            "photo_path": photo_path,
            "encoding_dimensions": len(encoding),
            "message": f"Étudiant {first_name} {last_name} ajouté avec succès (webcam)"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Erreur capture webcam: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")


@app.post("/students", status_code=201)
def create_student(
    file: UploadFile = File(...),
    first_name: str = Form(...),
    last_name: str = Form(...)
):
    """Crée un nouvel étudiant avec détection OpenCV (sans dlib)"""
    try:
        print(f"\n{'='*70}")
        print(f"📥 RÉCEPTION REQUÊTE ÉTUDIANT")
        print(f"{'='*70}")
        print(f"   Prénom: '{first_name}'")
        print(f"   Nom: '{last_name}'")
        print(f"   Fichier: {file.filename}")
        print(f"   Content-Type: {file.content_type}")
        
        # Lire l'image envoyée
        contents = file.file.read()
        print(f"   Taille fichier: {len(contents)} bytes")
        
        nparr = np.frombuffer(contents, np.uint8)
        print(f"   NumPy array: shape={nparr.shape}, dtype={nparr.dtype}")
        
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            print("❌ ERREUR: Impossible de décoder l'image")
            raise HTTPException(status_code=400, detail="Impossible de lire l'image")
        
        print(f"✅ Image décodée: shape={frame.shape}, dtype={frame.dtype}")
        print(f"   Dimensions: {frame.shape[1]}x{frame.shape[0]} pixels")

        # Sauvegarder une copie pour debug (optionnel)
        debug_dir = "debug_captures"
        os.makedirs(debug_dir, exist_ok=True)
        debug_path = os.path.join(debug_dir, f"debug_{first_name}_{last_name}.jpg")
        cv2.imwrite(debug_path, frame)
        print(f"🔍 Debug: Image sauvegardée dans {debug_path}")

        # Détecter les visages avec OpenCV
        print(f"\n🔍 DÉTECTION DES VISAGES...")
        faces = detector.detect_faces_in_frame(frame, return_all_faces=True)
        print(f"   Visages détectés: {len(faces)}")
        
        if len(faces) > 0:
            for i, face in enumerate(faces):
                print(f"   Visage {i+1}: location={face['location']}, confidence={face.get('confidence', 'N/A')}")
        
        if not faces or len(faces) == 0:
            print("❌ ERREUR: Aucun visage détecté")
            print("💡 SUGGESTIONS:")
            print("   - Vérifiez l'éclairage de la photo")
            print("   - Assurez-vous que le visage est face à la caméra")
            print("   - Essayez de vous rapprocher de la caméra")
            print(f"   - Consultez l'image debug: {debug_path}")
            raise HTTPException(
                status_code=400, 
                detail="Aucun visage détecté dans l'image. Assurez-vous que le visage est bien visible et éclairé."
            )
        
        if len(faces) > 1:
            print(f"⚠️ ATTENTION: {len(faces)} visages détectés (1 seul requis)")
            raise HTTPException(
                status_code=400,
                detail=f"{len(faces)} visages détectés. Une seule personne doit être visible dans l'image."
            )
        
        # Extraire l'encodage du visage détecté
        print(f"\n🧬 EXTRACTION DE L'ENCODAGE...")
        face = faces[0]
        top, right, bottom, left = face["location"]
        print(f"   Région du visage: top={top}, right={right}, bottom={bottom}, left={left}")
        
        face_image = frame[top:bottom, left:right]
        print(f"   Taille région: {face_image.shape}")
        
        if face_image.size == 0:
            print("❌ ERREUR: Région de visage vide")
            raise HTTPException(status_code=400, detail="Région de visage invalide")
        
        # Générer l'encodage avec OpenCV
        encoding = detector._extract_face_encoding(face_image)
        
        if encoding is None:
            print("❌ ERREUR: Impossible d'extraire l'encodage")
            raise HTTPException(
                status_code=500,
                detail="Erreur lors de l'extraction des caractéristiques du visage"
            )
        
        print(f"✅ Encodage extrait: {len(encoding)} dimensions")

        # Sauvegarder la photo
        print(f"\n💾 SAUVEGARDE...")
        save_dir = "students_photos"
        os.makedirs(save_dir, exist_ok=True)
        filename = f"{first_name.strip()}_{last_name.strip()}.jpg"
        photo_path = os.path.join(save_dir, filename)
        cv2.imwrite(photo_path, frame)
        print(f"   Photo sauvegardée: {photo_path}")

        # Ajouter l'étudiant à la base
        print(f"\n💿 AJOUT À LA BASE DE DONNÉES...")
        student_id = database.add_student(
            first_name.strip(),
            last_name.strip(),
            photo_path,
            encoding.tolist(),
        )
        print(f"✅ Étudiant créé avec ID: {student_id}")

        # Recharger les encodages
        detector.load_encodings_from_database(database)
        
        print(f"{'='*70}")
        print(f"✅ SUCCÈS: {first_name} {last_name} ajouté")
        print(f"{'='*70}\n")
        
        return {
            "id": student_id, 
            "photo_path": photo_path,
            "encoding_dimensions": len(encoding),
            "message": f"Étudiant {first_name} {last_name} ajouté avec succès"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n❌ EXCEPTION CAPTURÉE: {type(e).__name__}")
        print(f"   Message: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")
# BONUS: Endpoint de validation de photo
@app.post("/students/validate-photo")
def validate_student_photo(file: UploadFile = File(...)):
    """Valide qu'une photo contient un seul visage détectable"""
    try:
        contents = file.file.read()
        nparr = np.frombuffer(contents, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return {
                "valid": False,
                "message": "Image invalide ou corrompue"
            }
        
        faces = detector.detect_faces_in_frame(frame, return_all_faces=True)
        
        if len(faces) == 0:
            return {
                "valid": False,
                "message": "Aucun visage détecté. Assurez-vous que votre visage est bien visible et éclairé.",
                "faces_count": 0
            }
        
        if len(faces) > 1:
            return {
                "valid": False,
                "message": f"{len(faces)} visages détectés. Une seule personne doit être visible.",
                "faces_count": len(faces)
            }
        
        # Visage unique détecté
        face = faces[0]
        return {
            "valid": True,
            "message": "Photo valide - un visage détecté",
            "faces_count": 1,
            "face_location": {
                "top": face["location"][0],
                "right": face["location"][1],
                "bottom": face["location"][2],
                "left": face["location"][3]
            }
        }
    
    except Exception as e:
        return {
            "valid": False,
            "message": f"Erreur de validation: {str(e)}"
        }


# --- Sessions ---
@app.post("/sessions/start")
def start_session(request: SessionRequest):
    professors = database.get_all_professors()
    professor = next((p for p in professors if p[0] == request.professor_id), None)
    if professor is None:
        raise HTTPException(status_code=404, detail="Professeur introuvable")

    # Vérifier qu'il y a des étudiants
    students = database.get_all_students()
    if not students:
        raise HTTPException(status_code=400, detail="Aucun étudiant enregistré")

    # Charger les encodages
    detector.load_encodings_from_database(database)
    if len(detector.known_encodings) == 0:
        raise HTTPException(status_code=400, detail="Aucun encodage disponible")

    subject = request.subject.strip() if request.subject else professor[3]
    session_id = database.create_session(request.professor_id, subject)
    if not session_id:
        raise HTTPException(status_code=500, detail="Impossible de créer la séance")

    # Démarrer la session de présence dans un thread (webcam s'ouvre automatiquement)
    detector.start_attendance_session(database, session_id)

    return {"session_id": session_id, "subject": subject, "professor": f"{professor[1]} {professor[2]}"}

@app.post("/sessions/{session_id}/detect")
def detect_faces(session_id: int, file: UploadFile = File(...)):
    """Détecte les visages dans une image uploadée"""
    # Lire l'image
    np_img = np.frombuffer(file.file.read(), np.uint8)
    frame = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    
    if frame is None:
        raise HTTPException(status_code=400, detail="Image invalide")
    
    detected_faces = detector.detect_faces_in_frame(frame, return_all_faces=True)
    
    # Formater les résultats
    results = []
    for face in detected_faces:
        results.append({
            "student_id": face["student"].get("id", -1),
            "student_name": face["student"].get("name", "Inconnu"),
            "confidence": face.get("confidence", 0),
            "location": face["location"]
        })
    
    return {
        "detected_faces": results,
        "count": len(detected_faces)
    }


# --- Reports ---
@app.get("/sessions/{session_id}/stats")
def get_session_stats(session_id: int):
    stats = database.get_session_stats(session_id)
    return {"session_id": session_id, "stats": stats}


from fastapi.responses import FileResponse

@app.get("/sessions/{session_id}/report")
def download_report(session_id: int):
    try:
        # Ici on récupère le nom complet du fichier généré par la fonction
        filename = database.export_attendance_to_csv(session_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not os.path.exists(filename):
        raise HTTPException(status_code=404, detail="Report not found")

    return FileResponse(
        path=os.path.abspath(filename),
        media_type="text/csv",
        filename=os.path.basename(filename),  # navigateur utilisera ce nom
    )


 # Ajoutez ces endpoints à votre fichier api.py

# --- DELETE Endpoints ---

@app.delete("/students/{student_id}")
def delete_student(student_id: int):
    """Supprime un étudiant et sa photo"""
    success = database.delete_student(student_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Étudiant {student_id} introuvable")
    
    # Recharger les encodages dans le détecteur
    detector.load_encodings_from_database(database)
    
    return {
        "message": f"Étudiant {student_id} supprimé avec succès",
        "remaining_students": len(database.get_all_students())
    }

@app.delete("/professors/{professor_id}")
def delete_professor(professor_id: int):
    """Supprime un professeur"""
    success = database.delete_professor(professor_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Professeur {professor_id} introuvable")
    
    return {
        "message": f"Professeur {professor_id} supprimé avec succès",
        "remaining_professors": len(database.get_all_professors())
    }

# BONUS: Endpoint pour nettoyer les étudiants sans photo
@app.post("/students/cleanup")
def cleanup_students():
    """Supprime les étudiants dont la photo n'existe plus"""
    students = database.get_all_students()
    deleted = []
    
    for student in students:
        student_id, first_name, last_name, photo_path = student
        
        # Vérifier si la photo existe
        if photo_path and not os.path.exists(photo_path):
            if database.delete_student(student_id):
                deleted.append({
                    "id": student_id,
                    "name": f"{first_name} {last_name}",
                    "missing_photo": photo_path
                })
    
    # Recharger les encodages
    if deleted:
        detector.load_encodings_from_database(database)
    
    return {
        "cleaned": len(deleted),
        "deleted_students": deleted,
        "message": f"{len(deleted)} étudiant(s) nettoyé(s)"
    }



@app.get("/sessions/{session_id}/attendance")
def get_session_attendance(session_id: int):
    """Récupère la liste des présences pour une séance"""
    conn = sqlite3.connect(database.db_name)
    c = conn.cursor()
    
    try:
        c.execute('''
            SELECT student_id, check_in_time, status
            FROM attendance
            WHERE session_id = ?
            ORDER BY check_in_time
        ''', (session_id,))
        
        results = c.fetchall()
        
        attendance = [
            {
                "student_id": row[0],
                "check_in_time": row[1],
                "status": row[2]
            }
            for row in results
        ]
        
        return {"session_id": session_id, "attendance": attendance}
    finally:
        conn.close()