// An adaption of the "UncannyEyes" sketch (see eye_functions tab)
// for the TFT_eSPI library. As written the sketch is for driving
// two TFT displays.

// The size of the displayed eye is determined by the screen size and
// resolution. The eye image is 128 pixels wide. In humans the palpebral
// fissure (open eye) width is about 30mm so a low resolution, large
// pixel size display works best to show a scale eye image. Note that
// display manufacturers usually quote the diagonal measurement, so a
// 128 x 128 1.7" display or 128 x 160 2" display is about right.

// The number of displays and chip selects used are defined in the
// config.h tab. The display count can be set to 1. If using one
// TFT and the chip select for that display is already defined in
// the TFT_eSPI library then change the chip select pins to -1 in the
// "config.h" tab.

// The wiring for 2 TFT displays to an ESP32 is described in the
// "wiring" tab of this sketch.

// Configuration settings for the eye, eye style, display count,
// chip selects and x offsets can be defined in the sketch "config.h" tab.

// Performance (frames per second = fps) can be improved by using
// DMA (for SPI displays only) on ESP32 and STM32 processors. Use
// as high a SPI clock rate as is supported by the display. 27MHz
// minimum, some displays can be operated at higher clock rates in
// the range 40-80MHz.

// Single defaultEye performance for different processors
//                                  No DMA   With DMA
// ESP8266 (160MHz CPU) 40MHz SPI   36 fps
// ESP32 27MHz SPI                  53 fps     85 fps
// ESP32 40MHz SPI                  67 fps    102 fps
// ESP32 80MHz SPI                  82 fps    116 fps // Note: Few displays work reliably at 80MHz
// STM32F401 55MHz SPI              44 fps     90 fps
// STM32F446 55MHz SPI              83 fps    155 fps
// STM32F767 55MHz SPI             136 fps    197 fps



// DMA can be used with RP2040, STM32 and ESP32 processors when the interface
// is SPI, uncomment the next line:
#define USE_DMA



// Load TFT driver library
#include <SPI.h>
#include <TFT_eSPI.h>
TFT_eSPI tft;           // A single instance is used for 1 or 2 displays



// A pixel buffer is used during eye rendering
#define BUFFER_SIZE 1024 // 128 to 1024 seems optimum

#ifdef USE_DMA
  #define BUFFERS 2      // 2 toggle buffers with DMA
#else
  #define BUFFERS 1      // 1 buffer for no DMA
#endif

uint16_t pbuffer[BUFFERS][BUFFER_SIZE]; // Pixel rendering buffer
bool     dmaBuf   = 0;                  // DMA buffer selection



#include "config.h"     // ****** CONFIGURATION IS DONE IN HERE ******


// Variables/funciones compartidas
extern EyeRuntime eye[NUM_EYES];  // definido en eye_functions.ino
String incomingData;              // definido aquí

// Prototipos de funciones implementadas en eye_functions.ino
void initEyes(void);
void updateEye(void);

// (si tienes user_setup/user_loop en otra pestaña)
extern void user_setup(void);
extern void user_loop(String incomingData);

uint32_t startTime;  // For FPS indicator

uint8_t uThreshold = 40;  // umbral párpado superior
uint8_t lThreshold = 50;  // umbral párpado inferior

// INITIALIZATION -- runs once at startup ----------------------------------
void setup(void) {
  
  Serial.begin(9600);
  //while (!Serial);
  Serial.println("Starting");

  #if defined(DISPLAY_BACKLIGHT) && (DISPLAY_BACKLIGHT >= 0)
    // Enable backlight pin, initially off
    Serial.println("Backlight turned off");
    pinMode(DISPLAY_BACKLIGHT, OUTPUT);
    digitalWrite(DISPLAY_BACKLIGHT, LOW);
  #endif

  // User call for additional features
  user_setup();

  // Initialise the eye(s), this will set all chip selects low for the tft.init()
  initEyes();

  // Initialise TFT
  Serial.println("Initialising displays");
  tft.init(); // Inicializar cada pantalla por separado
  
  #ifdef USE_DMA
    tft.initDMA();
  #endif

  // Raise chip select(s) so that displays can be individually configured
  digitalWrite(eye[0].tft_cs, HIGH);
  if (NUM_EYES > 1) digitalWrite(eye[1].tft_cs, HIGH);

  for (uint8_t e = 0; e < NUM_EYES; e++) {
    digitalWrite(eye[e].tft_cs, LOW);
    tft.setRotation(eyeInfo[e].rotation);
    tft.fillScreen(TFT_BLACK);
    digitalWrite(eye[e].tft_cs, HIGH);
  }

  #if defined(DISPLAY_BACKLIGHT) && (DISPLAY_BACKLIGHT >= 0)
    Serial.println("Backlight now on!");
    analogWrite(DISPLAY_BACKLIGHT, BACKLIGHT_MAX);
  #endif

  startTime = millis(); // For frame-rate calculation
  Serial.println("Initialization done!");
  Serial.println("Emotions available:");
  Serial.println("-happy");
  Serial.println("-sad");
  Serial.println("-angry");
  Serial.println("-bored");
  Serial.println("-lwink");
  Serial.println("-rwink");
  Serial.println("-suspicious");
  Serial.println("-surprised");
  Serial.println("-yes");
  Serial.println("-no");
  
}

// MAIN LOOP -- runs continuously after setup() ----------------------------
void loop() {
  loop_mouth();
  updateEye();
}

void loop_mouth() {
  while (Serial.available() > 0) {
    char c = Serial.read();

    if (c == '0') {
      user_loop(incomingData);
      incomingData = "";  // Reinicia para el siguiente mensaje
    } else {
      incomingData += c;
    }
  }

  user_loop("");
}

