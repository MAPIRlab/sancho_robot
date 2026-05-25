#!/usr/bin/env python3
import sys
import time
import pyaudio
import numpy as np

def main():
    p = pyaudio.PyAudio()
    
    # List devices
    print("Available Input Devices:")
    default_idx = -1
    try:
        default_info = p.get_default_input_device_info()
        default_idx = default_info['index']
        print(f"  * Default Device Index: {default_idx} ({default_info['name']})")
    except Exception as e:
        print(f"  No default input device found: {e}")

    input_devices = []
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev.get("maxInputChannels", 0) > 0:
            marker = " [DEFAULT]" if i == default_idx else ""
            print(f"  Index {i}: {dev['name']}{marker} (channels: {dev['maxInputChannels']})")
            input_devices.append(i)

    if not input_devices:
        print("No input devices found!")
        p.terminate()
        return

    try:
        selection = input("\nEnter device index to monitor (or press Enter for default): ").strip()
        if selection == "":
            target_idx = default_idx if default_idx != -1 else input_devices[0]
        else:
            target_idx = int(selection)
    except ValueError:
        print("Invalid index selection.")
        p.terminate()
        return

    dev_info = p.get_device_info_by_index(target_idx)
    print(f"\nStarting real-time volume monitor on device {target_idx} ({dev_info['name']})...")

    try:
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            input_device_index=target_idx,
            frames_per_buffer=1024
        )
    except Exception as e:
        print(f"Error opening stream: {e}")
        p.terminate()
        return

    print("\nPress Ctrl+C to exit.")
    print("Volume Meter (speaking should make the bar grow):")
    try:
        while True:
            data = stream.read(1024, exception_on_overflow=False)
            if data:
                samples = np.frombuffer(data, dtype=np.int16)
                rms = np.sqrt(np.mean(samples.astype(float)**2))
                
                # Scale bar
                bar_len = int(min(rms / 100, 50))
                bar = "#" * bar_len + " " * (50 - bar_len)
                sys.stdout.write(f"\r[{bar}] RMS: {rms:7.1f}")
                sys.stdout.flush()
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nExiting monitor.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    main()
