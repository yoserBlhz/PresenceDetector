# 🎓 Smart Attendance System

This project is an **Intelligent Attendance System** using **Facial Recognition** and **Computer Vision**.  
It allows professors to manage attendance for students and automatically records their presence during sessions.

---

## Features

- Add and manage professors and students.
- Capture student photos via webcam.
- Start and monitor attendance sessions.
- Generate attendance reports in CSV format.
- Real-time session statistics.

---

## Technologies

- **Frontend:** React, Vite, JavaScript
- **Backend:** FastAPI, Python 3.11
- **Database:** SQLite / PostgreSQL (depending on configuration)
- **Face Recognition & Computer Vision:** OpenCV / face_recognition (Python)
- **Other Tools:** Uvicorn (ASGI server), npm

---

## Installation

Follow these steps to set up the project locally.

### 1. Clone the repository


git clone <repository_url>
cd attendancyProject

### 2. Backend Setup (FastAPI)
# Create and activate a Python virtual environment:
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1

# Run the backend server:
uvicorn backend.api:app --reload

#### 3. Frontend Setup (React + Vite)
# Navigate to the frontend folder: 
cd ../frontend

# Install dependencies:
npm install

# Start the development server:
npm run dev

