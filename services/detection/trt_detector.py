"""TensorRT-accelerated RF-DETR detector for fire/smoke detection.

Engine I/O contract (RF-DETR nano, 2-class fire/smoke):
    Input:   (1, 3, 384, 384) float32  — ImageNet-normalized RGB, CHW
    Output   boxes:  (1, 300, 4) float32 — [cx, cy, w, h] normalized [0,1]
    Output   logits: (1, 300, 2) float32 — class logits (0=fire, 1=smoke)

The actual tensor names vary depending on the ONNX export (e.g. "dets"/"labels",
"onnx::Reshape_...", etc.). This module discovers them at load time so it works
regardless of naming.

Requires: tensorrt >=10.0, pycuda.
TensorRT engines are tied to the GPU architecture and TRT version they were
built with — the runtime version must match the build version.

Tested with: TensorRT 10.10.0.31
"""

from __future__ import annotations

import logging

import cv2
import numpy as np
import pycuda.autoinit  # noqa: F401 — initializes CUDA context on import
import pycuda.driver as cuda
import tensorrt as trt

from shared.schemas.messages import DetectionResult

from detector import BaseDetector

logger = logging.getLogger(__name__)

_TRT_LOGGER = trt.Logger(trt.Logger.WARNING)
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class RFDETRTensorRTDetector(BaseDetector):
    """RF-DETR fire/smoke detector backed by a TensorRT .engine file.

    Do not share instances across threads or processes — CUDA contexts
    and device allocations are not thread-safe in pycuda.
    """

    def __init__(self, input_resolution: int = 384) -> None:
        self._resolution = input_resolution
        self._engine: trt.ICudaEngine | None = None
        self._context: trt.IExecutionContext | None = None
        self._stream: cuda.Stream | None = None
        self._input_names: list[str] = []
        self._output_names: list[str] = []
        self._output_shapes: dict[str, tuple] = {}
        self._output_dtypes: dict[str, type] = {}
        self._d_inputs: dict[str, cuda.DeviceAllocation] = {}
        self._d_outputs: dict[str, cuda.DeviceAllocation] = {}
        self._h_outputs: dict[str, np.ndarray] = {}

    def load(self, model_path: str, device: str = "cuda") -> None:
        logger.info("Loading TensorRT engine: %s (TRT %s)", model_path, trt.__version__)

        runtime = trt.Runtime(_TRT_LOGGER)
        with open(model_path, "rb") as f:
            self._engine = runtime.deserialize_cuda_engine(f.read())
        if self._engine is None:
            raise RuntimeError(
                f"Failed to deserialize TensorRT engine: {model_path}. "
                f"Ensure the engine was built with the same TensorRT version "
                f"(current: {trt.__version__}) and GPU architecture."
            )

        self._context = self._engine.create_execution_context()
        self._stream = cuda.Stream()
        self._allocate_buffers()

        # Resolve which output tensor is boxes vs logits
        self._boxes_name, self._logits_name = self._resolve_output_names()

        logger.info(
            "TensorRT engine loaded: %s  inputs=%s  outputs=%s  resolution=%d",
            model_path, self._input_names, self._output_names, self._resolution,
        )

    def _allocate_buffers(self) -> None:
        for i in range(self._engine.num_io_tensors):
            name = self._engine.get_tensor_name(i)
            shape = tuple(self._engine.get_tensor_shape(name))
            dtype = trt.nptype(self._engine.get_tensor_dtype(name))
            nbytes = int(np.prod(shape) * np.dtype(dtype).itemsize)
            d_buf = cuda.mem_alloc(nbytes)
            self._context.set_tensor_address(name, int(d_buf))

            mode = self._engine.get_tensor_mode(name)
            if mode == trt.TensorIOMode.INPUT:
                self._input_names.append(name)
                self._d_inputs[name] = d_buf
                logger.info(
                    "  Input  '%s': shape=%s, dtype=%s",
                    name, shape, np.dtype(dtype).name,
                )
            else:
                self._output_names.append(name)
                self._output_shapes[name] = shape
                self._output_dtypes[name] = dtype
                self._d_outputs[name] = d_buf
                self._h_outputs[name] = np.empty(shape, dtype=dtype)
                logger.info(
                    "  Output '%s': shape=%s, dtype=%s",
                    name, shape, np.dtype(dtype).name,
                )

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """BGR ndarray (H, W, C) → (1, 3, H, W) float32 ImageNet-normalized."""
        resized = cv2.resize(
            image, (self._resolution, self._resolution), interpolation=cv2.INTER_LINEAR
        )
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        normalized = (rgb - _IMAGENET_MEAN) / _IMAGENET_STD
        return np.ascontiguousarray(normalized.transpose(2, 0, 1)[np.newaxis], dtype=np.float32)

    def _infer(self, input_tensor: np.ndarray) -> dict[str, np.ndarray]:
        for name in self._input_names:
            cuda.memcpy_htod_async(self._d_inputs[name], input_tensor, self._stream)
        self._context.execute_async_v3(stream_handle=self._stream.handle)
        for name in self._output_names:
            cuda.memcpy_dtoh_async(self._h_outputs[name], self._d_outputs[name], self._stream)
        self._stream.synchronize()
        return {name: self._h_outputs[name].copy() for name in self._output_names}

    def _resolve_output_names(self) -> tuple[str, str]:
        """Map engine output tensors to (boxes_name, logits_name) by shape.

        RF-DETR engines always produce two outputs:
          - boxes:  (1, N, 4)  — cx, cy, w, h normalised
          - logits: (1, N, C)  — raw class logits

        The actual tensor names vary across export tools / ONNX versions,
        so we match by the last dimension size (4 → boxes, else → logits).
        """
        if len(self._output_names) != 2:
            raise RuntimeError(
                f"Expected exactly 2 output tensors, got {len(self._output_names)}: "
                f"{self._output_names}"
            )

        boxes_name: str | None = None
        logits_name: str | None = None

        for name in self._output_names:
            last_dim = self._output_shapes[name][-1]
            if last_dim == 4:
                boxes_name = name
            else:
                logits_name = name

        if boxes_name is None or logits_name is None:
            # Fallback: assume first output is boxes, second is logits
            # (matches the order produced by rfdetr.export)
            boxes_name, logits_name = self._output_names[0], self._output_names[1]
            logger.warning(
                "Could not resolve output tensors by shape; falling back to "
                "positional order: boxes='%s', logits='%s'",
                boxes_name, logits_name,
            )

        logger.info(
            "Output mapping: boxes='%s' %s, logits='%s' %s",
            boxes_name, self._output_shapes[boxes_name],
            logits_name, self._output_shapes[logits_name],
        )
        return boxes_name, logits_name

    def predict(
        self,
        image: np.ndarray,
        confidence_threshold: float = 0.5,
    ) -> DetectionResult:
        orig_h, orig_w = image.shape[:2]
        raw = self._infer(self._preprocess(image))

        boxes_cxcywh = raw[self._boxes_name][0]   # (300, 4) normalised cx cy w h
        logits = raw[self._logits_name][0]         # (300, C)  raw logits

        # Sigmoid activation → per-class probabilities
        scores_per_class = 1.0 / (1.0 + np.exp(-logits.astype(np.float32)))
        class_ids = np.argmax(scores_per_class, axis=1)
        class_scores = np.max(scores_per_class, axis=1)

        keep = class_scores > confidence_threshold
        if not keep.any():
            return DetectionResult()

        boxes_f = boxes_cxcywh[keep].astype(np.float32)
        cx, cy, bw, bh = boxes_f[:, 0], boxes_f[:, 1], boxes_f[:, 2], boxes_f[:, 3]
        boxes_xyxy = np.stack(
            [(cx - bw / 2) * orig_w,
             (cy - bh / 2) * orig_h,
             (cx + bw / 2) * orig_w,
             (cy + bh / 2) * orig_h],
            axis=1,
        )

        return DetectionResult(
            boxes=boxes_xyxy.tolist(),
            scores=class_scores[keep].tolist(),
            classes=class_ids[keep].tolist(),
        )
