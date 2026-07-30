import React, { useState, useRef, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, SafeAreaView, Alert } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import Svg, { Ellipse } from 'react-native-svg';
import { supabase } from '../../services/supabase';

// Use your computer's local IP address if running on physical device, e.g., 'ws://192.168.1.5:8000/ws/rppg'
// Or 10.0.2.2 for Android Emulator
const WS_URL = process.env.EXPO_PUBLIC_SERVER_URL || 'ws://10.0.2.2:8000/ws/rppg';

export default function RppgMonitorScreen() {
    const [permission, requestPermission] = useCameraPermissions();
    const [isScanning, setIsScanning] = useState(false);
    
    // UI State for live data
    const [bpm, setBpm] = useState(0);
    const [status, setStatus] = useState("ALIGN FACE INSIDE OVAL");
    const [accuracy, setAccuracy] = useState(0);
    const [progress, setProgress] = useState(0);
    
    const cameraRef = useRef<CameraView>(null);
    const ws = useRef<WebSocket | null>(null);
    const frameLoop = useRef<NodeJS.Timeout | null>(null);

    useEffect(() => {
        return () => {
            stopScan();
        };
    }, []);

    const stopScan = () => {
        setIsScanning(false);
        setStatus("ALIGN FACE INSIDE OVAL");
        if (frameLoop.current) clearInterval(frameLoop.current);
        if (ws.current) ws.current.close();
    };

    const syncToDoctor = async (finalBpm: number) => {
        const { error } = await supabase
            .from('reports')
            .insert([{
                patient_name: 'Alex Johnson',
                bpm: finalBpm,
                accuracy: 98,
                status: finalBpm > 90 ? 'Elevated' : 'Normal'
            }]);
        if (!error) {
            Alert.alert("Scan Synced", `Heart rate of ${finalBpm} BPM synced to doctor.`);
        }
    };

    const handleScan = async () => {
        if (isScanning) {
            stopScan();
            return;
        }

        setIsScanning(true);
        setStatus("CONNECTING TO ENGINE...");

        try {
            ws.current = new WebSocket(WS_URL);
            
            ws.current.onopen = () => {
                setStatus("ENGINE CONNECTED - ACQUIRING BASELINE");
                startFrameStreaming();
            };

            ws.current.onmessage = async (e) => {
                const data = JSON.parse(e.data);
                
                if (data.bpm) setBpm(data.bpm);
                if (data.accuracy) setAccuracy(data.accuracy);
                if (data.progress) setProgress(data.progress);
                if (data.diagnostic_reason) setStatus(data.diagnostic_reason);
                
                // Demo logic: once we hit 100% progress and have a good reading, sync it
                if (data.progress === 100 && data.bpm > 0) {
                    syncToDoctor(data.bpm);
                    stopScan(); // Auto-stop after successful scan
                }
            };

            ws.current.onerror = (e) => {
                setStatus("ENGINE CONNECTION ERROR");
                stopScan();
            };

            ws.current.onclose = () => {
                stopScan();
            };

        } catch (error) {
            setStatus("FAILED TO CONNECT");
            stopScan();
        }
    };

    const startFrameStreaming = () => {
        // Stream frames at ~10 FPS (100ms interval) to the Python engine
        frameLoop.current = setInterval(async () => {
            if (cameraRef.current && ws.current?.readyState === WebSocket.OPEN) {
                try {
                    const photo = await cameraRef.current.takePictureAsync({
                        base64: true,
                        quality: 0.1, // very low quality to reduce latency/bandwidth
                        skipProcessing: true,
                    });
                    if (photo && photo.base64) {
                        ws.current.send(photo.base64);
                    }
                } catch (e) {
                    console.log("Frame drop");
                }
            }
        }, 150); 
    };

    if (!permission) return <View style={styles.centerContainer}><Text>Requesting permission...</Text></View>;
    if (!permission.granted) {
        return (
            <SafeAreaView style={styles.centerContainer}>
                <Text style={styles.permText}>Camera permission is required.</Text>
                <TouchableOpacity style={styles.permBtn} onPress={requestPermission}>
                    <Text style={styles.permBtnText}>Grant Permission</Text>
                </TouchableOpacity>
            </SafeAreaView>
        );
    }

    return (
        <View style={styles.container}>
            <CameraView ref={cameraRef} style={StyleSheet.absoluteFillObject} facing="front" />
            <Svg height="100%" width="100%" viewBox="0 0 100 100" style={StyleSheet.absoluteFillObject}>
                <Ellipse cx="50" cy="42" rx="26" ry="36" stroke={isScanning ? "#16A34A" : "#14B8A6"} strokeWidth="1.5" strokeDasharray="4, 2" fill="none" />
            </Svg>

            <View style={styles.overlayHeader}>
                <View style={styles.guideBadge}>
                    <Text style={styles.guideText}>
                        {status} {isScanning && progress > 0 ? `(${progress}%)` : ""}
                    </Text>
                </View>
                {isScanning && bpm > 0 && (
                    <View style={styles.liveBpmBadge}>
                        <Text style={styles.liveBpmText}>{bpm} BPM</Text>
                        <Text style={styles.liveAccText}>Acc: {accuracy}%</Text>
                    </View>
                )}
            </View>

            <View style={styles.overlayFooter}>
                <TouchableOpacity
                    style={[styles.scanActionBtn, isScanning && styles.scanActionBtnActive]}
                    onPress={handleScan}
                >
                    <Text style={styles.scanActionText}>
                        {isScanning ? "Stop Biometric Capture" : "Begin Biometric Capture"}
                    </Text>
                </TouchableOpacity>
            </View>
        </View>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: '#000000' },
    centerContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24, backgroundColor: '#FFFFFF' },
    permText: { fontSize: 16, textAlign: 'center', color: '#111827', marginBottom: 20 },
    permBtn: { backgroundColor: '#DC2626', paddingHorizontal: 20, paddingVertical: 12, borderRadius: 10 },
    permBtnText: { color: '#FFFFFF', fontWeight: '700' },
    overlayHeader: { position: 'absolute', top: 30, left: 0, right: 0, alignItems: 'center' },
    guideBadge: { backgroundColor: '#000000B3', paddingHorizontal: 16, paddingVertical: 8, borderRadius: 20 },
    guideText: { color: '#14B8A6', fontSize: 12, fontWeight: '700', letterSpacing: 0.5 },
    liveBpmBadge: { backgroundColor: '#000000B3', paddingHorizontal: 16, paddingVertical: 12, borderRadius: 12, marginTop: 12, alignItems: 'center' },
    liveBpmText: { color: '#FFFFFF', fontSize: 24, fontWeight: '800' },
    liveAccText: { color: '#14B8A6', fontSize: 12, fontWeight: '700', marginTop: 4 },
    overlayFooter: { position: 'absolute', bottom: 40, left: 20, right: 20 },
    scanActionBtn: { backgroundColor: '#0F766E', paddingVertical: 16, borderRadius: 12, alignItems: 'center' },
    scanActionBtnActive: { backgroundColor: '#DC2626' },
    scanActionText: { color: '#FFFFFF', fontSize: 16, fontWeight: '700' },
});