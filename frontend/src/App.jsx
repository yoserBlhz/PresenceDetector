import { useEffect, useMemo, useState, useRef } from 'react'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const initialProfessor = { first_name: '', last_name: '', subject: '' }
const initialStudent = { first_name: '', last_name: '' }
const initialSession = { professor_id: '', subject: '' }

const PAGE_SIZE = 5

// Composant Popup de confirmation
function ConfirmDialog({ message, onConfirm, onCancel }) {
  return (
    <div className="modal-overlay">
      <div className="confirm-dialog">
        <div className="confirm-icon">⚠️</div>
        <h3>Confirmation requise</h3>
        <p>{message}</p>
        <div className="confirm-actions">
          <button onClick={onCancel} className="secondary">
            Annuler
          </button>
          <button onClick={onConfirm} className="danger">
            Confirmer
          </button>
        </div>
      </div>
    </div>
  )
}

// Composant Liste de présence
function AttendanceList({ sessionId, students, onClose }) {
  const [attendanceData, setAttendanceData] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchAttendance = async () => {
      try {
        const response = await fetch(`${API_URL}/sessions/${sessionId}/attendance`)
        if (response.ok) {
          const data = await response.json()
          setAttendanceData(data.attendance || [])
        }
      } catch (error) {
        console.error('Erreur chargement présences:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchAttendance()
  }, [sessionId])

  // Créer un Set des IDs présents
  const presentIds = new Set(attendanceData.map(a => a.student_id))

  // Créer la liste complète avec statut
  const fullList = students.map(student => ({
    ...student,
    status: presentIds.has(student.id) ? 'P' : 'A'
  }))

  const presentCount = fullList.filter(s => s.status === 'P').length
  const absentCount = fullList.length - presentCount

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="attendance-modal" onClick={(e) => e.stopPropagation()}>
        <div className="attendance-header">
          <h2>📋 Liste de présence - Séance #{sessionId}</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        <div className="attendance-summary">
          <div className="summary-card present">
            <div className="summary-label">Présents</div>
            <div className="summary-value">{presentCount}</div>
          </div>
          <div className="summary-card absent">
            <div className="summary-label">Absents</div>
            <div className="summary-value">{absentCount}</div>
          </div>
          <div className="summary-card total">
            <div className="summary-label">Total</div>
            <div className="summary-value">{fullList.length}</div>
          </div>
        </div>

        {loading ? (
          <p className="loading-text">Chargement...</p>
        ) : (
          <div className="attendance-list">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Nom complet</th>
                  <th>Statut</th>
                </tr>
              </thead>
              <tbody>
                {fullList.map((student) => (
                  <tr key={student.id} className={student.status === 'P' ? 'present-row' : 'absent-row'}>
                    <td><span className="badge">{student.id}</span></td>
                    <td>{student.first_name} {student.last_name}</td>
                    <td>
                      <span className={`status-badge ${student.status === 'P' ? 'present' : 'absent'}`}>
                        {student.status === 'P' ? '✓ Présent' : '✗ Absent'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="modal-actions">
          <button onClick={onClose} className="primary">
            Fermer
          </button>
        </div>
      </div>
    </div>
  )
}

function App() {
  const [activeTab, setActiveTab] = useState('professors')
  const [professors, setProfessors] = useState([])
  const [students, setStudents] = useState([])
  const [professorForm, setProfessorForm] = useState(initialProfessor)
  const [studentForm, setStudentForm] = useState(initialStudent)
  const [sessionForm, setSessionForm] = useState(initialSession)
  const [reportSessionId, setReportSessionId] = useState('')
  const [sessionResult, setSessionResult] = useState(null)
  const [feedback, setFeedback] = useState(null)
  const [loading, setLoading] = useState({
    professor: false,
    student: false,
    session: false,
    report: false,
  })

  const [profSearch, setProfSearch] = useState('')
  const [studSearch, setStudSearch] = useState('')
  const [profPage, setProfPage] = useState(1)
  const [studPage, setStudPage] = useState(1)

  const [showCaptureModal, setShowCaptureModal] = useState(false)
  const [captureStream, setCaptureStream] = useState(null)
  const videoRef = useRef(null)
  const canvasRef = useRef(null)

  // États pour les popups
  const [confirmDialog, setConfirmDialog] = useState(null)
  const [showAttendanceList, setShowAttendanceList] = useState(null)

  const selectedProfessor = useMemo(
    () => professors.find((prof) => prof.id === Number(sessionForm.professor_id || -1)),
    [professors, sessionForm.professor_id],
  )

  useEffect(() => {
    refreshData()
  }, [])

  useEffect(() => {
    return () => {
      if (captureStream) {
        captureStream.getTracks().forEach(track => track.stop())
      }
    }
  }, [captureStream])

  const extractErrorDetail = async (response, fallback) => {
    try {
      const data = await response.json()
      return data?.detail || fallback
    } catch {
      return fallback
    }
  }

  const refreshData = async () => {
    await Promise.all([fetchProfessors(), fetchStudents()])
  }

  const fetchProfessors = async () => {
    try {
      const response = await fetch(`${API_URL}/professors`)
      if (!response.ok) throw new Error('Impossible de charger les professeurs')
      const data = await response.json()
      setProfessors(data)
      setProfPage(1)
    } catch (error) {
      notify('error', error.message)
    }
  }

  const fetchStudents = async () => {
    try {
      const response = await fetch(`${API_URL}/students`)
      if (!response.ok) throw new Error('Impossible de charger les étudiants')
      const data = await response.json()
      setStudents(data)
      setStudPage(1)
    } catch (error) {
      notify('error', error.message)
    }
  }

  const notify = (type, message) => {
    setFeedback({ type, message })
    setTimeout(() => setFeedback(null), 5000)
  }

  const handleProfessorSubmit = async (event) => {
    event.preventDefault()
    setLoading((prev) => ({ ...prev, professor: true }))
    try {
      const response = await fetch(`${API_URL}/professors`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(professorForm),
      })
      if (!response.ok) {
        const detail = await extractErrorDetail(response, "Création du professeur impossible")
        throw new Error(detail)
      }
      await fetchProfessors()
      setProfessorForm(initialProfessor)
      notify('success', 'Professeur enregistré')
    } catch (error) {
      notify('error', error.message)
    } finally {
      setLoading((prev) => ({ ...prev, professor: false }))
    }
  }

  const openCaptureModal = async () => {
    if (!studentForm.first_name || !studentForm.last_name) {
      notify('error', 'Veuillez remplir le prénom et le nom avant de capturer')
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480 }
      })
      setCaptureStream(stream)
      setShowCaptureModal(true)

      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream
        }
      }, 100)
    } catch (error) {
      notify('error', 'Impossible d\'accéder à la webcam: ' + error.message)
    }
  }

  const closeCaptureModal = () => {
    if (captureStream) {
      captureStream.getTracks().forEach(track => track.stop())
      setCaptureStream(null)
    }
    setShowCaptureModal(false)
  }

  const captureAndSubmit = async () => {
    if (!videoRef.current || !canvasRef.current) return

    setLoading((prev) => ({ ...prev, student: true }))

    try {
      const canvas = canvasRef.current
      const video = videoRef.current

      if (!video.videoWidth || !video.videoHeight) {
        throw new Error('Vidéo non initialisée. Attendez quelques secondes.')
      }

      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      const ctx = canvas.getContext('2d')
      ctx.drawImage(video, 0, 0)

      const blob = await new Promise((resolve) => {
        canvas.toBlob(resolve, 'image/jpeg', 0.95)
      })

      if (!blob) {
        throw new Error('Erreur lors de la conversion de l\'image')
      }

      const formData = new FormData()
      formData.append('file', blob, 'photo.jpg')
      formData.append('first_name', studentForm.first_name.trim())
      formData.append('last_name', studentForm.last_name.trim())

      const response = await fetch(`${API_URL}/students`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorText = await response.text()
        let detail
        try {
          const errorData = JSON.parse(errorText)
          detail = errorData.detail || errorText
        } catch {
          detail = errorText || "Création de l'étudiant impossible"
        }
        throw new Error(detail)
      }

      await fetchStudents()
      setStudentForm(initialStudent)
      closeCaptureModal()
      notify('success', 'Étudiant enregistré avec succès')
    } catch (error) {
      notify('error', error.message)
    } finally {
      setLoading((prev) => ({ ...prev, student: false }))
    }
  }

  const handleSessionSubmit = async (event) => {
    event.preventDefault()
    if (!sessionForm.professor_id) {
      notify('error', 'Sélectionnez un professeur')
      return
    }
    setLoading((prev) => ({ ...prev, session: true }))
    setSessionResult(null)

    try {
      const payload = {
        professor_id: Number(sessionForm.professor_id),
        subject: sessionForm.subject || undefined,
      }

      const response = await fetch(`${API_URL}/sessions/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!response.ok) {
        const detail = await extractErrorDetail(response, 'Session impossible à démarrer')
        throw new Error(detail)
      }
      const data = await response.json()

      const statsRes = await fetch(`${API_URL}/sessions/${data.session_id}/stats`)
      const statsData = await statsRes.json()

      setSessionResult({ ...data, stats: statsData.stats })

      notify(
        'success',
        `Session ${data.session_id} lancée. La webcam est ouverte. Utilisez la touche Q pour terminer.`,
      )
    } catch (error) {
      notify('error', error.message)
    } finally {
      setLoading((prev) => ({ ...prev, session: false }))
    }
  }

  const refreshSessionStats = async (sessionId) => {
    try {
      const statsRes = await fetch(`${API_URL}/sessions/${sessionId}/stats`)
      const statsData = await statsRes.json()
      setSessionResult((prev) => ({ ...prev, stats: statsData.stats }))
    } catch (error) {
      notify('error', 'Impossible de rafraîchir les stats')
    }
  }

  // Terminer la séance et afficher la liste
  const endSessionAndShowList = () => {
    if (sessionResult) {
      setShowAttendanceList(sessionResult.session_id)
      setSessionResult(null)
    }
  }

  const handleReportDownload = async (event) => {
    event.preventDefault()
    if (!reportSessionId) {
      notify('error', 'Indiquez un ID de séance')
      return
    }
    setLoading((prev) => ({ ...prev, report: true }))
    try {
      const response = await fetch(`${API_URL}/sessions/${reportSessionId}/report`)
      if (!response.ok) {
        const detail = await extractErrorDetail(response, 'Rapport introuvable')
        throw new Error(detail)
      }
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `attendance_session_${reportSessionId}.csv`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
      notify('success', 'Rapport téléchargé')
    } catch (error) {
      notify('error', error.message)
    } finally {
      setLoading((prev) => ({ ...prev, report: false }))
    }
  }

  const deleteProfessor = (id) => {
    setConfirmDialog({
      message: `Voulez-vous vraiment supprimer le professeur #${id} ?`,
      onConfirm: async () => {
        setConfirmDialog(null)
        try {
          const res = await fetch(`${API_URL}/professors/${id}`, { method: 'DELETE' })
          if (!res.ok) {
            const detail = await extractErrorDetail(res, 'Suppression impossible')
            throw new Error(detail)
          }
          notify('success', `Professeur ${id} supprimé`)
          await fetchProfessors()
        } catch (err) {
          notify('error', err.message)
        }
      },
      onCancel: () => setConfirmDialog(null)
    })
  }

  const deleteStudent = (id) => {
    setConfirmDialog({
      message: `Voulez-vous vraiment supprimer l'étudiant #${id} ?`,
      onConfirm: async () => {
        setConfirmDialog(null)
        try {
          const res = await fetch(`${API_URL}/students/${id}`, { method: 'DELETE' })
          if (!res.ok) {
            const detail = await extractErrorDetail(res, 'Suppression impossible')
            throw new Error(detail)
          }
          notify('success', `Étudiant ${id} supprimé`)
          await fetchStudents()
        } catch (err) {
          notify('error', err.message)
        }
      },
      onCancel: () => setConfirmDialog(null)
    })
  }

  const filteredProfessors = useMemo(() => {
    const q = profSearch.trim().toLowerCase()
    if (!q) return professors
    return professors.filter(p =>
      `${p.first_name} ${p.last_name} ${p.subject}`.toLowerCase().includes(q)
    )
  }, [professors, profSearch])

  const filteredStudents = useMemo(() => {
    const q = studSearch.trim().toLowerCase()
    if (!q) return students
    return students.filter(s =>
      `${s.first_name} ${s.last_name}`.toLowerCase().includes(q)
    )
  }, [students, studSearch])

  const profTotalPages = Math.max(1, Math.ceil(filteredProfessors.length / PAGE_SIZE))
  const studTotalPages = Math.max(1, Math.ceil(filteredStudents.length / PAGE_SIZE))

  useEffect(() => { if (profPage > profTotalPages) setProfPage(1) }, [profTotalPages])
  useEffect(() => { if (studPage > studTotalPages) setStudPage(1) }, [studTotalPages])

  const profPageData = filteredProfessors.slice((profPage-1)*PAGE_SIZE, profPage*PAGE_SIZE)
  const studPageData = filteredStudents.slice((studPage-1)*PAGE_SIZE, studPage*PAGE_SIZE)

  return (
    <div className="app">
      <header className="header-panel">
        <div style={{ textAlign: 'left' }}>
          <h1>🎓 Système de Présence Intelligent</h1>
          <p className="subtitle">Reconnaissance faciale • Vision par ordinateur</p>
        </div>
        <button className="ghost" onClick={refreshData}>
          🔄 Actualiser
        </button>
      </header>

      {feedback && (
        <div className={`alert ${feedback.type}`}>{feedback.message}</div>
      )}

      {confirmDialog && (
        <ConfirmDialog
          message={confirmDialog.message}
          onConfirm={confirmDialog.onConfirm}
          onCancel={confirmDialog.onCancel}
        />
      )}

      {showAttendanceList && (
        <AttendanceList
          sessionId={showAttendanceList}
          students={students}
          onClose={() => setShowAttendanceList(null)}
        />
      )}

      <nav className="tabs">
        <button
          className={`tab ${activeTab === 'professors' ? 'active' : ''}`}
          onClick={() => setActiveTab('professors')}
        >
          👨‍🏫 Professeurs ({professors.length})
        </button>
        <button
          className={`tab ${activeTab === 'students' ? 'active' : ''}`}
          onClick={() => setActiveTab('students')}
        >
          👥 Étudiants ({students.length})
        </button>
        <button
          className={`tab ${activeTab === 'sessions' ? 'active' : ''}`}
          onClick={() => setActiveTab('sessions')}
        >
          📹 Séances
        </button>
        <button
          className={`tab ${activeTab === 'reports' ? 'active' : ''}`}
          onClick={() => setActiveTab('reports')}
        >
          📊 Rapports
        </button>
      </nav>

      {showCaptureModal && (
        <div className="modal-overlay" onClick={closeCaptureModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>📸 Capture photo - {studentForm.first_name} {studentForm.last_name}</h2>
            <div className="video-container">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                style={{ width: '100%', maxWidth: '640px', borderRadius: '8px' }}
              />
              <canvas ref={canvasRef} style={{ display: 'none' }} />
            </div>
            <div className="modal-actions">
              <button
                onClick={captureAndSubmit}
                disabled={loading.student}
                className="primary"
              >
                {loading.student ? 'Enregistrement...' : '📸 Capturer'}
              </button>
              <button onClick={closeCaptureModal} className="secondary">
                Annuler
              </button>
            </div>
          </div>
        </div>
      )}

      <main className="tab-content">
        {activeTab === 'professors' && (
          <div className="tab-panel">
            <div className="panel-grid">
              <div className="panel form-panel">
                <h2>➕ Ajouter un professeur</h2>
                <form onSubmit={handleProfessorSubmit} className="form">
                  <label>
                    Prénom
                    <input
                      required
                      value={professorForm.first_name}
                      onChange={(e) => setProfessorForm(prev => ({ ...prev, first_name: e.target.value }))}
                      placeholder="Ex: Jean"
                    />
                  </label>
                  <label>
                    Nom
                    <input
                      required
                      value={professorForm.last_name}
                      onChange={(e) => setProfessorForm(prev => ({ ...prev, last_name: e.target.value }))}
                      placeholder="Ex: Dupont"
                    />
                  </label>
                  <label>
                    Matière
                    <input
                      required
                      value={professorForm.subject}
                      onChange={(e) => setProfessorForm(prev => ({ ...prev, subject: e.target.value }))}
                      placeholder="Ex: Machine Learning"
                    />
                  </label>
                  <button type="submit" disabled={loading.professor} className="primary">
                    {loading.professor ? 'Enregistrement…' : '✓ Ajouter'}
                  </button>
                </form>
              </div>

              <div className="panel list-panel">
                <h2>📋 Liste des professeurs</h2>
                <input
                  className="search-input"
                  placeholder="Rechercher professeur..."
                  value={profSearch}
                  onChange={(e) => { setProfSearch(e.target.value); setProfPage(1) }}
                />
                {professors.length === 0 ? (
                  <p className="empty">Aucun professeur enregistré.</p>
                ) : (
                  <>
                    <div className="table-wrapper">
                      <table>
                        <thead>
                          <tr>
                            <th>ID</th>
                            <th>Nom complet</th>
                            <th>Matière</th>
                            <th></th>
                          </tr>
                        </thead>
                        <tbody>
                          {profPageData.map((prof) => (
                            <tr key={prof.id}>
                              <td><span className="badge">{prof.id}</span></td>
                              <td>{prof.first_name} {prof.last_name}</td>
                              <td><span className="subject-tag">{prof.subject}</span></td>
                              <td className="table-actions">
                                <button className="btn-delete" onClick={() => deleteProfessor(prof.id)}>Supprimer</button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {profTotalPages > 1 && (
                      <div className="pager">
                        <button onClick={() => setProfPage(p => Math.max(1, p-1))} disabled={profPage<=1}>Précédent</button>
                        <div>Page {profPage} / {profTotalPages}</div>
                        <button onClick={() => setProfPage(p => Math.min(profTotalPages, p+1))} disabled={profPage>=profTotalPages}>Suivant</button>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'students' && (
          <div className="tab-panel">
            <div className="panel-grid">
              <div className="panel form-panel">
                <h2>➕ Inscrire un étudiant</h2>
                <p className="hint">
                  💡 La webcam s'ouvrira pour capturer une photo du visage
                </p>
                <div className="form">
                  <label>
                    Prénom
                    <input
                      required
                      value={studentForm.first_name}
                      onChange={(e) => setStudentForm(prev => ({ ...prev, first_name: e.target.value }))}
                      placeholder="Ex: Marie"
                    />
                  </label>
                  <label>
                    Nom
                    <input
                      required
                      value={studentForm.last_name}
                      onChange={(e) => setStudentForm(prev => ({ ...prev, last_name: e.target.value }))}
                      placeholder="Ex: Martin"
                    />
                  </label>
                  <button
                    type="button"
                    onClick={openCaptureModal}
                    disabled={!studentForm.first_name || !studentForm.last_name}
                    className="primary"
                  >
                    📷 Capturer la photo
                  </button>
                </div>
              </div>

              <div className="panel list-panel">
                <h2>📋 Liste des étudiants</h2>
                <input
                  className="search-input"
                  placeholder="Rechercher étudiant..."
                  value={studSearch}
                  onChange={(e) => { setStudSearch(e.target.value); setStudPage(1) }}
                />
                {students.length === 0 ? (
                  <p className="empty">Aucun étudiant enregistré.</p>
                ) : (
                  <>
                    <div className="table-wrapper">
                      <table>
                        <thead>
                          <tr>
                            <th>ID</th>
                            <th>Nom complet</th>
                            <th>Photo</th>
                            <th></th>
                          </tr>
                        </thead>
                        <tbody>
                          {studPageData.map((student) => (
                            <tr key={student.id}>
                              <td><span className="badge">{student.id}</span></td>
                              <td>{student.first_name} {student.last_name}</td>
                              <td className="photo-cell">
                                {student.photo_path ? '✓ Enregistrée' : '—'}
                              </td>
                              <td className="table-actions">
                                <button className="btn-delete" onClick={() => deleteStudent(student.id)}>Supprimer</button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {studTotalPages > 1 && (
                      <div className="pager">
                        <button onClick={() => setStudPage(p => Math.max(1, p-1))} disabled={studPage<=1}>Précédent</button>
                        <div>Page {studPage} / {studTotalPages}</div>
                        <button onClick={() => setStudPage(p => Math.min(studTotalPages, p+1))} disabled={studPage>=studTotalPages}>Suivant</button>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'sessions' && (
          <div className="tab-panel">
            <div className="panel-grid">
              <div className="panel form-panel">
                <h2>▶️ Démarrer une séance</h2>
                <p className="hint">
                  💡 Une fenêtre webcam s'ouvrira automatiquement. Appuyez sur <strong>Q</strong> pour terminer.
                </p>
                <form onSubmit={handleSessionSubmit} className="form">
                  <label>
                    Professeur
                    <select
                      required
                      value={sessionForm.professor_id}
                      onChange={(e) => setSessionForm(prev => ({ ...prev, professor_id: e.target.value }))}
                    >
                      <option value="">Sélectionnez un professeur</option>
                      {professors.map((prof) => (
                        <option key={prof.id} value={prof.id}>
                          {prof.first_name} {prof.last_name} · {prof.subject}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Matière (optionnel)
                    <input
                      placeholder={selectedProfessor?.subject || 'Ex: Deep Learning'}
                      value={sessionForm.subject}
                      onChange={(e) => setSessionForm(prev => ({ ...prev, subject: e.target.value }))}
                    />
                  </label>
                  <button type="submit" disabled={loading.session} className="primary large">
                    {loading.session ? '⏳ Démarrage...' : '▶️ Lancer la séance'}
                  </button>
                </form>
              </div>

              {sessionResult && (
                <div className="panel stats-panel">
                  <h2>📊 Séance en cours</h2>
                  <div className="session-stats">
                    <div className="stat-card">
                      <div className="stat-label">Séance #</div>
                      <div className="stat-value">{sessionResult.session_id}</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-label">Présents</div>
                      <div className="stat-value success">
                        {sessionResult.stats.present} / {sessionResult.stats.total}
                      </div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-label">Taux</div>
                      <div className="stat-value">{sessionResult.stats.percentage.toFixed(1)}%</div>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => refreshSessionStats(sessionResult.session_id)}
                    className="secondary"
                    style={{ marginRight: '10px' }}
                  >
                    🔄 Actualiser
                  </button>
                  <button
                    type="button"
                    onClick={endSessionAndShowList}
                    className="danger"
                  >
                    ⏹️ Terminer et voir la liste
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'reports' && (
          <div className="tab-panel">
            <div className="panel form-panel centered">
              <h2>📥 Exporter un rapport</h2>
              <p className="hint">
                Téléchargez les données de présence d'une séance au format CSV
              </p>
              <form onSubmit={handleReportDownload} className="form">
                <label>
                  ID de la séance
                  <input
                    required
                    type="number"
                    min="1"
                    value={reportSessionId}
                    onChange={(e) => setReportSessionId(e.target.value)}
                    placeholder="Ex: 1"
                  />
                </label>
                <button type="submit" disabled={loading.report} className="primary large">
                  {loading.report ? '⏳ Génération...' : '📥 Télécharger le CSV'}
                </button>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

export default App