// ====================== config.h ======================
#pragma once
#include <Arduino.h>

// ---------- RESOLUCIÓN / NÚMERO DE OJOS ----------
#define SCREEN_WIDTH   240
#define SCREEN_HEIGHT  240
#define NUM_EYES       2

// ---------- PINS Y ROTACIONES ----------
#define TFT1_CS     22
#define TFT2_CS     21
#define TFT_1_ROT   3
#define TFT_2_ROT   3
#define EYE_1_XPOSITION  0
#define EYE_2_XPOSITION  0
#define LH_WINK_PIN  -1
#define RH_WINK_PIN  -1

#define DISPLAY_BACKLIGHT  -1
#define BACKLIGHT_MAX      255

// ---------- ASSETS (elige uno) ----------
#include "data/normalEye.h" // Debe aportar sclera[], iris[], polar[], upper[], lower[] y tamaños

// ---------- ESTRUCTURA DE eyeInfo ----------
typedef struct {
  int8_t  select;     // pin CS
  int8_t  wink;       // pin de guiño (-1 si no)
  uint8_t rotation;   // rotación 0..3
  int16_t xposition;  // offset X
} eyeInfo_t;

#if (NUM_EYES == 2)
  static eyeInfo_t eyeInfo[] = {
    { TFT1_CS, LH_WINK_PIN, TFT_1_ROT, EYE_1_XPOSITION },
    { TFT2_CS, RH_WINK_PIN, TFT_2_ROT, EYE_2_XPOSITION },
  };
#else
  static eyeInfo_t eyeInfo[] = {
    { TFT1_CS, LH_WINK_PIN, TFT_1_ROT, EYE_1_XPOSITION },
  };
#endif

// ---------- PARPADEO / ESTADOS COMPARTIDOS ----------
#define NOBLINK  0
#define ENBLINK  1
#define DEBLINK  2

typedef struct {
  uint8_t  state;       // NOBLINK/ENBLINK/DEBLINK
  uint32_t duration;    // micros
  uint32_t startTime;   // micros
} eyeBlink;

// Estructura de runtime de cada ojo
typedef struct {
  int16_t   tft_cs;
  eyeBlink  blink;
  int16_t   xposition;
} EyeRuntime;

// ---------- EXTERN COMPARTIDOS (definidos en UN .ino) ----------
extern EyeRuntime eye[NUM_EYES];   // definido en eye_functions.ino
extern String incomingData;        // definido en Animated_Eyes_2.ino

// ---------- OPCIONES DE COMPORTAMIENTO ----------
#define AUTOBLINK
// #define TRACKING    // si quieres que el párpado superior siga la mirada
// ===================================================
