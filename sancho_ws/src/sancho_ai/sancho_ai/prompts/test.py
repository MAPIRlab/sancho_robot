import argparse
import time
import numpy as np
import sounddevice as sd

# openWakeWord
from openwakeword.model import Model

def main():
    parser = argparse.ArgumentParser(description="Detector de wake word 'Sancho' con openWakeWord")
    parser.add_argument("--model", required=True, help="Ruta al modelo .tflite o .onnx (p.ej. /ruta/sancho.tflite)")
    parser.add_argument("--threshold", type=float, default=0.5, help="Umbral de activación (0–1, por defecto 0.5)")
    parser.add_argument("--frames", type=int, default=3, help="Nº de frames consecutivos por encima del umbral")
    parser.add_argument("--rate", type=int, default=16000, help="Frecuencia de muestreo (Hz), debe ser 16000")
    parser.add_argument("--frame_ms", type=int, default=80, help="Duración de cada chunk en ms (recomendado 80)")
    parser.add_argument("--cooldown_ms", type=int, default=1500, help="Tiempo mínimo entre avisos (ms)")
    parser.add_argument("--no_speex", action="store_true", help="Desactiva supresión de ruido Speex")
    parser.add_argument("--vad", type=float, default=0.5, help="Umbral del VAD (0 desactiva VAD)")
    args = parser.parse_args()

    RATE = int(args.rate)
    FRAME_MS = int(args.frame_ms)
    SAMPLES = RATE * FRAME_MS // 1000

    # Inicializa el modelo
    model = Model(
        wakeword_models=[args.model],
        vad_threshold=(0.0 if args.vad <= 0 else float(args.vad)),
        enable_speex_noise_suppression=(not args.no_speex)
    )

    # Debouncing
    consec_hits = 0
    last_fire_ts = 0.0
    cooldown_s = args.cooldown_ms / 1000.0

    def on_audio(indata, frames, t, status):
        nonlocal consec_hits, last_fire_ts
        if status:
            # Errores del stream (buffers perdidos, etc.)
            # No retornamos para no detener la captura
            pass

        # Convierte a PCM16 mono
        mono = indata[:, 0]  # si tu micro es estéreo, coge el canal 0
        pcm16 = (np.clip(mono, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()

        # Predicción por chunk -> dict {model_name: score}
        scores = model.predict(pcm16)
        # Como cargamos 1 modelo, tomamos su único score
        score = next(iter(scores.values()))

        # Lógica de activación con frames consecutivos
        if score >= args.threshold:
            consec_hits += 1
            # ¿supera N frames y ha pasado el cooldown?
            now = time.time()
            if consec_hits >= args.frames and (now - last_fire_ts) >= cooldown_s:
                print("SANCHO HA SIDO ESCUCHADO", flush=True)
                last_fire_ts = now
                consec_hits = 0  # resetea para no espamear
        else:
            consec_hits = 0

    print("Escuchando wake word 'Sancho'… Ctrl+C para salir")
    print(f"- modelo: {args.model}")
    print(f"- chunk: {FRAME_MS} ms, samplerate: {RATE} Hz, umbral: {args.threshold}, frames seguidos: {args.frames}")

    # Stream de audio: 16 kHz, mono, bloques de FRAME_MS
    with sd.InputStream(
        channels=1,
        samplerate=RATE,
        blocksize=SAMPLES,
        dtype="float32",
        callback=on_audio
    ):
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    main()
