import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, SafeAreaView, Alert } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import Svg, { Ellipse } from 'react-native-svg';
import { supabase } from '../../services/supabase';

export default function RppgMonitorScreen() {
    const [permission, requestPermission] = useCameraPermissions();
    const [isScanning, setIsScanning] = useState(false);

    const handleScan = async () => {
        if (isScanning) return;
        setIsScanning(true);

        // Simulating the 10-second Python engine calculation
        setTimeout(async () => {
            setIsScanning(false);

            const mockBpm = Math.floor(Math.random() * (95 - 65 + 1)) + 65;

            // Push the biometric report to Supabase
            const { error } = await supabase
                .from('reports')
                .insert([{
                    patient_name: 'Alex Johnson',
                    bpm: mockBpm,
                    accuracy: 98,
                    status: mockBpm > 90 ? 'Elevated' : 'Normal'
                }]);

            if (!error) {
                Alert.alert("Scan Complete", `Your heart rate is ${mockBpm} BPM. Report synced to doctor.`);
            }
        }, 3000); // Set to 3 seconds for quick testing
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
            <CameraView style={StyleSheet.absoluteFillObject} facing="front" />
            <Svg height="100%" width="100%" viewBox="0 0 100 100" style={StyleSheet.absoluteFillObject}>
                <Ellipse cx="50" cy="42" rx="26" ry="36" stroke={isScanning ? "#16A34A" : "#14B8A6"} strokeWidth="1.5" strokeDasharray="4, 2" fill="none" />
            </Svg>

            <View style={styles.overlayHeader}>
                <View style={styles.guideBadge}>
                    <Text style={styles.guideText}>
                        {isScanning ? "SCANNING... HOLD STILL" : "ALIGN FACE INSIDE OVAL"}
                    </Text>
                </View>
            </View>

            <View style={styles.overlayFooter}>
                <TouchableOpacity
                    style={[styles.scanActionBtn, isScanning && styles.scanActionBtnActive]}
                    onPress={handleScan}
                >
                    <Text style={styles.scanActionText}>
                        {isScanning ? "Extracting Vitals..." : "Begin Biometric Capture"}
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
    overlayFooter: { position: 'absolute', bottom: 40, left: 20, right: 20 },
    scanActionBtn: { backgroundColor: '#0F766E', paddingVertical: 16, borderRadius: 12, alignItems: 'center' },
    scanActionBtnActive: { backgroundColor: '#DC2626' },
    scanActionText: { color: '#FFFFFF', fontSize: 16, fontWeight: '700' },
});