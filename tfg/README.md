# 🤖 Sancho HRI System

[![Build](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/eulogioqt/sancho)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

**Sancho** is a complete Human–Robot Interaction system based on **ROS&nbsp;2 Humble**, designed to enable natural, expressive and multimodal interactions through voice, vision, logic and web interfaces.

The system combines:
- 🔊 Speech-to-text and text-to-speech modules.
- 👁️ Real-time facial recognition and memory.
- 🧠 Intent understanding powered by LLMs.
- 🌐 A modern web interface for full control and monitoring.
- 😶 Physical control of robot facial expression (LEDs, ESP32).

> 💡 Built with a **modular architecture**, Sancho is fully extensible, cloud/local ready, and supports advanced real-time interaction.

---

## 🧩 Core Components

| Component          | Description                                                        |
|--------------------|--------------------------------------------------------------------|
| `hri_audio`        | Audio input, VAD, hotword detection and chunking for STT.         |
| `speech_tools`     | Manages local/cloud TTS and STT models like Whisper, Piper, etc.  |
| `llm_tools`        | Loads and uses LLMs and embeddings dynamically.                   |
| `hri_vision`       | Real-time face detection and recognition with lightweight DB.     |
| `sancho_ai`        | Central logic: extracts intents and orchestrates robot actions.   |
| `mouth_controller` | Controls LED mouth (and soon eyes) based on voice/emotion.        |
| `ros2web`          | Real-time ROS ↔ Web communication via WebSockets.                 |
| `sancho_web_assistant`       | REST API backend for managing models, logs, and face data.        |
| `rumi_web`         | Web dashboard for face database and interaction statistics.       |
| `web_interface`    | React + Vite frontend for user interaction and robot control.     |

---

# 🚀 Complete Installation Guide (Ubuntu 22.04)

This guide will get your system fully running from scratch, including ROS 2, Python dependencies, Node.js, ESP32 firmware, and tests.

---

## 1. Install ROS 2 Humble (Official Method)

Follow the official guide:  
📎 https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html

### Set UTF-8 Locale

```
locale  # check for UTF-8

sudo apt update && sudo apt install locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

locale  # verify
```

### Add ROS 2 APT Source

```
sudo apt install software-properties-common
sudo add-apt-repository universe
```

```
sudo apt update && sudo apt install curl -y
export ROS_APT_SOURCE_VERSION=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F "tag_name" | awk -F\" '{print $4}')
curl -L -o /tmp/ros2-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.$(. /etc/os-release && echo $VERSION_CODENAME)_all.deb" # If using Ubuntu derivates use $UBUNTU_CODENAME
sudo apt install /tmp/ros2-apt-source.deb
```

### Install ROS 2 Packages

```
sudo apt update
sudo apt upgrade
```

```
sudo apt install ros-humble-desktop
```

```
sudo apt install ros-dev-tools
```

### Source ROS

```
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

---

## 2. Clone and Set Up the Project

```
mkdir -p ~/sancho_ws/src
cd ~/sancho_ws/src
git clone https://github.com/eulogioqt/sancho.git .
```

Install Python dependencies:

```
python3 -m pip install -r requirements.txt
```

---

## 3. Build the ROS 2 Workspace

```
cd ~/sancho_ws
colcon build
source install/setup.bash
```

(Optional: auto-source on shell startup)

```
echo "source ~/sancho_ws/install/setup.bash" >> ~/.bashrc
```

---

## 4. Launch Everything 🚀

This will start **ALL ROS 2 nodes**: audio, vision, LLMs, REST, WebSockets, physical control...

```
ros2 launch hri_audio the_launch.py
```

> ⚠️ Note: the web must be built before using this launch file.

---

## 5. Set Up the Web Interface (React + Vite)

### Install Node.js 18+

```
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

### Install Dependencies

```
cd ~/sancho_ws/src/web_interface
npm install
```

### Development Mode

```
npm run dev
```

Visit [http://localhost:5173](http://localhost:5173)

### Production Build

```
npm run build
```

> Required for `the_launch.py` to serve the web correctly.

---

## 6. Upload the ESP32 Firmware

Install the [Arduino IDE](https://www.arduino.cc/en/software) or [Arduino CLI](https://arduino.github.io/arduino-cli/installation/).

1. Open `face_code/user.cpp`
2. Select your board (ESP32)
3. Compile and upload the sketch

> This controls the mouth (RGB LED strip) and emotion expressions.

---

## 7. Run Unit and Load Tests

### Python Unit Tests (pytest)

```
cd ~/sancho_ws
python3 -m pytest src/**/tests/
```

### Web Load Test (K6)

```
sudo apt install k6
k6 run web_interface/tests/load_test.js
```

---

# ✅ System Ready

If you followed all steps:

- ROS 2 is fully running with audio, vision, logic and REST services.
- The web interface is live at [http://localhost:5173](http://localhost:5173) (dev) or integrated in production.
- ESP32 controls the mouth animations in sync with speech.
- You can interact with Sancho via voice or web, with full multimodal intelligence.

✨ Congratulations – you’ve deployed a fully modular, expressive, multimodal HRI system like a pro!

---

## 👤 Author

**Eulogio Quemada Torres**  
University of Málaga – MAPIR Group  
eulogioquemada@uma.es
