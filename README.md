# 🫀 OMNI-PULSE: Zero-Touch Biometric Intelligence Engine

> A software-only, contactless health monitoring platform that extracts real-time vital signs (BPM), cognitive stress levels, and demographic data purely through standard video streams using Remote Photoplethysmography (rPPG).

---

## 📌 Table of Contents
- [Overview]
- [System Architecture]
- [Biological Science Behind rPPG]
- [Mathematical & Signal Processing Pipeline]
- [Key Features]
- [Tech Stack]
- [Getting Started]
- [API Reference]

---

## 📖 Overview

Traditional cardiovascular monitoring relies on wearable sensors, pulse oximeters, or chest straps. **OMNI-PULSE** eliminates physical hardware dependencies by using optical physics and computer vision. By analyzing subtle, invisible color shifts in facial skin tissue caused by blood circulation, OMNI-PULSE calculates heart rate, detects cognitive strain, and syncs vital health reports between patients and clinical providers via a modern mobile app and cloud database.

---

## 🏗 System Architecture

┌────────────────────────┐      Video Upload      ┌─────────────────────────────┐
│                        ├───────────────────────►│                             │
│  React Native / Expo   │                        │  Python FastAPI Server      │
│     Mobile App         │◄───────────────────────┤  (rPPG Math & OpenCV Engine)│
└───────────┬────────────┘      JSON Vitals       └──────────────┬──────────────┘
│                                                    │
│               ┌──────────────────┐                 │
└──────────────►│  Supabase Cloud  │◄────────────────┘
│    (PostgreSQL)  │
└──────────────────┘

The system operates across three core layers:
1. **Frontend (React Native & Expo Router):** Multi-portal mobile interface featuring dual dashboards (Patient & Doctor), live camera framing guides, and E-Prescription builders.
2. **Biometric Engine (Python & FastAPI):** Headless signal processing backend executing facial mesh tracking, color extraction, bandpass filtering, and FFT spectral breakdown.
3. **Database & Sync (Supabase):** Managed cloud PostgreSQL database facilitating real-time data exchange between patient vital scans and doctor prescription workflows.

---

## 🧬 Biological Science Behind rPPG

### 1. The Cardiovascular Cycle & Micro-Vascular Expansion
During **left ventricular systole** (heart contraction), a high-pressure blood surge propagates through the arterial tree down to the facial micro-vascular capillaries. As the pressure wave hits the dermal layer:
* **Systole (Heartbeat):** Capillaries expand, increasing blood volume in facial tissue.
* **Diastole (Resting):** Capillaries contract, allowing blood volume to temporarily decline.

### 2. Light Absorption & Hemoglobin Dynamics
Human red blood cells contain **hemoglobin**, an oxygen-binding protein with strong light absorption peaks in the green spectrum ($\approx 520 - 580\text{ nm}$):
* **High Blood Volume (Systole):** Increased hemoglobin absorbs **more green light**, causing facial skin to reflect **less green light** back to the camera lens.
* **Low Blood Volume (Diastole):** Decreased hemoglobin absorbs **less green light**, causing facial skin to reflect **more green light**.

[Heart Systole] ──► [Capillary Surge] ──► [Hemoglobin Increases] ──► [Green Reflection Drops]

### 3. Micro-Vascular Region Selection
The face is chosen due to its high concentration of thin-skinned capillary beds supplied by branches of the **carotid artery** (facial and superficial temporal arteries). OMNI-PULSE targets three optimal Regions of Interest (ROIs):
* **Forehead**
* **Left Cheek**
* **Right Cheek**

### 4. Facial Strain & Cognitive Stress Mechanics
Cognitive stress and mental strain activate the *corrugator supercilii* muscle, causing involuntary brow furrowing. By tracking the distance ratio between inner brow landmarks ($\text{Landmarks 107, 336}$) and facial width ($\text{Landmarks 234, 454}$), OMNI-PULSE quantifies facial strain against a baseline to calculate a **Cognitive Load Score (%)**.

---

## 🧮 Mathematical & Signal Processing Pipeline

### 1. Spatial ROI Averaging
To eliminate camera sensor noise, color channels are averaged across all valid pixels $N$ inside the facial ROI masks for each video frame:

