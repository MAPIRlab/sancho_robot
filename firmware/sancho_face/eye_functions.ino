#include <Arduino.h>
#include <TFT_eSPI.h>
extern TFT_eSPI tft;                      // usar instancia del .ino principal

#define USE_DMA
#define BUFFER_SIZE 1024
#ifdef USE_DMA
  #define BUFFERS 2
#else
  #define BUFFERS 1
#endif
extern uint16_t pbuffer[BUFFERS][BUFFER_SIZE];
extern bool     dmaBuf;

#include "config.h"                       // trae EyeRuntime, macros, eyeInfo, etc.

// Definición ÚNICA del array de runtime de ojos
EyeRuntime eye[NUM_EYES];

// Canal serie compartido
extern String incomingData;

// (si necesitas startTime para FPS)
extern uint32_t startTime;

//definir IRIS_STATIC
uint8_t IRIS_STATIC = 128;

const uint8_t ease[] = { // Ease in/out curve for eye movements 3*t^2-2*t^3 
0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 3, // T 
3, 3, 4, 4, 4, 5, 5, 6, 6, 7, 7, 8, 9, 9, 10, 10, // h
11, 12, 12, 13, 14, 15, 15, 16, 17, 18, 18, 19, 20, 21, 22, 23, // x
24, 25, 26, 27, 27, 28, 29, 30, 31, 33, 34, 35, 36, 37, 38, 39, // 2
40, 41, 42, 44, 45, 46, 47, 48, 50, 51, 52, 53, 54, 56, 57, 58, // A
60, 61, 62, 63, 65, 66, 67, 69, 70, 72, 73, 74, 76, 77, 78, 80, // l
81, 83, 84, 85, 87, 88, 90, 91, 93, 94, 96, 97, 98, 100, 101, 103, // e
104, 106, 107, 109, 110, 112, 113, 115, 116, 118, 119, 121, 122, 124, 125, 127, // c
128, 130, 131, 133, 134, 136, 137, 139, 140, 142, 143, 145, 146, 148, 149, 151, // J
152, 154, 155, 157, 158, 159, 161, 162, 164, 165, 167, 168, 170, 171, 172, 174, // a
175, 177, 178, 179, 181, 182, 183, 185, 186, 188, 189, 190, 192, 193, 194, 195, // c
197, 198, 199, 201, 202, 203, 204, 205, 207, 208, 209, 210, 211, 213, 214, 215, // o
216, 217, 218, 219, 220, 221, 222, 224, 225, 226, 227, 228, 228, 229, 230, 231, // b
232, 233, 234, 235, 236, 237, 237, 238, 239, 240, 240, 241, 242, 243, 243, 244, // s
245, 245, 246, 246, 247, 248, 248, 249, 249, 250, 250, 251, 251, 251, 252, 252, // o
252, 253, 253, 253, 254, 254, 254, 254, 254, 255, 255, 255, 255, 255, 255, 255 }; // n

#ifdef AUTOBLINK
uint32_t timeOfLastBlink = 0;   // momento del último parpadeo
uint32_t timeToNextBlink = 0;   // tiempo aleatorio hasta el siguiente
#endif

// ============================================================
//  INIT
// ============================================================
void initEyes(void) {
  Serial.println("Inicializando ojos...");
  for (uint8_t e = 0; e < NUM_EYES; e++) {
    eye[e].tft_cs      = eyeInfo[e].select;
    eye[e].blink.state = NOBLINK;
    eye[e].xposition   = eyeInfo[e].xposition;

    pinMode(eye[e].tft_cs, OUTPUT);
    digitalWrite(eye[e].tft_cs, LOW);
    if (eyeInfo[e].wink >= 0) pinMode(eyeInfo[e].wink, INPUT_PULLUP);
  }
  startTime = millis();
}

// ============================================================
//  LOOP LIGERO DE ACTUALIZACIÓN (iris fijo)
// ============================================================
void updateEye() {
  frame(IRIS_STATIC);
}

// ============================================================
//  DRAW HELPERS
// ============================================================

// Toma un pixel de la esclera (RGB565)
static inline uint16_t sampleSclera(uint32_t sx, uint32_t sy) {
  return pgm_read_word(sclera + sy * SCLERA_WIDTH + sx);
}

// Comprueba si el pixel está cubierto por párpados en (x,y)
static inline bool pixelCoveredByLids(uint32_t x, uint32_t y, uint8_t uT, uint8_t lT) {
  // Si cualquiera de los mapas de párpados supera su umbral, ese pixel queda tapado (negro)
  if (pgm_read_byte(upper + y * SCREEN_WIDTH + x) <= uT) return true;
  if (pgm_read_byte(lower + y * SCREEN_WIDTH + x) <= lT) return true;
  return false;
}

