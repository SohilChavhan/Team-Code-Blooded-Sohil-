import { Stack } from 'expo-router';
import { TouchableOpacity, Text, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';

export default function DoctorLayout() {
    const router = useRouter();

    return (
        <Stack
            screenOptions={{
                headerStyle: { backgroundColor: '#FFFFFF' },
                headerTintColor: '#DC2626',
                headerTitleStyle: { fontWeight: '700', color: '#111827' },
                headerShadowVisible: false,
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
            <Stack.Screen
                name="index"
                options={{ title: 'Clinical Dashboard' }}
            />
        </Stack>
    );
}

const styles = StyleSheet.create({
    signOutBtn: {
        backgroundColor: '#0F766E15', // Light teal background
        paddingHorizontal: 12,
        paddingVertical: 6,
        borderRadius: 6,
    },
    signOutText: {
        color: '#0F766E',
        fontSize: 12,
        fontWeight: '700',
    },
});