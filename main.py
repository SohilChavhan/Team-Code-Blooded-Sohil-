import cv2
import numpy as np
import time
from scipy.signal import butter, filtfilt
import mediapipe as mp

# --- DSP PARAMETERS ---
BUFFER_SECONDS = 10 
MOTION_THRESHOLD = 5.0 # How many pixels the nose can move before recalibrating
BPM_JUMP_LIMIT = 15.0 # Max BPM change allowed per second (anti-spike)

mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# Using laptop webcam
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_FPS, 30)

window_name = 'Omni-Pulse Biometric Engine'
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.resizeWindow(window_name, 1280, 720)

timestamps = []
rgb_buffer = []
bpm_history = []
stable_bpm = 0.0
prev_nose_pos = None

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

print("Engine starting. Webcam initialized.")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
        
    current_time = time.time()
    h, w, _ = frame.shape
    
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb_frame)

    state = "SEARCHING"
    status_color = (0, 0, 255) # Red

    if not results.multi_face_landmarks:
        # State 0: No Face
        timestamps.clear()
        rgb_buffer.clear()
        prev_nose_pos = None
        state = "NO FACE DETECTED - STEP INTO FRAME"
    else:
        landmarks = results.multi_face_landmarks[0].landmark
        
        # Motion Detection (Track nose tip - landmark 4)
        nose_x, nose_y = int(landmarks[4].x * w), int(landmarks[4].y * h)
        
        if prev_nose_pos is not None:
            movement = np.sqrt((nose_x - prev_nose_pos[0])**2 + (nose_y - prev_nose_pos[1])**2)
            if movement > MOTION_THRESHOLD:
                # State 1: Motion Detected - Flush Buffers
                timestamps.clear()
                rgb_buffer.clear()
                state = "MOTION DETECTED - RECALIBRATING!"
                status_color = (0, 165, 255) # Orange
        
        prev_nose_pos = (nose_x, nose_y)

        # Only extract data if we aren't actively flushing the buffer
        if state != "MOTION DETECTED - RECALIBRATING!":
            fh_rgb = extract_roi_mean(frame, landmarks, FOREHEAD_INDICES, w, h)
            cl_rgb = extract_roi_mean(frame, landmarks, CHEEK_LEFT, w, h)
            cr_rgb = extract_roi_mean(frame, landmarks, CHEEK_RIGHT, w, h)
            
            master_rgb = np.mean([fh_rgb, cl_rgb, cr_rgb], axis=0)
            
            timestamps.append(current_time)
            rgb_buffer.append(master_rgb)

            actual_fps = (len(timestamps) - 1) / (timestamps[-1] - timestamps[0]) if len(timestamps) > 1 else 30.0
            target_size = int(actual_fps * BUFFER_SECONDS)

            # Limit buffer size safely
            if len(rgb_buffer) > target_size:
                timestamps.pop(0)
                rgb_buffer.pop(0)

            progress = min(100, int((len(rgb_buffer) / target_size) * 100)) if target_size > 0 else 0

            if len(rgb_buffer) < target_size:
                # State 2: Acquiring
                state = f"ACQUIRING SIGNAL - HOLD STILL ({progress}%)"
                status_color = (0, 255, 255) # Yellow
            else:
                # State 3: Locked and Calculating
                state = "LOCKED"
                status_color = (0, 255, 0) # Green

                rgb_arr = np.array(rgb_buffer)
                mean_c = np.mean(rgb_arr, axis=0)
                norm_rgb = rgb_arr / (mean_c + 1e-6)
                
                X = 3 * norm_rgb[:, 0] - 2 * norm_rgb[:, 1]
                Y = 1.5 * norm_rgb[:, 0] + norm_rgb[:, 1] - 1.5 * norm_rgb[:, 2]
                
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

                    # Anti-Spike Logic: Ignore physically impossible jumps
                    if stable_bpm == 0.0 or abs(raw_bpm - stable_bpm) < BPM_JUMP_LIMIT:
                        bpm_history.append(raw_bpm)
                        if len(bpm_history) > 10:
                            bpm_history.pop(0)
                        stable_bpm = np.median(bpm_history)

        # Draw UI
        if results.multi_face_landmarks:
            for idx in FOREHEAD_INDICES + CHEEK_LEFT + CHEEK_RIGHT:
                cx, cy = int(landmarks[idx].x * w), int(landmarks[idx].y * h)
                cv2.circle(frame, (cx, cy), 1, status_color, -1)

    # Main Status Text
    cv2.putText(frame, state, (30, 50), cv2.FONT_HERSHEY_DUPLEX, 0.8, status_color, 2)
    
    # BPM Text (Only show if we have a stable reading)
    if stable_bpm > 0:
        cv2.putText(frame, f"HEART RATE: {stable_bpm:.0f} BPM", (30, 100), cv2.FONT_HERSHEY_DUPLEX, 1.2, (0, 255, 0), 2)

    cv2.imshow(window_name, frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
