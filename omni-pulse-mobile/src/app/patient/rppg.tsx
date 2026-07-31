import React, { useState, useEffect, useRef } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, SafeAreaView } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';

const WS_URL = 'ws://xx.xxx.xx.xxx:xxxx'; // Put your PC's IP here

export default function RppgMonitorScreen() {
    const [permission, requestPermission] = useCameraPermissions();
    const [isScanning, setIsScanning] = useState(false);
    
    const [hudData, setHudData] = useState({
        bpm: 0,
        accuracy: 0,
        status: "STANDBY",
        age: "--",
        stress: 0
    });

    const wsRef = useRef<WebSocket | null>(null);
    const cameraRef = useRef<CameraView>(null);
    const loopRef = useRef<boolean>(false);

    useEffect(() => {
        const connectWebSocket = () => {
            console.log("Connecting to Python Server...");
            const ws = new WebSocket(WS_URL);
            
            ws.onopen = () => {
                console.log('Connected to OmniPulse Python Engine');
                wsRef.current = ws;
            };
            
            ws.onmessage = (e) => {
                try {
                    const data = JSON.parse(e.data);
                    setHudData(data);
                } catch (err) {
                    console.log("Parse error", err);
                }
            };
            
            ws.onerror = (e) => console.log('WebSocket Error: ', e);
            ws.onclose = () => {
                console.log('WebSocket Disconnected');
                wsRef.current = null;
                setIsScanning(false);
                loopRef.current = false;
            };
        };

        connectWebSocket();
        return () => {
            if (wsRef.current) wsRef.current.close();
            loopRef.current = false;
        };
    }, []);

    const captureLoop = async () => {
        // 1. Initial check
        if (!loopRef.current || !cameraRef.current || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            return;
        }

        try {
            const photo = await cameraRef.current.takePictureAsync({
                base64: true,
                quality: 0.5, // Up from 0.2
                scale: 0.3,
                skipProcessing: true,
            });

            // 2. THE CRITICAL GHOST-FRAME CHECK: 
            // Did the user press "Stop" while we were waiting for the camera?
            if (!loopRef.current) return; 

            if (photo && photo.base64) {
                wsRef.current.send(photo.base64);
            }
        } catch (error) {
            console.log("Capture Error: ", error);
        }

        if (loopRef.current) {
            setTimeout(captureLoop, 50); 
        }
    };

    const toggleScan = () => {
        if (isScanning) {
            setIsScanning(false);
            loopRef.current = false;
        } else {
            if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
                alert("Cannot connect to Python Server.");
                return;
            }
            setIsScanning(true);
            loopRef.current = true;
            captureLoop();
        }
    };

    if (!permission || !permission.granted) {
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
            <CameraView 
                ref={cameraRef} 
                style={StyleSheet.absoluteFillObject} 
                facing="front" 
            />

            {/* Outside Slot Cards */}
            <View style={styles.hudContainer}>
                <View style={styles.hudCard}>
                    <Text style={styles.hudLabel}>ACCURACY</Text>
                    <Text style={[styles.hudValue, { color: hudData.accuracy > 70 ? '#4ADE80' : '#F87171' }]}>
                        {hudData.accuracy}%
                    </Text>
                </View>

                <View style={styles.hudCard}>
                    <Text style={styles.hudLabel}>LIVE PULSE</Text>
                    <Text style={styles.hudValue}>{hudData.bpm > 0 ? `${Math.round(hudData.bpm)} BPM` : 'CALIBRATING'}</Text>
                </View>

                <View style={styles.hudCard}>
                    <Text style={styles.hudLabel}>EST. AGE</Text>
                    <Text style={styles.hudValue}>{hudData.age}</Text>
                </View>
            </View>

            {/* In-Feed Floating Banner Overlay showing live BPM directly inside the camera view */}
            <View style={styles.inFeedBanner}>
                <Text style={styles.inFeedTitle}>OMNIPULSE BIO-FEED</Text>
                <Text style={styles.inFeedBpm}>
                    {hudData.bpm > 0 ? `♥ ${Math.round(hudData.bpm)} BPM` : '♥ calibrating...'}
                </Text>
                <Text style={styles.inFeedSub}>Age Group: {hudData.age}</Text>
            </View>

            <View style={styles.statusBanner}>
                <Text style={styles.statusText}>{hudData.status}</Text>
            </View>

            <View style={styles.overlayFooter}>
                <TouchableOpacity
                    style={[styles.scanActionBtn, isScanning && styles.scanActionBtnActive]}
                    onPress={toggleScan}
                >
                    <Text style={styles.scanActionText}>
                        {isScanning ? "Stop Transmission" : "Connect & Stream to Engine"}
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
    hudContainer: { position: 'absolute', top: 50, left: 20, right: 20, flexDirection: 'row', justifyContent: 'space-between' },
    hudCard: { backgroundColor: 'rgba(0,0,0,0.75)', padding: 10, borderRadius: 10, alignItems: 'center', flex: 1, marginHorizontal: 4, borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)' },
    hudLabel: { color: '#9CA3AF', fontSize: 9, fontWeight: '700', marginBottom: 2 },
    hudValue: { color: '#FFFFFF', fontSize: 14, fontWeight: 'bold' },
    inFeedBanner: { position: 'absolute', top: 125, left: 20, right: 20, backgroundColor: 'rgba(15, 23, 42, 0.85)', padding: 14, borderRadius: 12, alignItems: 'center', borderWidth: 1, borderColor: '#0F766E' },
    inFeedTitle: { color: '#2DD4BF', fontSize: 10, fontWeight: '800', letterSpacing: 1 },
    inFeedBpm: { color: '#FFFFFF', fontSize: 26, fontWeight: '900', marginVertical: 2 },
    inFeedSub: { color: '#94A3B8', fontSize: 11, fontWeight: '600' },
    statusBanner: { position: 'absolute', top: 210, left: 20, right: 20, backgroundColor: 'rgba(15, 118, 110, 0.8)', padding: 8, borderRadius: 8, alignItems: 'center' },
    statusText: { color: '#FFFFFF', fontWeight: '600', fontSize: 12 },
    overlayFooter: { position: 'absolute', bottom: 40, left: 20, right: 20 },
    scanActionBtn: { backgroundColor: '#0F766E', paddingVertical: 16, borderRadius: 12, alignItems: 'center' },
    scanActionBtnActive: { backgroundColor: '#DC2626' },
    scanActionText: { color: '#FFFFFF', fontSize: 16, fontWeight: '700' },
});