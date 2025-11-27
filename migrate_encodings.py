"""
Script de migration : Ré-encode tous les étudiants avec le nouveau système OpenCV
À exécuter UNE SEULE FOIS après le changement de système
"""

import cv2
import numpy as np
import os
import sys
import pickle
import sqlite3
from face_detector import FaceDetector

class EncodingMigrator:
    def __init__(self, db_name='attendance_system.db'):
        self.db_name = db_name
        self.detector = FaceDetector()
    
    def get_all_students(self):
        """Récupère tous les étudiants de la base"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT id, first_name, last_name, photo_path FROM students')
        students = c.fetchall()
        conn.close()
        
        return [
            {
                'id': row[0],
                'first_name': row[1],
                'last_name': row[2],
                'photo_path': row[3],
                'name': f"{row[1]} {row[2]}"
            }
            for row in students
        ]
    
    def update_student_encoding(self, student_id, encoding):
        """Met à jour l'encodage d'un étudiant"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        try:
            encoding_blob = pickle.dumps(encoding)
            c.execute('UPDATE students SET encoding = ? WHERE id = ?', 
                     (encoding_blob, student_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"   Erreur DB: {e}")
            return False
        finally:
            conn.close()
    
    def get_encoding_info(self):
        """Récupère les infos sur les encodages existants"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT id, first_name, last_name, encoding FROM students WHERE encoding IS NOT NULL')
        results = c.fetchall()
        conn.close()
        
        encodings_info = []
        for student_id, first_name, last_name, encoding_blob in results:
            if encoding_blob:
                try:
                    encoding = pickle.loads(encoding_blob)
                    encoding_array = np.array(encoding)
                    encodings_info.append({
                        'id': student_id,
                        'name': f"{first_name} {last_name}",
                        'dimensions': len(encoding_array),
                        'type': 'face_recognition (dlib)' if len(encoding_array) == 128 else 'OpenCV'
                    })
                except:
                    encodings_info.append({
                        'id': student_id,
                        'name': f"{first_name} {last_name}",
                        'dimensions': 'Erreur',
                        'type': 'Corrompu'
                    })
        
        return encodings_info
    
    def migrate_all(self, debug_mode=False):
        """Ré-encode tous les étudiants"""
        print("=" * 70)
        print(" MIGRATION DES ENCODAGES : face_recognition → OpenCV ".center(70))
        print("=" * 70)
        
        students = self.get_all_students()
        
        if not students:
            print("\n✗ Aucun étudiant trouvé dans la base")
            return
        
        print(f"\n📋 {len(students)} étudiant(s) à traiter\n")
        if debug_mode:
            print("🔍 MODE DEBUG ACTIVÉ - Les images avec détection seront affichées\n")
        
        success_count = 0
        fail_count = 0
        no_photo_count = 0
        
        for student in students:
            student_id = student['id']
            student_name = student['name']
            photo_path = student['photo_path']
            
            # Vérifier si une photo existe
            if not photo_path:
                print(f"⚠️ {student_name} (ID: {student_id}) - Aucun chemin photo en DB")
                no_photo_count += 1
                continue
            
            # Chemins possibles pour l'image (relatifs et absolus)
            possible_paths = [
                photo_path,
                os.path.join('static', photo_path) if not photo_path.startswith('static') else photo_path,
                os.path.join('uploads', photo_path),
                photo_path.replace('\\', '/'),
            ]
            
            image = None
            found_path = None
            
            # Trouver l'image
            for path in possible_paths:
                if os.path.exists(path):
                    image = cv2.imread(path)
                    if image is not None:
                        found_path = path
                        break
            
            if image is None:
                print(f"✗ {student_name} (ID: {student_id}) - Image introuvable: {photo_path}")
                fail_count += 1
                continue
            
            if debug_mode:
                print(f"\n🔍 DEBUG - {student_name}:")
                print(f"   Chemin: {found_path}")
                print(f"   Dimensions: {image.shape}")
            
            # ESSAYER PLUSIEURS MÉTHODES DE DÉTECTION
            faces = []
            
            # Méthode 1: Haar Cascade standard
            faces = self.detector.detect_faces_in_frame(image, return_all_faces=False)
            
            # Méthode 2: Si échec, essayer avec paramètres moins stricts
            if not faces:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                detected = self.detector.face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.05,  # Plus sensible
                    minNeighbors=3,     # Moins strict
                    minSize=(20, 20)    # Visages plus petits
                )
                
                if len(detected) > 0:
                    # Convertir au format attendu
                    for (x, y, w, h) in detected:
                        faces.append({
                            "location": (y, x + w, y + h, x),
                            "student": {"id": -1}
                        })
            
            # Méthode 3: Si toujours échec, utiliser toute l'image comme visage
            if not faces and debug_mode:
                print(f"   ⚠️ Aucun visage détecté avec Haar Cascade")
                print(f"   💡 Essai: utiliser l'image entière comme visage")
                h, w = image.shape[:2]
                faces = [{
                    "location": (0, w, h, 0),
                    "student": {"id": -1}
                }]
            
            if not faces:
                print(f"⚠️ {student_name} (ID: {student_id}) - Aucun visage détecté")
                if debug_mode:
                    # Afficher l'image pour diagnostic
                    display = image.copy()
                    cv2.putText(display, "Aucun visage detecte", (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    cv2.imshow(f"DEBUG - {student_name}", display)
                    cv2.waitKey(0)
                    cv2.destroyAllWindows()
                fail_count += 1
                continue
            
            if len(faces) > 1:
                print(f"⚠️ {student_name} (ID: {student_id}) - Plusieurs visages ({len(faces)}), utilisation du premier")
            
            # Extraire l'encodage du premier visage
            face = faces[0]
            t, r, b, l = face["location"]
            
            if debug_mode:
                print(f"   ✓ Visage détecté à: top={t}, right={r}, bottom={b}, left={l}")
                # Afficher l'image avec le rectangle
                display = image.copy()
                cv2.rectangle(display, (l, t), (r, b), (0, 255, 0), 2)
                cv2.putText(display, student_name, (l, t-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                cv2.imshow(f"DEBUG - {student_name}", display)
                print(f"   Appuyez sur une touche pour continuer...")
                cv2.waitKey(0)
                cv2.destroyAllWindows()
            
            face_image = image[t:b, l:r]
            
            if face_image.size == 0:
                print(f"✗ {student_name} (ID: {student_id}) - Région de visage vide")
                fail_count += 1
                continue
            
            encoding = self.detector._extract_face_encoding(face_image)
            
            if encoding is None:
                print(f"✗ {student_name} (ID: {student_id}) - Erreur extraction encodage")
                fail_count += 1
                continue
            
            # Sauvegarder le nouvel encodage
            if self.update_student_encoding(student_id, encoding.tolist()):
                print(f"✓ {student_name} (ID: {student_id}) - Encodage mis à jour ({len(encoding)}D)")
                success_count += 1
            else:
                print(f"✗ {student_name} (ID: {student_id}) - Erreur sauvegarde DB")
                fail_count += 1
        
        # Résumé
        print("\n" + "=" * 70)
        print(" RÉSUMÉ DE LA MIGRATION ".center(70))
        print("=" * 70)
        print(f"✓ Succès        : {success_count}/{len(students)}")
        print(f"✗ Échecs        : {fail_count}/{len(students)}")
        print(f"⚠ Sans photo    : {no_photo_count}/{len(students)}")
        print("\n💡 Vous pouvez maintenant utiliser le système de présence!")
    
    def verify_encodings(self):
        """Vérifie le format de tous les encodages"""
        encodings_info = self.get_encoding_info()
        
        if not encodings_info:
            print("\n⚠️ Aucun encodage trouvé dans la base de données")
            return
        
        print(f"\n📊 Vérification de {len(encodings_info)} encodage(s):\n")
        print(f"{'ID':<5} {'Nom':<30} {'Dimensions':<12} {'Type':<25}")
        print("-" * 75)
        
        opencv_count = 0
        old_count = 0
        error_count = 0
        
        for info in encodings_info:
            status = "✓" if info['dimensions'] == 512 else "✗"
            print(f"{status} {info['id']:<3} {info['name']:<30} {str(info['dimensions']):<12} {info['type']:<25}")
            
            if info['dimensions'] == 512:
                opencv_count += 1
            elif info['dimensions'] == 128:
                old_count += 1
            else:
                error_count += 1
        
        print("\n" + "-" * 75)
        print(f"OpenCV (512D)      : {opencv_count}")
        print(f"Ancien format (128D): {old_count}")
        print(f"Erreurs/Corrompus  : {error_count}")
        
        if old_count > 0:
            print("\n⚠️ ATTENTION: Des encodages au format face_recognition (128D) sont encore présents!")
            print("   Exécutez la migration pour les mettre à jour.")


def main():
    print("\n" + "=" * 70)
    print(" 🔄 SCRIPT DE MIGRATION DES ENCODAGES ".center(70))
    print("=" * 70)
    print("\nCe script va ré-encoder tous les étudiants avec le nouveau système OpenCV.")
    print("Les anciens encodages face_recognition (128D) seront remplacés")
    print("par des encodages OpenCV (512D).\n")
    
    # Vérifier que la DB existe
    db_name = 'attendance_system.db'
    if not os.path.exists(db_name):
        print(f"✗ Base de données '{db_name}' introuvable!")
        print("  Assurez-vous d'être dans le bon répertoire.")
        return
    
    migrator = EncodingMigrator(db_name)
    
    # Menu
    while True:
        print("\n" + "=" * 70)
        print("MENU:")
        print("  1. Vérifier les encodages actuels")
        print("  2. Migrer tous les encodages (mode normal)")
        print("  3. Migrer avec mode DEBUG (voir les détections)")
        print("  4. Quitter")
        print("=" * 70)
        
        choice = input("\nVotre choix (1-4): ").strip()
        
        if choice == '1':
            migrator.verify_encodings()
        
        elif choice == '2':
            confirm = input("\n⚠️ Êtes-vous sûr de vouloir migrer tous les encodages? (o/n): ").lower()
            if confirm == 'o':
                migrator.migrate_all(debug_mode=False)
                print("\n" + "=" * 70)
                migrator.verify_encodings()
            else:
                print("\n❌ Migration annulée")
        
        elif choice == '3':
            confirm = input("\n⚠️ Migrer en mode DEBUG (affiche chaque image)? (o/n): ").lower()
            if confirm == 'o':
                migrator.migrate_all(debug_mode=True)
                print("\n" + "=" * 70)
                migrator.verify_encodings()
            else:
                print("\n❌ Migration annulée")
        
        elif choice == '4':
            print("\n👋 Au revoir!")
            break
        
        else:
            print("\n✗ Choix invalide, veuillez réessayer")


if __name__ == "__main__":
    main()