import React, { useEffect, useRef, useState } from 'react';
import { View, Text, StyleSheet, Animated, Easing, Platform } from 'react-native';

interface AnimatedSplashScreenProps {
  visible: boolean;
  onFinish: () => void;
}

export const AnimatedSplashScreen: React.FC<AnimatedSplashScreenProps> = ({ visible, onFinish }) => {
  const fadeAnim = useRef(new Animated.Value(1)).current;
  const scaleAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (visible) {
      setTimeout(() => {
        Animated.parallel([
          Animated.timing(fadeAnim, {
            toValue: 0,
            duration: 500,
            useNativeDriver: true,
          }),
          Animated.timing(scaleAnim, {
            toValue: 1.2,
            duration: 500,
            useNativeDriver: true,
          }),
        ]).start(() => onFinish());
      }, 2500);
    }
  }, [visible]);

  if (!visible) return null;

  return (
    <Animated.View style={[styles.container, { opacity: fadeAnim }]}>
      <Animated.View style={[styles.logoContainer, { transform: [{ scale: scaleAnim }] }]}>
        {Platform.OS === 'web' && <CometRingWeb />}
        <View style={styles.logoCenter}>
          <Text style={styles.logoText}>CalcAuto</Text>
          <Text style={styles.logoSubtext}>AiPro</Text>
        </View>
      </Animated.View>
      <Text style={styles.loadingText}>Chargement...</Text>
    </Animated.View>
  );
};

const CometRingWeb = () => {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);
  if (!mounted) return null;

  // All trail + head in ONE rotating container = perfect sync
  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes orbit {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 0.2; }
          50% { opacity: 0.4; }
        }
        .orbit-group {
          position: absolute;
          width: 180px;
          height: 180px;
          animation: orbit 2s linear infinite;
        }
        .static-ring {
          position: absolute;
          width: 174px;
          height: 174px;
          border-radius: 50%;
          border: 2px solid rgba(78,205,196,0.2);
          animation: pulse 3s ease-in-out infinite;
        }
        .comet-head {
          position: absolute;
          top: -7px;
          left: 50%;
          margin-left: -7px;
          width: 14px;
          height: 14px;
          border-radius: 50%;
          background: radial-gradient(circle, #fff 0%, #4ECDC4 50%, rgba(78,205,196,0) 80%);
          box-shadow: 0 0 6px 2px rgba(78,205,196,0.8), 0 0 15px 5px rgba(78,205,196,0.4), 0 0 30px 10px rgba(78,205,196,0.15);
        }
        .trail-arc {
          position: absolute;
          width: 180px;
          height: 180px;
          border-radius: 50%;
          border: 3px solid transparent;
          border-top-color: rgba(78,205,196,0.7);
          border-right-color: rgba(78,205,196,0.15);
        }
        .trail-glow {
          position: absolute;
          width: 186px;
          height: 186px;
          top: -3px;
          left: -3px;
          border-radius: 50%;
          border: 4px solid transparent;
          border-top-color: rgba(78,205,196,0.25);
          border-right-color: rgba(78,205,196,0.05);
          filter: blur(4px);
        }
      `}} />

      {/* Static orbit ring */}
      <div className="static-ring" />

      {/* Single rotating group: trail + head = perfectly synced */}
      <div className="orbit-group">
        <div className="trail-glow" />
        <div className="trail-arc" />
        <div className="comet-head" />
      </div>
    </>
  );
};

const styles = StyleSheet.create({
  container: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#1a1a2e',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 9999,
  },
  logoContainer: {
    width: 190,
    height: 190,
    justifyContent: 'center',
    alignItems: 'center',
  },
  logoCenter: {
    width: 140,
    height: 140,
    borderRadius: 70,
    backgroundColor: '#2d2d44',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: 'rgba(78, 205, 196, 0.5)',
    zIndex: 10,
  },
  logoText: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#4ECDC4',
    fontStyle: 'italic',
  },
  logoSubtext: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
    marginTop: -2,
  },
  loadingText: {
    marginTop: 30,
    fontSize: 14,
    color: '#888',
  },
});
