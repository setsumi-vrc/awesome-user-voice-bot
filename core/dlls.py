import os
import sys
import ctypes
from pathlib import Path

def setup_cuda_paths(cuda_x64_path: str, cudnn_bin_path: str, verify: bool = True):
    if sys.platform != "win32":
        return

    def add_dir(p: Path, label: str):
        if p.exists():
            os.add_dll_directory(str(p))
            # PATH ayuda a dependencias que no usan AddDllDirectory
            os.environ["PATH"] = f"{p};" + os.environ.get("PATH", "")
            print(f"[CUDA] add_dll_directory {label}: {p}")
        else:
            print(f"[CUDA] WARNING missing {label}: {p}")

    if cuda_x64_path:
        add_dir(Path(cuda_x64_path), "CUDA_X64_PATH")
    if cudnn_bin_path:
        add_dir(Path(cudnn_bin_path), "CUDNN_BIN_PATH")

    if verify and cuda_x64_path:
        dll = Path(cuda_x64_path) / "cublasLt64_13.dll"
        if dll.exists():
            ctypes.WinDLL(str(dll))
            print(f"[CUDA] Loaded OK: {dll.name}")
        else:
            print(f"[CUDA] WARNING: no encuentro {dll}")
