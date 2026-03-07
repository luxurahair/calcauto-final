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
      // Fade out after 2.5 seconds
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
        ]).start(() => {
          onFinish();
        });
      }, 2500);
    }
  }, [visible]);

  if (!visible) return null;

  return (
    <Animated.View style={[styles.container, { opacity: fadeAnim }]}>
      <Animated.View style={[styles.logoContainer, { transform: [{ scale: scaleAnim }] }]}>
        {/* CSS comet ring - only on web */}
        {Platform.OS === 'web' && <CometRingWeb />}

        {/* Logo center */}
        <View style={styles.logoCenter}>
          <Text style={styles.logoText}>CalcAuto</Text>
          <Text style={styles.logoSubtext}>AiPro</Text>
        </View>
      </Animated.View>

      <Text style={styles.loadingText}>Chargement...</Text>
    </Animated.View>
  );
};

// Web-only comet ring using CSS animations
const CometRingWeb = () => {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  if (!mounted) return null;

  return (
    <>
      {/* Inject CSS keyframes */}
      <style
        dangerouslySetInnerHTML={{
          __html: `
            @keyframes cometSpin {
              from { transform: rotate(0deg); }
              to { transform: rotate(360deg); }
            }
            @keyframes ringPulse {
              0%, 100% { opacity: 0.25; }
              50% { opacity: 0.5; }
            }
            .comet-trail {
              position: absolute;
              width: 180px;
              height: 180px;
              border-radius: 50%;
              animation: cometSpin 2s linear infinite;
            }
            .comet-trail-1 {
              border: 3px solid transparent;
              border-top-color: rgba(78,205,196,0.8);
              border-right-color: rgba(78,205,196,0.4);
              filter: blur(1px);
            }
            .comet-trail-2 {
              border: 2px solid transparent;
              border-top-color: rgba(78,205,196,0.3);
              filter: blur(3px);
              width: 186px;
              height: 186px;
            }
            .comet-trail-3 {
              border: 2px solid transparent;
              border-top-color: rgba(78,205,196,0.15);
              border-right-color: rgba(78,205,196,0.08);
              filter: blur(5px);
              width: 192px;
              height: 192px;
            }
            .comet-head-orbit {
              position: absolute;
              width: 180px;
              height: 180px;
              animation: cometSpin 2s linear infinite;
            }
            .comet-head {
              position: absolute;
              top: -7px;
              left: 50%;
              margin-left: -7px;
              width: 14px;
              height: 14px;
              border-radius: 50%;
              background: radial-gradient(circle, #fff 0%, #4ECDC4 40%, rgba(78,205,196,0) 70%);
              box-shadow: 0 0 8px 3px rgba(78,205,196,0.7), 0 0 20px 8px rgba(78,205,196,0.3), 0 0 35px 12px rgba(78,205,196,0.1);
            }
          `,
        }}
      />

      {/* Outer glow ring with pulse */}
      <div
        style={{
          position: 'absolute',
          width: 190,
          height: 190,
          borderRadius: '50%',
          border: '1px solid rgba(78,205,196,0.2)',
          animation: 'ringPulse 3s ease-in-out infinite',
        }}
      />

      {/* Static orbit ring */}
      <div
        style={{
          position: 'absolute',
          width: 172,
          height: 172,
          borderRadius: '50%',
          border: '2px solid rgba(78,205,196,0.25)',
        }}
      />

      {/* Comet trail layers (outer glow → inner bright) */}
      <div className="comet-trail comet-trail-3" />
      <div className="comet-trail comet-trail-2" />
      <div className="comet-trail comet-trail-1" />

      {/* Comet head */}
      <div className="comet-head-orbit">
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
    borderColor: 'rgba(78, 205, 196, 0.6)',
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
