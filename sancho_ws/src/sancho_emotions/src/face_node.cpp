#include "rclcpp/rclcpp.hpp"
#include <std_msgs/msg/string.hpp>
#include <vector>
#include <cmath>
#include <algorithm>
#include <string>
#include <fstream>
#include <memory>
#include <portaudio.h>
#include <thread>
#include <chrono>
#include <cstdint>
#include <mutex>
#include <sstream>
#include <fcntl.h>
#include <unistd.h>
#include <termios.h>
#include <array>
#include <cstdio>
#include <cstdlib>

int configure_serial_port(int fd, int baudrate)
{
    struct termios options;
    if (tcgetattr(fd, &options) != 0)
    {
        return -1;
    }

    speed_t speed;
    switch (baudrate)
    {
    case 9600:
        speed = B9600;
        break;
    case 19200:
        speed = B19200;
        break;
    case 38400:
        speed = B38400;
        break;
    case 57600:
        speed = B57600;
        break;
    case 115200:
        speed = B115200;
        break;
    default:
        return -1;
    }

    cfsetispeed(&options, speed);
    cfsetospeed(&options, speed);
    options.c_cflag |= (CLOCAL | CREAD);
    options.c_cflag &= ~CSIZE;
    options.c_cflag |= CS8;
    options.c_cflag &= ~PARENB;
    options.c_cflag &= ~CSTOPB;
    options.c_cflag &= ~CRTSCTS;
    options.c_lflag = 0;
    options.c_oflag = 0;
    options.c_cc[VMIN] = 1;
    options.c_cc[VTIME] = 0;

    if (tcsetattr(fd, TCSANOW, &options) != 0)
    {
        return -1;
    }

    return 0;
}

// -------------------- Helpers para PulseAudio --------------------

static std::string run_cmd(const std::string &cmd) {
    std::array<char, 256> buf{};
    std::string out;
    FILE *pipe = popen(cmd.c_str(), "r");
    if (!pipe) return out;
    while (fgets(buf.data(), buf.size(), pipe) != nullptr) out += buf.data();
    pclose(pipe);
    while (!out.empty() && (out.back()=='\n' || out.back()=='\r' || out.back()==' ')) out.pop_back();
    return out;
}

static bool pulse_source_exists(const std::string &name) {
    if (name.empty()) return false;
    std::string cmd =
        "pactl list short sources | awk '{print $2}' | grep -Fx \"" + name + "\" || true";
    return !run_cmd(cmd).empty();
}

// ----------------------------------------------------------------

class FaceNode : public rclcpp::Node
{
public:
    FaceNode() : Node("face_node")
    {
        declare_parameter<double>("send_interval_sec", 0.1);
        get_parameter("send_interval_sec", chunk_send_interval_);
        RCLCPP_INFO(get_logger(), "Intervalo de envío configurado: %.2f s", chunk_send_interval_);

        std::vector<std::string> serial_paths = {"/dev/esp32", "/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2"};
        for (const auto &path : serial_paths)
        {
            serial_fd_ = open(path.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK);
            if (serial_fd_ != -1)
            {
                if (configure_serial_port(serial_fd_, 9600) == 0)
                {
                    RCLCPP_INFO(get_logger(), "Puerto serie abierto correctamente: %s", path.c_str());
                    break;
                }
                else
                {
                    close(serial_fd_);
                    serial_fd_ = -1;
                }
            }
        }

        if (serial_fd_ == -1)
        {
            RCLCPP_ERROR(get_logger(), "No se pudo abrir ningún puerto serie.");
            return;
        }

        send_to_esp32("idle");

        serial_thread_ = std::thread([this]()
                                     {
            std::string buffer;
            char c;
            while (rclcpp::ok())
            {
                ssize_t len = read(serial_fd_, &c, 1);
                if (len > 0)
                {
                    if (c == '0') {
                        buffer.clear();
                    } else {
                        buffer += c;
                    }
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(5));
            } });

        mode_subscription_ = create_subscription<std_msgs::msg::String>(
            "face/mode", 10,
            std::bind(&FaceNode::mode_callback, this, std::placeholders::_1));

        start_audio_monitoring();
    }

private:
    void mode_callback(const std_msgs::msg::String::SharedPtr msg)
    {
        static const std::vector<std::string> valid_modes = {"idle", "listening", "thinking", "speaking"};
        static const std::vector<std::string> valid_emotions = {"happy", "surprised", "sad", "angry", "bored", "suspicious", "neutral"};

        if (std::find(valid_modes.begin(), valid_modes.end(), msg->data) != valid_modes.end())
        {
            std::lock_guard<std::mutex> lock(mode_mutex_);
            current_mode_ = msg->data;
            RCLCPP_INFO(get_logger(), "Modo actualizado a: %s", current_mode_.c_str());
            for (int i = 0; i < 20; i++)
                send_to_esp32(current_mode_);
        }
        else if (std::find(valid_emotions.begin(), valid_emotions.end(), msg->data) != valid_emotions.end())
        {
            RCLCPP_INFO(get_logger(), "Emoción recibida: %s", msg->data.c_str());
            std::string modified = "1" + msg->data;
            for (int i = 0; i < 20; i++)
                send_to_esp32(modified);
        }
        else
        {
            RCLCPP_ERROR(get_logger(), "Mensaje recibido no reconocido: %s", msg->data.c_str());
        }
    }

