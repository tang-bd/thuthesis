# 第二阶段仿真失败样本分析记录

本文件记录 chap04.tex 仿真失败分析中引用的具体样本，便于后续查找与核实。

数据来源：`/tmp/eval_stage2/eval_verilog_bundle/`（从 HuggingFace `tbd-lab/verilog-wavedrom-stage-2` 解压）
- `manifest.json`：全部 117 个样本的指标
- `sim_work/sample_XXXXX/`：每个样本的生成代码、测试平台、仿真产物
- `vllm_stage2_wd_w2v_eval.jsonl`：原始推理输出（含完整 predict 文本）

## 一、重复退化（5 个样本，原文"生成截断"改为"重复退化"）

### Sample 3 (module=073156, 生成文件 073156.v)
- **表现**: 1353 行，无 endmodule
- **原因**: 模块名 `ablk`，声明了状态机框架后，进入 temp 寄存器重复声明循环。1247/1353 行为 `reg ablk_*_temp_N;`（N 从 1 递增到 104），每轮约 12 个变量名组合 × 104 轮。
- **模式**: 递增编号的重复声明

### Sample 8 (module=033946, 生成文件 033946.v)
- **表现**: 提取后仅 2 行（`\`timescale 1ns/1ps` + `module Counter32`），但原始 predict 长 32771 字符
- **原因**: 模型输出 `module Adi` 后立即进入 "Im" 二字母重复循环，重复 16370 次（32740 字符的垃圾）。提取脚本正确地仅保留了有意义的前缀。
- **模式**: 单一 token 的无限重复

### Sample 13 (module=009401, 生成文件 009401.v)
- **表现**: 593 行，无 endmodule
- **原因**: 模块名 `decoderparam`，14 位输入 `code` 的 case 语句。模型试图逐一枚举所有 2^14=16384 种输入组合，已生成 583 条 case 分支后被截断。每条 case 用 16 位字面量匹配 14 位输入（位宽不匹配）。
- **模式**: 暴力枚举的组合爆炸

### Sample 83 (module=013629, 生成文件 013629.v)
- **表现**: 2055 行，无 endmodule
- **原因**: 模块名 `i2c_master`，生成了 244 个几乎相同的状态（8'd0 到 8'd244）。每个状态的逻辑均为 `if (counter == 8'h08) begin state <= 8'd(N+1); counter <= 8'h00; end else begin counter <= counter + 8'h01; end`——即简单的计数等待后跳转到下一状态。
- **模式**: 状态机状态爆炸

### Sample 108 (module=045583, 生成文件 045583.v)
- **表现**: 1499 行，无 endmodule
- **原因**: 模块名 `mojo_top`，声明了端口后进入参数声明循环。1484/1499 行为 `parameter CPLL_CFG_X = 14;`，后缀按 A-Z 循环重复约 57 轮。
- **模式**: 字母循环的重复声明

## 二、端口接口错误（has-TB 但编译失败的样本）

### Sample 69 (module=039462, 生成文件 039462.v + 039462_tb.v)
- 缺少参数 AXIS_TDATA_WIDTH, ALWAYS_READY, CROSS_MASK

### Sample 77 (module=007412, 生成文件 007412.v + 007412_tb.v)
- 缺少参数 DATA_WIDTH

### Sample 97 (module=045917, 生成文件 045917.v + 045917_tb.v)
- 缺少参数 WIDTH, RANGE

### Sample 102 (module=017884, 生成文件 017884.v + 017884_tb.v)
- 缺少参数 W

### Sample 113 (module=036489, 生成文件 036489.v + 036489_tb.v)
- 缺少参数 DATA_WIDTH, ADDR_WIDTH

### Sample 50 (module=054753, 生成文件 054753.v + 054753_tb.v)
- 输出端口 s422_data 位宽不匹配（生成 24 位，TB 期望 16 位）

## 三、逻辑实现错误（sim_ok 但 F1 < 1.0 的典型样本）

### Sample 39 (module=059134, 生成文件 059134.v + 059134_tb.v)
- F1=0（仿真失败，TB 引用不存在的内部信号）
- 流量控制模块 valve36 被简化为 3 条 assign 直通连线

### Sample 38 (module=015077, F1=0.407)
- 指令译码器，13 端口中 12 个输出几乎全部保持常量 0/z
- GT 显示丰富的译码模式，模型的 case 分支条件错误

### Sample 45 (module=041557, F1=0.584)
- 行扫描控制状态机，15 信号中 5 个输出为高阻态 z，其余复位后恒为 0
- GT 显示 prev/curr/next_row_load 依次偏移的周期脉冲

### Sample 28 (module=045460, F1=0.254)
- 相位译码器，信号跳变时序大致正确但数据标签值完全错误
- GT: dqs_phase data=[16,36,56,77,7,27,48,68]; PRED: [66,25,66,25,0,25,66,25]

### Sample 92 (module=038540, F1=0.690)
- VGA 显示控制器，输出信号全部保持常量
