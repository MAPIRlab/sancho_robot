import onnxruntime as ort
import numpy as np

session = ort.InferenceSession("models/yolox_tiny.onnx")
# Create a fake normalized image (matching your working script's range)
dummy_input = np.random.randn(1, 3, 416, 416).astype(np.float32)
outputs = session.run(None, {session.get_inputs()[0].name: dummy_input})

raw_data = outputs[0]
print(f"Output Shape: {raw_data.shape}")
print(f"Max Value: {np.max(raw_data)}")
print(f"Min Value: {np.min(raw_data)}")
print(f"Mean Value: {np.mean(raw_data)}")