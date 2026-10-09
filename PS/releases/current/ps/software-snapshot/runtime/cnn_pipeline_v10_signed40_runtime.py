"""A0005 signed40 chain runtime over the fused A0004 data path.

The arena layout, direct mapped conversion, and 2->3->0->1 execution plan are
unchanged.  This adapter changes only the strictly validated combined
parameter contract; the A0005 transport separately enforces ABI/capability and
per-handle approved-parameter admission.
"""
from __future__ import print_function

try:
    from cnn_pipeline_v10_p3_dma_runtime import V10P3DmaChainMixin
    from cnn_pipeline_v10_signed40_parameters import CHAIN_CONTRACT
except ImportError:
    from .cnn_pipeline_v10_p3_dma_runtime import V10P3DmaChainMixin
    from .cnn_pipeline_v10_signed40_parameters import CHAIN_CONTRACT


class V10Signed40ChainMixin(V10P3DmaChainMixin):
    """Run the A0005 candidate with its immutable signed40 parameter proof."""

    PARAMETER_CONTRACT = CHAIN_CONTRACT
    PARAMETER_LABEL = "A0005"


__all__ = ["V10Signed40ChainMixin"]
