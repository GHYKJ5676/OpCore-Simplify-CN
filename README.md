<br/>
<div align="center">
  <h3 align="center">OpCore Simplify</h3>

  <p align="center">
    一款专用工具，可自动化完成核心配置流程、提供标准化配置文件，简化 <a href="https://github.com/acidanthera/OpenCorePkg">OpenCore</a> EFI 文件制作。旨在减少黑苹果手动配置工作量，同时保障配置精准可靠。
    <br />
    <br />
    <a href="#-功能特性">功能特性</a> •
    <a href="#-使用教程">使用教程</a> •
    <a href="#-参与贡献">参与贡献</a> •
    <a href="#-开源协议">开源协议</a> •
    <a href="#-致谢名单">致谢名单</a> •
    <a href="#-联系方式">联系方式</a>
  </p>
  
  <p align="center">
    <a href="https://trendshift.io/repositories/15410" target="_blank"><img src="https://trendshift.io/api/badge/repositories/15410" alt="lzhoang2801%2FOpCore-Simplify | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
  </p>
</div>

> [!NOTE]
> **OpenCore Legacy Patcher 3.0.0 现已支持 macOS Tahoe 26！**
> 
> 万众期待的 OpenCore Legacy Patcher 3.0.0 版本正式发布，社区可抢先体验对 **macOS Tahoe 26** 的基础适配支持！
> 
> 🚨 **重要须知：**  
> - 仅 [lzhoang2801/OpenCore-Legacy-Patcher](https://github.com/lzhoang2801/OpenCore-Legacy-Patcher/releases/tag/3.0.0) 仓库发布的 3.0.0 版本，提供适配 macOS Tahoe 26 的早期补丁。
> - Dortania 官方原版发行版、旧版补丁**均无法兼容** macOS Tahoe 26。  

> [!WARNING]
> OpCore Simplify 虽能大幅缩短配置耗时，但搭建黑苹果仍需你做到以下几点：
> - 熟读 [Dortania 官方教程](https://dortania.github.io/OpenCore-Install-Guide/) 掌握基础原理
> - 安装过程中自行测试、排查故障
> - 有耐心、逐步解决各类适配问题
>
> 本工具无法保证一次安装成功，但能帮你快速搭建基础可用引导。

## ✨ **功能特性**

1. **全品类硬件与 macOS 系统兼容支持**  
   完整适配主流现代硬件。内置「兼容性检测器」，可查询设备兼容状态、支持的 macOS 系统版本。

   | **硬件组件**  | **兼容范围**                                                                                       |
   |----------------|-----------------------------------------------------------------------------------------------------|
   | **处理器**        | Intel：初代Nehalem、Westmere → 15代Arrow Lake（酷睿Ultra 2系列）<br>AMD：锐龙、线程撕裂者，搭配 [AMD Vanilla](https://github.com/AMD-OSX/AMD_Vanilla) 方案 |
   | **显卡**        | Intel核显：一代Iron Lake → 十代Ice Lake <br>AMD核显：全Vega Raven架构（锐龙1xxx~5xxx、7x30系列）<br>AMD独显：Navi23/22/21及前代架构 <br>NVIDIA显卡：Kepler、Pascal、Maxwell、Fermi、Tesla架构 |
   | **macOS系统**      | macOS High Sierra 至 macOS Tahoe |

2. **自动ACPI补丁与驱动注入**  
   根据硬件信息自动识别并添加对应ACPI修复补丁、内核驱动kext。
   
   - 内置整合 [SSDTTime](https://github.com/corpnewt/SSDTTime) 常用补丁（FakeEC、FixHPET、PLUG、RTCAWAC等）。
   - 内置专属自定义补丁集：
      - 工作站平台修复：指定首个CPU为活动核心、屏蔽UNC0设备、新建RTC设备，避免内核崩溃。
      - 屏蔽无用/不兼容PCI设备：双显卡独显屏蔽（Optimus/Bumblebee方案、添加屏蔽显卡设备属性）、无线网卡、NVMe硬盘控制器。
      - 修复_PRW电源唤醒参数（通用GPRW、专属UPRW、惠普机型特殊补丁），解决开机秒唤醒问题。
      - 新增设备补丁：ALS0、BUS0、MCHC、PMCR、PNLF、RMNE、IMEI、USBX、XOSI，附带Surface专属补丁。
      - 启用ALSD、GPI0设备。

3. **自动更新组件**  
   每次生成EFI前，自动从 [Dortania Builds](https://dortania.github.io/builds/) 与GitHub发行版拉取最新OpenCore引导程序、驱动文件并完成更新。
            
4. **EFI引导精细化配置**  
   整合行业通用方案与作者实操经验，自动添加大量优化配置项。

   - 为macOS无法识别的部分AMD显卡伪装设备ID。
   - 大小核Intel处理器自动加载CpuTopologyRebuild驱动，提升调度性能。
   - 可选关闭系统完整性保护SIP。
   - 为奔腾、赛扬、酷睿、至强Intel处理器伪装CPU型号ID。
   - 自定义CPU显示名称：全系列AMD锐龙、11代Rocket Lake及更新奔腾/赛扬/酷睿/至强。
   - 新增补丁，允许使用不兼容机型标识SMBIOS启动macOS。
   - 写入NVRAM参数，跳过内置蓝牙控制器校验。
   - 根据主板可调整显存大小Resizable BAR信息，自动配置ResizeAppleGpuBars参数。
   - 存在兼容独显时，灵活切换核显无头输出/显示器输出模式。
   - 强制Intel核显启用VESA兼容模式（HDMI/DVI接口），简化安装流程。
   - 预配置OpenCore Legacy Patcher配套参数。
   - 内置网络、存储设备属性修复：解决iServices提示「无法连接服务器」、内置硬盘识别为外置磁盘问题。
   - 优先选用兼顾功耗与性能的机型SMBIOS。
   - Ventura 13及以上系统，恢复老旧Intel处理器CPU电源管理。
   - 导入itlwm无线驱动WiFi配置文件，开机自动连接无线网络。

   以及更多优化项……

5. **高度自定义拓展**  
   除默认自动配置外，用户可按需进一步自定义引导参数。

   - 手动添加自定义ACPI补丁、驱动、修改机型标识（**不推荐新手操作**）。
   - 强制在不兼容macOS版本加载驱动。

## 🚀 **使用教程**

1. **下载 OpCore Simplify**:
   - 点击仓库右上角 **Code** → **Download ZIP**，或直接点击此[下载链接](https://github.com/GHYKJ5676/OpCore-Simplify/archive/refs/heads/main.zip)。  
   - 将下载的压缩包解压至任意目录。

   

2. **启动工具**:
   - Windows系统：运行 `OpCore-Simplify.bat`。
   - macOS系统：运行 `OpCore-Simplify.command`。
   - Linux系统：使用本地Python环境执行 `OpCore-Simplify.py`。

   

3. **导入硬件信息报告**:
   - Windows端菜单提供「E. 导出硬件报告」选项，推荐生成报告，工具可根据当前硬件、BIOS精准适配配置。
   - 也可使用 [**Hardware Sniffer**](https://github.com/GHYKJ5676/Hardware-Sniffer-CN) 手动导出 `Report.json` 硬件文件与ACPI转储文件用于配置。

   

   

   

4. **选择macOS版本并自定义OpenCore引导**:
   - 工具会自动预选适配本机硬件的最新macOS版本。
   - 程序自动加载必备ACPI补丁与驱动。
   - 你可手动逐项查看、修改各项配置。

   

5. **生成OpenCore EFI引导文件**:
   - 全部参数调整完成后，选择「构建OpenCore EFI」生成引导文件夹。
   - 工具会自动下载所需引导程序与驱动，该过程可能耗时数分钟。

   

   

   

6. **USB端口映射**:
   EFI构建完成后，按照指引完成USB端口定制映射。

   

7. **制作安装U盘并安装macOS**: 
   - Windows平台使用 [**UnPlugged**](https://github.com/corpnewt/UnPlugged) 制作macOS安装U盘；macOS平台可参考[官方制作教程](https://dortania.github.io/OpenCore-Install-Guide/installer-guide/mac-install.html)。
   - 安装出现故障时，查阅 [OpenCore 排错指南](https://dortania.github.io/OpenCore-Install-Guide/troubleshooting/troubleshooting.html)。

> [!NOTE]
> 1. 系统安装完成后，若需OpenCore Legacy Patcher，执行底层根补丁即可解锁缺失硬件功能（例如新款博通无线网卡、显卡硬件加速）。
> 
> 2. AMD显卡打完OCLP底层补丁后，需删除启动参数 `-radvesa`/`-amd_no_dgpu_accel`，显卡硬件加速才能正常启用。

## 🤝 **参与贡献**

欢迎所有人提交改进代码与建议！如果你有优化本项目的想法，可以Fork仓库提交PR，或新建Issue并打上「功能增强」标签。

别忘了给项目点亮 ⭐ Star！感谢你的支持！ 🌟

## 📜 **开源协议**

本项目基于 BSD 3-Clause 开源协议分发，详情查看仓库内 `LICENSE` 文件。

## 🙌 **致谢名单**

- [OpenCorePkg](https://github.com/acidanthera/OpenCorePkg) 及配套驱动集合 [kexts](https://github.com/lzhoang2801/OpCore-Simplify/blob/main/Scripts/datasets/kext_data.py) —— 本项目核心底层依赖
- [SSDTTime](https://github.com/corpnewt/SSDTTime) —— SSDT补丁制作工具

## 📞 **联系方式**

**Hoang Hong Quan（黄鸿全）**
> Facebook [@macforce2601](https://facebook.com/macforce2601) &nbsp;&middot;&nbsp;
> Telegram [@lzhoang2601](https://t.me/lzhoang2601) &nbsp;&middot;&nbsp;
> 邮箱：lzhoang2601@gmail.com

## 🌟 **项目Star增长趋势**

[![Star 趋势图表](https://api.star-history.com/svg?repos=lzhoang2801/OpCore-Simplify&type=Date)](https://star-history.com/#lzhoang2801/OpCore-Simplify&Date)
