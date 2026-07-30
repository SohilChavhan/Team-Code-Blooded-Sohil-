import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from collections import deque
from PIL import Image, ImageTk
import cv2

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class OmniPulseUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("OMNI-PULSE | rPPG Biometric Engine")
        self.geometry("1200x700") 

        # 3-Column Layout
        self.grid_columnconfigure(0, weight=0) 
        self.grid_columnconfigure(1, weight=1) 
        self.grid_columnconfigure(2, weight=0) 
        self.grid_rowconfigure(0, weight=1)

        # --- DATA BUFFERS FOR WAVEFORM ---
        self.max_points = 100
        self.y_data = deque([0]*self.max_points, maxlen=self.max_points)
        self.x_data = np.linspace(0, self.max_points, self.max_points)

        self._build_left_sidebar()
        self._build_center_feed()
        self._build_right_sidebar()
        
        self.is_simulating = True
        self.after(100, self._check_simulation)

    def _check_simulation(self):
        if self.is_simulating:
            self.simulate_live_feed()

    def _build_left_sidebar(self):
        self.left_frame = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew")
        self.left_frame.grid_rowconfigure(4, weight=1)

        self.logo = ctk.CTkLabel(self.left_frame, text="OMNI-PULSE", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.status_label = ctk.CTkLabel(self.left_frame, text="STATUS: ACQUIRING", text_color="#F2C94C", font=ctk.CTkFont(size=14, weight="bold"))
        self.status_label.grid(row=1, column=0, padx=20, pady=10)

        self.calib_label = ctk.CTkLabel(self.left_frame, text="CALIBRATING: 0%", font=ctk.CTkFont(size=12))
        self.calib_label.grid(row=2, column=0, padx=20, pady=(20, 5), sticky="w")
        
        self.calib_progressbar = ctk.CTkProgressBar(self.left_frame)
        self.calib_progressbar.grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        self.calib_progressbar.set(0)

        specs = "ENGINE SPECS\n\n• MediaPipe 468-Mesh\n• CHROM Isolation\n• Butterworth (0.75-2.5Hz)\n• Time-Series Interp.\n• 4x Zero-Pad FFT\n• Dynamic Motion Comp."
        self.specs_label = ctk.CTkLabel(self.left_frame, text=specs, font=ctk.CTkFont(size=12), justify="left", text_color="gray")
        self.specs_label.grid(row=5, column=0, padx=20, pady=20, sticky="sw")

    def _build_center_feed(self):
        self.center_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.center_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.center_frame.grid_columnconfigure(0, weight=1)
        self.center_frame.grid_rowconfigure(0, weight=1)

        self.camera_label = ctk.CTkLabel(
            self.center_frame, 
            text="CAMERA FEED\n(Awaiting Video Signal)", 
            font=ctk.CTkFont(size=20, weight="bold"), 
            text_color="#4A4A4A",
            fg_color="#1A1A1A",
            corner_radius=10
        )
        self.camera_label.grid(row=0, column=0, sticky="nsew")

    def _build_right_sidebar(self):
        self.right_frame = ctk.CTkFrame(self, width=300, corner_radius=0)
        self.right_frame.grid(row=0, column=2, sticky="nsew")
        self.right_frame.grid_rowconfigure(3, weight=1)

        # BPM Display
        self.bpm_title = ctk.CTkLabel(self.right_frame, text="HEART RATE", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray")
        self.bpm_title.grid(row=0, column=0, padx=20, pady=(20, 0), sticky="w")
        
        self.bpm_value = ctk.CTkLabel(self.right_frame, text="-- BPM", font=ctk.CTkFont(size=48, weight="bold"), text_color="#FF4B4B")
        self.bpm_value.grid(row=1, column=0, padx=20, sticky="w")

        # Telemetry Display (Replacing Stress)
        self.accuracy_label = ctk.CTkLabel(self.right_frame, text="SIGNAL ACCURACY: 100%", font=ctk.CTkFont(size=12, weight="bold"))
        self.accuracy_label.grid(row=2, column=0, padx=20, pady=(15, 5), sticky="w")
        
        self.accuracy_progressbar = ctk.CTkProgressBar(self.right_frame, progress_color="#27AE60")
        self.accuracy_progressbar.grid(row=3, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.accuracy_progressbar.set(1.0)
        
        # Advice / Action Label
        self.advice_label = ctk.CTkLabel(self.right_frame, text="OPTIMAL LIGHTING & POSITION", font=ctk.CTkFont(size=11, weight="bold"), text_color="#27AE60", wraplength=260, justify="left")
        self.advice_label.grid(row=4, column=0, padx=20, pady=(0, 20), sticky="w")

        # Waveform Graph Setup
        self.fig, self.ax = plt.subplots(figsize=(3.5, 3), facecolor='#2B2B2B', dpi=100)
        self.fig.subplots_adjust(left=0.05, right=0.95, top=0.85, bottom=0.1) 
        self.ax.set_facecolor('#2B2B2B')
        self.ax.axis('off') 
        
        self.line, = self.ax.plot(self.x_data, self.y_data, color='#FF4B4B', linewidth=2)
        self.ax.set_ylim(-1.5, 1.5)
        self.ax.set_title("CHROMINANCE HISTORY", color="gray", fontsize=10)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.right_frame)
        self.canvas.get_tk_widget().grid(row=5, column=0, padx=10, pady=20, sticky="nsew")

    def update_camera(self, cv2_frame):
        rgb_image = cv2.cvtColor(cv2_frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_image)
        
        max_width = self.center_frame.winfo_width() - 20
        max_height = self.center_frame.winfo_height() - 20
        
        if max_width > 0 and max_height > 0:
            pil_image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
        ctk_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(pil_image.width, pil_image.height))
        self.camera_label.configure(image=ctk_image, text="")
        self.camera_label.image = ctk_image

    def update_state(self, bpm, wave_point, calib_pct, accuracy, advice_text):
        """API for main.py to push the new diagnostic data."""
        self.bpm_value.configure(text=f"{int(bpm)} BPM" if bpm > 0 else "-- BPM")
        self.calib_progressbar.set(calib_pct)
        self.calib_label.configure(text=f"CALIBRATING: {int(calib_pct * 100)}%")

        if calib_pct >= 1.0:
            self.status_label.configure(text="STATUS: LOCKED", text_color="#27AE60")
        else:
            self.status_label.configure(text="STATUS: ACQUIRING", text_color="#F2C94C")
        
        # Drive the Accuracy bar and Advice colors dynamically
        self.accuracy_label.configure(text=f"SIGNAL ACCURACY: {max(0, int(accuracy))}%")
        self.accuracy_progressbar.set(max(0, accuracy) / 100.0)
        self.advice_label.configure(text=advice_text)

        if accuracy >= 75:
            self.accuracy_progressbar.configure(progress_color="#27AE60")
            self.advice_label.configure(text_color="#27AE60")
        elif accuracy >= 50:
            self.accuracy_progressbar.configure(progress_color="#F2C94C")
            self.advice_label.configure(text_color="#F2C94C")
        else:
            self.accuracy_progressbar.configure(progress_color="#E74C3C")
            self.advice_label.configure(text_color="#E74C3C")

        # Update Scrolling Waveform
        self.y_data.append(wave_point)
        self.line.set_ydata(self.y_data)
        self.ax.draw_artist(self.ax.patch)
        self.ax.draw_artist(self.line)
        self.canvas.copy_from_bbox(self.ax.bbox)
        self.canvas.flush_events()

    def simulate_live_feed(self, frame=0):
        if not self.is_simulating:
            return
            
        t = frame * 0.1
        bpm = 72 + np.sin(t * 0.5) * 5
        wave = np.sin(t * (bpm / 60) * 2 * np.pi) + np.random.normal(0, 0.1)
        
        # Fake a head movement error every 100 frames for testing
        acc = 100 if frame % 100 < 80 else 40
        adv = "OPTIMAL LIGHTING & POSITION" if acc == 100 else "HOLD STILL - HEAD MOVED"
        
        self.update_state(bpm if frame > 50 else 0, wave, min(frame/50, 1.0), acc, adv)
        self.after(33, self.simulate_live_feed, frame + 1)

if __name__ == "__main__":
    app = OmniPulseUI()
    app.mainloop()