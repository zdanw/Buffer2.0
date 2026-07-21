"""仓库根兼容入口（HF Gradio 误配时的兜底；Docker 实际启动 bebcare.main:app）。"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
for _cand in (
    os.path.join(_ROOT, "hf-space"),
    os.path.join(_ROOT, "backend"),
    _ROOT,
):
    if os.path.isdir(os.path.join(_cand, "bebcare")) and _cand not in sys.path:
        sys.path.insert(0, _cand)
        break

from bebcare.main import app  # noqa: E402

__all__ = ["app"]
