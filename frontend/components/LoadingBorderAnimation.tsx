import React, { useRef, useEffect } from 'react';
import { View, Text, Animated, Easing, Dimensions, ActivityIndicator } from 'react-native';
import { loadingStyles } from '../styles/homeStyles';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

const LoadingBorderAnimation = ({ loading }: { loading: boolean }) => {
  const animatedValue = useRef(new Animated.Value(0)).current;
  
  useEffect(() => {
    if (loading) {
      Animated.loop(
        Animated.timing(animatedValue, {
          toValue: 1,
          duration: 2000,
          easing: Easing.linear,
          useNativeDriver: false,
        })
      ).start();
    } else {
      animatedValue.setValue(0);
    }
  }, [loading, animatedValue]);

  if (!loading) return null;

  // Calculate the perimeter for the light to travel
  const perimeter = 2 * (SCREEN_WIDTH + SCREEN_HEIGHT);
  
  // Interpolate position around the border
  const lightPosition = animatedValue.interpolate({
    inputRange: [0, 0.25, 0.5, 0.75, 1],
    outputRange: [0, SCREEN_WIDTH, SCREEN_WIDTH + SCREEN_HEIGHT, 2 * SCREEN_WIDTH + SCREEN_HEIGHT, perimeter],
  });

  // Calculate X and Y based on position around rectangle
  const translateX = animatedValue.interpolate({
    inputRange: [0, 0.25, 0.5, 0.75, 1],
    outputRange: [0, SCREEN_WIDTH - 20, SCREEN_WIDTH - 20, 0, 0],
  });
  
  const translateY = animatedValue.interpolate({
    inputRange: [0, 0.25, 0.5, 0.75, 1],
    outputRange: [0, 0, SCREEN_HEIGHT - 20, SCREEN_HEIGHT - 20, 0],
  });

  return (
    <View style={loadingStyles.container}>
      {/* Border glow effect */}
      <View style={loadingStyles.borderContainer}>
        {/* Top border */}
        <Animated.View 
          style={[
            loadingStyles.topBorder,
            {
              opacity: animatedValue.interpolate({
                inputRange: [0, 0.125, 0.25, 1],
                outputRange: [1, 0.5, 0.2, 0.2],
              }),
            }
          ]} 
        />
        {/* Right border */}
        <Animated.View 
          style={[
            loadingStyles.rightBorder,
            {
              opacity: animatedValue.interpolate({
                inputRange: [0, 0.25, 0.375, 0.5, 1],
                outputRange: [0.2, 1, 0.5, 0.2, 0.2],
              }),
            }
          ]} 
        />
        {/* Bottom border */}
        <Animated.View 
          style={[
            loadingStyles.bottomBorder,
            {
              opacity: animatedValue.interpolate({
                inputRange: [0, 0.5, 0.625, 0.75, 1],
                outputRange: [0.2, 1, 0.5, 0.2, 0.2],
              }),
            }
          ]} 
        />
        {/* Left border */}
        <Animated.View 
          style={[
            loadingStyles.leftBorder,
            {
              opacity: animatedValue.interpolate({
                inputRange: [0, 0.75, 0.875, 1],
                outputRange: [0.2, 1, 0.5, 1],
              }),
            }
          ]} 
        />
      </View>
      
      {/* Moving light dot */}
      <Animated.View
        style={[
          loadingStyles.lightDot,
          {
            transform: [
              { translateX },
              { translateY },
            ],
          },
        ]}
      />
      
      {/* Center loading indicator */}
      <View style={loadingStyles.centerContainer}>
        <View style={loadingStyles.logoContainer}>
          <Text style={loadingStyles.logoText}>CalcAuto</Text>
          <Text style={loadingStyles.logoSubText}>AiPro</Text>
        </View>
        <ActivityIndicator size="large" color="#4ECDC4" style={loadingStyles.spinner} />
        <Text style={loadingStyles.loadingText}>Chargement des programmes...</Text>
      </View>
    </View>
  );
};

export { LoadingBorderAnimation };
