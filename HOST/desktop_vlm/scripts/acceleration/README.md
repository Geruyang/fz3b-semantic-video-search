# S1 算子替换的主机参考与切分工具

这些工具使用已锁定的真实ONNX及既有实拍输入tensor，不访问板卡。它们提供数值契约、真实权重/激活和对拍证据；工程烟雾实验不替代独立校准集及准确率验收。

运行环境沿用`desktop_vlm/ONNX_EXPORT.md`：项目根目录，Python为`artifacts/desktop-vlm-20261003/reviewer/venv/Scripts/python.exe`，`PYTHONPATH`包含`artifacts/board-debug-20261004/host/onnx-deps`，设置`PYTHONDONTWRITEBYTECODE=1`。依赖已有NumPy、ONNX1.17、ORT1.20.1；测试额外使用现有PyTorch/pytest。所有`--output`必须是不存在的新目录。

## 工具

- `prepare_pointwise.py`：选择精确Conv节点，要求group1、stride1、无padding、1×1；提取真实输入和权重，对称INT8量化，输出行优先A[M,K]、B[K,N]、C[M,N]。每张图first16空间位置、first32输出通道、完整K形成C/RTL fixture；INT64矩阵结果逐项用Python标量复核，并检查INT32范围。另在完整模型里注入该量化Conv输出，测512维特征偏差。
- `split_subgraph.py`：指定连续区域首/末节点，计算全部活跃跨界tensor，保留残差旁路，导出prefix/region/suffix三个ONNX；三段常驻CPU执行与原图对拍。边界尺寸、字节数和文件SHA全部记录，不是PL性能结果。
- `integer_postops.py`：检查bias与INT32累加范围；每通道Q31乘数/右移，正负均nearest ties-to-even，饱和到[-127,127]。GELU查表以INT8的原始无符号byte为索引，定义全部256项；输入先按独立scale重量化，不截取累加器低位。
- `quantize_ffn_smoke.py`：处理上述两层pointwise/GELU/layerscale/residual区域。两层卷积为INT8×INT8、INT32累加/bias和整数重量化，GELU为256项LUT；layer-scale与残差暂留FP32。导出权重、bias、Q31参数、LUT和每阶段first16行golden，再跑剩余模型。
- `prepare_depthwise.py`：提取实际group=C、channel-multiplier1、stride1、同尺寸DW3/7的输入/权重与无bias INT32 golden；支持指定通道数，全部边缘以显式索引scalar参考再核一次。
- `summarize_profile.py`：读取网口agent生成的真实节点分析及其精确SHA匹配的优化ONNX，按group/shape区分pointwise、DW3/7和普通Conv，汇总真实时间；不按节点名字猜group。仅主机Python3.12运行。

共同边界：zero_point=0；权重逐输出通道scale，激活逐tensor scale。当前用同一组三张历史输入估计范围和测误差，**没有独立验证集**。用户暂不方便采集新样本，准确率验收延期。

## 复现参数

在项目根调用本目录脚本，解释器用上述Python路径。每个`--input`是`artifacts/board-debug-20261004/host/s1-onnx-001/image-00-input.f32`等；可重复传入00/01/02三张。

`prepare_pointwise.py`和`split_subgraph.py`共同参数：

```text
--model artifacts/board-debug-20261004/host/s1-onnx-001/mobileclip_s1_image.onnx
--expected-model-sha256 5b8494a03aa81a59b2bd0a3f3dcba91813363bb65060c32d6e4bf4243f8e3587
--input artifacts/board-debug-20261004/host/s1-onnx-001/image-00-input.f32
--output NEW_DIRECTORY
```

pointwise额外使用`--node /image_encoder/model/network.0/network.0.0/convffn/fc1/Conv`。

split额外使用：

```text
--first-node /image_encoder/model/network.0/network.0.0/convffn/fc1/Conv
--last-node /image_encoder/model/network.0/network.0.0/Add
```

FFN量化工具参数为`--partition EXISTING_SPLIT_DIRECTORY --input INPUT.f32 --output NEW_DIRECTORY`，输入可重复。上述是参数清单，续行按所用shell规则书写。

## 当前证据

相对项目根`artifacts/board-debug-20261004/acceleration/host/`：

| 目录/文件 | 实际结果 |
|---|---|
| `pointwise-fixture-001/manifest.json` | M16/N32/K64三组tile共1536整数输出标量复核通过；单层替换feature余弦0.999963～0.999969 |
| `ffn-split-001/manifest.json` | 含残差的FFN切分，两个输入各1MiB FP32、一个输出1MiB；3图全模型输出max_abs=0 |
| `ffn-int8-001/manifest.json` | 两层INT8＋整数重量化＋LUT的FFN软件参考；3图全模型feature余弦0.9995145～0.9997193 |
| `ffn-int8-001/independent-score-check.json` | 从保存特征独立计算8候选得分，三图排名与FP32一致、最大分数差0.0016007以内；无标签，不是准确率 |
| `depthwise-fixture-001/manifest.json` | 真实network.2.0的DW7，两通道32×32/pad3，每图2048、共6144整数输出全部scalar核验 |
| `stage2-split-001/manifest.json` | network.2完整12块切分，FP32边界单输入/输出各0.5MiB，三图全模型输出max_abs=0 |
| `profile-t4-operator-priority.json` | 4线程诊断：DW7 39.61%、pointwise35.63%、GELU9.48%、DW3 8.91%；当前性能开发以实测优先级为准 |

