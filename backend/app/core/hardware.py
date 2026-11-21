"""Hardware detection and execution capability inspection."""

import os
from typing import Dict, Any
from backend.app.core.logger import logger


def detect_hardware() -> Dict[str, Any]:
    """
    Inspects available system acceleration capabilities (NVIDIA CUDA vs CPU).
    Guarantees no crash even if torch/cuda dependencies are not yet installed.
    """
    capabilities = {
        "device": "cpu",
        "compute_type": "int8",
        "cuda_available": False,
        "device_name": "CPU",
        "gpu_count": 0,
        "total_memory_gb": None,
        "description": "Standard multi-threaded CPU execution with int8 quantization"
    }

    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            capabilities["cuda_available"] = True
            capabilities["device"] = "cuda"
            capabilities["compute_type"] = "float16"
            capabilities["gpu_count"] = torch.cuda.device_count()
            capabilities["device_name"] = torch.cuda.get_device_name(0)
            mem_bytes = torch.cuda.get_device_properties(0).total_memory
            capabilities["total_memory_gb"] = round(mem_bytes / (1024 ** 3), 2)
            capabilities["description"] = (
                f"NVIDIA CUDA acceleration enabled: {capabilities['device_name']} "
                f"({capabilities['total_memory_gb']} GB VRAM, float16 precision)"
            )
    except ImportError:
        # PyTorch not installed yet; fallback safely to CPU
        pass
    except Exception as e:
        logger.warning(f"Error inspecting hardware acceleration: {e}. Falling back to CPU.")

    logger.info(f"Hardware capability detected: {capabilities['description']}")
    return capabilities
