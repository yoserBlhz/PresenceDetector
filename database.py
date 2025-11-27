import sqlite3
from datetime import datetime
import pickle
import os
import csv

class AttendanceDatabase:
    def __init__(self, db_name='attendance_system.db'):
        self.db_name = db_name
        self.init_database()
    
    def init_database(self):
        """Initialise la base de données avec les tables nécessaires"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        # Table des professeurs
        c.execute('''CREATE TABLE IF NOT EXISTS professors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Table des étudiants
        c.execute('''CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            photo_path TEXT,
            encoding BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Table des séances
        c.execute('''CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            professor_id INTEGER,
            subject TEXT,
            session_date DATE,
            start_time TIME,
            end_time TIME,
            FOREIGN KEY (professor_id) REFERENCES professors(id)
        )''')
        
        # Table des présences
        c.execute('''CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            student_id INTEGER,
            check_in_time TIMESTAMP,
            status TEXT DEFAULT 'present',
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(session_id, student_id)
        )''')
        
        conn.commit()
        conn.close()
        print("✓ Base de données initialisée avec succès")
    

    # === GESTION PROFESSEURS ===
    def add_professor(self, first_name, last_name, subject):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        try:
            c.execute('''INSERT INTO professors (first_name, last_name, subject)
                        VALUES (?, ?, ?)''', (first_name, last_name, subject))
            conn.commit()
            return c.lastrowid
        except:
            return None
        finally:
            conn.close()
    
    def get_all_professors(self):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT * FROM professors ORDER BY last_name')
        data = c.fetchall()
        conn.close()
        return data

    def delete_professor(self, professor_id):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM professors WHERE id = ?', (professor_id,))
            conn.commit()
            print(f"✓ Professeur {professor_id} supprimé")
            return True
        except Exception as e:
            print(f"✗ Erreur suppression professeur: {e}")
            return False
        finally:
            conn.close()



    # === GESTION ÉTUDIANTS ===
    def add_student(self, first_name, last_name, photo_path=None, encoding=None):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        try:
            encoding_blob = pickle.dumps(encoding) if encoding is not None else None
            
            c.execute('''INSERT INTO students (first_name, last_name, photo_path, encoding)
                        VALUES (?, ?, ?, ?)''', 
                     (first_name, last_name, photo_path, encoding_blob))
            conn.commit()
            return c.lastrowid
        except:
            return None
        finally:
            conn.close()
    
    def get_all_students(self):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT id, first_name, last_name, photo_path FROM students ORDER BY last_name')
        data = c.fetchall()
        conn.close()
        return data
    

    def get_student_encodings(self):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT id, first_name, last_name, encoding FROM students WHERE encoding IS NOT NULL')
        results = c.fetchall()
        conn.close()
        
        encodings = []
        students_info = []
        
        for student_id, first_name, last_name, encoding_blob in results:
            if encoding_blob:
                encoding = pickle.loads(encoding_blob)
                encodings.append(encoding)
                students_info.append({
                    'id': student_id,
                    'name': f"{first_name} {last_name}",
                })
        
        return encodings, students_info
    

    # === 🔥 MÉTHODE CORRIGÉE : update_student_encoding ===
    def update_student_encoding(self, student_id, encoding):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        try:
            encoding_blob = pickle.dumps(encoding) if encoding is not None else None
            c.execute('UPDATE students SET encoding = ? WHERE id = ?', 
                     (encoding_blob, student_id))
            conn.commit()
            print(f"✓ Encodage mis à jour pour étudiant {student_id}")
            return True
        except Exception as e:
            print("Erreur:", e)
            return False
        finally:
            conn.close()
    

    # === 🔥 MÉTHODE CORRIGÉE : delete_student ===
    def delete_student(self, student_id):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()

        # récupérer photo avant suppression
        c.execute('SELECT photo_path FROM students WHERE id = ?', (student_id,))
        result = c.fetchone()

        if not result:
            conn.close()
            return False

        photo_path = result[0]

        # supprimer l'étudiant
        c.execute('DELETE FROM students WHERE id = ?', (student_id,))
        conn.commit()
        conn.close()

        # supprimer la photo
        if photo_path and os.path.exists(photo_path):
            os.remove(photo_path)

        print(f"✓ Étudiant {student_id} supprimé")
        return True
    

    # === GESTION SÉANCES / PRÉSENCES (inchangé) ===
    def create_session(self, professor_id, subject, session_date=None):
        if session_date is None:
            session_date = datetime.now().strftime('%Y-%m-%d')
        
        start_time = datetime.now().strftime('%H:%M:%S')
        
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('INSERT INTO sessions (professor_id, subject, session_date, start_time) VALUES (?, ?, ?, ?)',
                  (professor_id, subject, session_date, start_time))
        conn.commit()
        session_id = c.lastrowid
        conn.close()
        return session_id
    

    def end_session(self, session_id):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        end_time = datetime.now().strftime('%H:%M:%S')
        c.execute('UPDATE sessions SET end_time = ? WHERE id = ?', (end_time, session_id))
        conn.commit()
        conn.close()
    

    def mark_attendance(self, session_id, student_id):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()

        check_in = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            c.execute('INSERT OR IGNORE INTO attendance (session_id, student_id, check_in_time) VALUES (?, ?, ?)',
                      (session_id, student_id, check_in))
            conn.commit()
            return True
        except:
            return False
        finally:
            conn.close()
    

    def get_session_stats(self, session_id):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()

        c.execute('SELECT COUNT(*) FROM students')
        total = c.fetchone()[0]

        c.execute('SELECT COUNT(*) FROM attendance WHERE session_id = ?', (session_id,))
        present = c.fetchone()[0]

        conn.close()

        return {
            "total": total,
            "present": present,
            "absent": total - present,
            "percentage": (present / total * 100) if total else 0
        }



    def export_attendance_to_csv(self, session_id: int, reports_dir="reports"):
        os.makedirs(reports_dir, exist_ok=True)
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()

    # Récupérer le sujet et la date de la séance
        c.execute("SELECT subject, session_date FROM sessions WHERE id = ?", (session_id,))
        session = c.fetchone()
        if not session:
            conn.close()
            raise ValueError(f"Session {session_id} introuvable")
        subject, session_date = session

    # Récupérer tous les étudiants
        c.execute("SELECT id, first_name, last_name FROM students ORDER BY last_name")
        students = c.fetchall()

    # Récupérer les présences
        c.execute("SELECT student_id, check_in_time, status FROM attendance WHERE session_id = ?", (session_id,))
        attendance_records = c.fetchall()
        attendance_dict = {record[0]: {"check_in_time": record[1], "status": record[2]} for record in attendance_records}

    # Nom du fichier basé sur date + sujet + ID
        filename = os.path.join(reports_dir, f"{session_date}_{subject.replace(' ', '_')}_session{session_id}.csv")

    # Écrire le CSV
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Student ID", "First Name", "Last Name", "Check-in Time", "Status", "Session Name"])

            for student_id, first_name, last_name in students:
                record = attendance_dict.get(student_id, {})
                check_in_time = record.get("check_in_time", "")
                status = record.get("status", "absent")
                writer.writerow([student_id, first_name, last_name, check_in_time, status, subject])

        conn.close()
        print("CSV généré:", filename)

        return filename


    