19项pytest覆盖量化ties-even/饱和/通道scale/非法值，整数右移对精确Fraction参考，以及三组scale的全部GELU表项对PyTorch FP64：

```text
PYTHON -m pytest desktop_vlm/scripts/acceleration/test_pointwise_reference.py desktop_vlm/scripts/acceleration/test_integer_postops.py -q -p no:cacheprovider
```

当前硬件tile最多K128，而FFN第二层K192。集成时须分K累加部分和，再且仅再应用一次bias/重量化；不能把每块先饱和的结果相加。全尺寸tile调度、片上缓存重用和DMA协议仍须硬件集成验证，软件参考不证明这些已经实现。

另有`test_dw_capture_contract.py`的9项采集检查器测试：合成CSV覆盖signed INT32、完成计数回绕，以及实际值与片上golden同时错误、重复/缺少样本、错误round/event/failure/输入计数的拒绝。这些合成样本仅验证检查器，不能当作实板采集；真实采集须另留原生`.ila`并对原始fixture核验。

`prepare_axi_jobs.py FIXTURE --manifest-sha256 SHA --output NEW_JSON`核验冻结pointwise数据，生成12组真实K64点积与6组长度/极值边界任务。`host/axi-dot-jobs-001.json`有18组，供PS–PL寄存器通路测试；文件的PREPARED状态不是上板结果。

`quantize_dw_smoke.py --model MODEL --fixture DW_FIXTURE --fixture-manifest-sha256 SHA --input INPUT ... --output NEW_DIRECTORY`将已验证DW节点扩展到全部128通道，并用FP32反量化/bias接回模型。默认主机2线程，可用`--threads 1`降低后台负载。`host/dw-int8-001/manifest.json`三图FP32透传逐位一致，已上板前两通道的输入/权重/6144个输出与原fixture完全相同，其余通道各覆盖边缘与中心scalar检查；完整特征余弦0.9998047～0.9999629。该实验在主机执行，冻结scale来自同三张图，不代表独立准确率验收或整个模型已调用PL。

`host/dw-int8-002/`进一步保存全128通道输入、权重和INT32输出；独立PyTorch CPU FP64分组卷积逐值验证全部393216个整数结果。`host/dw-split-001/`保留单DW前后CPU子图与残差边界，三图FP32结果完全一致。

`check_hpm_capture.py CAPTURE.csv --columns EXACT_COLUMN_MAP.json [--jobs EXPECTED_JOBS.json] --output NEW_RESULT.json`用于后续HPM原生ILA导出的CSV。列名映射必须取自实际候选/probe身份；默认2048个无条件采样，核验heartbeat逐拍递增、reset/error、有效AXI响应及任务完成结果。省略jobs时只检查尚未发PS任务的初始状态；jobs列表格式为`job_id/length/expected`，须从已锁定输入和实际PS任务编号建立。15项合成数据测试通过，**这些测试不证明HPM已经上板**。

随后真实HPM两次采集和18个PS任务已经通过独立检查，见`host/hpm-baseline-independent-check.json`、`host/hpm-transaction-independent-check.json`和`host/hpm-job-independent-check.json`。原厂PL及驱动已恢复；这项证据只证明点积实际双向通路。

`prepare_dw_jobs.py --source DW_INT8_002 --output NEW_DIRECTORY`固定可信量化manifest，重新标量计算6个真实通道和4个极值/零任务，共10240值。每个request为49字节权重+1024字节像素，输出golden为4096字节小端INT32。`host/dw-jobs-001/manifest.json`是新FZC2动态接口的输入，不是实板回执。

`check_dw_partition_inputs.py --reference DW_INT8_002 --split DW_SPLIT --prefix PS_PREFIX_F32 ... --collection-receipt RECEIPT_JSON --ps-prefix-threads 4 --output NEW_DIRECTORY`从真实PS前段结果建立独立量化/整数卷积/后段特征参考，报告与主机旧图量化的边界差异。输入须按image00/01/02顺序，主机后段参考CPU两线程，与板端前段采集线程分别标注；不访问PL。

`check_dw_hpm_capture.py CAPTURE.csv --columns EXACT_MAP.json [--jobs DW_JOBS_DIRECTORY] --output NEW_RESULT.json`验证计划中的8192连续采样与14个probe；实际列名必须由最终LTX核验。检查首任务完整1024个输出、同拍事件/计数、周期和BUSY→DONE关系；省略jobs时为初始clock/reset检查。5项合成测试含16种字段故障、读写错误响应、截断采样拒绝，仅证明检查器行为。

`check_dw_board_outputs.py WINDOW_DIRECTORY HOST_REFERENCE_DIRECTORY smoke|full --output NEW_RESULT.json`独立检查下载文件的字节、SHA和实际作业编号。smoke 对比十个固定任务的10240个整数；full 对比实际PS前段对应oracle002的393216个整数、量化/反量化张量、连续硬件job11..394以及最终512维特征，保留实际分项计时。只有传入真实板端回传文件且检查通过后才产生实板PASS报告。
