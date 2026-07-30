import cv2
import numpy as np
import time
import threading
from scipy.signal import butter, filtfilt
import mediapipe as mp

# Import your UI class
from UI import OmniPulseUI

# --- PARAMETERS ---
BUFFER_SECONDS = 10 
MOTION_THRESHOLD = 4.0
BPM_JUMP_LIMIT = 15.0
GRAPH_HISTORY_SIZE = 120 

def butter_bandpass(data, lowcut=0.8, highcut=2.5, fs=30.0):
    if len(data) <= 22:
        return data
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

def draw_face_anchored_graph(frame, wave_data, gx, gy, gw, gh, accuracy):
    if gw < 150 or gh < 50:
        return
    
    overlay = frame.copy()
    cv2.rectangle(overlay, (gx, gy), (gx + gw, gy + gh), (10, 10, 10), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
    
    border_color = (0, 255, 0) if accuracy >= 75 else ((0, 255, 255) if accuracy >= 50 else (0, 0, 255))
    cv2.rectangle(frame, (gx, gy), (gx + gw, gy + gh), border_color, 3)
    
    cv2.line(frame, (gx, gy + gh // 2), (gx + gw, gy + gh // 2), (80, 80, 80), 1)
    cv2.putText(frame, "LIVE PULSE WAVEFORM", (gx + 12, gy + 24), cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1)

    if len(wave_data) < 2:
        return

    wave_arr = np.array(wave_data)
    ptp = np.ptp(wave_arr)
    if ptp < 1e-5:
        return
        
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

FOREHEAD_INDICES = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323]
CHEEK_LEFT = [118, 119, 100, 126, 209, 49, 129, 103, 54, 68]
CHEEK_RIGHT = [347, 348, 329, 355, 429, 279, 358, 332, 284, 298]

# ======================================================================
# WRAP THE ENTIRE LOOP IN A FUNCTION SO WE CAN PASS 'APP' INTO IT
# ======================================================================
def dsp_engine_worker(app):
    print("Engine starting cleanly...")
    
    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=False,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    timestamps = []
    rgb_buffer = []
    bpm_history = []
    wave_history = []  
    stable_bpm = 0.0
    prev_nose_pos = None

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        current_time = time.time()
        h, w, _ = frame.shape
        
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb_frame)

        accuracy_score = 100
        advice_text = "OPTIMAL LIGHTING & POSITION"
        advice_color = (0, 255, 0)
        
        if not results.multi_face_landmarks:
            timestamps.clear()
            rgb_buffer.clear()
            wave_history.clear()
            prev_nose_pos = None
            accuracy_score = 0
            advice_text = "NO FACE DETECTED"
            advice_color = (0, 0, 255)
        else:
            landmarks = results.multi_face_landmarks[0].landmark
            
            x_coords = [int(l.x * w) for l in landmarks]
            y_coords = [int(l.y * h) for l in landmarks]
            min_x, max_x = max(0, min(x_coords)), min(w, max(x_coords))
            min_y, max_y = max(0, min(y_coords)), min(h, max(y_coords))
            face_w = max_x - min_x
            
            nose_x, nose_y = int(landmarks[4].x * w), int(landmarks[4].y * h)
            if prev_nose_pos is not None:
                movement = np.sqrt((nose_x - prev_nose_pos[0])**2 + (nose_y - prev_nose_pos[1])**2)
                if movement > MOTION_THRESHOLD:
                    timestamps.clear()
                    rgb_buffer.clear()
                    wave_history.clear()
                    accuracy_score -= 40
                    advice_text = "HOLD STILL - HEAD MOVED"
                    advice_color = (0, 165, 255)
            
            prev_nose_pos = (nose_x, nose_y)

            fh_rgb = extract_roi_mean(frame, landmarks, FOREHEAD_INDICES, w, h)
            cl_rgb = extract_roi_mean(frame, landmarks, CHEEK_LEFT, w, h)
            cr_rgb = extract_roi_mean(frame, landmarks, CHEEK_RIGHT, w, h)
            
            master_rgb = np.mean([fh_rgb, cl_rgb, cr_rgb], axis=0)
            
            brightness = np.mean(master_rgb)
            if brightness < 70:
                accuracy_score -= 30
                advice_text = "TOO DARK - INCREASE LIGHT"
                advice_color = (0, 165, 255)
            elif brightness > 220:
                accuracy_score -= 25
                advice_text = "TOO BRIGHT / OVEREXPOSED"
                advice_color = (0, 165, 255)

            fh_brightness = np.mean(fh_rgb)
            cheek_brightness = np.mean([cl_rgb, cr_rgb])
            if fh_brightness < cheek_brightness * 0.70:
                accuracy_score -= 20
                if advice_text == "OPTIMAL LIGHTING & POSITION":
                    advice_text = "CLEAR HAIR FROM FOREHEAD"
                    advice_color = (0, 255, 255)

            timestamps.append(current_time)
            rgb_buffer.append(master_rgb)

            actual_fps = (len(timestamps) - 1) / (timestamps[-1] - timestamps[0]) if len(timestamps) > 1 else 30.0
            target_size = int(actual_fps * BUFFER_SECONDS)

            if len(rgb_buffer) > target_size:
                timestamps.pop(0)
                rgb_buffer.pop(0)

            if len(rgb_buffer) > 22:
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
                
                wave_history.append(chrom_signal[-1])
                if len(wave_history) > GRAPH_HISTORY_SIZE:
                    wave_history.pop(0)

            progress = min(100, int((len(rgb_buffer) / target_size) * 100)) if target_size > 0 else 0

            if len(rgb_buffer) >= target_size and actual_fps > 15:
                windowed_signal = chrom_signal * np.hanning(len(chrom_signal))
                fft_size = len(windowed_signal) * 4
                fft_data = np.abs(np.fft.rfft(windowed_signal, n=fft_size))
                freqs = np.fft.rfftfreq(fft_size, 1.0 / actual_fps)

                valid_idx = np.where((freqs >= 0.8) & (freqs <= 2.5))[0]

                if len(valid_idx) > 0:
                    peak_idx = valid_idx[np.argmax(fft_data[valid_idx])]
                    raw_bpm = freqs[peak_idx] * 60.0

                    if stable_bpm == 0.0 or abs(raw_bpm - stable_bpm) < BPM_JUMP_LIMIT:
                        bpm_history.append(raw_bpm)
                        if len(bpm_history) > 10:
                            bpm_history.pop(0)
                        stable_bpm = np.median(bpm_history)

            for idx in FOREHEAD_INDICES + CHEEK_LEFT + CHEEK_RIGHT:
                cx, cy = int(landmarks[idx].x * w), int(landmarks[idx].y * h)
                cv2.circle(frame, (cx, cy), 2, (0, 255, 0), -1)

            graph_w = max(320, face_w)
            graph_h = 100
            graph_x = max(15, min(w - graph_w - 15, min_x))
            graph_y = min(h - graph_h - 15, max_y + 20)
            
            draw_face_anchored_graph(frame, wave_history, graph_x, graph_y, graph_w, graph_h, accuracy_score)

        # --- TELEMETRY PUSH TO UI ---
        progress_pct = progress / 100.0 if 'progress' in locals() else 0.0
        wave_point = chrom_signal[-1] if 'chrom_signal' in locals() else 0.0
        
        # We push the frame and the math directly to the app
        # ==========================================================
        # UI INTEGRATION BLOCK
        # ==========================================================
        progress_pct = progress / 100.0 if 'progress' in locals() else 0.0
        wave_point = chrom_signal[-1] if 'chrom_signal' in locals() else 0.0
        
        # Initialize the frame counter
        if 'frame_counter' not in locals():
            frame_counter = 0
        frame_counter += 1
        
        # Push the camera frame EVERY loop (30 FPS)
        app.after(0, app.update_camera, frame)
        
        # Push the heavy graph/text updates EVERY 3RD FRAME (10 FPS)
        if frame_counter % 3 == 0:
            app.after(0, app.update_state, stable_bpm, wave_point, progress_pct, accuracy_score, advice_text)
        # ==========================================================

    cap.release()


# ======================================================================
# THIS IS WHERE 'APP' IS DEFINED AND THE SCRIPT ACTUALLY STARTS
# ======================================================================
if __name__ == "__main__":
    # 1. Create the application (this defines 'app')
    app = OmniPulseUI()
    app.is_simulating = False
    
    # 2. Start the math engine in a background thread, passing 'app' to it
    engine = threading.Thread(target=dsp_engine_worker, args=(app,), daemon=True)
    engine.start()
    
    # 3. Run the visual UI on the main threadd
    app.mainloop()