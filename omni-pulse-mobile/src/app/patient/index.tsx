import React, { useState, useEffect } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    ScrollView,
    SafeAreaView
} from 'react-native';
import { useRouter } from 'expo-router';
import { supabase } from '../../services/supabase';

export default function PatientDashboard() {
    const router = useRouter();
    const [reminders, setReminders] = useState([
        { id: 'static-1', title: 'Evening rPPG Heart Rate Scan', time: '08:00 PM', tag: 'VITAL CHECK', done: false },
    ]);
    const [latestBpm, setLatestBpm] = useState('--');

    useEffect(() => {
        fetchPrescriptions();
        fetchLatestVital();
    }, []);

    const fetchPrescriptions = async () => {
        const { data, error } = await supabase
            .from('prescriptions')
            .select('*')
            .eq('patient_name', 'Alex Johnson')
            .order('created_at', { ascending: false });

        if (data) {
            const dbReminders = data.map(rx => ({
                id: rx.id,
                title: `${rx.medication} (${rx.dosage})`,
                time: rx.timing,
                tag: 'MEDICATION',
                done: false,
            }));
            // Merge DB prescriptions with the static daily scan reminder
            setReminders([...dbReminders, { id: 'static-1', title: 'Evening rPPG Heart Rate Scan', time: '08:00 PM', tag: 'VITAL CHECK', done: false }]);
        }
    };

    const fetchLatestVital = async () => {
        const { data } = await supabase
            .from('reports')
            .select('bpm')
            .eq('patient_name', 'Alex Johnson')
            .order('created_at', { ascending: false })
            .limit(1);

        if (data && data.length > 0) {
            setLatestBpm(data[0].bpm.toString());
        }
    };

    const toggleReminder = (id: string) => {
        setReminders(prev => prev.map(item => item.id === id ? { ...item, done: !item.done } : item));
    };

    return (
        <SafeAreaView style={styles.container}>
            <ScrollView contentContainerStyle={styles.scrollContent}>

                <View style={styles.vitalsCard}>
                    <View style={styles.vitalsHeader}>
                        <Text style={styles.vitalsTitle}>LAST RECORDED VITAL</Text>
                        <View style={styles.statusBadge}>
                            <Text style={styles.statusBadgeText}>NORMAL</Text>
                        </View>
                    </View>

                    <View style={styles.bpmRow}>
                        <Text style={styles.bpmNumber}>{latestBpm}</Text>
                        <Text style={styles.bpmUnit}>BPM</Text>
                    </View>
                    <Text style={styles.vitalsMeta}>Measured via rPPG Engine</Text>
                </View>

                <TouchableOpacity
                    style={styles.scanButton}
                    activeOpacity={0.85}
                    onPress={() => router.push('/patient/rppg')}
                >
                    <Text style={styles.scanButtonIcon}>🫀</Text>
                    <View>
                        <Text style={styles.scanButtonTitle}>Start Heart Rate Scan</Text>
                        <Text style={styles.scanButtonSubtitle}>Zero-touch camera detection</Text>
                    </View>
                </TouchableOpacity>

                <View style={styles.sectionHeader}>
                    <Text style={styles.sectionTitle}>Today's Care Schedule</Text>
                    <Text style={styles.sectionSubtitle}>Tap to check off completed items</Text>
                </View>

                {reminders.map((item) => (
                    <TouchableOpacity
                        key={item.id}
                        style={[styles.reminderCard, item.done && styles.reminderCardDone]}
                        onPress={() => toggleReminder(item.id)}
                        activeOpacity={0.7}
                    >
                        <View style={styles.reminderCheck}>
                            <Text style={styles.checkText}>{item.done ? '✓' : '○'}</Text>
                        </View>

                        <View style={{ flex: 1 }}>
                            <Text style={[styles.reminderText, item.done && styles.reminderTextDone]}>
                                {item.title}
                            </Text>
                            <Text style={styles.reminderTime}>{item.time}</Text>
                        </View>

                        <View style={[styles.tagBadge, item.done && { backgroundColor: '#E5E7EB' }]}>
                            <Text style={[styles.tagText, item.done && { color: '#9CA3AF' }]}>{item.tag}</Text>
                        </View>
                    </TouchableOpacity>
                ))}
            </ScrollView>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: '#FFFFFF' },
    scrollContent: { padding: 20 },
    vitalsCard: { backgroundColor: '#F9FAFB', borderRadius: 16, padding: 20, borderWidth: 1, borderColor: '#E5E7EB', marginBottom: 16 },
    vitalsHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
    vitalsTitle: { fontSize: 11, fontWeight: '700', color: '#6B7280', letterSpacing: 0.5 },
    statusBadge: { backgroundColor: '#16A34A15', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
    statusBadgeText: { color: '#16A34A', fontSize: 11, fontWeight: '700' },
    bpmRow: { flexDirection: 'row', alignItems: 'baseline', marginTop: 10 },
    bpmNumber: { fontSize: 48, fontWeight: '800', color: '#111827' },
    bpmUnit: { fontSize: 18, fontWeight: '700', color: '#DC2626', marginLeft: 6 },
    vitalsMeta: { fontSize: 12, color: '#6B7280', marginTop: 4 },
    scanButton: { backgroundColor: '#1E40AF', borderRadius: 14, padding: 18, flexDirection: 'row', alignItems: 'center', marginBottom: 24 },
    scanButtonIcon: { fontSize: 28, marginRight: 14 },
    scanButtonTitle: { color: '#FFFFFF', fontSize: 16, fontWeight: '700' },
    scanButtonSubtitle: { color: '#93C5FD', fontSize: 12, marginTop: 2 },
    sectionHeader: { marginBottom: 12 },
    sectionTitle: { fontSize: 18, fontWeight: '700', color: '#111827' },
    sectionSubtitle: { fontSize: 13, color: '#6B7280', marginTop: 2 },
    reminderCard: { backgroundColor: '#F9FAFB', borderRadius: 12, padding: 16, flexDirection: 'row', alignItems: 'center', borderWidth: 1, borderColor: '#E5E7EB', marginBottom: 10 },
    reminderCardDone: { backgroundColor: '#F3F4F6', borderColor: '#E5E7EB' },
    reminderCheck: { width: 28, height: 28, borderRadius: 14, justifyContent: 'center', alignItems: 'center', marginRight: 12 },
    checkText: { fontSize: 18, fontWeight: '700', color: '#1E40AF' },
    reminderText: { fontSize: 14, fontWeight: '600', color: '#111827' },
    reminderTextDone: { textDecorationLine: 'line-through', color: '#9CA3AF' },
    reminderTime: { fontSize: 12, color: '#6B7280', marginTop: 2 },
    tagBadge: { backgroundColor: '#1E40AF15', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
    tagText: { color: '#1E40AF', fontSize: 10, fontWeight: '700' },
});