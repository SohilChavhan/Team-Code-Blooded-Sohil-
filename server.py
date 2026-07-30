import cv2
import numpy as np
import time
import math
import base64
from scipy.signal import butter, filtfilt
import mediapipe as mp
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- KALMAN FILTER ---
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

# --- RPPG ENGINE STATE MANAGER ---
class RPPGEngine:
    def __init__(self):
        # Parameters
        self.INITIAL_BUFFER_SECONDS = 10
        self.ACTIVE_BUFFER_SECONDS = 5
        self.UI_REFRESH_SECONDS = 4.0
        self.MOTION_THRESHOLD = 8.0
        
        # State
        self.timestamps = []
        self.rgb_buffer = []
        self.wave_history = []
        self.prev_nose_pos = None
        self.bpm_kalman = KalmanFilter1D()
        
        self.snr_margin = 0.0
        self.motion_magnitude = 0.0
        self.ambient_brightness = 0.0
        self.diagnostic_reason = "ACQUIRING..."
        
        self.current_live_bpm = 0.0
        self.display_bpm = 0.0
        self.display_margin = 0.0
        self.display_reason = "CALIBRATING..."
        self.last_ui_update = 0.0
        self.accuracy_score = 100
        
        # MP Mesh
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(max_num_faces=1, refine_landmarks=False, min_detection_confidence=0.5, min_tracking_confidence=0.5)

        # Landmarks
        self.FOREHEAD = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323]
        self.CHEEK_LEFT = [118, 119, 100, 126, 209, 49, 129, 103, 54, 68]
        self.CHEEK_RIGHT = [347, 348, 329, 355, 429, 279, 358, 332, 284, 298]

    def butter_bandpass(self, data, lowcut=0.8, highcut=3.0, fs=30.0):
        if len(data) <= 22: return data
        nyq = 0.5 * fs
        safe_highcut = min(highcut, nyq - 0.05)
        if lowcut >= safe_highcut: return data 
        b, a = butter(3, [lowcut / nyq, safe_highcut / nyq], btype='band')
        return filtfilt(b, a, data)

    def extract_roi_mean(self, frame, landmarks, indices, w, h):
        mask = np.zeros((h, w), dtype=np.uint8)
        points = np.array([[(int(landmarks[i].x * w), int(landmarks[i].y * h)) for i in indices]])
        cv2.fillPoly(mask, points, 255)
        mean_c = cv2.mean(frame, mask=mask)[:3]
        return [mean_c[2], mean_c[1], mean_c[0]]

    def process_frame(self, frame):
        current_time = time.time()
        h, w, _ = frame.shape
        
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb_frame)

        self.accuracy_score = 100
        progress = 0
        is_calibrated = False
        advice_text = "OPTIMAL TRACKING"
        
        if not results.multi_face_landmarks:
            self.timestamps.clear(); self.rgb_buffer.clear(); self.wave_history.clear()
            self.prev_nose_pos = None; self.bpm_kalman.estimated_bpm = 0.0 
            self.current_live_bpm, self.display_bpm = 0.0, 0.0
            self.accuracy_score, advice_text, self.diagnostic_reason = 0, "NO FACE DETECTED", "TARGET LOST"
            return {"bpm": 0, "accuracy": 0, "status": advice_text, "progress": 0}
            
        landmarks = results.multi_face_landmarks[0].landmark
        
        nose_x, nose_y = int(landmarks[4].x * w), int(landmarks[4].y * h)
        if self.prev_nose_pos is not None:
            self.motion_magnitude = math.dist((nose_x, nose_y), self.prev_nose_pos)
            if self.motion_magnitude > self.MOTION_THRESHOLD:
                self.accuracy_score -= 30
                advice_text = "HOLD STILL - HEAD MOVED"
                if self.motion_magnitude > 20.0:
                    self.timestamps.clear(); self.rgb_buffer.clear(); self.wave_history.clear()
                    self.display_bpm = 0.0
        self.prev_nose_pos = (nose_x, nose_y)

        fh_rgb = self.extract_roi_mean(frame, landmarks, self.FOREHEAD, w, h)
        cl_rgb = self.extract_roi_mean(frame, landmarks, self.CHEEK_LEFT, w, h)
        cr_rgb = self.extract_roi_mean(frame, landmarks, self.CHEEK_RIGHT, w, h)
        master_rgb = np.mean([fh_rgb, cl_rgb, cr_rgb], axis=0)
        self.ambient_brightness = np.mean(master_rgb)

        self.timestamps.append(current_time)
        self.rgb_buffer.append(master_rgb)

        actual_fps = (len(self.timestamps) - 1) / (self.timestamps[-1] - self.timestamps[0]) if len(self.timestamps) > 1 else 30.0
        is_calibrated = (len(self.timestamps) >= int(actual_fps * self.INITIAL_BUFFER_SECONDS))
        target_buffer_size = int(actual_fps * self.ACTIVE_BUFFER_SECONDS) if is_calibrated else int(actual_fps * self.INITIAL_BUFFER_SECONDS)

        if len(self.rgb_buffer) > target_buffer_size:
            self.timestamps.pop(0)
            self.rgb_buffer.pop(0)

        if len(self.rgb_buffer) > 22:
            rgb_arr = np.array(self.rgb_buffer)
            norm_rgb = rgb_arr / (np.mean(rgb_arr, axis=0) + 1e-6)
            
            X, Y = norm_rgb[:, 1] - norm_rgb[:, 2], norm_rgb[:, 1] + norm_rgb[:, 2] - 2 * norm_rgb[:, 0]    
            
            t_arr = np.array(self.timestamps)
            u_time = np.linspace(t_arr[0], t_arr[-1], len(t_arr))
            
            X_f = self.butter_bandpass(np.interp(u_time, t_arr, X), fs=actual_fps)
            Y_f = self.butter_bandpass(np.interp(u_time, t_arr, Y), fs=actual_fps)
            
            pos_signal = X_f + (np.std(X_f) / (np.std(Y_f) + 1e-6)) * Y_f
            self.wave_history.append(pos_signal[-1])

        progress = min(100, int((len(self.rgb_buffer) / target_buffer_size) * 100))

        if len(self.rgb_buffer) >= target_buffer_size and actual_fps > 15:
            windowed_signal = pos_signal * np.hanning(len(pos_signal))
            fft_size = len(windowed_signal) * 4
            fft_data = np.abs(np.fft.rfft(windowed_signal, n=fft_size))
            freqs = np.fft.rfftfreq(fft_size, 1.0 / actual_fps)

            valid_idx = np.where((freqs >= 0.8) & (freqs <= 3.0))[0] 

            if len(valid_idx) > 0:
                peak_idx = valid_idx[np.argmax(fft_data[valid_idx])]
                raw_bpm = freqs[peak_idx] * 60.0

                peak_power = np.sum(fft_data[max(0, peak_idx-2):peak_idx+3])
                total_power = np.sum(fft_data[valid_idx]) + 1e-6
                snr = peak_power / total_power 
                
                if snr > 0.40: self.snr_margin = 1.0  
                elif snr > 0.25: self.snr_margin = 3.0 
                else: self.snr_margin = 6.0            
                
                if self.snr_margin > 2.0:
                    if self.motion_magnitude > 4.0: self.diagnostic_reason = "MICRO-MOTION ARTIFACTS"
                    elif self.ambient_brightness < 70 or self.ambient_brightness > 230: self.diagnostic_reason = "POOR LIGHTING CONDITIONS"
                    else: self.diagnostic_reason = "CAMERA AUTO-EXPOSURE SHIFTS"; self.bpm_kalman.r = 0.5 
                else:
                    self.diagnostic_reason = "CLEAN OPTICAL SIGNAL"
                    self.bpm_kalman.r = 0.05 

                self.current_live_bpm = self.bpm_kalman.update(raw_bpm)
                
                if current_time - self.last_ui_update >= self.UI_REFRESH_SECONDS or self.display_bpm == 0.0:
                    self.display_bpm = self.current_live_bpm
                    self.display_margin = self.snr_margin
                    self.display_reason = self.diagnostic_reason
                    self.last_ui_update = current_time

        return {
            "bpm": int(self.display_bpm),
            "accuracy": max(0, self.accuracy_score),
            "status": advice_text,
            "progress": progress,
            "is_calibrated": is_calibrated,
            "diagnostic_reason": self.display_reason
        }


@app.websocket("/ws/rppg")
async def websocket_rppg(websocket: WebSocket):
    await websocket.accept()
    engine = RPPGEngine()
    
    try:
        while True:
            # Wait for text containing base64 image data
            data = await websocket.receive_text()
            try:
                # Remove header if present e.g. "data:image/jpeg;base64,"
                if "," in data:
                    data = data.split(",")[1]
                
                # Decode base64 to OpenCV frame
                img_data = base64.b64decode(data)
                np_arr = np.frombuffer(img_data, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                
                if frame is not None:
                    result = engine.process_frame(frame)
                    await websocket.send_json(result)
                else:
                    await websocket.send_json({"error": "Failed to decode frame"})
            except Exception as e:
                print(f"Error processing frame: {e}")
    except WebSocketDisconnect:
        print("Client disconnected from rPPG socket")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