    void start_audio_monitoring()
    {
        // *** Monitor objetivo: "lo que suena" en tu equipo (concretamente el USB C-Media) ***
        const std::string kDesiredPulseSource =
            "alsa_output.usb-C-Media_Electronics_Inc._USB_Audio_Device-00.analog-stereo.monitor";

        // Fijar PULSE_SOURCE solo para este proceso (sin tocar configuración global)
        if (pulse_source_exists(kDesiredPulseSource)) {
            setenv("PULSE_SOURCE", kDesiredPulseSource.c_str(), 1);
            RCLCPP_INFO(get_logger(), "Usando Pulse source (monitor): %s", kDesiredPulseSource.c_str());
        } else {
            // Fallback: monitor del sink por defecto
            std::string def_sink = run_cmd("pactl info | sed -n 's/Default Sink: //p' | head -n1");
            std::string fallback = def_sink.empty() ? "" : def_sink + ".monitor";
            if (!fallback.empty() && pulse_source_exists(fallback)) {
                setenv("PULSE_SOURCE", fallback.c_str(), 1);
                RCLCPP_WARN(get_logger(), "Monitor fijo no encontrado. Usando monitor del sink por defecto: %s",
                            fallback.c_str());
            } else {
                RCLCPP_ERROR(get_logger(),
                             "No se encontró el monitor objetivo ni el del sink por defecto. Abortando captura.");
                return;
            }
        }

        // Inicializa PortAudio DESPUÉS de fijar PULSE_SOURCE
        Pa_Initialize();

        // Seleccionar el dispositivo PortAudio llamado "pulse" (o fallback a "default")
        int selected_device = paNoDevice;
        int numDevices = Pa_GetDeviceCount();
        if (numDevices < 0) {
            RCLCPP_ERROR(get_logger(), "Pa_GetDeviceCount error: %s", Pa_GetErrorText(numDevices));
            return;
        }

        for (int i = 0; i < numDevices; ++i) {
            const PaDeviceInfo *info = Pa_GetDeviceInfo(i);
            if (!info || info->maxInputChannels <= 0) continue;
            std::string name = info->name ? info->name : "";
            if (name == "pulse") { selected_device = i; break; }
        }
        if (selected_device == paNoDevice) {
            for (int i = 0; i < numDevices; ++i) {
                const PaDeviceInfo *info = Pa_GetDeviceInfo(i);
                if (!info || info->maxInputChannels <= 0) continue;
                std::string name = info->name ? info->name : "";
                if (name == "default") { selected_device = i; break; }
            }
        }
        if (selected_device == paNoDevice) {
            for (int i = 0; i < numDevices; ++i) {
                const PaDeviceInfo *info = Pa_GetDeviceInfo(i);
                if (info && info->maxInputChannels > 0) { selected_device = i; break; }
            }
        }

        if (selected_device == paNoDevice) {
            RCLCPP_ERROR(get_logger(), "No hay dispositivo de entrada disponible en PortAudio.");
            return;
        }

        const PaDeviceInfo *deviceInfo = Pa_GetDeviceInfo(selected_device);
        sampleRate_ = deviceInfo->defaultSampleRate;
        size_t frames_per_chunk = 1024;

        PaStream *stream;
        PaStreamParameters inputParams;
        inputParams.device = selected_device;
        inputParams.channelCount = 1;
        inputParams.sampleFormat = paInt16;
        inputParams.suggestedLatency = deviceInfo->defaultLowInputLatency;
        inputParams.hostApiSpecificStreamInfo = nullptr;

        PaError err = Pa_OpenStream(
            &stream,
            &inputParams,
            nullptr,
            sampleRate_,
            frames_per_chunk,
            paClipOff,
            nullptr,
            nullptr);
        if (err != paNoError)
        {
            RCLCPP_ERROR(get_logger(), "No se pudo abrir el stream de audio: %s", Pa_GetErrorText(err));
            return;
        }

        Pa_StartStream(stream);
        RCLCPP_INFO(get_logger(), "Captura de audio iniciada: PortAudio '%s' con PULSE_SOURCE='%s'.",
                    deviceInfo->name, getenv("PULSE_SOURCE"));

        audio_thread_ = std::thread([this, stream, frames_per_chunk]()
                                    {
            std::vector<int16_t> buffer(frames_per_chunk);
            auto chunk_start = std::chrono::steady_clock::now();
            std::vector<int16_t> current_chunk;

            while (rclcpp::ok() && running_)
            {
                std::string mode;
                {
                    std::lock_guard<std::mutex> lock(mode_mutex_);
                    mode = current_mode_;
                }
                if (mode != "speaking")
                {
                    std::this_thread::sleep_for(std::chrono::milliseconds(100));
                    continue;
                }

                Pa_ReadStream(stream, buffer.data(), frames_per_chunk);
                current_chunk.insert(current_chunk.end(), buffer.begin(), buffer.end());

                auto now = std::chrono::steady_clock::now();
                double elapsed = std::chrono::duration<double>(now - chunk_start).count();

                if (elapsed >= chunk_send_interval_)
                {
                    handle_chunk(current_chunk);
                    current_chunk.clear();
                    chunk_start = now;
                }
            }

            Pa_StopStream(stream);
            Pa_CloseStream(stream);
            Pa_Terminate(); });
    }

