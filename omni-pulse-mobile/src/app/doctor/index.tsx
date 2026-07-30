import React, { useState, useEffect } from 'react';
import {
    View,
    Text,
    StyleSheet,
    ScrollView,
    TouchableOpacity,
    TextInput,
    SafeAreaView,
    Alert
} from 'react-native';
import { supabase } from '../../services/supabase';

export default function DoctorDashboard() {
    const [patientQueue, setPatientQueue] = useState<any[]>([]);
    const [selectedPatient, setSelectedPatient] = useState('');

    // Form State
    const [diagnosis, setDiagnosis] = useState('');
    const [medication, setMedication] = useState('');
    const [dosage, setDosage] = useState('');
    const [timing, setTiming] = useState('');

    useEffect(() => {
        fetchQueue();
    }, []);

    const fetchQueue = async () => {
        const { data, error } = await supabase
            .from('reports')
            .select('*')
            .order('created_at', { ascending: false });

        if (data && data.length > 0) {
            setPatientQueue(data);
            setSelectedPatient(data[0].patient_name);
        }
    };

    const dispatchPrescription = async () => {
        if (!diagnosis || !medication || !dosage || !timing) {
            Alert.alert("Error", "Please fill out all fields.");
            return;
        }

        const { error } = await supabase
            .from('prescriptions')
            .insert([{
                patient_name: selectedPatient,
                diagnosis,
                medication,
                dosage,
                timing
            }]);

        if (!error) {
            Alert.alert("Success", "E-Prescription dispatched to patient.");
            setDiagnosis('');
            setMedication('');
            setDosage('');
            setTiming('');
        } else {
            Alert.alert("Database Error", error.message);
        }
    };

    return (
        <SafeAreaView style={styles.container}>
            <ScrollView contentContainerStyle={styles.scrollContent}>

                <View style={styles.sectionHeader}>
                    <Text style={styles.sectionTitle}>Recent rPPG Scans</Text>
                    <Text style={styles.sectionSubtitle}>Pull down to refresh</Text>
                </View>

                {patientQueue.map((patient: any) => (
                    <TouchableOpacity
                        key={patient.id}
                        style={[styles.patientCard, selectedPatient === patient.patient_name && styles.patientCardActive]}
                        onPress={() => setSelectedPatient(patient.patient_name)}
                        activeOpacity={0.8}
                    >
                        <View style={styles.patientInfo}>
                            <Text style={styles.patientName}>{patient.patient_name}</Text>
                            <Text style={styles.patientTime}>Status: {patient.status}</Text>
                        </View>
                        <View style={styles.telemetryBadge}>
                            <Text style={styles.bpmText}>{patient.bpm} BPM</Text>
                            <Text style={styles.accuracyText}>Acc: {patient.accuracy}%</Text>
                        </View>
                    </TouchableOpacity>
                ))}

                <View style={[styles.sectionHeader, { marginTop: 24 }]}>
                    <Text style={styles.sectionTitle}>E-Prescription Builder</Text>
                </View>

                <View style={styles.prescriptionForm}>
                    <View style={styles.formGroup}>
                        <Text style={styles.inputLabel}>Selected Patient</Text>
                        <View style={styles.lockedInput}>
                            <Text style={styles.lockedInputText}>{selectedPatient || "Select a patient above"}</Text>
                            <Text style={styles.lockedIcon}>🔒</Text>
                        </View>
                    </View>

                    <View style={styles.formGroup}>
                        <Text style={styles.inputLabel}>Clinical Diagnosis / Notes</Text>
                        <TextInput
                            style={[styles.inputField, { height: 80 }]}
                            placeholder="Enter diagnosis notes..."
                            placeholderTextColor="#9CA3AF"
                            multiline value={diagnosis} onChangeText={setDiagnosis}
                        />
                    </View>

                    <View style={styles.formGroup}>
                        <Text style={styles.inputLabel}>Medication</Text>
                        <TextInput
                            style={styles.inputField}
                            placeholder="e.g. Lisinopril"
                            placeholderTextColor="#9CA3AF"
                            value={medication} onChangeText={setMedication}
                        />
                    </View>

                    <View style={styles.rowGroup}>
                        <View style={[styles.formGroup, { flex: 1, marginRight: 10 }]}>
                            <Text style={styles.inputLabel}>Dosage</Text>
                            <TextInput
                                style={styles.inputField}
                                placeholder="e.g. 10mg"
                                placeholderTextColor="#9CA3AF"
                                value={dosage} onChangeText={setDosage}
                            />
                        </View>
                        <View style={[styles.formGroup, { flex: 2 }]}>
                            <Text style={styles.inputLabel}>Time / Schedule</Text>
                            <TextInput
                                style={styles.inputField}
                                placeholder="e.g. After dinner"
                                placeholderTextColor="#9CA3AF"
                                value={timing} onChangeText={setTiming}
                            />
                        </View>
                    </View>

                    <TouchableOpacity style={styles.dispatchButton} activeOpacity={0.85} onPress={dispatchPrescription}>
                        <Text style={styles.dispatchIcon}>✍️</Text>
                        <Text style={styles.dispatchText}>Sign & Dispatch E-Prescription</Text>
                    </TouchableOpacity>
                </View>
            </ScrollView>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: '#FFFFFF' },
    scrollContent: { padding: 20 },
    sectionHeader: { marginBottom: 12 },
    sectionTitle: { fontSize: 18, fontWeight: '700', color: '#111827' },
    sectionSubtitle: { fontSize: 13, color: '#6B7280', marginTop: 2 },
    patientCard: { backgroundColor: '#F9FAFB', borderRadius: 12, padding: 16, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', borderWidth: 1, borderColor: '#E5E7EB', marginBottom: 10 },
    patientCardActive: { borderColor: '#0F766E', backgroundColor: '#0F766E0A' },
    patientInfo: { flex: 1 },
    patientName: { fontSize: 15, fontWeight: '700', color: '#111827' },
    patientTime: { fontSize: 12, color: '#6B7280', marginTop: 4 },
    telemetryBadge: { backgroundColor: '#FFFFFF', padding: 8, borderRadius: 8, borderWidth: 1, borderColor: '#E5E7EB', alignItems: 'center' },
    bpmText: { fontSize: 16, fontWeight: '800', color: '#DC2626' },
    accuracyText: { fontSize: 10, color: '#14B8A6', fontWeight: '700', marginTop: 2 },
    prescriptionForm: { backgroundColor: '#F9FAFB', padding: 20, borderRadius: 16, borderWidth: 1, borderColor: '#E5E7EB' },
    formGroup: { marginBottom: 16 },
    rowGroup: { flexDirection: 'row' },
    inputLabel: { fontSize: 12, fontWeight: '700', color: '#6B7280', marginBottom: 6 },
    lockedInput: { flexDirection: 'row', justifyContent: 'space-between', backgroundColor: '#E5E7EB', padding: 14, borderRadius: 10 },
    lockedInputText: { color: '#111827', fontWeight: '600' },
    lockedIcon: { fontSize: 14 },
    inputField: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#D1D5DB', borderRadius: 10, padding: 14, fontSize: 14, color: '#111827', textAlignVertical: 'top' },
    dispatchButton: { backgroundColor: '#0F766E', padding: 16, borderRadius: 12, flexDirection: 'row', justifyContent: 'center', alignItems: 'center', marginTop: 10 },
    dispatchIcon: { fontSize: 20, marginRight: 10 },
    dispatchText: { color: '#FFFFFF', fontSize: 15, fontWeight: '700' },
});