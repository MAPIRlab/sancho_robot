#if 1 // Change to 0 to disable this code (must enable ONE user*.cpp only!)
// This file provides a crude way to "drop in" user code to the eyes,
// allowing concurrent operations without having to maintain a bunch of
// special derivatives of the eye code (which is still undergoing a lot
// of development). Just replace the source code contents of THIS TAB ONLY,
// compile and upload to board. Shouldn't need to modify other eye code.

// FOR CONTROLLING THE LED STRIP (WS2812B)

#include <Adafruit_NeoPixel.h>
#include "esp_sleep.h"
#include "math.h"

#define PIN_WS2812B 17     // ESP32 GPIO pin connected to the LED strip
#define NUM_PIXELS 12      // Number of LEDs on the strip
#define BASE_BRIGHTNESS 80 // Base LED brightness (0–255)

Adafruit_NeoPixel ws2812b(NUM_PIXELS, PIN_WS2812B, NEO_GRB + NEO_KHZ800);

// LED masks (bitmasks for LED positions)
const uint16_t LED_MASKS[] = {
    0b000000000000, // OFF
    0b000001100000, // LOW
    0b000011110000, // MEDIUM-LOW
    0b000111111000, // MEDIUM
    0b001111111100, // MEDIUM-HIGH
    0b011111111110  // HIGH
    0b111111111111  // FULL
};

enum Level
{
  LEVEL_OFF,
  LEVEL_LOW,
  LEVEL_MEDLOW,
  LEVEL_MED,
  LEVEL_MEDHIGH,
  LEVEL_HIGH
};
Level current_level = LEVEL_OFF;

enum SystemMode
{
  IDLE_MODE,
  LISTENING_MODE,
  THINKING_MODE,
  SPEAKING_MODE
};
SystemMode current_mode = IDLE_MODE;

extern String incomingData;
extern bool serial_data_available;

uint32_t current_color = 0;
uint16_t last_mask = 0;

// Mode-specific fixed colors
const uint32_t COLOR_LISTENING = ws2812b.Color(0, 0, 255);    // Blue
const uint32_t COLOR_THINKING = ws2812b.Color(85, 255, 255);  // Aqua
const uint32_t COLOR_SPEAKING = ws2812b.Color(255, 255, 255); // White

// Minecraft-style 16 color palette
struct NamedColor
{
  const char *name;
  uint32_t value;
};

NamedColor color_defs[] = {
    {"black", ws2812b.Color(0, 0, 0)},
    {"dark_blue", ws2812b.Color(0, 0, 170)},
    {"dark_green", ws2812b.Color(0, 170, 0)},
    {"dark_aqua", ws2812b.Color(0, 170, 170)},
    {"dark_red", ws2812b.Color(170, 0, 0)},
    {"dark_purple", ws2812b.Color(170, 0, 170)},
    {"gold", ws2812b.Color(255, 170, 0)},
    {"gray", ws2812b.Color(170, 170, 170)},
    {"dark_gray", ws2812b.Color(85, 85, 85)},
    {"blue", ws2812b.Color(85, 85, 255)},
    {"green", ws2812b.Color(85, 255, 85)},
    {"aqua", ws2812b.Color(85, 255, 255)},
    {"red", ws2812b.Color(255, 85, 85)},
    {"light_purple", ws2812b.Color(255, 85, 255)},
    {"yellow", ws2812b.Color(255, 255, 85)},
    {"white", ws2812b.Color(255, 255, 255)}};

// Set LEDs based on a mask and color
void lightLEDs(uint16_t mask, uint32_t color)
{
  last_mask = mask;
  for (int i = 0; i < NUM_PIXELS; ++i)
  {
    ws2812b.setPixelColor(i, (mask & (1 << i)) ? color : 0);
  }
  ws2812b.show();
}

// Re-apply last mask with current color
void applyCurrentColor()
{
  lightLEDs(last_mask, current_color);
}

// Called once near the end of the setup() function.
void user_setup(void)
{
  ws2812b.begin();
  ws2812b.setBrightness(BASE_BRIGHTNESS);
  esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_ALL);
  delay(1000);

  current_mode = IDLE_MODE;
  ws2812b.clear();
  ws2812b.show();
}

// Listening animation: center-out waves of intensity
void animationListening()
{
  static uint32_t t_start = millis();
  uint32_t elapsed = millis() - t_start;

  const float speed = 0.005; // wave speed
  const int center = NUM_PIXELS / 2;

  for (int i = 0; i < NUM_PIXELS; ++i)
  {
    float distance = abs(i - center);
    float intensity = (sin((elapsed * speed) - distance) + 1.0) / 2.0; // [0,1]
    uint8_t r = (COLOR_LISTENING >> 16) & 0xFF;
    uint8_t g = (COLOR_LISTENING >> 8) & 0xFF;
    uint8_t b = COLOR_LISTENING & 0xFF;

    ws2812b.setPixelColor(i,
                          ws2812b.Color(
                              uint8_t(r * intensity),
                              uint8_t(g * intensity),
                              uint8_t(b * intensity)));
  }
  ws2812b.show();
  delay(30);
}

// Thinking animation: bouncing light
void animationThinking()
{
  static int index = 0;
  static int dir = 1;

  ws2812b.clear();
  ws2812b.setPixelColor(index, COLOR_THINKING);
  ws2812b.show();

  index += dir;
  if (index == NUM_PIXELS - 1 || index == 0)
    dir *= -1;
  delay(50);
}

// Called periodically during eye animation.
void user_loop(void)
{
  if (Serial.available() > 0)
  {
    incomingData = Serial.readStringUntil('\n');
    incomingData.trim();
    Serial.println("[LED] Received: " + incomingData);

    // Mode commands
    if (incomingData == "idle")
    {
      current_mode = IDLE_MODE;
      ws2812b.clear();
      ws2812b.show();
    }
    else if (incomingData == "listening")
    {
      current_mode = LISTENING_MODE;
    }
    else if (incomingData == "thinking")
    {
      current_mode = THINKING_MODE;
    }
    else if (incomingData == "speaking")
    {
      current_mode = SPEAKING_MODE;
      current_color = COLOR_SPEAKING;
      current_level = LEVEL_LOW;
      lightLEDs(LED_MASKS[current_level], current_color);
    }

    // Color change only in SPEAKING_MODE
    else if (current_mode == SPEAKING_MODE)
    {
      for (const auto &c : color_defs)
      {
        if (incomingData == c.name)
        {
          current_color = c.value;
          applyCurrentColor();
          return;
        }
      }

      // Level control (only in SPEAKING_MODE)
      if (incomingData == "off")
      {
        current_level = LEVEL_OFF;
      }
      else if (incomingData == "low")
      {
        current_level = LEVEL_LOW;
      }
      else if (incomingData == "medium_low")
      {
        current_level = LEVEL_MEDLOW;
      }
      else if (incomingData == "medium")
      {
        current_level = LEVEL_MED;
      }
      else if (incomingData == "medium_high")
      {
        current_level = LEVEL_MEDHIGH;
      }
      else if (incomingData == "high")
      {
        current_level = LEVEL_HIGH;
      }
      else
      {
        Serial.println("[LED] Unknown command");
        return;
      }
      lightLEDs(LED_MASKS[current_level], current_color);
    }
  }

  // Animation handling
  switch (current_mode)
  {
  case LISTENING_MODE:
    animationListening();
    break;
  case THINKING_MODE:
    animationThinking();
    break;
  case SPEAKING_MODE:
    delay(10); // passive
    break;
  case IDLE_MODE:
  default:
    delay(100);
    break;
  }
}

#endif // 0
