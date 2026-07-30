import cv2
import numpy as np
import time
from scipy.signal import butter, filtfilt
import mediapipe as mp  # The normal, unbroken import

# --- DSP PARAMETERS ---
BUFFER_SECONDS = 10 

mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# Dropped CAP_DSHOW and dropped to 720p to guarantee CPU loop speed & zero frame buffer lag
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_FPS, 30)

window_name = 'rPPG - Jitter Corrected Engine'
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.resizeWindow(window_name, 1280, 720)

timestamps = []
rgb_buffer = []
bpm_history = []
stable_bpm = 0.0

def butter_bandpass(data, lowcut=0.8, highcut=2.5, fs=30.0):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(3, [low, high], btype='band')
    return filtfilt(b, a, data)

def extract_roi_mean(frame, landmarks, indices, w, h):
    mask = np.zeros((h, w), dtype=np.uint8)
    points = np.array([[(int(landmarks[i].x * w), int(landmarks[i].y * h)) for i in indices]])
    cv2.fillPoly(mask, points, 255)
    mean_color = cv2.mean(frame, mask=mask)[:3]
    return [mean_color[2], mean_color[1], mean_color[0]]

FOREHEAD_INDICES = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323]
CHEEK_LEFT = [118, 119, 100, 126, 209, 49, 129, 103, 54, 68]
CHEEK_RIGHT = [347, 348, 329, 355, 429, 279, 358, 332, 284, 298]

print("Engine starting. Enforcing time-series interpolation...")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
        
    current_time = time.time()
    h, w, _ = frame.shape
    
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb_frame)

    if results.multi_face_landmarks:
        landmarks = results.multi_face_landmarks[0].landmark
        
        fh_rgb = extract_roi_mean(frame, landmarks, FOREHEAD_INDICES, w, h)
        cl_rgb = extract_roi_mean(frame, landmarks, CHEEK_LEFT, w, h)
        cr_rgb = extract_roi_mean(frame, landmarks, CHEEK_RIGHT, w, h)
        
        master_rgb = np.mean([fh_rgb, cl_rgb, cr_rgb], axis=0)
        
        timestamps.append(current_time)
        rgb_buffer.append(master_rgb)

        if len(timestamps) > 1:
            time_span = timestamps[-1] - timestamps[0]
            actual_fps = (len(timestamps) - 1) / time_span if time_span > 0 else 30.0
        else:
            actual_fps = 30.0

        target_size = int(actual_fps * BUFFER_SECONDS)

        if len(rgb_buffer) > target_size:
            timestamps.pop(0)
            rgb_buffer.pop(0)

        if len(rgb_buffer) >= target_size and actual_fps > 15:
            rgb_arr = np.array(rgb_buffer)
            
            # --- CHROM MATH ---
            mean_c = np.mean(rgb_arr, axis=0)
            norm_rgb = rgb_arr / (mean_c + 1e-6)
            
            X = 3 * norm_rgb[:, 0] - 2 * norm_rgb[:, 1]
            Y = 1.5 * norm_rgb[:, 0] + norm_rgb[:, 1] - 1.5 * norm_rgb[:, 2]
            
            # --- THE FIX: TIME SERIES INTERPOLATION ---
            time_arr = np.array(timestamps)
            uniform_time = np.linspace(time_arr[0], time_arr[-1], len(time_arr))
            
            X_interp = np.interp(uniform_time, time_arr, X)
            Y_interp = np.interp(uniform_time, time_arr, Y)
            
            X_f = butter_bandpass(X_interp, fs=actual_fps)
            Y_f = butter_bandpass(Y_interp, fs=actual_fps)
            
            alpha = np.std(X_f) / (np.std(Y_f) + 1e-6)
            chrom_signal = X_f - alpha * Y_f
            
            windowed_signal = chrom_signal * np.hanning(len(chrom_signal))
            fft_size = len(windowed_signal) * 4
            fft_data = np.abs(np.fft.rfft(windowed_signal, n=fft_size))
            freqs = np.fft.rfftfreq(fft_size, 1.0 / actual_fps)

            valid_idx = np.where((freqs >= 0.8) & (freqs <= 2.5))[0]

            if len(valid_idx) > 0:
                peak_idx = valid_idx[np.argmax(fft_data[valid_idx])]
                raw_bpm = freqs[peak_idx] * 60.0

                bpm_history.append(raw_bpm)
                if len(bpm_history) > 15:
                    bpm_history.pop(0)
                stable_bpm = np.median(bpm_history)

        for idx in FOREHEAD_INDICES + CHEEK_LEFT + CHEEK_RIGHT:
            cx, cy = int(landmarks[idx].x * w), int(landmarks[idx].y * h)
            cv2.circle(frame, (cx, cy), 1, (0, 255, 0), -1)

        progress = min(100, int((len(rgb_buffer) / target_size) * 100)) if target_size > 0 else 0

        if progress < 100:
            text = f"CALIBRATING: {progress}% (FPS: {actual_fps:.1f})"
            color = (0, 165, 255)
        else:
            text = f"HEART RATE: {stable_bpm:.0f} BPM"
            color = (0, 255, 0)

        cv2.putText(frame, text, (30, 50), cv2.FONT_HERSHEY_DUPLEX, 1.0, color, 2)

    cv2.imshow(window_name, frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
