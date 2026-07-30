import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
  StatusBar
} from 'react-native';
import { useRouter } from 'expo-router';

export default function PortalSelectionScreen() {
  const router = useRouter();

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="dark-content" backgroundColor="#FFFFFF" />

      {/* Brand Header */}
      <View style={styles.header}>
        <View style={styles.badge}>
          <Text style={styles.badgeText}>ZERO-TOUCH BIOMETRICS</Text>
        </View>
        <Text style={styles.logoText}>OMNI-PULSE</Text>
        <Text style={styles.subtitleText}>
          Select your entry portal to access real-time biometric telemetry and care tools.
        </Text>
      </View>

      {/* Portal Selection Cards */}
      <View style={styles.cardsContainer}>
        {/* Patient Portal Button */}
        <TouchableOpacity
          style={styles.portalCard}
          activeOpacity={0.85}
          onPress={() => router.push('/patient')}
        >
          <View style={styles.cardHeader}>
            <View style={[styles.iconCircle, { backgroundColor: '#1E40AF15' }]}>
              <Text style={styles.iconText}>🫀</Text>
            </View>
            <View style={[styles.actionBadge, { backgroundColor: '#1E40AF' }]}>
              <Text style={styles.actionBadgeText}>Enter →</Text>
            </View>
          </View>

          <Text style={styles.cardTitle}>Patient Portal</Text>
          <Text style={styles.cardDescription}>
            Measure live heart rate, view schedule reminders, and receive E-Prescriptions.
          </Text>
        </TouchableOpacity>

        {/* Doctor Portal Button */}
        <TouchableOpacity
          style={styles.portalCard}
          activeOpacity={0.85}
          onPress={() => router.push('/doctor')}
        >
          <View style={styles.cardHeader}>
            <View style={[styles.iconCircle, { backgroundColor: '#0F766E15' }]}>
              <Text style={styles.iconText}>👨‍⚕️</Text>
            </View>
            <View style={[styles.actionBadge, { backgroundColor: '#0F766E' }]}>
              <Text style={styles.actionBadgeText}>Enter →</Text>
            </View>
          </View>

          <Text style={styles.cardTitle}>Doctor's Portal</Text>
          <Text style={styles.cardDescription}>
            Review patient rPPG vital telemetry, assess accuracy scores, and create prescriptions.
          </Text>
        </TouchableOpacity>
      </View>

      {/* Footer */}
      <View style={styles.footer}>
        <Text style={styles.footerText}>Powered by OMNI-PULSE rPPG Engine</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 24,
    justifyContent: 'space-between',
  },
  header: {
    marginTop: 40,
  },
  badge: {
    backgroundColor: '#DC262615',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
    alignSelf: 'flex-start',
    marginBottom: 12,
  },
  badgeText: {
    color: '#DC2626',
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1,
  },
  logoText: {
    fontSize: 32,
    fontWeight: '800',
    color: '#111827',
    letterSpacing: -0.5,
  },
  subtitleText: {
    fontSize: 15,
    color: '#6B7280',
    marginTop: 8,
    lineHeight: 22,
  },
  cardsContainer: {
    gap: 16,
    marginVertical: 20,
  },
  portalCard: {
    backgroundColor: '#F9FAFB',
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  iconCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  iconText: {
    fontSize: 22,
  },
  actionBadge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
  },
  actionBadgeText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
  },
  cardTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 6,
  },
  cardDescription: {
    fontSize: 13,
    color: '#6B7280',
    lineHeight: 18,
  },
  footer: {
    marginBottom: 20,
    alignItems: 'center',
  },
  footerText: {
    fontSize: 12,
    color: '#9CA3AF',
    fontWeight: '500',
  },
});