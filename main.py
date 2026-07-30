import cv2
import numpy as np
import time
import math
from scipy.signal import butter, filtfilt
import mediapipe as mp

# --- 1. PARAMETERS ---
INITIAL_BUFFER_SECONDS = 10  
ACTIVE_BUFFER_SECONDS = 5    
UI_REFRESH_SECONDS = 4.0     
MOTION_THRESHOLD = 8.0
GRAPH_HISTORY_SIZE = 120 

# --- 2. AGE DETECTION MODEL SETUP (OPENCV DNN) ---
try:
    age_net = cv2.dnn.readNetFromCaffe("age_deploy.prototxt", "age_net.caffemodel")
    AGE_CLASSES = ['[0-2]', '[4-6]', '[8-12]', '[15-20]', '[25-32]', '[38-43]', '[48-53]', '[60+]']
    has_age_net = True
    print("[SYSTEM] Age DNN Module Loaded Successfully.")
except Exception as e:
    has_age_net = False
    print(f"[WARNING] Age weights missing. Error: {e}")

# --- 3. KALMAN FILTER ---
class KalmanFilter1D:
    # Lower q (assume biological HR changes slowly), higher r (distrust the noisy optical sensor)
    def __init__(self, process_variance=1e-4, measurement_variance=2.0):
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

bpm_kalman = KalmanFilter1D()
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(max_num_faces=1, refine_landmarks=False, min_detection_confidence=0.5, min_tracking_confidence=0.5)

# --- THE BACKGROUND ERASER ---
mp_selfie_segmentation = mp.solutions.selfie_segmentation
segmenter = mp_selfie_segmentation.SelfieSegmentation(model_selection=1)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_FPS, 30)
cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0) 

window_name = 'Omni-Pulse Biometric Intelligence HUD'
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.resizeWindow(window_name, 1280, 720)

# --- ENGINE STATE VARIABLES ---
timestamps, rgb_buffer, wave_history = [], [], []
prev_nose_pos = None

snr_margin, motion_magnitude, ambient_brightness = 0.0, 0.0, 0.0
diagnostic_reason = "ACQUIRING..."

# UI Display Locks
current_live_bpm, display_bpm, display_margin = 0.0, 0.0, 0.0
display_reason = "CALIBRATING..."
last_ui_update = 0.0

# Cognitive Stress State
baseline_brow_ratio = 0.0
brow_ratio_buffer = []
current_stress_score = 0
display_age_bracket = "[18-25] (Demo)"

# Landmarks
FOREHEAD = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323]
CHEEK_LEFT = [118, 119, 100, 126, 209, 49, 129, 103, 54, 68]
CHEEK_RIGHT = [347, 348, 329, 355, 429, 279, 358, 332, 284, 298]
BROW_INNER_L, BROW_INNER_R = 107, 336
FACE_LEFT, FACE_RIGHT = 234, 454

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