// Devuelve true si el punto (ix,iy) cae dentro del disco del iris (según polar[] y escala),
// y en outColor deja el color tomado de la textura 'iris'
static inline bool pixelInsideIris(int32_t ix, int32_t iy,
                                   uint16_t irisScale, uint16_t &outColor) {
  if (iy < 0 || iy >= IRIS_HEIGHT || ix < 0 || ix >= IRIS_WIDTH) return false;

  uint16_t p = pgm_read_word(polar + iy * IRIS_WIDTH + ix);
  uint16_t r = (p & 0x7F);                 // 0..127
  if (r == 127) return false;              // ← fuera del círculo: no pintar iris

  uint16_t a = (IRIS_MAP_WIDTH * (p >> 7)) / 512;
  uint16_t d = (irisScale * r) >> 7;       // 0..126 si scale=128

  if (d >= IRIS_MAP_HEIGHT) return false;

  outColor = pgm_read_word(iris + d * IRIS_MAP_WIDTH + a);
  return true;
}


// ============================================================
//  RENDER: Esclera → Iris completo → Máscara párpados
// ============================================================
void drawEye(
  uint8_t e,
  uint16_t irisScale,
  uint32_t scleraX, uint32_t scleraY,
  uint8_t  uT, uint8_t lT)
{
  uint32_t screenX, screenY, scleraXsave = scleraX;
  int32_t  irisX, irisY;
  uint32_t pixels = 0;
  uint16_t color;

  // Centro del iris respecto a la esclera (alineación básica)
  irisY = scleraY - (SCLERA_HEIGHT - IRIS_HEIGHT) / 2;

  // Ajuste de dirección del mapa de párpados para ojo izq/der
  uint16_t lidXStart = (e ? 0 : SCREEN_WIDTH - 1);
  int16_t  lidXStep  = (e ? +1 : -1);

  digitalWrite(eye[e].tft_cs, LOW);
  tft.startWrite();
  tft.setAddrWindow(eye[e].xposition, 0, SCREEN_WIDTH, SCREEN_HEIGHT);

  for (screenY = 0; screenY < SCREEN_HEIGHT; screenY++, scleraY++, irisY++) {
    scleraX = scleraXsave;
    irisX   = scleraXsave - (SCLERA_WIDTH - IRIS_WIDTH) / 2;
    uint16_t lidX = lidXStart;

    for (screenX = 0; screenX < SCREEN_WIDTH; screenX++, scleraX++, irisX++, lidX += lidXStep) {

      // 1) Párpados: si cubren, pintamos negro (o podrías pintar color de párpado)
      if (pixelCoveredByLids(lidX, screenY, uT, lT)) {
        color = 0x0000; // negro
      } else {
        // 2) Intentar iris (pupila incluida). Si no cae dentro, pintamos esclera.
        uint16_t irisColor;
        if (pixelInsideIris(irisX, irisY, irisScale, irisColor)) {
          color = irisColor;               // Iris/pupila (capa superior)
        } else {
          color = sampleSclera(scleraX, scleraY); // verde
        }
      }

      // Empujar al buffer (RGB565 big-endian)
      uint16_t be = (color >> 8) | (color << 8);
      *(&pbuffer[dmaBuf][0] + pixels++) = be;

      if (pixels >= BUFFER_SIZE) {
        yield();
        #ifdef USE_DMA
          tft.pushPixelsDMA(&pbuffer[dmaBuf][0], pixels);
          dmaBuf = !dmaBuf;
        #else
          tft.pushPixels(pbuffer, pixels);
        #endif
        pixels = 0;
      }
    }
  }

  if (pixels) {
    #ifdef USE_DMA
      tft.pushPixelsDMA(&pbuffer[dmaBuf][0], pixels);
    #else
      tft.pushPixels(pbuffer, pixels);
    #endif
  }

  tft.endWrite();
  digitalWrite(eye[e].tft_cs, HIGH);
}

