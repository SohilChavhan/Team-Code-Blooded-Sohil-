import { Drawer } from 'expo-router/drawer';
import { TouchableOpacity, Text, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';

export default function PatientLayout() {
    const router = useRouter();

    return (
        <Drawer
            screenOptions={{
                headerStyle: { backgroundColor: '#FFFFFF' },
                headerTintColor: '#111827',
                headerTitleStyle: { fontWeight: '700' },
                drawerActiveTintColor: '#DC2626',
                drawerInactiveTintColor: '#6B7280',
                drawerStyle: { backgroundColor: '#FFFFFF', width: 280 },
                // Added the Sign Out button to the top right of the header
                headerRight: () => (
                    <TouchableOpacity
                        style={styles.signOutBtn}
                        onPress={() => router.replace('/')}
                    >
                        <Text style={styles.signOutText}>Sign Out</Text>
                    </TouchableOpacity>
                ),
            }}
        >
            <Drawer.Screen
                name="index"
                options={{
                    drawerLabel: '🏠 Dashboard & Schedule',
                    title: 'Patient Dashboard',
                }}
            />
            <Drawer.Screen
                name="rppg"
                options={{
                    drawerLabel: '🫀 Heart Rate Monitor',
                    title: 'rPPG Heart Rate Scan',
                }}
            />
        </Drawer>
    );
}

const styles = StyleSheet.create({
    signOutBtn: {
        marginRight: 16,
        backgroundColor: '#DC262615', // Light red background
        paddingHorizontal: 12,
        paddingVertical: 6,
        borderRadius: 6,
    },
    signOutText: {
        color: '#DC2626',
        fontSize: 12,
        fontWeight: '700',
    },
});