def draw_face_anchored_graph(frame, wave_data, gx, gy, gw, gh, accuracy):
    if gw < 150 or gh < 50: return
    overlay = frame.copy()
    cv2.rectangle(overlay, (gx, gy), (gx + gw, gy + gh), (10, 10, 12), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
    
    border_color = (0, 255, 0) if accuracy >= 75 else ((0, 255, 255) if accuracy >= 50 else (0, 0, 255))
    cv2.rectangle(frame, (gx, gy), (gx + gw, gy + gh), border_color, 3)
    cv2.line(frame, (gx, gy + gh // 2), (gx + gw, gy + gh // 2), (80, 80, 80), 1)
    cv2.putText(frame, "LIVE POS OPTICAL WAVEFORM", (gx + 12, gy + 24), cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1)

    if len(wave_data) < 2: return
    wave_arr = np.array(wave_data)
    ptp = np.ptp(wave_arr)
    if ptp < 1e-5: return
        
    norm_wave = (wave_arr - np.min(wave_arr)) / ptp
    points = []
    step = gw / max(1, GRAPH_HISTORY_SIZE - 1)
    for i in range(len(norm_wave)):
        px = int(gx + i * step)
        py = int(gy + gh - (norm_wave[i] * (gh - 35) + 10))
        points.append((px, py))

    line_color = (0, 255, 127) if accuracy >= 60 else (0, 165, 255)
    for i in range(1, len(points)):
        cv2.line(frame, points[i - 1], points[i], line_color, 3)

frame_count = 0
condition = None 

while cap.isOpened():
    ret, frame = cap.read()
    if not ret: break

    # ==================================================
    # OPTIMIZED GREEN SCREEN LOOP
    # ==================================================
    frame_count += 1
    
    if frame_count % 3 == 0 or condition is None:
        rgb_frame_for_seg = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        seg_results = segmenter.process(rgb_frame_for_seg)
        condition = np.stack((seg_results.segmentation_mask,) * 3, axis=-1) > 0.1
        
    black_bg = np.zeros(frame.shape, dtype=np.uint8)
    frame = np.where(condition, frame, black_bg)
    frame = np.ascontiguousarray(frame, dtype=np.uint8)
    # ==================================================
        
    current_time = time.time()
    h, w, _ = frame.shape
    
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb_frame)

    accuracy_score = 100
    progress = 0
    is_calibrated = False
    advice_text, advice_color = "OPTIMAL TRACKING", (0, 255, 0)
    
    if not results.multi_face_landmarks:
        timestamps.clear(); rgb_buffer.clear(); wave_history.clear(); brow_ratio_buffer.clear()
        prev_nose_pos = None; bpm_kalman.estimated_bpm = 0.0 
        current_live_bpm, display_bpm, baseline_brow_ratio = 0.0, 0.0, 0.0
        accuracy_score, advice_text, diagnostic_reason = 0, "NO FACE DETECTED", "TARGET LOST"
        advice_color = (0, 0, 255)
    else:
        landmarks = results.multi_face_landmarks[0].landmark
        
        # Bounding box mapping
        x_coords, y_coords = [int(l.x * w) for l in landmarks], [int(l.y * h) for l in landmarks]
        min_x, max_x = max(0, min(x_coords)), min(w, max(x_coords))
        min_y, max_y = max(0, min(y_coords)), min(h, max(y_coords))
        face_w, face_h = max_x - min_x, max_y - min_y
        
        # --- LAYER B: COGNITIVE STRESS (Facial Strain) ---
        brow_dist = math.dist((landmarks[BROW_INNER_L].x * w, landmarks[BROW_INNER_L].y * h),
                              (landmarks[BROW_INNER_R].x * w, landmarks[BROW_INNER_R].y * h))
        face_width = math.dist((landmarks[FACE_LEFT].x * w, landmarks[FACE_LEFT].y * h),
                               (landmarks[FACE_RIGHT].x * w, landmarks[FACE_RIGHT].y * h))
        
        current_brow_ratio = brow_dist / max(1.0, face_width)
        
        # --- Motion check & Freeze Fix (UPDATED FOR HIGH-RES CAMERAS) ---
        nose_x, nose_y = int(landmarks[4].x * w), int(landmarks[4].y * h)
        if prev_nose_pos is not None:
            motion_magnitude = math.dist((nose_x, nose_y), prev_nose_pos)
            
            # Dynamic thresholds: Scale allowed movement to 3% and 8% of the user's face width
            # This makes the math identical whether on a 480p potato cam or a 4K studio lens
            dynamic_warn_limit = face_w * 0.03 
            dynamic_reset_limit = face_w * 0.08 
            
            if motion_magnitude > dynamic_warn_limit:
                accuracy_score -= 30
                advice_text, advice_color = "HOLD STILL - HEAD MOVED", (0, 165, 255)
                # If motion clears the buffer, forcefully reset the UI
                if motion_magnitude > dynamic_reset_limit:
                    timestamps.clear(); rgb_buffer.clear(); wave_history.clear()
                    display_bpm = 0.0; current_stress_score = 0
        prev_nose_pos = (nose_x, nose_y)

        # --- LAYER A: CARDIOVASCULAR POS ENGINE ---
        fh_rgb = extract_roi_mean(frame, landmarks, FOREHEAD, w, h)
        cl_rgb = extract_roi_mean(frame, landmarks, CHEEK_LEFT, w, h)
        cr_rgb = extract_roi_mean(frame, landmarks, CHEEK_RIGHT, w, h)
        master_rgb = np.mean([fh_rgb, cl_rgb, cr_rgb], axis=0)
        ambient_brightness = np.mean(master_rgb)

        timestamps.append(current_time)
        rgb_buffer.append(master_rgb)

        actual_fps = (len(timestamps) - 1) / (timestamps[-1] - timestamps[0]) if len(timestamps) > 1 else 30.0
        is_calibrated = (len(timestamps) >= int(actual_fps * INITIAL_BUFFER_SECONDS))
        target_buffer_size = int(actual_fps * ACTIVE_BUFFER_SECONDS) if is_calibrated else int(actual_fps * INITIAL_BUFFER_SECONDS)

        if len(rgb_buffer) > target_buffer_size:
            timestamps.pop(0)
            rgb_buffer.pop(0)

        # Baseline logic for Stress Engine
        if not is_calibrated:
            brow_ratio_buffer.append(current_brow_ratio)
            baseline_brow_ratio = np.mean(brow_ratio_buffer)
            current_stress_score = 0
        else:
            strain = (baseline_brow_ratio - current_brow_ratio) / max(0.001, baseline_brow_ratio)
            raw_stress = max(0, min(100, strain * 400)) 
            current_stress_score = int(0.8 * current_stress_score + 0.2 * raw_stress)

        if len(rgb_buffer) > 22:
            rgb_arr = np.array(rgb_buffer)
            norm_rgb = rgb_arr / (np.mean(rgb_arr, axis=0) + 1e-6)
            
            X, Y = norm_rgb[:, 1] - norm_rgb[:, 2], norm_rgb[:, 1] + norm_rgb[:, 2] - 2 * norm_rgb[:, 0]    
            
            t_arr = np.array(timestamps)
            u_time = np.linspace(t_arr[0], t_arr[-1], len(t_arr))
            
            X_f = butter_bandpass(np.interp(u_time, t_arr, X), fs=actual_fps)
            Y_f = butter_bandpass(np.interp(u_time, t_arr, Y), fs=actual_fps)
            
            pos_signal = X_f + (np.std(X_f) / (np.std(Y_f) + 1e-6)) * Y_f
            
            wave_history.append(pos_signal[-1])
            if len(wave_history) > GRAPH_HISTORY_SIZE: wave_history.pop(0)

        progress = min(100, int((len(rgb_buffer) / target_buffer_size) * 100))

        if len(rgb_buffer) >= target_buffer_size and actual_fps > 8:
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
                
                if snr > 0.40: snr_margin = 1.0  
                elif snr > 0.25: snr_margin = 3.0 
                else: snr_margin = 6.0            
                
                if snr_margin > 2.0:
                    if motion_magnitude > 4.0: diagnostic_reason = "MICRO-MOTION ARTIFACTS"
                    elif ambient_brightness < 70 or ambient_brightness > 230: diagnostic_reason = "POOR LIGHTING CONDITIONS"
                    else: 
                        diagnostic_reason = "CAMERA AUTO-EXPOSURE SHIFTS"
                        bpm_kalman.r = 20.0 # HEAVY DAMPING: Ignore the noisy sensor almost entirely
                else:
                    diagnostic_reason = "CLEAN OPTICAL SIGNAL"
                    bpm_kalman.r = 3.0 # NORMAL DAMPING: Trust the sensor a bit more, but still smooth it

                current_live_bpm = bpm_kalman.update(raw_bpm)
                
                if current_time - last_ui_update >= UI_REFRESH_SECONDS or display_bpm == 0.0:
                    display_bpm = current_live_bpm
                    display_margin = snr_margin
                    display_reason = diagnostic_reason
                    last_ui_update = current_time

        # --- LAYER C: DEMOGRAPHICS (Age Detection) ---
        if has_age_net and is_calibrated and frame_count % 30 == 0:
            face_roi = frame[max(0, min_y):min(h, max_y), max(0, min_x):min(w, max_x)]
            if face_roi.size > 0:
                blob = cv2.dnn.blobFromImage(face_roi, 1.0, (227, 227), (78.4263377603, 87.7689143744, 114.895847746), swapRB=False)
                age_net.setInput(blob)
                age_preds = age_net.forward()
                display_age_bracket = AGE_CLASSES[age_preds[0].argmax()]

        # Rendering Graphics
        for idx in FOREHEAD + CHEEK_LEFT + CHEEK_RIGHT:
            cx, cy = int(landmarks[idx].x * w), int(landmarks[idx].y * h)
            cv2.circle(frame, (cx, cy), 1, (0, 255, 0), -1)

        graph_w, graph_h = max(320, face_w), 100
        graph_x, graph_y = max(15, min(w - graph_w - 15, min_x)), min(h - graph_h - 15, max_y + 20)
        draw_face_anchored_graph(frame, wave_history, graph_x, graph_y, graph_w, graph_h, accuracy_score)

    # --- TOP LEFT HUD (Cardiovascular & Diagnostics) ---
    acc_color = (0, 255, 0) if accuracy_score > 70 else (0, 165, 255)
    cv2.putText(frame, f"ACCURACY: {max(0, accuracy_score)}%", (30, 45), cv2.FONT_HERSHEY_DUPLEX, 1.0, acc_color, 2)
    cv2.putText(frame, f"ACTION: {advice_text}", (30, 80), cv2.FONT_HERSHEY_DUPLEX, 0.7, advice_color, 1)

    if display_bpm > 0:
        cv2.putText(frame, f"LIVE PULSE: {current_live_bpm:.0f} BPM", (30, 130), cv2.FONT_HERSHEY_DUPLEX, 0.9, (255, 255, 0), 2)
        cv2.putText(frame, f"4s AVERAGE: {display_bpm:.0f} BPM", (30, 175), cv2.FONT_HERSHEY_DUPLEX, 1.4, (0, 255, 0), 3)
        margin_color = (0, 255, 0) if display_margin <= 2.0 else (0, 165, 255)
        cv2.putText(frame, f"MARGIN: +/- {display_margin:.1f} BPM", (30, 220), cv2.FONT_HERSHEY_DUPLEX, 0.85, margin_color, 2)
        cv2.putText(frame, f"REASON: {display_reason}", (30, 255), cv2.FONT_HERSHEY_DUPLEX, 0.65, (200, 200, 200), 1)
    else:
        cv2.putText(frame, f"CALIBRATING BASELINE: {progress}%", (30, 135), cv2.FONT_HERSHEY_DUPLEX, 1.1, (0, 255, 255), 2)

    # --- TOP RIGHT HUD (Cognitive & Demographics Panel) ---
    panel_x = w - 450
    if is_calibrated:
        cv2.rectangle(frame, (panel_x, 15), (w - 15, 220), (15, 15, 15), -1)
        cv2.rectangle(frame, (panel_x, 15), (w - 15, 220), (100, 100, 100), 1)
        
        cv2.putText(frame, "DEMOGRAPHIC PROFILE", (panel_x + 15, 45), cv2.FONT_HERSHEY_DUPLEX, 0.6, (150, 150, 150), 1)
        cv2.putText(frame, f"AGE: {display_age_bracket}", (panel_x + 15, 85), cv2.FONT_HERSHEY_DUPLEX, 1.1, (255, 255, 255), 2)
        
        stress_text, stress_color = "NOMINAL", (0, 255, 0)
        if current_stress_score > 30: stress_text, stress_color = "ELEVATED", (0, 255, 255)
        if current_stress_score > 60: stress_text, stress_color = "HIGH STRAIN", (0, 0, 255)
        
        cv2.line(frame, (panel_x + 15, 110), (w - 30, 110), (80, 80, 80), 1)
        
        cv2.putText(frame, f"COGNITIVE LOAD: {current_stress_score}%", (panel_x + 15, 150), cv2.FONT_HERSHEY_DUPLEX, 0.85, (150, 150, 150), 2)
        cv2.putText(frame, stress_text, (panel_x + 15, 190), cv2.FONT_HERSHEY_DUPLEX, 0.9, stress_color, 2)
    cv2.putText(frame, f"REAL FPS: {actual_fps:.1f}", (30, 400), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 255, 255), 2)
    cv2.imshow(window_name, frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()