$$\mathbf{C}_{mean}(t) = \frac{1}{N} \sum_{i=1}^{N} \begin{bmatrix} R_i(t) \\ G_i(t) \\ B_i(t) \end{bmatrix}$$

### 2. Zero-Mean Normalization
Color vectors are normalized by their temporal mean intensity $\mu_C$ to eliminate brightness variations across different lighting environments and skin complexions:

$$C_{norm}(t) = \frac{C(t)}{\mu_C}$$

### 3. Plane-Orthogonal-to-Skin (POS) Algorithm
The normalized RGB signals are projected into two orthogonal chrominance vectors ($X$ and $Y$) to isolate the pulse signal from surface specular reflection and head motion noise:

$$X(t) = G(t) - B(t)$$

$$Y(t) = G(t) + B(t) - 2R(t)$$

An adaptive ratio $\alpha$ blends $X(t)$ and $Y(t)$ based on their standard deviations:

$$\alpha = \frac{\sigma(X_{filtered})}{\sigma(Y_{filtered})}$$

$$S(t) = X_{filtered}(t) + \alpha \cdot Y_{filtered}(t)$$

### 4. Digital Butterworth Bandpass Filter
A 3rd-order Butterworth bandpass filter suppresses frequencies outside human heart rates ($0.8\text{ Hz} - 3.0\text{ Hz} \equiv 48 - 180\text{ BPM}$):

$$H(s) = \frac{1}{1 + \epsilon^2 \left(\frac{s}{\omega_c}\right)^{2n}}$$

### 5. Fast Fourier Transform (FFT) & Peak Extraction
The filtered time-series signal $S(t)$ is multiplied by a Hanning window to prevent edge leakage, zero-padded, and converted to a frequency spectrum $P(f)$:

$$P(f) = \sum_{n=0}^{N-1} S(n) \cdot e^{-i 2 \pi f n / N}$$

$$\text{BPM} = f_{peak} \times 60 \quad \text{where } f_{peak} = \arg\max_{f \in [0.8, 3.0]} P(f)$$

### 6. 1D Kalman Filtering
To remove micro-motion artifacts, estimated BPM readings are updated through a 1D Kalman filter:

$$K_k = \frac{P_k^-}{P_k^- + R}$$

$$\hat{x}_k = \hat{x}_k^- + K_k \left( z_k - \hat{x}_k^- \right)$$

---

## ✨ Key Features

* **Contactless rPPG Scan:** Non-invasive heart rate measurement using standard front cameras.
* **Cognitive Load Tracking:** Real-time facial strain assessment via brow furrowing metrics.
* **Dual-Portal Mobile UI:** Customized navigation stack for both Patients and Doctors.
* **E-Prescription Builder:** Direct digital prescription creation with specific dosages, timings, and diagnosis notes.
* **Real-Time Supabase Sync:** Instant database integration syncing vital reports directly to clinical dashboards.

---

## 🛠 Tech Stack

| Category | Technology |
| :--- | :--- |
| **Mobile Framework** | React Native, Expo Router, TypeScript |
| **Mobile UI & Camera** | Expo Camera, React Native SVG, React Native Reanimated |
| **Backend API** | Python 3.10, FastAPI, Uvicorn |
| **Computer Vision** | OpenCV, MediaPipe Face Mesh (468 3D Landmarks) |
| **Signal Processing** | SciPy (Butterworth Filters), NumPy |
| **Database & Cloud** | Supabase (PostgreSQL), RESTful Data API |

---
## 🚀 Getting Started

### Prerequisites
* Node.js (v18+) & npm
* Python 3.10+
* Supabase Account & Project

## Backend Setup
# Install Python Dependencies
pip install fastapi uvicorn python-multipart opencv-python numpy scipy mediapipe

# Start the FastAPI Server
python api_server.py

# Navigate to Mobile Directory
cd omni-pulse-mobile

# Install NPM Packages
npm install

# Start the Expo Development Server (Clear Cache)
npx expo start -c

📡 API Reference
Process Vitals Endpoint
URL: /process-vitals

Method: POST

Payload: multipart/form-data (Key: video, Value: .mp4 video clip)

Response Example:

JSON
{
  "bpm": 74.2,
  "stress_load": 18,
  "demographic": "[25-32]",
  "status": "Normal"
}
