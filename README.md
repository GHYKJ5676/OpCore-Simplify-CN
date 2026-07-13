<br/>
<div align="center">
  <h3 align="center">OpCore Simplify</h3>

  <p align="center">
    一款专为简化 <a href="https://github.com/acidanthera/OpenCorePkg">OpenCore</a> EFI 制作而生的工具，通过自动化基础设置流程并提供标准化配置，减少手动操作，助力您的黑苹果之旅更加准确高效。
    <br />
    <br />
    <a href="#-功能特性">功能特性</a> •
    <a href="#-如何使用">如何使用</a> •
    <a href="#-参与贡献">参与贡献</a> •
    <a href="#-许可证">许可证</a> •
    <a href="#-致谢">致谢</a> •
    <a href="#-联系方式">联系方式</a>
  </p>
  
  <p align="center">
    <a href="https://trendshift.io/repositories/15410" target="_blank"><img src="https://trendshift.io/api/badge/repositories/15410" alt="lzhoang2801%2FOpCore-Simplify | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
  </p>
</div>

> [!NOTE]
> **OpenCore Legacy Patcher 3.0.0 – 现已支持 macOS Tahoe 26！**
> 
> 万众期待的 OpenCore Legacy Patcher 3.0.0 版本现已发布，为社区带来了 **对 macOS Tahoe 26 的初步支持**！
> 
> 🚨 **请注意：**  
> - 只有 **来自 [lzhoang2801/OpenCore-Legacy-Patcher](https://github.com/lzhoang2801/OpenCore-Legacy-Patcher/releases/tag/3.0.0) 仓库的 OpenCore-Patcher 3.0.0** 才提供对 macOS Tahoe 26 的支持及早期补丁。
> - 官方 Dortania 发布版或旧版补丁 **无法** 在 macOS Tahoe 26 上工作。

> [!WARNING]
> 虽然 OpCore Simplify 能大幅缩短设置时间，但黑苹果之旅仍需：
> - 理解 [Dortania 指南](https://dortania.github.io/OpenCore-Install-Guide/) 中的基本概念
> - 在安装过程中进行测试和故障排查
> - 耐心和毅力来解决可能出现的各种问题
>
> 我们的工具不保证首次尝试就能成功安装，但能帮助您顺利起步。

## ✨ **功能特性**

1. **全面的硬件与 macOS 支持**  
   完整支持现代硬件。可使用“兼容性检查器”查看受支持/不受支持的设备及可安装的 macOS 版本。

   | **组件**       | **支持情况**                                                                                        |
   |----------------|-----------------------------------------------------------------------------------------------------|
   | **CPU**        | Intel：Nehalem 和 Westmere（第1代）→ Arrow Lake（第15代/酷睿 Ultra 系列2）<br> AMD：Ryzen 和 Threadripper，配合 [AMD Vanilla](https://github.com/AMD-OSX/AMD_Vanilla) |
   | **GPU**        | Intel iGPU：Iron Lake（第1代）→ Ice Lake（第10代）<br> AMD APU：全系列 Vega Raven ASIC 家族（Ryzen 1xxx → 5xxx，7x30 系列）<br> AMD dGPU：Navi 23、Navi 22、Navi 21 及更早系列<br> NVIDIA：Kepler、Pascal、Maxwell、Fermi、Tesla 系列 |
   | **macOS**      | macOS High Sierra → macOS Tahoe |

2. **ACPI 补丁与 Kexts**  
   根据硬件配置自动检测并添加所需的 ACPI 补丁和 kexts。
   
   - 集成 [SSDTTime](https://github.com/corpnewt/SSDTTime) 用于常用补丁（如 FakeEC、FixHPET、PLUG、RTCAWAC）。
   - 包含定制补丁：
      - 通过将第一个 CPU 条目指向活动 CPU、禁用 UNC0 设备，并为 HEDT 系统创建新 RTC 设备，防止内核崩溃。
      - 禁用不支持或不使用的 PCI 设备，如 GPU（使用 Optimus 和 Bumblebee 方法或添加 disable-gpu 属性）、Wi-Fi 卡和 NVMe 存储控制器。
      - 修复 _PRW 方法（GPRW、UPRW、HP 特殊）中的睡眠状态值，防止立即唤醒。
      - 添加设备包括 ALS0、BUS0、MCHC、PMCR、PNLF、RMNE、IMEI、USBX、XOSI 以及 Surface 补丁。
      - 启用 ALSD 和 GPI0 设备。

3. **自动更新**  
   每次构建 EFI 前，自动检查并更新 OpenCorePkg 和 kexts（来自 [Dortania Builds](https://dortania.github.io/builds/) 及 GitHub 发布版）。

4. **EFI 配置**  
   根据广泛使用的资料和个人经验，应用额外的定制化配置。

   - 为某些不被 macOS 识别的 AMD GPU 伪造 GPU ID。
   - 对具有 P-core 和 E-core 的 Intel CPU 使用 CpuTopologyRebuild kext 以提升性能。
   - 禁用系统完整性保护（SIP）。
   - 为 Intel Pentium、Celeron、Core 和 Xeon 处理器伪造 CPU ID。
   - 为 AMD CPU 以及 Rocket Lake（第11代）及更新型号的 Intel Pentium、Celeron、Xeon、Core 系列添加自定义 CPU 名称。
   - 添加补丁以允许在不支持的 SMBIOS 下启动 macOS。
   - 添加 NVRAM 条目以跳过内部蓝牙控制器检查。
   - 根据具体的 Resizable BAR 信息正确配置 ResizeAppleGpuBars。
   - 在存在支持的独立 GPU 时，灵活配置 iGPU 为无头模式或驱动显示器。
   - 强制 Intel GPU 使用 VESA 模式及 HDMI/DVI 连接器，简化安装过程。
   - 提供使用 OpenCore Legacy Patcher 所需的配置。
   - 为网络设备（修复 iServices 中“无法与服务器通信”的问题）和存储控制器（修复内置驱动器显示为外置的问题）添加内置设备属性。
   - 优先选择针对电源管理和性能都优化的 SMBIOS。
   - 在 macOS Ventura 13 及更新版本中，重新启用旧款 Intel CPU 的电源管理。
   - 为 itlwm kext 应用 WiFi 配置文件，实现开机时自动连接 WiFi。

   等等……

5. **轻松定制**  
   除了应用的默认设置外，用户还可根据需要轻松进行进一步定制。

   - 自定义 ACPI 补丁、kexts 和 SMBIOS 调整（**不推荐**）。
   - 在不支持的 macOS 版本上强制加载 kexts。

## 🚀 **如何使用**

1. **下载 OpCore Simplify**：
   - 点击 **Code** → **Download ZIP**，或通过此 [链接](https://github.com/lzhoang2801/OpCore-Simplify/archive/refs/heads/main.zip) 直接下载。  
   - 将下载的 ZIP 文件解压到您想要的位置。

   ![下载 OpCore Simplify](https://i.imgur.com/mcE7OSX.png)

2. **运行 OpCore Simplify**：
   - 在 **Windows** 上，运行 `OpCore-Simplify.bat`。
   - 在 **macOS** 上，运行 `OpCore-Simplify.command`。
   - 在 **Linux** 上，使用现有 Python 解释器运行 `OpCore-Simplify.py`。

   ![OpCore Simplify 菜单](https://i.imgur.com/vTr1V9D.png)

3. **选择硬件报告**：
   - 在 Windows 上，会有 `E. Export hardware report` 选项，建议使用此选项以获得基于当前硬件配置和 BIOS 的最佳结果。
   - 或者，使用 [**Hardware Sniffer**](https://github.com/lzhoang2801/Hardware-Sniffer) 创建 `Report.json` 和 ACPI 转储，以便手动配置。

   ![选择硬件报告](https://i.imgur.com/MbRmIGJ.png)

   ![加载 ACPI 表](https://i.imgur.com/SbL6N6v.png)

   ![兼容性检查器](https://i.imgur.com/kuDGMmp.png)

4. **选择 macOS 版本并自定义 OpenCore EFI**：
   - 默认情况下，会自动为您的硬件选择最新的兼容 macOS 版本。
   - OpCore Simplify 会自动应用必要的 ACPI 补丁和 kexts。
   - 您可以根据需要手动查看和自定义这些设置。

   ![OpCore Simplify 菜单](https://i.imgur.com/TSk9ejy.png)

5. **构建 OpenCore EFI**：
   - 自定义完所有选项后，选择 **Build OpenCore EFI** 生成您的 EFI。
   - 该工具会自动下载必要的引导程序和 kexts，可能需要几分钟时间。

   ![WiFi 配置文件提取器](https://i.imgur.com/71TkJkD.png)

   ![选择声卡 Layout ID](https://i.imgur.com/Mcm20EQ.png)

   ![构建 OpenCore EFI](https://i.imgur.com/deyj5de.png)

6. **USB 端口映射**：
   - 构建 EFI 后，按照步骤进行 USB 端口映射。

   ![结果](https://i.imgur.com/MIPigPF.png)

7. **制作 USB 并安装 macOS**：
   - 在 Windows 上使用 [**UnPlugged**](https://github.com/corpnewt/UnPlugged) 制作 macOS USB 安装盘，或在 macOS 上参考 [此指南](https://dortania.github.io/OpenCore-Install-Guide/installer-guide/mac-install.html)。
   - 故障排查请参考 [OpenCore 故障排查指南](https://dortania.github.io/OpenCore-Install-Guide/troubleshooting/troubleshooting.html)。

> [!NOTE]
> 1. 安装成功后，若需要使用 OpenCore Legacy Patcher，只需应用 root 补丁即可激活缺失的功能（如现代 Broadcom Wi-Fi 卡和图形加速）。
> 
> 2. 对于 AMD GPU，在应用 OpenCore Legacy Patcher 的 root 补丁后，需要移除引导参数 `-radvesa`/`-amd_no_dgpu_accel` 才能使图形加速生效。

## 🤝 **参与贡献**

**非常欢迎** 贡献！如果您有改进此项目的想法，请随时 fork 仓库并创建 pull request，或使用“enhancement”标签开启 issue。

别忘了 ⭐ 给项目点个星！感谢您的支持！🌟

## 📜 **许可证**

基于 BSD 3-Clause License 分发。详见 `LICENSE` 文件。

## 🙌 **致谢**

- [OpenCorePkg](https://github.com/acidanthera/OpenCorePkg) 及 [kexts](https://github.com/lzhoang2801/OpCore-Simplify/blob/main/Scripts/datasets/kext_data.py) – 本项目的基石。
- [SSDTTime](https://github.com/corpnewt/SSDTTime) – SSDT 补丁工具。

## 📞 **联系方式**

**Hoang Hong Quan**
> Facebook [@macforce2601](https://facebook.com/macforce2601) &nbsp;&middot;&nbsp;
> Telegram [@lzhoang2601](https://t.me/lzhoang2601) &nbsp;&middot;&nbsp;
> 邮箱：lzhoang2601@gmail.com

## 🌟 **Star 历史**

[![Star History Chart](https://api.star-history.com/svg?repos=lzhoang2801/OpCore-Simplify&type=Date)](https://star-history.com/#lzhoang2801/OpCore-Simplify&Date)
