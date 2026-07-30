
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, UploadFile, File
# pyrefly: ignore [missing-import]
from fastapi.responses import JSONResponse
# pyrefly: ignore [missing-import]
import cv2
# pyrefly: ignore [missing-import]
import numpy as np
import math
# pyrefly: ignore [missing-import]
from scipy.signal import butter, filtfilt
# pyrefly: ignore [missing-import]
import mediapipe as mp
import tempfile
import os

app = FastAPI(title="OMNI-PULSE API")

# --- PARAMETERS & MODELS ---
has_age_net = False
try:
    age_net = cv2.dnn.readNetFromCaffe("age_deploy.prototxt", "age_net.caffemodel")
    AGE_CLASSES = ['[0-2]', '[4-6]', '[8-12]', '[15-20]', '[25-32]', '[38-43]', '[48-53]', '[60+]']
    has_age_net = True
except:
    pass

class KalmanFilter1D:
    def __init__(self, process_variance=1e-2, measurement_variance=0.1):
        self.estimated_bpm = 0.0
        self.error_covariance = 1.0
        self.q = process_variance  
        self.r = measurement_variance 

    def update(self, measurement):
        if self.estimated_bpm == 0.0:
            self.estimated_bpm = measurement
            return self.estimated_bpm
        prediction = self.estimated_bpm
        error_cov_pred = self.error_covariance + self.q
        kalman_gain = error_cov_pred / (error_cov_pred + self.r)
        self.estimated_bpm = prediction + kalman_gain * (measurement - prediction)
        self.error_covariance = (1 - kalman_gain) * error_cov_pred
        return self.estimated_bpm

def butter_bandpass(data, lowcut=0.8, highcut=3.0, fs=30.0):
    if len(data) <= 22: return data
    nyq = 0.5 * fs
    safe_highcut = min(highcut, nyq - 0.05)
    if lowcut >= safe_highcut: return data 
    b, a = butter(3, [lowcut / nyq, safe_highcut / nyq], btype='band')
    return filtfilt(b, a, data)

def extract_roi_mean(frame, landmarks, indices, w, h):
    mask = np.zeros((h, w), dtype=np.uint8)
    points = np.array([[(int(landmarks[i].x * w), int(landmarks[i].y * h)) for i in indices]])
    cv2.fillPoly(mask, points, 255)
    mean_c = cv2.mean(frame, mask=mask)[:3]
    return [mean_c[2], mean_c[1], mean_c[0]]

# --- API ENDPOINT ---
@app.post("/process-vitals")
async def process_vitals(video: UploadFile = File(...)):
    # 1. Save uploaded mobile video to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video:
        temp_video.write(await video.read())
        temp_video_path = temp_video.name

    # 2. Initialize Headless Processing
    cap = cv2.VideoCapture(temp_video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    
    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(max_num_faces=1, refine_landmarks=False)
    bpm_kalman = KalmanFilter1D()

    timestamps, rgb_buffer, brow_ratio_buffer = [], [], []
    FOREHEAD = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323]
    CHEEK_LEFT = [118, 119, 100, 126, 209, 49, 129, 103, 54, 68]
    CHEEK_RIGHT = [347, 348, 329, 355, 429, 279, 358, 332, 284, 298]
    BROW_INNER_L, BROW_INNER_R = 107, 336
    FACE_LEFT, FACE_RIGHT = 234, 454

    final_bpm = 0.0
    final_stress = 0
    final_age = "[18-25] (Demo)"
    frame_count = 0
    baseline_brow_ratio = 0.0

    # 3. Frame Processing Loop (No UI, just math)
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        
        h, w, _ = frame.shape
        frame_count += 1
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb_frame)

        if results.multi_face_landmarks:
            landmarks = results.multi_face_landmarks[0].landmark
            
            # Stress Math
            brow_dist = math.dist((landmarks[BROW_INNER_L].x * w, landmarks[BROW_INNER_L].y * h),
                                  (landmarks[BROW_INNER_R].x * w, landmarks[BROW_INNER_R].y * h))
            face_width = math.dist((landmarks[FACE_LEFT].x * w, landmarks[FACE_LEFT].y * h),
                                   (landmarks[FACE_RIGHT].x * w, landmarks[FACE_RIGHT].y * h))
            current_brow_ratio = brow_dist / max(1.0, face_width)
            
            if frame_count < 30:
                brow_ratio_buffer.append(current_brow_ratio)
                baseline_brow_ratio = np.mean(brow_ratio_buffer)
            else:
                strain = (baseline_brow_ratio - current_brow_ratio) / max(0.001, baseline_brow_ratio)
                raw_stress = max(0, min(100, strain * 400))
                final_stress = int(0.8 * final_stress + 0.2 * raw_stress)

            # POS Engine Math
            fh_rgb = extract_roi_mean(frame, landmarks, FOREHEAD, w, h)
            cl_rgb = extract_roi_mean(frame, landmarks, CHEEK_LEFT, w, h)
            cr_rgb = extract_roi_mean(frame, landmarks, CHEEK_RIGHT, w, h)
            
            timestamps.append(frame_count / fps)
            rgb_buffer.append(np.mean([fh_rgb, cl_rgb, cr_rgb], axis=0))

            # Age Net Math
            if has_age_net and frame_count == int(fps * 2):
                x_coords, y_coords = [int(l.x * w) for l in landmarks], [int(l.y * h) for l in landmarks]
                min_y, max_y = max(0, min(y_coords)), min(h, max(y_coords))
                min_x, max_x = max(0, min(x_coords)), min(w, max(x_coords))
                face_roi = frame[min_y:max_y, min_x:max_x]
                if face_roi.size > 0:
                    blob = cv2.dnn.blobFromImage(face_roi, 1.0, (227, 227), (78.4, 87.7, 114.8), swapRB=False)
                    age_net.setInput(blob)
                    final_age = AGE_CLASSES[age_net.forward()[0].argmax()]

    # 4. Final FFT Calculation over the entire buffered video clip
    if len(rgb_buffer) > 30:
        rgb_arr = np.array(rgb_buffer)
        norm_rgb = rgb_arr / (np.mean(rgb_arr, axis=0) + 1e-6)
        X, Y = norm_rgb[:, 1] - norm_rgb[:, 2], norm_rgb[:, 1] + norm_rgb[:, 2] - 2 * norm_rgb[:, 0]
        
        X_f = butter_bandpass(X, fs=fps)
        Y_f = butter_bandpass(Y, fs=fps)
        pos_signal = X_f + (np.std(X_f) / (np.std(Y_f) + 1e-6)) * Y_f
        
        windowed = pos_signal * np.hanning(len(pos_signal))
        fft_data = np.abs(np.fft.rfft(windowed, n=len(windowed)*4))
        freqs = np.fft.rfftfreq(len(windowed)*4, 1.0 / fps)
        
        valid = np.where((freqs >= 0.8) & (freqs <= 3.0))[0]
        if len(valid) > 0:
            final_bpm = bpm_kalman.update(freqs[valid[np.argmax(fft_data[valid])]] * 60.0)

    # 5. Cleanup & Return
    cap.release()
    os.remove(temp_video_path)

    return JSONResponse(content={
        "bpm": round(final_bpm, 1),
        "stress_load": final_stress,
        "demographic": final_age,
        "status": "Elevated" if final_bpm > 90 else "Normal"
    })

if __name__ == "__main__":
    # pyrefly: ignore [missing-import]
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)