    void handle_chunk(const std::vector<int16_t> &samples)
    {
        if (samples.empty())
            return;

        double sum_sq = 0.0;
        for (int16_t s : samples)
            sum_sq += static_cast<double>(s) * s;

        double rms = std::sqrt(sum_sq / samples.size());

        if (min_rms_ == -1.0 || rms < min_rms_)
            min_rms_ = rms;

        if (rms > max_rms_)
            max_rms_ = rms;

        auto now = std::chrono::steady_clock::now();
        double seconds_since_last_send = std::chrono::duration<double>(now - last_send_time_).count();

        if (seconds_since_last_send > 3.0)
        {
            RCLCPP_INFO(get_logger(), "3 segundos de silencio detectados. Reiniciando min y max rms.");
            max_rms_ = 0.0;
            min_rms_ = -1.0;
            last_send_time_ = now;
        }

        double normalized = (max_rms_ > 0.0 && min_rms_ >= 0.0) ? std::clamp((rms - min_rms_) / (max_rms_ - min_rms_), 0.0, 1.0) : 0.0;

        const int num_levels = 6;
        int level = static_cast<int>(normalized * (num_levels - 1) + 0.5);
        level = std::clamp(level, 0, num_levels - 1);

        static const char *LEVEL_NAMES[] = {
            "low", "medium_low", "medium", "medium_high", "high", "full"};

        const char *level_str = LEVEL_NAMES[level];
        RCLCPP_INFO(get_logger(), "RMS: %.2f | Norm: %.2f | Nivel: %s", rms, normalized, level_str);

        send_to_esp32(level_str);
        last_send_time_ = now;
    }

    void send_to_esp32(const std::string &level)
    {
        if (serial_fd_ != -1)
        {
            std::string message = level + "0";
            write(serial_fd_, message.c_str(), message.size());
        }
    }

    int serial_fd_ = -1;
    std::thread serial_thread_;
    std::thread audio_thread_;
    bool running_ = true;

    double sampleRate_ = 48000;
    double chunk_send_interval_ = 0.1;
    double min_rms_ = -1.0;
    double max_rms_ = 0.0;

    std::chrono::steady_clock::time_point last_send_time_ = std::chrono::steady_clock::now();

    rclcpp::Subscription<std_msgs::msg::String>::SharedPtr mode_subscription_;
    std::string current_mode_ = "idle";
    std::mutex mode_mutex_;
};

int main(int argc, char **argv)
{
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<FaceNode>());
    rclcpp::shutdown();
    return 0;
}