// ============================================================
//  ANIMACIÓN POR FRAME (movimiento, parpadeo, emociones)
// ============================================================
void frame(uint16_t iScale) {
  static uint8_t  eyeIndex = 0;
  static uint32_t frames = 0;
  uint32_t t = micros();

  if (!(++frames & 255)) {
    // opcional: medir FPS
    // float elapsed = (millis() - startTime) / 1000.0;
    // if (elapsed) Serial.println((uint16_t)(frames / elapsed));
  }

  // ---------- LECTURA SERIE PARA EMOCIONES ----------
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '0') { incomingData = ""; } else { incomingData += c; }
  }

  if (incomingData.length() > 0) {
    String emotion = incomingData;
    incomingData = "";
    // Ajusta aquí tus presets de párpados y offsets si quieres
    if (emotion == "happy")      { uThreshold = 10;  lThreshold = 110; }
    else if (emotion == "surprised"){ uThreshold = 1;   lThreshold = 1;   }
    else if (emotion == "sad")   { uThreshold = 150; lThreshold = 20;  }
    else if (emotion == "angry") { uThreshold = 200; lThreshold = 250; }
    else if (emotion == "bored") { uThreshold = 100; lThreshold = 10;  }
    else if (emotion == "neutral"){uThreshold = 40;  lThreshold = 50;  }
    else if (emotion == "suspicious"){uThreshold = 150; lThreshold = 254;  }
  }

  // ---------- MOVIMIENTO AUTÓNOMO XY ----------
  static bool     eyeInMotion = false;
  static int16_t  eyeOldX = 512, eyeOldY = 512, eyeNewX = 512, eyeNewY = 512;
  static uint32_t eyeMoveStartTime = 0L;
  static int32_t  eyeMoveDuration  = 0L;

  int32_t dt = t - eyeMoveStartTime;
  int16_t eyeX, eyeY;

  if (eyeInMotion) {
    if (dt >= eyeMoveDuration) {
      eyeInMotion      = false;
      eyeMoveDuration  = random(3000000); // parada 0-3 s
      eyeMoveStartTime = t;
      eyeX = eyeOldX = eyeNewX;
      eyeY = eyeOldY = eyeNewY;
    } else {
      uint16_t e = ease[255 * dt / eyeMoveDuration] + 1;
      eyeX = eyeOldX + (((eyeNewX - eyeOldX) * e) / 256);
      eyeY = eyeOldY + (((eyeNewY - eyeOldY) * e) / 256);
    }
  } else {
    eyeX = eyeOldX; eyeY = eyeOldY;
    if (dt > eyeMoveDuration) {
      int16_t dx, dy; uint32_t d;
      do {
        eyeNewX = random(1024);
        eyeNewY = random(1024);
        dx = (eyeNewX * 2) - 1023;
        dy = (eyeNewY * 2) - 1023;
      } while ((d = (dx * dx + dy * dy)) > (1023 * 1023));
      eyeMoveDuration  = random(72000, 144000); // ~1/14 - ~1/7 s
      eyeMoveStartTime = t;
      eyeInMotion      = true;
    }
  }

  // Escalar a coordenadas de texturas
  int32_t sx = map(eyeX, 0, 1023, 0, SCLERA_WIDTH  - SCREEN_WIDTH);
  int32_t sy = map(eyeY, 0, 1023, 0, SCLERA_HEIGHT - SCREEN_HEIGHT);

  // Cruzado leve para convergencia
  if (NUM_EYES > 1) {
    if (eyeIndex == 1) sx += 4;
    else               sx -= 4;
  }

  // ---------- PARPADEO (AUTO + GUIÑOS) ----------
  #ifdef AUTOBLINK
    if ((t - timeOfLastBlink) >= timeToNextBlink) {
      timeOfLastBlink = t;
      uint32_t blinkDuration = random(36000, 72000);
      for (uint8_t e = 0; e < NUM_EYES; e++) {
        if (eye[e].blink.state == NOBLINK) {
          eye[e].blink.state     = ENBLINK;
          eye[e].blink.startTime = t;
          eye[e].blink.duration  = blinkDuration;
        }
      }
      timeToNextBlink = blinkDuration * 3 + random(4000000);
    }
  #endif

  // Mantener/avanzar estados de parpadeo
  if (eye[eyeIndex].blink.state) {
    if ((t - eye[eyeIndex].blink.startTime) >= eye[eyeIndex].blink.duration) {
      if (++eye[eyeIndex].blink.state > DEBLINK) {
        eye[eyeIndex].blink.state = NOBLINK;
      } else {
        eye[eyeIndex].blink.duration *= 2;
        eye[eyeIndex].blink.startTime = t;
      }
    }
  } else {
    // Botones de blink/wink si los tienes
    if ((eyeInfo[eyeIndex].wink >= 0) &&
        (digitalRead(eyeInfo[eyeIndex].wink) == LOW)) {
      eye[eyeIndex].blink.state     = ENBLINK;
      eye[eyeIndex].blink.startTime = t;
      eye[eyeIndex].blink.duration  = random(45000, 90000);
    }
  }

  // Aplicar progresión de parpadeo a umbrales (suaviza cierre/apertura)
  uint8_t uT = uThreshold, lT = lThreshold;
  if (eye[eyeIndex].blink.state) {
    uint32_t s = (t - eye[eyeIndex].blink.startTime);
    if (s >= eye[eyeIndex].blink.duration) s = 255;
    else s = 255 * s / eye[eyeIndex].blink.duration;
    s  = (eye[eyeIndex].blink.state == DEBLINK) ? 1 + s : 256 - s;

    // Mezcla hacia 254 (cerrado) en el transcurso del blink
    uT = (uThreshold * s + 254 * (257 - s)) / 256;
    lT = (lThreshold * s + 254 * (257 - s)) / 256;
  }

  // ---------- DIBUJO DE ESTE OJO ----------
  drawEye(eyeIndex, iScale, sx, sy, uT, lT);

  // Siguiente ojo (si hay 2)
  if (++eyeIndex >= NUM_EYES) eyeIndex = 0;
}

