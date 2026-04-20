# ONNX Model Assets for Local Inference

Place exported ONNX assets in this folder to enable true local inference mode.

Required files:
- model_optimized.onnx
- tokenizer.json
- config.json
- metadata.json (optional but recommended)

Optional runtime file:
- ../background/lib/ort.min.js (from onnxruntime-web)

Without these files, the extension automatically uses heuristic fallback mode.
