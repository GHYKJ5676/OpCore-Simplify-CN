# 原始来源：https://github.com/corpnewt/SSDTTime/blob/44aadf01b7fe75cb4a3eab5590e7b6c458265c6f/SSDTTime.py

from Scripts.datasets import acpi_patch_data
from Scripts.datasets import chipset_data
from Scripts.datasets import cpu_data
from Scripts.datasets import pci_data
from Scripts import smbios
from Scripts import dsdt
from Scripts import run
from Scripts import utils
import os
import binascii
import re
import tempfile
import shutil
import sys
import plistlib

class ACPIGuru:
    def __init__(self):
        self.acpi = dsdt.DSDT()
        self.smbios = smbios.SMBIOS()
        self.run = run.Run().run
        self.utils = utils.Utils()
        self.patches = acpi_patch_data.patches
        self.hardware_report = None
        self.disabled_devices = None
        self.acpi_directory = None
        self.smbios_model = None
        self.dsdt = None
        self.lpc_bus_device = None
        self.osi_strings = {
            "Windows 2000": "Windows 2000",
            "Windows XP": "Windows 2001",
            "Windows XP SP1": "Windows 2001 SP1",
            "Windows Server 2003": "Windows 2001.1",
            "Windows XP SP2": "Windows 2001 SP2",
            "Windows Server 2003 SP1": "Windows 2001.1 SP1",
            "Windows Vista": "Windows 2006",
            "Windows Vista SP1": "Windows 2006 SP1",
            "Windows Server 2008": "Windows 2006.1",
            "Windows 7, Win Server 2008 R2": "Windows 2009",
            "Windows 8, Win Server 2012": "Windows 2012",
            "Windows 8.1": "Windows 2013",
            "Windows 10": "Windows 2015",
            "Windows 10, version 1607": "Windows 2016",
            "Windows 10, version 1703": "Windows 2017",
            "Windows 10, version 1709": "Windows 2017.2",
            "Windows 10, version 1803": "Windows 2018",
            "Windows 10, version 1809": "Windows 2018.2",
            "Windows 10, version 1903": "Windows 2019",
            "Windows 10, version 2004": "Windows 2020",
            "Windows 11": "Windows 2021",
            "Windows 11, version 22H2": "Windows 2022"
        }
        self.pre_patches = (
            {
                "PrePatch":"GPP7 重复 _PRW 方法",
                "Comment" :"将 GPP7._PRW 重命名为 XPRW 以修复技嘉的错误",
                "Find"    :"3708584847500A021406535245470214065350525701085F505257",
                "Replace" :"3708584847500A0214065352454702140653505257010858505257"
            },
            {
                "PrePatch":"GPP7 重复 UP00 设备",
                "Comment" :"将 GPP7.UP00 重命名为 UPXX 以修复技嘉的错误",
                "Find"    :"1047052F035F53425F50434930475050375B82450455503030",
                "Replace" :"1047052F035F53425F50434930475050375B82450455505858"
            },
            {
                "PrePatch":"GPP6 重复 _PRW 方法",
                "Comment" :"将 GPP6._PRW 重命名为 XPRW 以修复华擎的错误",
                "Find"    :"47505036085F4144520C04000200140F5F505257",
                "Replace" :"47505036085F4144520C04000200140F58505257"
            },
            {
                "PrePatch":"GPP1 重复 PTXH 设备",
                "Comment" :"将 GPP1.PTXH 重命名为 XTXH 以修复微星的错误",
                "Find"    :"50545848085F41445200140F",
                "Replace" :"58545848085F41445200140F"
            }
        )
        self.target_irqs = [0, 2, 8, 11]
        self.illegal_names = ("XHC1", "EHC1", "EHC2", "PXSX")
        self.dsdt_patches = []

    def get_unique_name(self,name,target_folder,name_append="-Patched"):
        # 在 Results 文件夹中获取新文件名，避免覆盖原文件
        name = os.path.basename(name)
        ext  = "" if not "." in name else name.split(".")[-1]
        if ext: name = name[:-len(ext)-1]
        if name_append: name = name+str(name_append)
        check_name = ".".join((name,ext)) if ext else name
        if not os.path.exists(os.path.join(target_folder,check_name)):
            return check_name
        # 需要唯一名称
        num = 1
        while True:
            check_name = "{}-{}".format(name,num)
            if ext: check_name += "."+ext
            if not os.path.exists(os.path.join(target_folder,check_name)):
                return check_name
            num += 1

    def get_unique_device(self, path, base_name, starting_number=0, used_names = []):
        # 追加十六进制数字直到找到唯一设备
        while True:
            hex_num = hex(starting_number).replace("0x","").upper()
            name = base_name[:-1*len(hex_num)]+hex_num
            if not len(self.acpi.get_device_paths("."+name)) and not name in used_names:
                return (name,starting_number)
            starting_number += 1

    def sorted_nicely(self, l): 
        convert = lambda text: int(text) if text.isdigit() else text 
        alphanum_key = lambda key: [ convert(c) for c in re.split('([0-9]+)', key.lower()) ] 
        return sorted(l, key = alphanum_key)
    
    def read_acpi_tables(self, path):
        if not path:
            return
        self.utils.head("加载 ACPI 表")
        print("by CorpNewt")
        print("")
        tables = []
        trouble_dsdt = None
        fixed = False
        temp = None
        prior_tables = self.acpi.acpi_tables # 保留以防失败
        # 清空现有表，重新加载
        self.acpi.acpi_tables = {}
        if os.path.isdir(path):
            print("正在从 {} 收集有效表...\n".format(os.path.basename(path)))
            for t in self.sorted_nicely(os.listdir(path)):
                if not "Patched" in t and self.acpi.table_is_valid(path,t):
                    print(" - {}".format(t))
                    tables.append(t)
            if not tables:
                # 检查传入目录内是否有 ACPI 子目录——可能拖入了 SysReport
                if os.path.isdir(os.path.join(path,"ACPI")):
                    return self.read_acpi_tables(os.path.join(path,"ACPI"))
                print(" - 未找到有效的 .aml 文件！")
                print("")
                self.utils.request_input()
                self.acpi.acpi_tables = prior_tables
                return
            print("")
            # 至少有一个文件，尝试找到 DSDT 并单独加载
            dsdt_list = [x for x in tables if self.acpi._table_signature(path,x) == "DSDT"]
            if len(dsdt_list) > 1:
                print("发现多个 DSDT 签名文件：")
                for d in self.sorted_nicely(dsdt_list):
                    print(" - {}".format(d))
                print("\n每次只允许一个，请移除一个后重试。")
                print("")
                self.utils.request_input()
                self.acpi.acpi_tables = prior_tables
                return
            dsdt = dsdt_list[0] if len(dsdt_list) else None
            if dsdt:
                print("正在反编译 {} 以验证是否需要预补丁...".format(dsdt))
                if not self.acpi.load(os.path.join(path,dsdt))[0]:
                    trouble_dsdt = dsdt
                else:
                    print("\n反编译成功！\n")
        elif not "Patched" in path and os.path.isfile(path):
            print("正在加载 {}...".format(os.path.basename(path)))
            if self.acpi.load(path)[0]:
                print("\n完成。")
                return os.path.dirname(path)
            if not self.acpi._table_signature(path) == "DSDT":
                print("\n{} 无法反编译！".format(os.path.basename(path)))
                print("")
                self.utils.request_input()
                self.acpi.acpi_tables = prior_tables
                return
            trouble_dsdt = os.path.basename(path)
            tables.append(os.path.basename(path))
            path = os.path.dirname(path)
        else:
            print("传入的文件/文件夹不存在！")
            print("")
            self.utils.request_input()
            self.acpi.acpi_tables = prior_tables
            return

        if trouble_dsdt:
            temp = tempfile.mkdtemp()
            for table in tables:
                shutil.copy(os.path.join(path,table), temp)
            trouble_path = os.path.join(temp,trouble_dsdt)
            print("检查可用预补丁...")
            print("将 {} 加载到内存...".format(trouble_dsdt))
            with open(trouble_path,"rb") as f:
                d = f.read()
            res = self.acpi.check_output(path)
            target_name = self.get_unique_name(trouble_dsdt,res,name_append="-Patched")
            self.dsdt_patches = []
            print("正在应用补丁...\n")
            for p in self.pre_patches:
                if not all(x in p for x in ("PrePatch","Comment","Find","Replace")): continue
                print(" - {}".format(p["PrePatch"]))
                find = binascii.unhexlify(p["Find"])
                if d.count(find) == 1:
                    self.dsdt_patches.append(p)
                    repl = binascii.unhexlify(p["Replace"])
                    print(" --> 已定位，正在应用...")
                    d = d.replace(find,repl)
                    with open(trouble_path,"wb") as f:
                        f.write(d)
                    if self.acpi.load(trouble_path)[0]:
                        fixed = True
                        print("\n反编译成功！\n")
                        break
            if not fixed:
                print("\n{} 无法反编译！".format(trouble_dsdt))
                print("")
                self.utils.request_input()
                if temp:
                    shutil.rmtree(temp,ignore_errors=True)
                self.acpi.acpi_tables = prior_tables
                return

        if len(tables) > 1:
            print("正在加载 {} 中的有效表...".format(path))
        loaded_tables,failed = self.acpi.load(temp or path)
        if not loaded_tables or failed:
            print("\n加载 {}{} 中的表失败\n".format(
                os.path.dirname(path) if os.path.isfile(path) else path,
                ":" if failed else ""
            ))
            for t in self.sorted_nicely(failed):
                print(" - {}".format(t))
            if not loaded_tables:
                self.acpi.acpi_tables = prior_tables
        else:
            if len(tables) > 1:
                print("")
            print("完成。")
        if trouble_dsdt or not loaded_tables or failed:
            print("")
        if temp:
            shutil.rmtree(temp,ignore_errors=True)
        self.dsdt = self.acpi.get_dsdt_or_only()
        return path

    def _ensure_dsdt(self, allow_any=False):
        return self.dsdt and ((allow_any and self.acpi.acpi_tables) or (not allow_any and self.acpi.get_dsdt_or_only()))

    def ensure_dsdt(self, allow_any=False):
        if self._ensure_dsdt(allow_any=allow_any):
            return True
        self.select_acpi_tables()
        self.dsdt = self.acpi.get_dsdt_or_only()
        return self._ensure_dsdt(allow_any=allow_any)

    def get_sta_var(self,var="STAS",device=None,dev_hid="ACPI000E",dev_name="AWAC",log_locate=False,table=None):
        has_var = False
        patches = []
        root = None
        if device:
            dev_list = self.acpi.get_device_paths(device,table=table)
            if not len(dev_list):
                if log_locate: print(" - 找不到 {}".format(device))
                return {"value":False}
        else:
            if log_locate: print("正在定位 {} ({}) 设备...".format(dev_hid,dev_name))
            dev_list = self.acpi.get_device_paths_with_hid(dev_hid,table=table)
            if not len(dev_list):
                if log_locate: print(" - 找不到任何 {} 设备".format(dev_hid))
                return {"valid":False}
        dev = dev_list[0]
        if log_locate: print(" - 找到 {}".format(dev[0]))
        root = dev[0].split(".")[0]
        sta_type = "MethodObj"
        sta  = self.acpi.get_method_paths(dev[0]+"._STA",table=table)
        xsta = self.acpi.get_method_paths(dev[0]+".XSTA",table=table)
        if not sta and not xsta:
            sta_type = "IntObj"
            sta = self.acpi.get_name_paths(dev[0]+"._STA",table=table)
            xsta = self.acpi.get_name_paths(dev[0]+".XSTA",table=table)
        if xsta and not sta:
            return {"valid":False,"break":True,"device":dev,"dev_name":dev_name,"dev_hid":dev_hid,"sta_type":sta_type}
        if sta:
            if var:
                scope = "\n".join(self.acpi.get_scope(sta[0][1],strip_comments=True,table=table))
                has_var = var in scope
        if sta and not has_var:
            sta_index = self.acpi.find_next_hex(sta[0][1],table=table)[1]
            sta_hex  = "5F535441" # _STA
            xsta_hex = "58535441" # XSTA
            padl,padr = self.acpi.get_shortest_unique_pad(sta_hex,sta_index,table=table)
            patches.append({"Comment":"{} _STA 重命名为 XSTA".format(dev_name),"Find":padl+sta_hex+padr,"Replace":padl+xsta_hex+padr})
        return {"valid":True,"has_var":has_var,"sta":sta,"patches":patches,"device":dev,"dev_name":dev_name,"dev_hid":dev_hid,"root":root,"sta_type":sta_type}

    def get_lpc_name(self,log=False,skip_ec=False,skip_common_names=False):
        if log: print("正在定位 LPC(B)/SBRG...")
        for table_name in self.sorted_nicely(list(self.acpi.acpi_tables)):
            table = self.acpi.acpi_tables[table_name]
            if not skip_ec:
                ec_list = self.acpi.get_device_paths_with_hid("PNP0C09",table=table)
                if len(ec_list):
                    lpc_name = ".".join(ec_list[0][0].split(".")[:-1])
                    if log: print(" - 在 {} 中找到 {}".format(lpc_name,table_name))
                    return lpc_name
            if not skip_common_names:
                for x in ("LPCB", "LPC0", "LPC", "SBRG", "PX40"):
                    try:
                        lpc_name = self.acpi.get_device_paths(x,table=table)[0][0]
                        if log: print(" - 在 {} 中找到 {}".format(lpc_name,table_name))
                        return lpc_name
                    except: pass
            paths = self.acpi.get_path_of_type(obj_type="Name",obj="_ADR",table=table)
            for path in paths:
                adr = self.get_address_from_line(path[1],table=table)
                if adr in (0x001F0000, 0x00140003):
                    lpc_name = path[0][:-5]
                    lpc_hid = lpc_name+"._HID"
                    if any(x[0]==lpc_hid for x in table.get("paths",[])):
                        continue
                    if log: print(" - 在 {} 中找到 {}".format(lpc_name,table_name))
                    return lpc_name
        if log:
            print(" - 找不到 LPC(B)！中止！")
            print("")
        return None

    def get_address_from_line(self, line, split_by="_ADR, ", table=None):
        if table is None:
            table = self.acpi.get_dsdt_or_only()
        try:
            return int(table["lines"][line].split(split_by)[1].split(")")[0].replace("Zero","0x0").replace("One","0x1"),16)
        except:
            return None

    def enable_cpu_power_management(self):
        for table_name in self.sorted_nicely(list(self.acpi.acpi_tables)):
            ssdt_name = "SSDT-PLUG"
            table = self.acpi.acpi_tables[table_name]
            if not table.get("signature") in (b"DSDT",b"SSDT"):
                continue
            try: cpu_name = self.acpi.get_processor_paths(table=table)[0][0]
            except: cpu_name = None
            if cpu_name:
                ssdt = """//
// 基于 https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/AcpiSamples/SSDT-PLUG.dsl 示例
//
DefinitionBlock ("", "SSDT", 2, "ZPSS", "CpuPlug", 0x00003000)
{
    External ([[CPUName]], ProcessorObj)
    Scope ([[CPUName]])
    {
        If (_OSI ("Darwin")) {
            Method (_DSM, 4, NotSerialized)  // _DSM: 设备特定方法
            {
                If (LNot (Arg2))
                {
                    Return (Buffer (One)
                    {
                        0x03
                    })
                }
                Return (Package (0x02)
                {
                    "plugin-type", 
                    One
                })
            }
        }
    }
}""".replace("[[CPUName]]",cpu_name)
            else:
                ssdt_name += "-ALT"
                procs = self.acpi.get_device_paths_with_hid(hid="ACPI0007",table=table)
                if not procs:
                    continue
                parent = procs[0][0].split(".")[0]
                proc_list = []
                for proc in procs:
                    uid = self.acpi.get_path_of_type(obj_type="Name",obj=proc[0]+"._UID",table=table)
                    if not uid:
                        continue
                    try:
                        _uid = table["lines"][uid[0][1]].split("_UID, ")[1].split(")")[0]
                        proc_list.append((proc[0],_uid))
                    except:
                        pass
                if not proc_list:
                    continue
                ssdt = """//
// 基于 https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/AcpiSamples/Source/SSDT-PLUG-ALT.dsl 示例
//
DefinitionBlock ("", "SSDT", 2, "ZPSS", "CpuPlugA", 0x00003000)
{
    External ([[parent]], DeviceObj)

    Scope ([[parent]])
    {""".replace("[[parent]]",parent)
                schemes = ("C000","CP00","P000","PR00","CX00","PX00")
                for i,proc_uid in enumerate(proc_list):
                    proc,uid = proc_uid
                    adr = hex(i)[2:].upper()
                    name = None
                    for s in schemes:
                        name_check = s[:-len(adr)]+adr
                        check_path = "{}.{}".format(parent,name_check)
                        if self.acpi.get_path_of_type(obj_type="Device",obj=check_path,table=table):
                            continue
                        name = name_check
                        break
                    if not name:
                        return
                    ssdt+="""
        Processor ([[name]], [[uid]], 0x00000510, 0x06)
        {
            // [[proc]]
            Name (_HID, "ACPI0007" /* 处理器设备 */)  // _HID: 硬件 ID
            Name (_UID, [[uid]])
            Method (_STA, 0, NotSerialized)  // _STA: 状态
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0F)
                }
                Else
                {
                    Return (Zero)
                }
            }""".replace("[[name]]",name).replace("[[uid]]",uid).replace("[[proc]]",proc)
                    if i == 0:
                        ssdt += """
            Method (_DSM, 4, NotSerialized)
            {
                If (LNot (Arg2)) {
                    Return (Buffer (One) { 0x03 })
                }
                Return (Package (0x02)
                {
                    "plugin-type",
                    One
                })
            }"""
                    ssdt += """
        }"""
                ssdt += """
    }
}"""
            return {
                "Add": [
                    {
                        "Comment": ssdt_name + ".aml",
                        "Enabled": self.write_ssdt(ssdt_name, ssdt),
                        "Path": ssdt_name + ".aml"
                    }
                ]
            }

    def list_irqs(self):
        devices = {}
        current_device = None
        current_hid = None
        irq = False
        last_irq = False
        irq_index = 0
        for index,line in enumerate(self.dsdt["lines"]):
            if self.acpi.is_hex(line):
                continue
            if irq:
                num = line.split("{")[1].split("}")[0].replace(" ","")
                num = "#" if not len(num) else num
                if current_device in devices:
                    if last_irq:
                        devices[current_device]["irq"] += ":"+num
                    else:
                        irq_index = self.acpi.find_next_hex(index)[1]
                        devices[current_device]["irq"] += "-"+str(irq_index)+"|"+num
                else:
                    irq_index = self.acpi.find_next_hex(index)[1]
                    devices[current_device] = {"irq":str(irq_index)+"|"+num}
                irq = False
                last_irq = True
            elif "Device (" in line:
                if current_device and current_device in devices and current_hid:
                    devices[current_device]["hid"] = current_hid
                last_irq = False
                current_hid = None
                try: current_device = line.split("(")[1].split(")")[0]
                except:
                    current_device = None
                    continue
            elif "_HID, " in line and current_device:
                try: current_hid = line.split('"')[1]
                except: pass
            elif "IRQNoFlags" in line and current_device:
                irq = True
            elif len(line.replace("{","").replace("}","").replace("(","").replace(")","").replace(" ","").split("//")[0]):
                last_irq = False
        if current_device and current_device in devices and current_hid:
            devices[current_device]["hid"] = current_hid
        return devices

    def get_irq_choice(self, irqs):
        names_and_hids = [
            "PIC",
            "IPIC",
            "TMR",
            "TIMR",
            "RTC",
            "RTC0",
            "RTC1",
            "PNPC0000",
            "PNP0100",
            "PNP0B00"
        ]
        defaults = [x for x in irqs if x.upper() in names_and_hids or irqs[x].get("hid","").upper() in names_and_hids]
        d = {}
        for x in defaults:
            d[x] = self.target_irqs
        return d

    def get_hex_from_irqs(self, irq, rem_irq = None):
        lines = []
        remd  = []
        for a in irq.split("-"):
            index,i = a.split("|")
            index = int(index)
            find = self.get_int_for_line(i)
            repl = [0]*len(find)
            if rem_irq:
                repl = [x for x in find]
                matched = []
                for x in rem_irq:
                    rem = self.convert_irq_to_int(x)
                    repl1 = [y&(rem^0xFFFF) if y >= rem else y for y in repl]
                    if repl1 != repl:
                        remd.append(x)
                    repl = [y for y in repl1]
            d = {
                "irq":i,
                "find": "".join(["22"+self.acpi.get_hex_from_int(x) for x in find]),
                "repl": "".join(["22"+self.acpi.get_hex_from_int(x) for x in repl]),
                "remd": remd,
                "index": index
                }
            d["changed"] = not (d["find"]==d["repl"])
            lines.append(d)
        return lines
    
    def get_int_for_line(self, irq):
        irq_list = []
        for i in irq.split(":"):
            irq_list.append(self.same_line_irq(i))
        return irq_list

    def convert_irq_to_int(self, irq):
        b = "0"*(16-irq)+"1"+"0"*(irq)
        return int(b,2)

    def same_line_irq(self, irq):
        total = 0
        for i in irq.split(","):
            if i == "#":
                continue
            try: i=int(i)
            except: continue
            if i > 15 or i < 0:
                continue
            total = total | self.convert_irq_to_int(i)
        return total
    
    def fix_irq_conflicts(self):
        hpets = self.acpi.get_device_paths_with_hid("PNP0103")
        hpet_fake = not hpets
        hpet_sta = False
        sta = None
        patches = []
        if hpets:
            name = hpets[0][0]
            sta = self.get_sta_var(var=None,dev_hid="PNP0103",dev_name="HPET",log_locate=False)
            if sta.get("patches"):
                hpet_sta = True
                patches.extend(sta.get("patches",[]))
            hpet = self.acpi.get_method_paths(name+"._CRS") or self.acpi.get_name_paths(name+"._CRS")
            if not hpet:
                return
            crs_index = self.acpi.find_next_hex(hpet[0][1])[1]
            mem_base = mem_length = primed = None
            for line in self.acpi.get_scope(hpets[0][1],strip_comments=True):
                if "Memory32Fixed (" in line:
                    primed = True
                    continue
                if not primed:
                    continue
                elif ")" in line:
                    break
                try:
                    val = line.strip().split(",")[0].replace("Zero","0x0").replace("One","0x1")
                    check = int(val,16)
                except:
                    break
                if mem_base is None:
                    mem_base = val
                else:
                    mem_length = val
                    break
            if not got_mem:
                mem_base = "0xFED00000"
                mem_length = "0x00000400"
            crs  = "5F435253"
            xcrs = "58435253"
            padl,padr = self.acpi.get_shortest_unique_pad(crs, crs_index)
            patches.append({"Comment":"{} _CRS 重命名为 XCRS".format(name.split(".")[-1].lstrip("\\")),"Find":padl+crs+padr,"Replace":padl+xcrs+padr})
        else:
            ec_list = self.acpi.get_device_paths_with_hid("PNP0C09")
            name = None
            if len(ec_list):
                name = ".".join(ec_list[0][0].split(".")[:-1])
            if name == None:
                for x in ("LPCB", "LPC0", "LPC", "SBRG", "PX40"):
                    try:
                        name = self.acpi.get_device_paths(x)[0][0]
                        break
                    except: pass
            if not name:
                return
        devs = self.list_irqs()
        target_irqs = self.get_irq_choice(devs)
        if target_irqs is None: return
        saved_dsdt = self.dsdt.get("raw")
        unique_patches  = {}
        generic_patches = []
        for dev in devs:
            if not dev in target_irqs:
                continue
            irq_patches = self.get_hex_from_irqs(devs[dev]["irq"],target_irqs[dev])
            i = [x for x in irq_patches if x["changed"]]
            for a,t in enumerate(i):
                if not t["changed"]:
                    continue
                matches = re.findall("("+t["find"]+"(.{0,8})(7900|4701|8609))",self.acpi.get_hex_starting_at(t["index"])[0])
                if not len(matches):
                    continue
                if len(matches) > 1:
                    for x in matches:
                        generic_patches.append({
                            "remd":",".join([str(y) for y in set(t["remd"])]),
                            "orig":t["find"],
                            "find":t["find"]+"".join(x[1:]),
                            "repl":t["repl"]+"".join(x[1:])
                        })
                    continue
                ending = "".join(matches[0][1:])
                padl,padr = self.acpi.get_shortest_unique_pad(t["find"]+ending, t["index"])
                t_patch = padl+t["find"]+ending+padr
                r_patch = padl+t["repl"]+ending+padr
                if not dev in unique_patches:
                    unique_patches[dev] = []
                unique_patches[dev].append({
                    "dev":dev,
                    "remd":",".join([str(y) for y in set(t["remd"])]),
                    "orig":t["find"],
                    "find":t_patch,
                    "repl":r_patch
                })
        if len(unique_patches):
            for x in unique_patches:
                for i,p in enumerate(unique_patches[x]):
                    patch_name = "{} IRQ {} 补丁".format(x, p["remd"])
                    if len(unique_patches[x]) > 1:
                        patch_name += " - {}/{}".format(i+1, len(unique_patches[x]))
                    patches.append({
                        "Comment": patch_name,
                        "Find": p["find"],
                        "Replace": p["repl"]
                    })
        if len(generic_patches):
            generic_set = []
            for x in generic_patches:
                if x in generic_set:
                    continue
                generic_set.append(x)
            for i,x in enumerate(generic_set):
                patch_name = "通用 IRQ 补丁 {}/{} - {} - {}".format(i+1,len(generic_set),x["remd"],x["orig"])
                patches.append({
                    "Comment": patch_name,
                    "Find": x["find"],
                    "Replace": x["repl"],
                    "Enabled": False
                })
        self.dsdt["raw"] = saved_dsdt

        ssdt_name = "SSDT-HPET"
        if hpet_fake:
            ssdt_content = """// 伪造 HPET 设备
//
DefinitionBlock ("", "SSDT", 2, "ZPSS", "HPET", 0x00000000)
{
    External ([[name]], DeviceObj)

    Scope ([[name]])
    {
        Device (HPET)
        {
            Name (_HID, EisaId ("PNP0103") /* HPET 系统计时器 */)  // _HID: 硬件 ID
            Name (_CID, EisaId ("PNP0C01") /* 系统板 */)  // _CID: 兼容 ID
            Method (_STA, 0, NotSerialized)  // _STA: 状态
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0F)
                }
                Else
                {
                    Return (Zero)
                }
            }
            Name (_CRS, ResourceTemplate ()  // _CRS: 当前资源设置
            {
                IRQNoFlags ()
                    {0,8,11}
                Memory32Fixed (ReadWrite,
                    0xFED00000,         // 地址基址
                    0x00000400,         // 地址长度
                    )
            })
        }
    }
}""".replace("[[name]]",name)
        else:
            ssdt_content = """//
// 来自 Goldfish64 的补充 HPET _CRS
// 需要将 HPET 的 _CRS 重命名为 XCRS
//
DefinitionBlock ("", "SSDT", 2, "ZPSS", "HPET", 0x00000000)
{
    External ([[name]], DeviceObj)
    External ([[name]].XCRS, [[type]])

    Scope ([[name]])
    {
        Name (BUFX, ResourceTemplate ()
        {
            IRQNoFlags ()
                {0,8,11}
            Memory32Fixed (ReadWrite,
                // [[mem]]
                [[mem_base]],         // 地址基址
                [[mem_length]],         // 地址长度
            )
        })
        Method (_CRS, 0, Serialized)  // _CRS: 当前资源设置
        {
            // 如果启动 macOS 或 XCRS 方法不再存在，则返回我们的缓冲区
            If (LOr (_OSI ("Darwin"), LNot(CondRefOf ([[name]].XCRS))))
            {
                Return (BUFX)
            }
            // 不是 macOS 且 XCRS 存在，返回其结果
            Return ([[name]].XCRS[[method]])
        }""" \
    .replace("[[name]]",name) \
    .replace("[[type]]","MethodObj" if hpet[0][-1] == "Method" else "BuffObj") \
    .replace("[[mem]]","从 DSDT 提取的基址/长度" if got_mem else "默认基址/长度 - 请与您的 DSDT 核对！") \
    .replace("[[mem_base]]",mem_base) \
    .replace("[[mem_length]]",mem_length) \
    .replace("[[method]]"," ()" if hpet[0][-1]=="Method" else "")
            if hpet_sta:
                ssdt_parts = []
                external = False
                for line in ssdt_content.split("\n"):
                    if "External (" in line: external = True
                    elif external:
                        ssdt_parts.append("    External ({}.XSTA, {})".format(name,sta["sta_type"]))
                        external = False
                    ssdt_parts.append(line)
                ssdt_content = "\n".join(ssdt_parts)
                ssdt_content += """
        Method (_STA, 0, NotSerialized)  // _STA: 状态
        {
            // 如果启动 macOS 或 XSTA 方法不再存在，返回 0x0F
            If (LOr (_OSI ("Darwin"), LNot (CondRefOf ([[name]].XSTA))))
            {
                Return (0x0F)
            }
            // 不是 macOS 且 XSTA 存在，返回其结果
            Return ([[name]].XSTA[[called]])
        }""".replace("[[name]]",name).replace("[[called]]"," ()" if sta["sta_type"]=="MethodObj" else "")
            ssdt_content += """
    }
}"""
        return {
            "Add": [
                {
                    "Comment": ssdt_name + ".aml",
                    "Enabled": self.write_ssdt(ssdt_name, ssdt_content),
                    "Path": ssdt_name + ".aml"
                }
            ],
            "Patch": patches
        }

    def fix_system_clock_awac(self):
        rtc_range_needed = False
        rtc_crs_type = None
        crs_lines = []
        lpc_name = None
        awac_dict = self.get_sta_var(var="STAS",dev_hid="ACPI000E",dev_name="AWAC")
        rtc_dict = self.get_sta_var(var="STAS",dev_hid="PNP0B00",dev_name="RTC")
        if not rtc_dict.get("valid"):
            lpc_name = self.get_lpc_name()
            if lpc_name is None:
                return
        else:
            rtc_crs = self.acpi.get_method_paths(rtc_dict["device"][0]+"._CRS") or self.acpi.get_name_paths(rtc_dict["device"][0]+"._CRS")
            if rtc_crs:
                rtc_crs_type = "MethodObj" if rtc_crs[0][-1] == "Method" else "BuffObj"
                if rtc_crs_type.lower() == "buffobj":
                    last_adr = last_len = last_ind = None
                    crs_scope = self.acpi.get_scope(rtc_crs[0][1])
                    pad_len = len(crs_scope[0])-len(crs_scope[0].lstrip())
                    pad = crs_scope[0][:pad_len]
                    fixed_scope = []
                    for line in crs_scope:
                        if line.startswith(pad):
                            fixed_scope.append(line[pad_len:])
                        else:
                            fixed_scope[-1] = fixed_scope[-1]+line
                    for i,line in enumerate(fixed_scope):
                        if "Name (_CRS, " in line:
                            line = line.replace("Name (_CRS, ","Name (BUFX, ").split("  //")[0]
                        if "IO (Decode16," in line:
                            try:
                                curr_adr = int(fixed_scope[i+1].strip().split(",")[0],16)
                                curr_len = int(fixed_scope[i+4].strip().split(",")[0],16)
                                curr_ind = i+4
                            except:
                                rtc_range_needed = False
                                break
                            if last_adr is not None:
                                adjust = curr_adr - (last_adr + last_len)
                                if adjust:
                                    rtc_range_needed = True
                                    try:
                                        hex_find,hex_repl = self.hexy(last_len,pad_to=2),self.hexy(last_len+adjust,pad_to=2)
                                        crs_lines[last_ind] = crs_lines[last_ind].replace(hex_find,hex_repl)
                                    except:
                                        rtc_range_needed = False
                                        break
                            last_adr,last_len,last_ind = curr_adr,curr_len,curr_ind
                        crs_lines.append(line)
                if rtc_range_needed:
                    crs_index = self.acpi.find_next_hex(rtc_crs[0][1])[1]
                    crs_hex  = "5F435253"
                    xcrs_hex = "58435253"
                    padl,padr = self.acpi.get_shortest_unique_pad(crs_hex, crs_index)
                    patches = rtc_dict.get("patches",[])
                    patches.append({"Comment":"{} _CRS 重命名为 XCRS".format(rtc_dict["dev_name"]),"Find":padl+crs_hex+padr,"Replace":padl+xcrs_hex+padr})
                    rtc_dict["patches"] = patches
                    rtc_dict["crs"] = True
        if not awac_dict.get("valid") and rtc_dict.get("valid") and not rtc_dict.get("has_var") and not rtc_dict.get("sta") and not rtc_range_needed:
            return
        suffix  = []
        for x in (awac_dict,rtc_dict):
            if not x.get("valid"): continue
            val = ""
            if x.get("sta") and not x.get("has_var"):
                val = "{} _STA 重命名为 XSTA".format(x["dev_name"])
            if x.get("crs"):
                val += "{} _CRS 重命名为 XCRS".format(" and " if val else x["dev_name"])
            if val: suffix.append(val)
        ssdt_name = "SSDT-RTCAWAC"
        ssdt = """//
// 原始来源 Acidanthera：
//  - https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/AcpiSamples/SSDT-AWAC.dsl
//  - https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/AcpiSamples/SSDT-RTC0.dsl
//
// 使用 ZPSS 名称表示此处生成，便于故障排除。
//
DefinitionBlock ("", "SSDT", 2, "ZPSS", "RTCAWAC", 0x00000000)
{
"""
        if any(x.get("has_var") for x in (awac_dict,rtc_dict)):
            ssdt += """    External (STAS, IntObj)
    Scope (\\)
    {
        Method (_INI, 0, NotSerialized)  // _INI: 初始化
        {
            If (_OSI ("Darwin"))
            {
                Store (One, STAS)
            }
        }
    }
"""
        for x in (awac_dict,rtc_dict):
            if not x.get("valid") or x.get("has_var") or not x.get("device"): continue
            macos,original = ("Zero","0x0F") if x.get("dev_hid") == "ACPI000E" else ("0x0F","Zero")
            if x.get("sta"):
                ssdt += """    External ([[DevPath]], DeviceObj)
    External ([[DevPath]].XSTA, [[sta_type]])
    Scope ([[DevPath]])
    {
        Name (ZSTA, [[Original]])
        Method (_STA, 0, NotSerialized)  // _STA: 状态
        {
            If (_OSI ("Darwin"))
            {
                Return ([[macOS]])
            }
            // 默认为 [[Original]]，但如果可能则返回重命名的 XSTA 结果
            If (CondRefOf ([[DevPath]].XSTA))
            {
                Store ([[DevPath]].XSTA[[called]], ZSTA)
            }
            Return (ZSTA)
        }
    }
""".replace("[[DevPath]]",x["device"][0]).replace("[[Original]]",original).replace("[[macOS]]",macos).replace("[[sta_type]]",x["sta_type"]).replace("[[called]]"," ()" if x["sta_type"]=="MethodObj" else "")
            elif x.get("dev_hid") == "ACPI000E":
                ssdt += """    External ([[DevPath]], DeviceObj)
    Scope ([[DevPath]])
    {
        Method (_STA, 0, NotSerialized)  // _STA: 状态
        {
            If (_OSI ("Darwin"))
            {
                Return (Zero)
            }
            Else
            {
                Return (0x0F)
            }
        }
    }
""".replace("[[DevPath]]",x["device"][0])
        if rtc_range_needed and rtc_crs_type.lower() == "buffobj" and crs_lines and rtc_dict.get("valid"):
            ssdt += """    External ([[DevPath]], DeviceObj)
    External ([[DevPath]].XCRS, [[type]])
    Scope ([[DevPath]])
    {
        // 从 DSDT 中提取的调整并重命名的 _CRS 缓冲区，修正了范围
[[NewCRS]]
        // 调整后的 _CRS 和重命名缓冲区结束

        // 创建一个新的 _CRS 方法，返回重命名 XCRS 的结果
        Method (_CRS, 0, Serialized)  // _CRS: 当前资源设置
        {
            If (LOr (_OSI ("Darwin"), LNot (CondRefOf ([[DevPath]].XCRS))))
            {
                // 如果启动 macOS 或 XCRS 方法不再存在，返回我们的缓冲区
                Return (BUFX)
            }
            // 不是 macOS 且 XCRS 存在，返回其结果
            Return ([[DevPath]].XCRS[[method]])
        }
    }
""".replace("[[DevPath]]",rtc_dict["device"][0]) \
    .replace("[[type]]",rtc_crs_type) \
    .replace("[[method]]"," ()" if rtc_crs_type == "Method" else "") \
    .replace("[[NewCRS]]","\n".join([(" "*8)+x for x in crs_lines]))
        if not rtc_dict.get("valid") and lpc_name:
            ssdt += """    External ([[LPCName]], DeviceObj)    // (from opcode)
    Scope ([[LPCName]])
    {
        Device (RTC0)
        {
            Name (_HID, EisaId ("PNP0B00"))  // _HID: 硬件 ID
            Name (_CRS, ResourceTemplate ()  // _CRS: 当前资源设置
            {
                IO (Decode16,
                    0x0070,             // 最小范围
                    0x0070,             // 最大范围
                    0x01,               // 对齐
                    0x08,               // 长度
                    )
                IRQNoFlags ()
                    {8}
            })
            Method (_STA, 0, NotSerialized)  // _STA: 状态
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0F)
                }
                Else
                {
                    Return (0)
                }
            }
        }
    }
""".replace("[[LPCName]]",lpc_name)
        ssdt += "}"
        if self.write_ssdt(ssdt_name, ssdt):
            return {
                "Add": [
                    {
                        "Comment": ssdt_name + ".aml",
                        "Enabled": True,
                        "Path": ssdt_name + ".aml"
                    }
                ],
                "Patch": awac_dict.get("patches",[])+rtc_dict.get("patches",[])
            }

    def fake_embedded_controller(self):
        ssdt_name = "SSDT-EC"
        laptop = "Laptop" in self.hardware_report.get("Motherboard").get("Platform")
        
        def sta_needs_patching(sta):
            if not isinstance(sta,dict) or not sta.get("sta"):
                return False
            if sta.get("sta_type") == "IntObj":
                try:
                    sta_scope = table["lines"][sta["sta"][0][1]]
                    if not "Name (_STA, 0x0F)" in sta_scope:
                        return True
                except Exception as e:
                    return True
            elif sta.get("sta_type") == "MethodObj":
                try:
                    sta_scope = "\n".join(self.acpi.get_scope(sta["sta"][0][1],strip_comments=True,table=table))
                    if sta_scope.count("Return (") > 1 or not "Return (0x0F)" in sta_scope:
                        return True
                except Exception as e:
                    return True
            return False
        rename = False
        named_ec = False
        ec_to_patch = []
        ec_to_enable = []
        ec_sta = {}
        ec_enable_sta = {}
        patches = []
        lpc_name = None
        ec_located = False
        for table_name in self.sorted_nicely(list(self.acpi.acpi_tables)):
            table = self.acpi.acpi_tables[table_name]
            ec_list = self.acpi.get_device_paths_with_hid("PNP0C09",table=table)
            if len(ec_list):
                lpc_name = ".".join(ec_list[0][0].split(".")[:-1])
                for x in ec_list:
                    device = orig_device = x[0]
                    if device.split(".")[-1] == "EC":
                        named_ec = True
                        if not laptop:
                            device = ".".join(device.split(".")[:-1]+["EC0"])
                            rename = True
                    scope = "\n".join(self.acpi.get_scope(x[1],strip_comments=True,table=table))
                    if all(y in scope for y in ["_HID","_CRS","_GPE"]):
                        ec_located = True
                        sta = self.get_sta_var(
                            var=None,
                            device=orig_device,
                            dev_hid="PNP0C09",
                            dev_name=orig_device.split(".")[-1],
                            log_locate=False,
                            table=table
                        )
                        if not laptop:
                            ec_to_patch.append(device)
                            if sta.get("patches"):
                                patches.extend(sta.get("patches",[]))
                                ec_sta[device] = sta
                        elif sta.get("patches"):
                            if sta_needs_patching(sta):
                                ec_to_enable.append(device)
                                ec_enable_sta[device] = sta
                                for patch in sta.get("patches",[]):
                                    patch["Enabled"] = False
                                    patch["Disabled"] = True
                                    patches.append(patch)
        if laptop and named_ec and not patches:
            return
        if lpc_name is None:
            lpc_name = self.get_lpc_name(skip_ec=True,skip_common_names=True)
        if lpc_name is None:
            return
        if rename == True:
            patches.insert(0,{
                "Comment":"EC 重命名为 EC0{}".format("" if not ec_sta else " - 必须位于任何 EC _STA 重命名之前！"),
                "Find":"45435f5f",
                "Replace":"4543305f"
            })
        ssdt = """
DefinitionBlock ("", "SSDT", 2, "ZPSS", "EC", 0x00001000)
{
    External ([[LPCName]], DeviceObj)
""".replace("[[LPCName]]",lpc_name)
        for x in ec_to_patch:
            ssdt += "    External ({}, DeviceObj)\n".format(x)
            if x in ec_sta:
                ssdt += "    External ({}.XSTA, {})\n".format(x,ec_sta[x].get("sta_type","MethodObj"))
        for x in ec_to_enable:
            ssdt += "    External ({}, DeviceObj)\n".format(x)
            if x in ec_enable_sta:
                ssdt += "    External ({0}._STA, {1})\n    External ({0}.XSTA, {1})\n".format(x,ec_enable_sta[x].get("sta_type","MethodObj"))
        for x in ec_to_patch:
            ssdt += """
    Scope ([[ECName]])
    {
        Method (_STA, 0, NotSerialized)  // _STA: 状态
        {
            If (_OSI ("Darwin"))
            {
                Return (0)
            }
            Else
            {
                Return ([[XSTA]])
            }
        }
    }
""".replace("[[LPCName]]",lpc_name).replace("[[ECName]]",x) \
    .replace("[[XSTA]]","{}.XSTA{}".format(x," ()" if ec_sta[x].get("sta_type","MethodObj")=="MethodObj" else "") if x in ec_sta else "0x0F")
        for x in ec_to_enable:
            ssdt += """
    If (LAnd (CondRefOf ([[ECName]].XSTA), LNot (CondRefOf ([[ECName]]._STA))))
    {
        Scope ([[ECName]])
        {
            Method (_STA, 0, NotSerialized)  // _STA: 状态
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0F)
                }
                Else
                {
                    Return ([[XSTA]])
                }
            }
        }
    }
""".replace("[[LPCName]]",lpc_name).replace("[[ECName]]",x) \
    .replace("[[XSTA]]","{}.XSTA{}".format(x," ()" if ec_enable_sta[x].get("sta_type","MethodObj")=="MethodObj" else "") if x in ec_enable_sta else "Zero")
        if not laptop or not named_ec:
            ssdt += """
    Scope ([[LPCName]])
    {
        Device (EC)
        {
            Name (_HID, "ACID0001")  // _HID: 硬件 ID
            Method (_STA, 0, NotSerialized)  // _STA: 状态
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0F)
                }
                Else
                {
                    Return (Zero)
                }
            }
        }
    }""".replace("[[LPCName]]",lpc_name)
        ssdt += """
}"""
        return {
            "Add": [
                {
                    "Comment": ssdt_name + ".aml",
                    "Enabled": self.write_ssdt(ssdt_name, ssdt),
                    "Path": ssdt_name + ".aml"
                }
            ],
            "Patch": patches
        }

    def get_data(self, data, pad_to=0):
        if sys.version_info >= (3, 0):
            if not isinstance(data,bytes):
                data = data.encode()
            return data+b"\x00"*(max(pad_to-len(data),0))
        else:
            return plistlib.Data(data+b"\x00"*(max(pad_to-len(data),0)))

    def write_ssdt(self, ssdt_name, ssdt_content, compile=True):
        dsl_path = os.path.join(self.acpi_directory, ssdt_name + ".dsl")
        aml_path = os.path.join(self.acpi_directory, ssdt_name + ".aml")
        if not os.path.exists(self.acpi_directory):
            os.makedirs(self.acpi_directory)
        with open(dsl_path,"w") as f:
            f.write(ssdt_content)
        if not compile:
            return False
        output = self.run({
            "args":[self.acpi.iasl, dsl_path]
        })
        if output[-1] != 0:
            return False
        else:
            os.remove(dsl_path)
        return os.path.exists(aml_path)

    def apply_acpi_patches(self, acpi_patches):
        acpi_patches = [
            {
                "Base": acpi_patch.get("Base", ""),
                "BaseSkip": acpi_patch.get("BaseSkip", 0),
                "Comment": acpi_patch.get("Comment", ""),
                "Count": acpi_patch.get("Count", 0),
                "Enabled": True,
                "Find": self.utils.hex_to_bytes(acpi_patch["Find"]),
                "Limit": acpi_patch.get("Limit", 0),
                "Mask": self.utils.hex_to_bytes(acpi_patch.get("Mask", "")),
                "OemTableId": self.utils.hex_to_bytes(acpi_patch.get("OemTableId", "")),
                "Replace": self.utils.hex_to_bytes(acpi_patch["Replace"]),
                "ReplaceMask": self.utils.hex_to_bytes(acpi_patch.get("ReplaceMask", "")),
                "Skip": acpi_patch.get("Skip", 0),
                "TableLength": acpi_patch.get("TableLength", 0),
                "TableSignature": self.utils.hex_to_bytes(acpi_patch.get("TableSignature", "")),
            }
            for acpi_patch in acpi_patches
        ]
        return sorted(acpi_patches, key=lambda x: x["Comment"])

    def add_intel_management_engine(self):
        ssdt_name = "SSDT-IMEI"
        ssdt_content = """
DefinitionBlock ("", "SSDT", 2, "ZPSS", "IMEI", 0x00000000)
{
    External (_SB_.PCI0, DeviceObj)

    Scope (_SB.PCI0)
    {
        Device (IMEI)
        {
            Name (_ADR, 0x00160000)  // _ADR: 地址
            Method (_STA, 0, NotSerialized)  // _STA: 状态
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0F)
                }
                Else
                {
                    Return (Zero)
                }
            }
        }
    }
}"""
        imei_device = self.acpi.get_device_paths_with_hid("0x00160000", self.dsdt)
        if not imei_device:
            return {
                "Add": [
                    {
                        "Comment": ssdt_name + ".aml",
                        "Enabled": self.write_ssdt(ssdt_name, ssdt_content),
                        "Path": ssdt_name + ".aml"
                    }
                ]
            }

    def add_memory_controller_device(self):
        if not self.lpc_bus_device:
            return
        ssdt_name = "SSDT-MCHC"
        ssdt_content = """
DefinitionBlock ("", "SSDT", 2, "ZPSS", "MCHC", 0)
{
    External ([[PCIName]], DeviceObj)

    Scope ([[PCIName]])
    {
        Device (MCHC)
        {
            Name (_ADR, Zero)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0F)
                }
                Else
                {
                    Return (Zero)
                }
            }
        }
    }
}"""
        mchc_device = self.acpi.get_device_paths("MCHC", self.dsdt)
        if mchc_device:
            return
        pci_bus_device = ".".join(self.lpc_bus_device.split(".")[:2])
        ssdt_content = ssdt_content.replace("[[PCIName]]", pci_bus_device)
        return {
            "Add": [
                {
                    "Comment": ssdt_name + ".aml",
                    "Enabled": self.write_ssdt(ssdt_name, ssdt_content),
                    "Path": ssdt_name + ".aml"
                }
            ]
        }

    def add_system_management_bus_device(self):
        if not self.lpc_bus_device:
            return
        try:
            smbus_device_name = self.acpi.get_device_paths_with_hid("0x001F0003" if self.hardware_report.get("CPU").get("Codename") in cpu_data.IntelCPUGenerations[50:] else "0x001F0004", self.dsdt)[0][0].split(".")[-1]
        except:
            smbus_device_name = "SBUS"
        pci_bus_device = ".".join(self.lpc_bus_device.split(".")[:2])
        smbus_device_path = "{}.{}".format(pci_bus_device, smbus_device_name)
        ssdt_name = "SSDT-{}".format(smbus_device_name)
        ssdt_content = """
DefinitionBlock ("", "SSDT", 2, "ZPSS", "[[SMBUSName]]", 0)
{
    External ([[SMBUSDevice]], DeviceObj)

    Scope ([[SMBUSDevice]])
    {
        Device (BUS0)
        {
            Name (_CID, "smbus")
            Name (_ADR, Zero)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0F)
                }
                Else
                {
                    Return (Zero)
                }
            }
        }
    }
}""".replace("[[SMBUSName]]", smbus_device_name).replace("[[SMBUSDevice]]", smbus_device_path)
        return {
            "Add": [
                {
                    "Comment": ssdt_name + ".aml",
                    "Enabled": self.write_ssdt(ssdt_name, ssdt_content),
                    "Path": ssdt_name + ".aml"
                }
            ]
        }

    def add_usb_power_properties(self):
        ssdt_name = "SSDT-USBX"
        ssdt_content = """
DefinitionBlock ("", "SSDT", 2, "ZPSS", "USBX", 0x00001000)
{
    Scope (\\_SB)
    {
        Device (USBX)
        {
            Name (_ADR, Zero)  // _ADR: 地址
            Method (_DSM, 4, NotSerialized)  // _DSM: 设备特定方法
            {
                If (LNot (Arg2))
                {
                    Return (Buffer ()
                    {
                        0x03
                    })
                }
                Return (Package ()
                {[[USBX_PROPS]]
                })
            }
            Method (_STA, 0, NotSerialized)  // _STA: 状态
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0F)
                }
                Else
                {
                    Return (Zero)
                }
            }
        }
    }
}"""
        usb_power_properties = None
        if self.utils.contains_any(["MacPro7,1", "iMacPro1,1", "iMac20,", "iMac19,", "iMac18,", "iMac17,", "iMac16,"], self.smbios_model):
            usb_power_properties = {
                "kUSBSleepPowerSupply":"0x13EC",
                "kUSBSleepPortCurrentLimit":"0x0834",
                "kUSBWakePowerSupply":"0x13EC",
                "kUSBWakePortCurrentLimit":"0x0834"
            }
        elif "MacMini8,1" in self.smbios_model:
            usb_power_properties = {
                "kUSBSleepPowerSupply":"0x0C80",
                "kUSBSleepPortCurrentLimit":"0x0834",
                "kUSBWakePowerSupply":"0x0C80",
                "kUSBWakePortCurrentLimit":"0x0834"
            }
        elif self.utils.contains_any(["MacBookPro16,", "MacBookPro15,", "MacBookPro14,", "MacBookPro13,", "MacBookAir9,1"], self.smbios_model):
            usb_power_properties = {
                "kUSBSleepPortCurrentLimit":"0x0BB8",
                "kUSBWakePortCurrentLimit":"0x0BB8"
            }
        elif "MacBook9,1" in self.smbios_model:
            usb_power_properties = {
                "kUSBSleepPowerSupply":"0x05DC",
                "kUSBSleepPortCurrentLimit":"0x05DC",
                "kUSBWakePowerSupply":"0x05DC",
                "kUSBWakePortCurrentLimit":"0x05DC"
            }
        if usb_power_properties:
            ssdt_content = ssdt_content.replace("[[USBX_PROPS]]", ",".join("\n                    \"{}\",\n                    {}".format(key, usb_power_properties[key]) for key in usb_power_properties))
            return {
                "Add": [
                    {
                        "Comment": ssdt_name + ".aml",
                        "Enabled": self.write_ssdt(ssdt_name, ssdt_content),
                        "Path": ssdt_name + ".aml"
                    }
                ]
            }

    def ambient_light_sensor(self):
        ssdt_name = "SSDT-ALS0"
        ssdt_content = """
// 资源：https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/AcpiSamples/Source/SSDT-ALS0.dsl

/*
 * 从 macOS 10.15 开始，环境光传感器的存在是背光工作所必需的。
 * 此处创建环境光传感器 ACPI 设备，可由 SMCLightSensor kext
 * 通过 SMC 接口报告虚拟值（无设备时）或有效值。
 */
DefinitionBlock ("", "SSDT", 2, "ZPSS", "ALS0", 0x00000000)
{
    Scope (_SB)
    {
        Device (ALS0)
        {
            Name (_HID, "ACPI0008" /* 环境光传感器设备 */)  // _HID: 硬件 ID
            Name (_CID, "smc-als")  // _CID: 兼容 ID
            Name (_ALI, 0x012C)  // _ALI: 环境光照度
            Name (_ALR, Package (0x01)  // _ALR: 环境光响应
            {
                Package (0x02)
                {
                    0x64, 
                    0x012C
                }
            })
            Method (_STA, 0, NotSerialized)  // _STA: 状态
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0F)
                }
                Else
                {
                    Return (Zero)
                }
            }
        }
    }
}"""
        try:
            als_device = self.acpi.get_device_paths_with_hid("ACPI0008", self.dsdt)[0][0]
        except:
            als_device = None
        patches = []
        if als_device:
            als_device_name = als_device.split(".")[-1]
            if "." not in als_device:
                als_device_name = als_device_name[1:]
            sta = self.get_sta_var(var=None, device=None, dev_hid="ACPI0008", dev_name=als_device_name, table=self.dsdt)
            patches.extend(sta.get("patches", []))
            ssdt_name = "SSDT-{}".format(als_device_name)
            ssdt_content = """
DefinitionBlock ("", "SSDT", 2, "ZPSS", "[[ALSName]]", 0x00000000)
{
    External ([[ALSDevice]], DeviceObj)
    External ([[ALSDevice]].XSTA, [[STAType]])

    Scope ([[ALSDevice]])
    {
        Method (_STA, 0, NotSerialized)  // _STA: 状态
        {
            If (_OSI ("Darwin"))
            {
                Return (0x0F)
            }
            Else
            {
                Return ([[XSTA]])
            }
        }
    }
}""".replace("[[ALSName]]", als_device_name) \
    .replace("[[ALSDevice]]", als_device) \
    .replace("[[STAType]]", sta.get("sta_type","MethodObj")) \
    .replace("[[XSTA]]", "{}.XSTA{}".format(als_device," ()" if sta.get("sta_type","MethodObj") == "MethodObj" else "") if sta else "0x0F")
        return {
            "Add": [
                {
                    "Comment": ssdt_name + ".aml",
                    "Enabled": self.write_ssdt(ssdt_name, ssdt_content),
                    "Path": ssdt_name + ".aml"
                }
            ],
            "Patch": patches
        }
    
    def findall_power_resource_blocks(self, table_lines):
        power_resource_blocks = []
        i = 0
        while i < len(table_lines):
            line = table_lines[i].strip()
            if line.startswith("PowerResource"):
                start_index = i
                open_brackets = 1
                i += 1
                while i < len(table_lines) and open_brackets > 0:
                    if '{' in table_lines[i]:
                        open_brackets += table_lines[i].count('{')
                    if '}' in table_lines[i]:
                        open_brackets -= table_lines[i].count('}')
                    i += 1
                end_index = i - 1
                power_resource_blocks.append((start_index, end_index))
            else:
                i += 1
        return power_resource_blocks

    def is_method_in_power_resource(self, method, table_lines):
        power_resource_blocks = self.findall_power_resource_blocks(table_lines)
        for start, end in power_resource_blocks:
            if start <= method[1] <= end:
                return True
        return False

    def disable_unsupported_device(self):
        results = {
            "Add": []
        }
        for device_name, device_props in self.disabled_devices.items():
            if not device_props.get("Bus Type", "PCI") == "PCI" or not device_props.get("ACPI Path"):
                continue
            ssdt_name = None
            if "GPU" in device_name and device_props.get("Device Type") != "Integrated GPU":
                ssdt_name = "SSDT-Disable_GPU_{}".format(device_props.get("ACPI Path").split(".")[2])
                target_device = device_props.get("ACPI Path")
                off_method_found = ps3_method_found = False
                for table_name, table_data in self.acpi.acpi_tables.items():
                    off_methods = self.acpi.get_method_paths("_OFF", table_data)
                    ps3_methods = self.acpi.get_method_paths("_PS3", table_data)
                    off_method_found = off_method_found or any(method[0].startswith(target_device) and not self.is_method_in_power_resource(method, table_data.get("lines")) for method in off_methods)
                    ps3_method_found = ps3_method_found or any(method[0].startswith(target_device) for method in ps3_methods)
                if not off_method_found and not ps3_method_found:
                    continue
                if off_method_found:
                    ps3_method_found = False
                device_props["Disabled"] = True
                ssdt_content = """
DefinitionBlock ("", "SSDT", 2, "ZPSS", "DGPU", 0x00000000)
{"""
                if off_method_found:
                    ssdt_content += """
    External ([[DevicePath]]._OFF, MethodObj)
    External ([[DevicePath]]._ON_, MethodObj)"""
                if ps3_method_found:
                    ssdt_content += """
    External ([[DevicePath]]._PS0, MethodObj)
    External ([[DevicePath]]._PS3, MethodObj)
    External ([[DevicePath]]._DSM, MethodObj)
"""
                ssdt_content += """
    Device (DGPU)
    {
        Name (_HID, "DGPU1000")
        Method (_INI, 0, NotSerialized)
        {
            _OFF ()
        }

        Method (_STA, 0, NotSerialized)
        {
            If (_OSI ("Darwin"))
            {
                Return (0x0F)
            }
            Else
            {
                Return (Zero)
            }
        }

        Method (_ON, 0, NotSerialized)
        {
"""
                if off_method_found:
                    ssdt_content += """
            [[DevicePath]]._ON ()
            """
                if ps3_method_found:
                    ssdt_content += """
            [[DevicePath]]._PS0 ()
            """
                ssdt_content += """
        }

        Method (_OFF, 0, NotSerialized)
        {
"""
                if off_method_found:
                    ssdt_content += """
            [[DevicePath]]._OFF ()
            """
                if ps3_method_found:
                    ssdt_content += """
            [[DevicePath]]._DSM (ToUUID ("a486d8f8-0bda-471b-a72b-6042a6b5bee0") /* 未知 UUID */, 0x0100, 0x1A, Buffer (0x04)
            {
                    0x01, 0x00, 0x00, 0x03                           // ....
            })
            [[DevicePath]]._PS3 ()
            """
                ssdt_content += """\n        }\n    }\n}"""
            elif "Network" in device_name and device_props.get("Bus Type") == "PCI":
                ssdt_name = "SSDT-Disable_Network_{}".format(device_props.get("ACPI Path").split(".")[2])
                ssdt_content = """
DefinitionBlock ("", "SSDT", 2, "ZPSS", "DNET", 0x00000000)
{
    External ([[DevicePath]], DeviceObj)

    Method ([[DevicePath]]._DSM, 4, NotSerialized)  // _DSM: 设备特定方法
    {
        If ((!Arg2 || (_OSI ("Darwin") == Zero)))
        {
            Return (Buffer (One)
            {
                 0x03                                             // .
            })
        }

        Return (Package (0x0A)
        {
            "name", 
            Buffer (0x09)
            {
                "#network"
            }, 

            "IOName", 
            "#display", 
            "class-code", 
            Buffer (0x04)
            {
                 0xFF, 0xFF, 0xFF, 0xFF                           // ....
            }, 

            "vendor-id", 
            Buffer (0x04)
            {
                 0xFF, 0xFF, 0x00, 0x00                           // ....
            }, 

            "device-id", 
            Buffer (0x04)
            {
                 0xFF, 0xFF, 0x00, 0x00                           // ....
            }
        })
    }
}
"""
            elif "Storage" in device_name:
                ssdt_name = "SSDT-Disable_NVMe_{}".format(device_props.get("ACPI Path").split(".")[-2])
                ssdt_content = """
DefinitionBlock ("", "SSDT", 2, "ZPSS", "DNVMe", 0x00000000)
{
    External ([[DevicePath]], DeviceObj)

    Method ([[DevicePath]]._DSM, 4, NotSerialized)  // _DSM: 设备特定方法
    {
        If (_OSI ("Darwin"))
        {
            If (!Arg2)
            {
                Return (Buffer (One)
                {
                     0x03                                             // .
                })
            }

            Return (Package (0x02)
            {
                "class-code", 
                Buffer (0x04)
                {
                     0xFF, 0x08, 0x01, 0x00                           // ....
                }
            })
        }
    }
}
"""
            if ssdt_name:
                ssdt_content = ssdt_content.replace("[[DevicePath]]", device_props.get("ACPI Path"))
                results["Add"].append(
                    {
                        "Comment": ssdt_name + ".aml",
                        "Enabled": self.write_ssdt(ssdt_name, ssdt_content),
                        "Path": ssdt_name + ".aml"
                    }
                )
        return results
  
    def enable_backlight_controls(self):
        patches = []
        integrated_gpu = list(self.hardware_report.get("GPU").items())[-1][-1]
        uid_value = 19
        if integrated_gpu.get("Codename") in ("Iron Lake", "Sandy Bridge", "Ivy Bridge"):
            uid_value = 14
        elif integrated_gpu.get("Codename") in ("Haswell", "Broadwell"):
            uid_value = 15
        elif integrated_gpu.get("Codename") in ("Skylake", "Kaby Lake"):
            uid_value = 16
        if "PNLF" in self.dsdt.get("table"):
            patches.append({
                "Comment": "PNLF 重命名为 XNLF",
                "Find": "504E4C46",
                "Replace": "584E4C46"
            })
        for table_name in self.sorted_nicely(list(self.acpi.acpi_tables)):
            table = self.acpi.acpi_tables[table_name]
            if binascii.unhexlify("084E4243460A00") in table.get("raw"):
                patches.append({
                    "Comment": "NBCF 0x00 改为 0x01",
                    "Find": "084E4243460A00",
                    "Replace": "084E4243460A01"
                })
                break
            elif binascii.unhexlify("084E42434600") in table.get("raw"):
                patches.append({
                    "Comment": "NBCF Zero 改为 One",
                    "Find": "084E42434600",
                    "Replace": "084E42434601"
                })
                break
        ssdt_name = "SSDT-PNLF"
        ssdt_content = """
DefinitionBlock ("", "SSDT", 2, "ZPSS", "PNLF", 0x00000000)
{"""
        if integrated_gpu.get("ACPI Path"):
            ssdt_content += """\n    External ([[DevicePath]], DeviceObj)\n    Device ([[DevicePath]].PNLF)"""
        else:
            ssdt_content += """\n    Device (PNLF)"""
        ssdt_content += """
    {
        Name (_HID, EisaId ("APP0002"))  // _HID: 硬件 ID
        Name (_CID, "backlight")  // _CID: 兼容 ID
        Name (_UID, [[uid_value]])  // _UID: 唯一 ID
        
        Method (_STA, 0, NotSerialized)  // _STA: 状态
        {
            If (_OSI ("Darwin"))
            {
                Return (0x0B)
            }
            Else
            {
                Return (Zero)
            }
        }"""
        if integrated_gpu.get("ACPI Path") and uid_value == 14:
            ssdt_content += """
        Method (_INI, 0, Serialized)
        {
            If (_OSI ("Darwin"))
            {
                OperationRegion ([[DevicePath]].RMP3, PCI_Config, Zero, 0x14)
                Field ([[DevicePath]].RMP3, AnyAcc, NoLock, Preserve)
                {
                    Offset (0x02), GDID,16,
                    Offset (0x10), BAR1,32,
                }
                // IGPU PWM 背光寄存器说明：
                //   LEV2 当前未使用
                //   LEVL Sandy/Ivy 背光级别
                //   P0BL 计数器，零时表示垂直消隐
                //   GRAN 见下方 INI1 方法中的描述
                //   LEVW 应初始化为 0xC0000000
                //   LEVX PWMMax 除 FBTYPE_HSWPLUS 外为 max/level 组合（Sandy/Ivy 存储在 MSW 中）
                //   LEVD Coffee Lake 背光级别
                //   PCHL 当前未使用
                OperationRegion (RMB1, SystemMemory, BAR1 & ~0xF, 0xe1184)
                Field(RMB1, AnyAcc, Lock, Preserve)
                {
                    Offset (0x48250),
                    LEV2, 32,
                    LEVL, 32,
                    Offset (0x70040),
                    P0BL, 32,
                    Offset (0xc2000),
                    GRAN, 32,
                    Offset (0xc8250),
                    LEVW, 32,
                    LEVX, 32,
                    LEVD, 32,
                    Offset (0xe1180),
                    PCHL, 32,
                }
                // 现在根据 framebuffer 类型修正背光 PWM
                // 此时：
                //   Local4 是 RMCF.BLKT 值（此处未使用），若指定则默认 1
                //   Local0 是 IGPU 的设备 ID
                //   Local2 是 LMAX，若指定（Ones 表示基于设备 ID）
                //   Local3 是 framebuffer 类型

                // 使用 WhateverGreen.kext 时需调整
                Local0 = GDID
                Local2 = Ones
                Local3 = 0

                // 检查 Sandy/Ivy
                // #define FBTYPE_SANDYIVY 1
                If (LOr (LEqual (1, Local3), LNotEqual (Match (Package()
                {
                    // Sandy HD3000
                    0x010b, 0x0102,
                    0x0106, 0x1106, 0x1601, 0x0116, 0x0126,
                    0x0112, 0x0122,
                    // Ivy
                    0x0152, 0x0156, 0x0162, 0x0166,
                    0x016a,
                    // Arrandale
                    0x0046, 0x0042,
                }, MEQ, Local0, MTR, 0, 0), Ones)))
                {
                    if (LEqual (Local2, Ones))
                    {
                        // #define SANDYIVY_PWMMAX 0x710
                        Store (0x710, Local2)
                    }
                    // 仅当不同时才更改/缩放...
                    Store (LEVX >> 16, Local1)
                    If (LNot (Local1))
                    {
                        Store (Local2, Local1)
                    }
                    If (LNotEqual (Local2, Local1))
                    {
                        // 设置新背光 PWMMax，但通过缩放保留当前背光级别
                        Store ((LEVL * Local2) / Local1, Local0)
                        Store (Local2 << 16, Local3)
                        If (LGreater (Local2, Local1))
                        {
                            // PWMMax 变大，先存储新 PWMMax
                            Store (Local3, LEVX)
                            Store (Local0, LEVL)
                        }
                        Else
                        {
                            // 否则，先存储新亮度级别，再存储 PWMMax
                            Store (Local0, LEVL)
                            Store (Local3, LEVX)
                        }
                    }
                }
            }
        }"""
        ssdt_content += """
    }
}"""
        ssdt_content = ssdt_content.replace("[[uid_value]]", str(uid_value))
        if integrated_gpu.get("ACPI Path"):
            ssdt_content = ssdt_content.replace("[[DevicePath]]", integrated_gpu.get("ACPI Path"))   
        return {
            "Add": [
                {
                    "Comment": ssdt_name + ".aml",
                    "Enabled": self.write_ssdt(ssdt_name, ssdt_content),
                    "Path": ssdt_name + ".aml"
                }
            ],
            "Patch": patches
        }

    def enable_gpio_device(self):
        try:
            gpio_device = self.acpi.get_device_paths("GPI0", self.dsdt)[0][0] or self.acpi.get_device_paths("GPIO", self.dsdt)[0][0]
        except:
            return
        sta = self.get_sta_var(var=None, device=gpio_device, dev_hid=None, dev_name=gpio_device.split(".")[-1], table=self.dsdt)
        ssdt_name = "SSDT-GPI0"
        ssdt_content = """
DefinitionBlock ("", "SSDT", 2, "ZPSS", "GPI0", 0x00000000)
{
    External ([[GPI0Path]], DeviceObj)
    External ([[GPI0Path]].XSTA, [[STAType]])

    Scope ([[GPI0Path]])
    {
        Method (_STA, 0, NotSerialized)  // _STA: 状态
        {
            If (_OSI ("Darwin"))
            {
                Return (0x0F)
            }
            Else
            {
                Return ([[XSTA]])
            }
        }
    }
}""".replace("[[GPI0Path]]", gpio_device) \
    .replace("[[STAType]]", sta.get("sta_type","MethodObj")) \
    .replace("[[XSTA]]", "{}.XSTA{}".format(gpio_device," ()" if sta.get("sta_type","MethodObj") == "MethodObj" else "") if sta else "0x0F")
        return {
            "Add": [
                {
                    "Comment": ssdt_name + ".aml",
                    "Enabled": self.write_ssdt(ssdt_name, ssdt_content),
                    "Path": ssdt_name + ".aml"
                }
            ],
            "Patch": sta.get("patches", [])
        }
    
    def enable_nvram_support(self):
        if not self.lpc_bus_device:
            return
        ssdt_name = "SSDT-PMC"
        ssdt_content = """
// 资源：https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/AcpiSamples/Source/SSDT-PMC.dsl

/*
 * Intel 300-series 芯片组 PMC 支持 macOS
 *
 * 从 Z390 芯片组开始，PMC (D31:F2) 仅可通过 MMIO 访问。
 * 由于 ACPI 中没有 PMC 的标准设备，Apple 引入了自己的命名 "APP9876"
 * 以允许 AppleIntelPCHPMC 驱动程序访问此设备。
 * 为避免混淆，我们对其他操作系统禁用此设备，因为它们通常使用另一个
 * 具有 "PNP0C02" HID 和 "PCHRESV" UID 的非标准设备。
 *
 * 在某些实现中（包括 APTIO V），PMC 初始化是 NVRAM 访问所必需的，
 * 否则会在 SMM 模式下冻结。原因尚不明确。注意 PMC 和 SPI 位于
 * 不同的内存区域，PCHRESV 映射了两者，但只有 PMC 区域被 AppleIntelPCHPMC 使用：
 * 0xFE000000~0xFE00FFFF - PMC MBAR
 * 0xFE010000~0xFE010FFF - SPI BAR0
 * 0xFE020000~0xFE035FFF - SerialIo 在 ACPI 模式
 *
 * PMC 设备与 LPC 总线无关，但添加到其范围以加快初始化。
 * 如果将其添加到 PCI0（通常所在位置），将在 PCI 配置结束时启动，对于 NVRAM 支持而言为时已晚。
 */
DefinitionBlock ("", "SSDT", 2, "ACDT", "PMCR", 0x00001000)
{
    External ([[LPCPath]], DeviceObj)

    Scope ([[LPCPath]])
    {
        Device (PMCR)
        {
            Name (_HID, EisaId ("APP9876"))  // _HID: 硬件 ID
            Method (_STA, 0, NotSerialized)  // _STA: 状态
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0B)
                }
                Else
                {
                    Return (Zero)
                }
            }
            Name (_CRS, ResourceTemplate ()  // _CRS: 当前资源设置
            {
                Memory32Fixed (ReadWrite,
                    0xFE000000,         // 地址基址
                    0x00010000,         // 地址长度
                    )
            })
        }
    }
}""".replace("[[LPCPath]]", self.lpc_bus_device)
        return {
            "Add": [
                {
                    "Comment": ssdt_name + ".aml",
                    "Enabled": self.write_ssdt(ssdt_name, ssdt_content),
                    "Path": ssdt_name + ".aml"
                }
            ],
        }
    
    def remove_conditional_scope(self):
        return {
            "Patch": [
                {
                    "Comment": "删除条件 ACPI 范围声明",
                    "Find": "A000000092935043484100",
                    "Replace": "A3A3A3A3A3A3A3A3A3A3A3",
                    "Mask": "FF000000FFFFFFFFFFFFFF",
                    "Count": 1,
                    "TableSignature": "44534454"
                }
            ]
        }

    def fix_hp_005_post_error(self):
        if binascii.unhexlify("4701700070000108") in self.dsdt.get("raw"):
            return {
                "Patch": [
                    {
                        "Comment": "修复 HP 实时时钟电源丢失 (005) 开机错误",
                        "Find": "4701700070000108",
                        "Replace": "4701700070000102"
                    }
                ]
            }

    def add_null_ethernet_device(self):
        random_mac_address = self.smbios.generate_random_mac()
        mac_address_byte = ", ".join([f'0x{random_mac_address[i:i+2]}' for i in range(0, len(random_mac_address), 2)])
        ssdt_name = "SSDT-RMNE"
        ssdt_content = """
// 资源：https://github.com/RehabMan/OS-X-Null-Ethernet/blob/master/SSDT-RMNE.dsl

/* ssdt.dsl -- NullEthernet 的 SSDT 注入器
 *
 * 版权所有 (c) 2014 RehabMan <racerrehabman@gmail.com>
 * 保留所有权利。
 *
 * 本程序是自由软件；您可以根据自由软件基金会发布的 GNU 通用公共许可证
 * 第 2 版或（您选择的）任何更高版本重新分发和/或修改它。
 *
 * 本程序分发时希望它有用，但没有任何保证；甚至没有
 * 适销性或特定用途适用性的隐含保证。请参阅 GNU 通用公共许可证
 * 了解详情。
 *
 */

// 使用此 SSDT 替代修补您的 DSDT...

DefinitionBlock("", "SSDT", 2, "ZPSS", "RMNE", 0x00001000)
{
    Device (RMNE)
    {
        Name (_ADR, Zero)
        // NullEthernet kext 匹配此 HID
        Name (_HID, "NULE0000")
        // 这是 kext 返回的 MAC 地址。如有必要请修改。
        Name (MAC, Buffer() { [[MACAddress]] })
        Method (_DSM, 4, NotSerialized)
        {
            If (LEqual (Arg2, Zero)) { Return (Buffer() { 0x03 } ) }
            Return (Package()
            {
                "built-in", Buffer() { 0x00 },
                "IOName", "ethernet",
                "name", Buffer() { "ethernet" },
                "model", Buffer() { "RM-NullEthernet-1001" },
                "device_type", Buffer() { "ethernet" },
            })
        }

        Method (_STA, 0, NotSerialized)  // _STA: 状态
        {
            If (_OSI ("Darwin"))
            {
                Return (0x0F)
            }
            Else
            {
                Return (Zero)
            }
        }
    }
}""".replace("[[MACAddress]]", mac_address_byte)
        return {
            "Add": [
                {
                    "Comment": ssdt_name + ".aml",
                    "Enabled": self.write_ssdt(ssdt_name, ssdt_content),
                    "Path": ssdt_name + ".aml"
                }
            ]
        }

    def is_intel_hedt_cpu(self, processor_name, cpu_codename):
        if cpu_codename in cpu_data.IntelCPUGenerations[45:66]:
            return cpu_codename.endswith(("-X", "-P", "-W", "-E", "-EP", "-EX"))
        if cpu_codename in cpu_data.IntelCPUGenerations[66:]:
            return "Xeon" in processor_name
        return False
    
    def fix_system_clock_hedt(self):
        awac_device = self.acpi.get_device_paths_with_hid("ACPI000E", self.dsdt)
        try:
            rtc_device = self.acpi.get_device_paths_with_hid("PNP0B00", self.dsdt)[0][0]
            if rtc_device.endswith("RTC"):
                rtc_device += "_"
        except:
            if not self.lpc_bus_device:
                return
            rtc_device = self.lpc_bus_device + ".RTC0"
        new_rtc_device = ".".join(rtc_device.split(".")[:-1] + [self.get_unique_device(rtc_device, rtc_device.split(".")[-1])[0]])
        patches = []
        ssdt_name = "SSDT-RTC0-RANGE"
        ssdt_content = """
DefinitionBlock ("", "SSDT", 2, "ZPSS", "RtcRange", 0x00000000)
{"""
        if not awac_device:
            sta = self.get_sta_var(var=None, device=rtc_device, dev_hid=None, dev_name=rtc_device.split(".")[-1], table=self.dsdt)
            patches.extend(sta.get("patches", []))
            ssdt_content += """
    External ([[device_path]], DeviceObj)
    
    Scope ([[device_path]])
    {
        Method (_STA, 0, NotSerialized)  // _STA: 状态
        {
            If (_OSI ("Darwin"))
            {
                Return (Zero)
            }
            Else
            {
                Return (0x0F)
            }
        }
    }""".replace("[[device_path]]", rtc_device)
        ssdt_content += """
    External ([[parent_path]], DeviceObj)

    Device ([[device_path]])
    {
        Name (_HID, EisaId ("PNP0B00") /* AT 实时时钟 */)  // _HID: 硬件 ID
        Name (_CRS, ResourceTemplate ()  // _CRS: 当前资源设置
        {
            IO (Decode16,
                0x0070,             // 最小范围
                0x0070,             // 最大范围
                0x01,               // 对齐
                0x04,               // 长度
                )
            IO (Decode16,
                0x0074,             // 最小范围
                0x0074,             // 最大范围
                0x01,               // 对齐
                0x04,               // 长度
                )
            IRQNoFlags ()
                {8}
        })
        Method (_STA, 0, NotSerialized)  // _STA: 状态
        {
            If (_OSI ("Darwin"))
            {
                Return (0x0F)
            }
            Else
            {
                Return (Zero)
            }
        }
    }
}""".replace("[[parent_path]]", ".".join(rtc_device.split(".")[:-1])).replace("[[device_path]]", new_rtc_device)
        return {
            "Add": [
                {
                    "Comment": ssdt_name + ".aml",
                    "Enabled": self.write_ssdt(ssdt_name, ssdt_content),
                    "Path": ssdt_name + ".aml"
                }
            ],
            "Patch": patches
        }

    def instant_wake_fix(self):
        ssdt_name = "SSDT-PRW"
        uswe_object = "9355535745"
        wole_object = "93574F4C45"
        gprw_method = "4750525702"
        uprw_method = "5550525702"
        xprw_method = "5850525702"
        patches = []
        if binascii.unhexlify(gprw_method) in self.dsdt.get("raw"):
            patches.append({
                "Comment": "GPRW 重命名为 XPRW",
                "Find": gprw_method,
                "Replace": xprw_method
            })
        else:
            gprw_method = None
        if binascii.unhexlify(uprw_method) in self.dsdt.get("raw"):
            patches.append({
                "Comment": "UPRW 重命名为 XPRW",
                "Find": uprw_method,
                "Replace": xprw_method
            })
        else:
            uprw_method = None
        if not binascii.unhexlify(uswe_object) in self.dsdt.get("raw"):
            uswe_object = None
        if not binascii.unhexlify(wole_object) in self.dsdt.get("raw"):
            wole_object = None
        ssdt_content = """
// 资源：https://github.com/5T33Z0/OC-Little-Translated/blob/main/04_Fixing_Sleep_and_Wake_Issues/060D_Instant_Wake_Fix/README.md

DefinitionBlock ("", "SSDT", 2, "ZPSS", "_PRW", 0x00000000)
{"""
        if gprw_method or uprw_method:
            ssdt_content += """\n    External(XPRW, MethodObj)"""
        if uswe_object:
            ssdt_content += "\n    External (USWE, FieldUnitObj)"
        if wole_object:
            ssdt_content += "\n    External (WOLE, FieldUnitObj)"
        if uswe_object or wole_object:
            ssdt_content += """\n
    Scope (\\)
    {
        If (_OSI ("Darwin"))
        {"""
            if uswe_object:
                ssdt_content += "\n            USWE = Zero"
            if wole_object:
                ssdt_content += "\n            WOLE = Zero"
            ssdt_content += """        }
    }"""
        if gprw_method:
            ssdt_content += """
    Method (GPRW, 2, NotSerialized)
    {
        If (_OSI ("Darwin"))
        {
            If ((0x6D == Arg0))
            {
                Return (Package ()
                {
                    0x6D, 
                    Zero
                })
            }

            If ((0x0D == Arg0))
            {
                Return (Package ()
                {
                    0x0D, 
                    Zero
                })
            }
        }
        Return (XPRW (Arg0, Arg1))
    }"""
        if uprw_method:
            ssdt_content += """
    Method (UPRW, 2, NotSerialized)
    {
        If (_OSI ("Darwin"))
        {
            If ((0x6D == Arg0))
            {
                Return (Package ()
                {
                    0x6D, 
                    Zero
                })
            }

            If ((0x0D == Arg0))
            {
                Return (Package ()
                {
                    0x0D, 
                    Zero
                })
            }
        }
        Return (XPRW (Arg0, Arg1))
    }"""
        ssdt_content += "\n}"
        if gprw_method or uprw_method or uswe_object or wole_object:
            return {
                "Add": [
                    {
                        "Comment": ssdt_name + ".aml",
                        "Enabled": self.write_ssdt(ssdt_name, ssdt_content),
                        "Path": ssdt_name + ".aml"
                    }
                ],
                "Patch": patches
            }

    def fix_uncore_bridge(self):
        unc0_device = self.acpi.get_device_paths("UNC0", self.dsdt)
        if not unc0_device:
            return
        ssdt_name = "SSDT-UNC"
        ssdt_content = """
// 资源：https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/AcpiSamples/Source/SSDT-UNC.dsl

/*
 * 在 X99 系列上发现。
 * 这些平台具有 4 个 CPU 插槽的 uncore PCI 桥，
 * 尽管物理上不存在，但 ACPI 中仍然存在。
 *
 * 正常情况下，这些桥根据 CPU 插槽中的 CPU 存在情况通过处理器位掩码 (PRBM) 禁用，
 * 但在 X99 上，此代码未使用或已损坏，因为此类桥根本不存在。
 * 我们通过将 PRBM 写入 0 来解决此问题。
 *
 * 这样做很重要，因为从 macOS 11 开始，IOPCIFamily 一旦看到不存在的 PCI 桥就会崩溃。
 */

DefinitionBlock ("", "SSDT", 2, "ZPSS", "UNC", 0x00000000)
{
    External (_SB.UNC0, DeviceObj)
    External (PRBM, IntObj)

    Scope (_SB.UNC0)
    {
        Method (_INI, 0, NotSerialized)
        {
            // 大多数情况下此补丁对所有操作系统都有益，
            // 但在某些 Windows 10 之前的版本上可能引起问题。
            // 如果您没有此问题，请删除 If (_OSI ("Darwin"))。
            If (_OSI ("Darwin")) {
                PRBM = 0
            }
        }
    }
}"""
        return {
            "Add": [
                {
                    "Comment": ssdt_name + ".aml",
                    "Enabled": self.write_ssdt(ssdt_name, ssdt_content),
                    "Path": ssdt_name + ".aml"
                }
            ]
        }

    def operating_system_patch(self):
        ssdt_name = "SSDT-XOSI"
        ssdt_content = """
// 资源：https://github.com/dortania/Getting-Started-With-ACPI/blob/master/extra-files/decompiled/SSDT-XOSI.dsl

DefinitionBlock ("", "SSDT", 2, "ZPSS", "XOSI", 0x00001000)
{
    Method (XOSI, 1, NotSerialized)
    {
        // 基于：
        // https://docs.microsoft.com/en-us/windows-hardware/drivers/acpi/winacpi-osi#_osi-strings-for-windows-operating-systems
        // 根据需要从以下列表中添加操作系统，大多数只检查到 Windows 2015
        // 但请检查您的 DSDT 中查找了什么
        Store (Package ()
        {
[[OSIStrings]]
        }, Local0)
        If (_OSI ("Darwin"))
        {
            Return (LNotEqual (Match (Local0, MEQ, Arg0, MTR, Zero, Zero), Ones))
        }
        Else
        {
            Return (_OSI (Arg0))
        }
    }
}""".replace("[[OSIStrings]]", "\n,".join(["            \"{}\"".format(osi_string) for target_os, osi_string in self.osi_strings.items() if osi_string in self.dsdt.get("table")]))
        patches = []
        osid = self.acpi.get_method_paths("OSID", self.dsdt)
        if osid:
            patches.append({
                "Comment": "OSID 重命名为 XSID - 必须在 _OSI 重命名之前！",
                "Find": "4F534944",
                "Replace": "58534944"
            })
        osif = self.acpi.get_method_paths("OSIF", self.dsdt)
        if osif:
            patches.append({
                "Comment": "OSIF 重命名为 XSIF - 必须在 _OSI 重命名之前！",
                "Find": "4F534946",
                "Replace": "58534946"
            })
        patches.append({
            "Comment": "_OSI 重命名为 XOSI - 需要 SSDT-XOSI.aml",
            "Find": "5F4F5349",
            "Replace": "584F5349"
        })
        return {
            "Add": [
                {
                    "Comment": ssdt_name + ".aml",
                    "Enabled": self.write_ssdt(ssdt_name, ssdt_content),
                    "Path": ssdt_name + ".aml"
                }
            ],
            "Patch": patches
        }

    def surface_laptop_special_patch(self):
        ssdt_name = "SSDT-SURFACE"
        ssdt_content = """
DefinitionBlock ("", "SSDT", 2, "ZPSS", "SURFACE", 0x00001000)
{
    External (_SB_.PCI0, DeviceObj)
    External (GPRW, MethodObj)    // 2 参数

    If (_OSI ("Darwin"))
    {
        Scope (_SB)
        {
            Device (ALS0)
            {
                Name (_HID, "ACPI0008" /* 环境光传感器设备 */)  // _HID: 硬件 ID
                Name (_CID, "smc-als")  // _CID: 兼容 ID
                Name (_ALI, 0x012C)  // _ALI: 环境光照度
                Name (_ALR, Package (0x05)  // _ALR: 环境光响应
                {
                    Package (0x02)
                    {
                        0x46, 
                        Zero
                    }, 

                    Package (0x02)
                    {
                        0x49, 
                        0x0A
                    }, 

                    Package (0x02)
                    {
                        0x55, 
                        0x50
                    }, 

                    Package (0x02)
                    {
                        0x64, 
                        0x012C
                    }, 

                    Package (0x02)
                    {
                        0x96, 
                        0x03E8
                    }
                })
                Method (XALI, 1, Serialized)
                {
                    _ALI = Arg0
                }
            }

            Device (ADP0)
            {
                Name (_HID, "ACPI0003" /* 电源设备 */)  // _HID: 硬件 ID
                Name (SPSR, Zero)
                Method (_PRW, 0, NotSerialized)  // _PRW: 唤醒电源资源
                {
                    Return (GPRW (0x6D, 0x04))
                }

                Method (_STA, 0, NotSerialized)  // _STA: 状态
                {
                    Return (0x0F)
                }

                Method (XPSR, 1, Serialized)
                {
                    If ((Arg0 == Zero))
                    {
                        SPSR = Zero
                    }
                    ElseIf ((Arg0 == One))
                    {
                        SPSR = One
                    }

                    Notify (ADP0, 0x80) // 状态更改
                }

                Method (_PSR, 0, Serialized)  // _PSR: 电源来源
                {
                    Return (SPSR) /* \\_SB_.ADP0.SPSR */
                }

                Method (_PCL, 0, NotSerialized)  // _PCL: 电源消费者列表
                {
                    Return (\\_SB)
                }
            }

            Device (BAT0)
            {
                Name (_HID, EisaId ("PNP0C0A") /* 控制方法电池 */)  // _HID: 硬件 ID
                Name (_UID, Zero)  // _UID: 唯一 ID
                Name (_PCL, Package (0x01)  // _PCL: 电源消费者列表
                {
                    _SB
                })
                Method (_STA, 0, NotSerialized)  // _STA: 状态
                {
                    Return (0x1F)
                }
            }
        }

        Scope (_SB.PCI0)
        {
            Device (IPTS)
            {
                Name (_ADR, 0x00160004)  // _ADR: 地址
            }
        }
    }
}
""" 
        return {
            "Add": [
                {
                    "Comment": ssdt_name + ".aml",
                    "Enabled": self.write_ssdt(ssdt_name, ssdt_content),
                    "Path": ssdt_name + ".aml"
                }
            ]
        }

    def find_line_start(self, text, index):
        current_idx = index
        while current_idx > 0:
            if text[current_idx] == '\n':
                return current_idx + 1
            current_idx -= 1
        return 0

    def extract_line(self, text, index):
        start_idx = self.find_line_start(text, index)
        end_idx = text.index("\n", start_idx) + 1 if "\n" in text[start_idx:] else len(text)
        return text[start_idx:end_idx].strip(), start_idx, end_idx

    def extract_block_content(self, text, start_idx):
        try:
            block_start = text.index("{", start_idx)
            brace_count = 1
            pos = block_start + 1
            while brace_count > 0 and pos < len(text):
                if text[pos] == '{':
                    brace_count += 1
                elif text[pos] == '}':
                    brace_count -= 1
                pos += 1
            if brace_count == 0:
                return text[block_start:pos]
        except ValueError as e:
            pass
        return ""

    def parse_field_line(self, line):
        try:
            if "//" in line:
                line = line.split("//")[0].strip()
            parts = line.split(",")
            if len(parts) >= 2:
                field_name = parts[0].strip()
                size_part = parts[1].strip()
                try:
                    field_size = int(size_part)
                except ValueError:
                    return None, None
                return field_name, field_size
        except (ValueError, IndexError) as e:
            pass
        return None, None

    def process_embedded_control_region(self, table, start_idx):
        try:
            embed_control_idx = table.index("EmbeddedControl", start_idx)
            line, start_line_idx, end_line_idx = self.extract_line(table, embed_control_idx)
            region_name = line.split("(")[1].split(",")[0].strip()
            return region_name, end_line_idx
        except (ValueError, IndexError) as e:
            return None, start_idx + 1

    def process_field_definition(self, table, region_name, start_idx):
        fields = []
        try:
            field_pattern = f"Field ({region_name}"
            if field_pattern not in table[start_idx:]:
                return fields, len(table)
            field_start_idx = table.index(field_pattern, start_idx)
            field_line, field_start_line_idx, field_end_line_idx = self.extract_line(table, field_start_idx)
            field_block = self.extract_block_content(table, field_end_line_idx)
            for line in field_block.splitlines():
                line = line.strip()
                if not line or line in ["{", "}"]:
                    continue
                field_name, field_size = self.parse_field_line(line)
                if field_name and field_size is not None:
                    field_info = {
                        "name": field_name,
                        "size": field_size,
                    }
                    fields.append(field_info)
            return fields, field_end_line_idx
        except (ValueError, IndexError) as e:
            return fields, start_idx + 1

    def battery_status_patch(self):
        if not self.dsdt:
            return False
        search_start_idx = 0
        all_fields = []
        while "EmbeddedControl" in self.dsdt.get("table")[search_start_idx:]:
            region_name, search_start_idx = self.process_embedded_control_region(self.dsdt.get("table"), search_start_idx)
            if not region_name:
                continue
            current_idx = search_start_idx
            region_fields = []
            while True:
                fields, next_idx = self.process_field_definition(self.dsdt.get("table"), region_name, current_idx)
                if not fields or next_idx <= current_idx:
                    break
                region_fields.extend(fields)
                current_idx = next_idx
                if f"Field ({region_name}" not in self.dsdt.get("table")[current_idx:]:
                    break
            all_fields.extend(region_fields)
        return any(f["size"] > 8 for f in all_fields)

    def dropping_the_table(self, signature=None, oemtableid=None):
        table_data = self.acpi.get_table_with_signature(signature) or self.acpi.get_table_with_id(oemtableid)
        if not table_data:
            return
        return {
            "All": True,
            "Comment": "删除 {}".format((signature or oemtableid).rstrip(b"\x00").decode()),
            "Enabled": True,
            "OemTableId": self.utils.hex_to_bytes(binascii.hexlify(table_data.get("id")).decode()),
            "TableLength": table_data.get("length"),
            "TableSignature": self.utils.hex_to_bytes(binascii.hexlify(table_data.get("signature")).decode())
        }

    def fix_apic_processor_id(self):
        self.apic = self.acpi.get_table_with_signature("APIC")
        new_apic = ""
        if not self.apic:
            return
        for table_name in self.sorted_nicely(list(self.acpi.acpi_tables)):
            table = self.acpi.acpi_tables[table_name]
            processors = self.acpi.get_processor_paths(table=table)
            if not processors:
                continue
            processor_index = -1
            apic_length = len(self.apic.get("lines"))
            skip_unknown_subtable = False
            for index in range(apic_length):
                line = self.apic.get("lines")[index]
                if "Unknown" in line:
                    skip_unknown_subtable = not skip_unknown_subtable
                    continue
                if skip_unknown_subtable:
                    continue
                if "Subtable Type" in line and "[Processor Local APIC]" in line:
                    processor_index += 1
                    apic_processor_id = self.apic["lines"][index + 2][-2:]
                    try:
                        processor_id = table.get("lines")[processors[processor_index][1]].split(", ")[1][2:]
                    except:
                        return
                    if processor_index == 0 and apic_processor_id == processor_id:
                        return
                    self.apic["lines"][index + 2] = self.apic["lines"][index + 2][:-2] + processor_id
                new_apic += line + "\n"
            if processor_index != -1:
                return {
                    "Add": [
                        {
                            "Comment": "APIC.aml",
                            "Enabled": self.write_ssdt("APIC", new_apic),
                            "Path": "APIC.aml"
                        }
                    ],
                    "Delete": [
                        self.dropping_the_table("APIC")
                    ]
                }

    def disable_usb_hub_devices(self):
        ssdt_name = "SSDT-USB-Reset"
        patches = []
        ssdt_content = """
DefinitionBlock ("", "SSDT", 2, "ZPSS", "UsbReset", 0x00001000)
{"""
        rhub_devices = self.acpi.get_device_paths("RHUB")
        rhub_devices.extend(self.acpi.get_device_paths("HUBN"))
        rhub_devices.extend(self.acpi.get_device_paths("URTH"))
        if not rhub_devices:
            return
        for device in rhub_devices:
            device_path = device[0]
            sta = self.get_sta_var(var=None, device=device_path, dev_hid=None, dev_name=device_path.split(".")[-1], table=self.dsdt)
            patches.extend(sta.get("patches", []))
            ssdt_content += """
    External ([[device_path]], DeviceObj)

    Scope ([[device_path]])
    {
        Method (_STA, 0, NotSerialized)  // _STA: 状态
        {
            If (_OSI ("Darwin"))
            {
                Return (Zero)
            }
            Else
            {
                Return (0x0F)
            }
        }
    }
""".replace("[[device_path]]", device_path)
        ssdt_content += "\n}"
        return {
            "Add": [
                {
                    "Comment": ssdt_name + ".aml",
                    "Enabled": self.write_ssdt(ssdt_name, ssdt_content),
                    "Path": ssdt_name + ".aml"
                }
            ],
            "Patch": patches
        }
    
    def return_thermal_zone(self):
        ssdt_name = "SSDT-WMIS"
        ssdt_content = """
// 资源：https://github.com/zhen-zen/YogaSMC/blob/master/YogaSMC/SSDTSample/SSDT-WMIS.dsl

/*
 * 修复传感器返回的示例 SSDT
 *
 * 某些型号忘记从 ThermalZone 返回结果：
 *
 * Method (WQBI, 1, NotSerialized)
 * {
 *     \\_TZ.WQBI (Arg0)
 * }
 *
 * 因此我们必须修补它以正确报告。
 * 将 Method (WQBI, 1, N) 重命名为 XQBI
 * （ThermalZone 的那个通常是 Serialized 类型）
 *
 * Find: 57514249 01 // WQBI
 * Repl: 58514249 01 // XQBI 
 *
 * MethodFlags :=
 * bit 0-2: ArgCount (0-7)
 * bit 3:   SerializeFlag
 *          0 NotSerialized
 *          1 Serialized
 */
DefinitionBlock ("", "SSDT", 2, "ZPSS", "WMIS", 0x00000000)
{
    External (_TZ.WQBI, MethodObj)    // ThermalZone 中的方法

    Method (_SB.WMIS.WQBI, 1, NotSerialized)
    {
        Return (\\_TZ.WQBI (Arg0))
    }
}
"""
        for table_name in self.sorted_nicely(list(self.acpi.acpi_tables)):
            table = self.acpi.acpi_tables[table_name]
            wqbi_method = self.acpi.get_method_paths("WQBI", table=table)
            if not wqbi_method:
                continue
            return {
                "Add": [
                    {
                        "Comment": ssdt_name + ".aml",
                        "Enabled": self.write_ssdt(ssdt_name, ssdt_content),
                        "Path": ssdt_name + ".aml"
                    }
                ],
                "Patch": [
                    {
                        "Comment": "WQBI 重命名为 XQBI",
                        "Find": "5751424901",
                        "Replace": "5851424901"
                    }
                ]
            }

    def drop_cpu_tables(self):
        cpu_tables = ["CpuPm", "Cpu0Ist"]
        deletes = []
        for table_name in cpu_tables:
            padded_table_id = self.get_data(table_name, pad_to=8)
            table_entry = self.dropping_the_table(oemtableid=padded_table_id)
            if table_entry:
                deletes.append(table_entry)
        return {
            "Delete": deletes
        }

    def select_acpi_tables(self):
        while True:
            self.utils.head("选择 ACPI 表")
            print("")
            print("Q. 退出")
            print(" ")
            menu = self.utils.request_input("请将 ACPI 表文件夹拖放到此处：")
            if menu.lower() == "q":
                self.utils.exit_program()
            path = self.utils.normalize_path(menu)
            if not path: 
                continue
            return self.read_acpi_tables(path)

    def get_patch_index(self, name):
        for index, patch in enumerate(self.patches):
            if patch.name == name:
                return index
        return None

    def select_acpi_patches(self, hardware_report, disabled_devices):
        selected_patches = []
        if  "Laptop" in hardware_report.get("Motherboard").get("Platform") and \
            "Integrated GPU" in list(hardware_report.get("GPU").items())[-1][-1].get("Device Type") and \
            not "SURFACE" in hardware_report.get("Motherboard").get("Name"):
            selected_patches.append("ALS")
            selected_patches.append("PNLF")
        if self.is_intel_hedt_cpu(hardware_report.get("CPU").get("Processor Name"), hardware_report.get("CPU").get("Codename")):
            selected_patches.append("APIC")
        for device_name, device_info in disabled_devices.items():
            if "PCI" in device_info.get("Bus Type", "PCI"):
                selected_patches.append("Disable Devices")
        selected_patches.append("FakeEC")
        if "HP " in hardware_report.get("Motherboard").get("Name"):
            selected_patches.append("CMOS")
        if hardware_report.get("Motherboard").get("Chipset") in chipset_data.IntelChipsets[-7:]:
            selected_patches.append("RCSP")
        if "Laptop" in hardware_report.get("Motherboard").get("Platform") and hardware_report.get("CPU").get("Codename") in cpu_data.IntelCPUGenerations[50:]:
            selected_patches.append("FixHPET")
        for device_name, device_info in hardware_report.get("System Devices", {}).items():
            device_id = device_info.get("Device ID")
            if not device_id in ("8086-1C3A", "8086-1E3A"):
                continue
            if  "Sandy Bridge" in hardware_report.get("CPU").get("Codename") and device_id in "8086-1E3A" or \
                "Ivy Bridge" in hardware_report.get("CPU").get("Codename") and device_id in "8086-1C3A":
                selected_patches.append("IMEI")
        if hardware_report.get("Motherboard").get("Chipset") in chipset_data.IntelChipsets[100:112]:
            selected_patches.append("PMC")
        if "Sandy Bridge" in hardware_report.get("CPU").get("Codename") or "Ivy Bridge" in hardware_report.get("CPU").get("Codename"):
            selected_patches.append("PM (Legacy)")
        else:
            selected_patches.append("PLUG")
        if all(network_props.get("Bus Type") == "USB" for network_props in hardware_report.get("Network", {}).values()):
            selected_patches.append("RMNE")
        if hardware_report.get("Motherboard").get("Chipset") in chipset_data.IntelChipsets[62:64] + chipset_data.IntelChipsets[90:100]:
            selected_patches.append("RTC0")
        if "AMD" in hardware_report.get("CPU").get("Manufacturer") or hardware_report.get("CPU").get("Codename") in cpu_data.IntelCPUGenerations[:40]:
            selected_patches.append("RTCAWAC")
        if "Intel" in hardware_report.get("CPU").get("Manufacturer"):
            selected_patches.append("BUS0")
        if "SURFACE" in hardware_report.get("Motherboard").get("Name"):
            selected_patches.append("Surface Patch")
        else:
            if "Intel" in hardware_report.get("CPU").get("Manufacturer"):
                for device_name, device_info in hardware_report.get("Input", {}).items():
                    if "I2C" in device_info.get("Device Type", "None"):
                        selected_patches.append("GPI0")
        if hardware_report.get("Motherboard").get("Chipset") in chipset_data.IntelChipsets[27:28] + chipset_data.IntelChipsets[62:64]:
            selected_patches.append("UNC")
        if "AMD" in hardware_report.get("CPU").get("Manufacturer") or hardware_report.get("Motherboard").get("Chipset") in chipset_data.IntelChipsets[112:]:
            selected_patches.append("USB Reset")
        selected_patches.append("USBX")
        if "Laptop" in hardware_report.get("Motherboard").get("Platform"):
            selected_patches.append("BATP")
            selected_patches.append("XOSI")
        for device_name, device_info in hardware_report.get("System Devices", {}).items():
            if device_info.get("Bus Type") == "ACPI" and device_info.get("Device") in pci_data.YogaHIDs:
                selected_patches.append("WMIS")
        for patch in self.patches:
            patch.checked = patch.name in selected_patches
    
    def customize_patch_selection(self):
        while True:
            contents = []
            contents.append("")
            contents.append("可用补丁列表：")
            contents.append("")
            for index, kext in enumerate(self.patches, start=1):
                checkbox = "[*]" if kext.checked else "[ ]"
                line = "{} {:2}. {:15} - {:60}".format(checkbox, index, kext.name, kext.description)
                if kext.checked:
                    line = "\033[1;32m{}\033[0m".format(line)
                contents.append(line)
            contents.append("")
            contents.append("\033[1;93m注意：\033[0m您可以输入用逗号分隔的索引来选择多个补丁（例如 '1, 2, 3'）。")
            contents.append("")
            contents.append("B. 返回")
            contents.append("Q. 退出")
            contents.append("")
            content = "\n".join(contents)
            self.utils.adjust_window_size(content)
            self.utils.head("自定义 ACPI 补丁选择", resize=False)
            print(content)
            option = self.utils.request_input("请选择选项：")
            if option.lower() == "q":
                self.utils.exit_program()
            if option.lower() == "b":
                return
            indices = [int(i.strip()) -1 for i in option.split(",") if i.strip().isdigit()]
            for index in indices:
                if index >= 0 and index < len(self.patches):
                    patch = self.patches[index]
                    patch.checked = not patch.checked