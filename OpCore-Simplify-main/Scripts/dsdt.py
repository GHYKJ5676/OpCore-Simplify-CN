# 原始来源：https://github.com/corpnewt/SSDTTime/blob/64446d553fcbc14a4e6ebf3d8d16e3357b5cbf50/Scripts/dsdt.py

import os, errno, tempfile, shutil, plistlib, sys, binascii, zipfile, getpass, re
from Scripts import github
from Scripts import resource_fetcher
from Scripts import run
from Scripts import utils

class DSDT:
    def __init__(self, **kwargs):
        self.github = github.Github()
        self.fetcher = resource_fetcher.ResourceFetcher()
        self.r  = run.Run()
        self.u = utils.Utils()
        self.iasl_url_macOS = "https://raw.githubusercontent.com/acidanthera/MaciASL/master/Dist/iasl-stable"
        self.iasl_url_macOS_legacy = "https://raw.githubusercontent.com/acidanthera/MaciASL/master/Dist/iasl-legacy"
        self.iasl_url_linux = "https://raw.githubusercontent.com/corpnewt/linux_iasl/main/iasl.zip"
        self.iasl_url_linux_legacy = "https://raw.githubusercontent.com/corpnewt/iasl-legacy/main/iasl-legacy-linux.zip"
        self.acpi_binary_tools = "https://github.com/acpica/acpica/releases"
        self.iasl_url_windows_legacy = "https://raw.githubusercontent.com/corpnewt/iasl-legacy/main/iasl-legacy-windows.zip"
        self.h = {}
        self.iasl = self.check_iasl()
        if not self.iasl:
            url = self.acpi_binary_tools if os.name=="nt" else \
            self.iasl_url_macOS if sys.platform=="darwin" else \
            self.iasl_url_linux if sys.platform.startswith("linux") else None
            exception = "找不到或无法下载 iasl！"
            if url:
                exception += "\n\n请从以下地址手动下载 {}：\n - {}\n\n并放置于：\n - {}\n".format(
                    "\"iasl-win-YYYYMMDD.zip\" 并解压出 iasl.exe" if os.name=="nt" else "iasl",
                    url,
                    os.path.dirname(os.path.realpath(__file__))
                )
            raise Exception(exception)
        self.allowed_signatures = (b"APIC",b"DMAR",b"DSDT",b"SSDT")
        self.mixed_listing      = (b"DSDT",b"SSDT")
        self.acpi_tables = {}
        self.hex_match  = re.compile(r"^\s*[0-9A-F]{4,}:(\s[0-9A-F]{2})+(\s+\/\/.*)?$")
        self.type_match = re.compile(r".*(?P<type>Processor|Scope|Device|Method|Name) \((?P<name>[^,\)]+).*")

    def _table_signature(self, table_path, table_name = None):
        path = os.path.join(table_path,table_name) if table_name else table_path
        if not os.path.isfile(path):
            return None
        with open(path,"rb") as f:
            try:
                sig = f.read(4)
                return sig
            except:
                pass
        return None

    def table_is_valid(self, table_path, table_name = None):
        return self._table_signature(table_path,table_name=table_name) in self.allowed_signatures

    def get_ascii_print(self, data):
        unprintables = False
        ascii_string = ""
        for b in data:
            if not isinstance(b,int):
                try: b = ord(b)
                except: pass
            if ord(" ") <= b < ord("~"):
                ascii_string += chr(b)
            else:
                ascii_string += "?"
                unprintables = True
        return (unprintables,ascii_string)

    def load(self, table_path):
        cwd = os.getcwd()
        temp = None
        target_files = {}
        failed = []
        try:
            if os.path.isdir(table_path):
                valid_files = [x for x in os.listdir(table_path) if self.table_is_valid(table_path,x)]
            elif os.path.isfile(table_path):
                valid_files = [table_path]
            else:
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), table_path)
            if not valid_files:
                raise FileNotFoundError(
                    errno.ENOENT,
                    os.strerror(errno.ENOENT),
                    "在 {} 中未找到有效的 .aml/.dat 文件".format(table_path)
                )
            temp = tempfile.mkdtemp()
            for file in valid_files:
                shutil.copy(
                    os.path.join(table_path,file),
                    temp
                )
            list_dir = os.listdir(temp)
            for x in list_dir:
                if len(list_dir) > 1 and not self.table_is_valid(temp,x):
                    continue
                name_ext = [y for y in os.path.basename(x).split(".") if y]
                if name_ext and name_ext[-1].lower() in ("asl","dsl"):
                    continue
                target_files[x] = {
                    "assembled_name": os.path.basename(x),
                    "disassembled_name": ".".join(x.split(".")[:-1]) + ".dsl",
                }
            if not target_files:
                raise FileNotFoundError(
                    errno.ENOENT,
                    os.strerror(errno.ENOENT),
                    "在 {} 中未找到有效的 .aml/.dat 文件".format(table_path)
                )
            os.chdir(temp)
            dsdt_or_ssdt = [x for x in list(target_files) if self._table_signature(temp,x) in self.mixed_listing]
            other_tables = [x for x in list(target_files) if not x in dsdt_or_ssdt]
            out_d = ("","",0)
            out_t = ("","",0)

            def exists(folder_path,file_name):
                check_path = os.path.join(folder_path,file_name)
                if os.path.isfile(check_path) and os.stat(check_path).st_size > 0:
                    return True
                return False
            
            if dsdt_or_ssdt:
                args = [self.iasl,"-da","-dl","-l"]+list(dsdt_or_ssdt)
                out_d = self.r.run({"args":args})
                if out_d[2] != 0:
                    args = [self.iasl,"-dl","-l"]+list(dsdt_or_ssdt)
                    out_d = self.r.run({"args":args})
                fail_temp = []
                for x in dsdt_or_ssdt:
                    if not exists(temp,target_files[x]["disassembled_name"]):
                        fail_temp.append(x)
                for x in fail_temp:
                    args = [self.iasl,"-dl","-l",x]
                    self.r.run({"args":args})
                    if not exists(temp,target_files[x]["disassembled_name"]):
                        failed.append(x)
            if other_tables:
                args = [self.iasl]+list(other_tables)
                out_t = self.r.run({"args":args})
                for x in other_tables:
                    if not exists(temp,target_files[x]["disassembled_name"]):
                        failed.append(x)
            if len(failed) == len(target_files):
                raise Exception("反编译失败 - {}".format(", ".join(failed)))
            to_remove = []
            for file in target_files:
                if not exists(temp,target_files[file]["disassembled_name"]):
                    to_remove.append(file)
                    continue
                with open(os.path.join(temp,target_files[file]["disassembled_name"]),"r") as f:
                    target_files[file]["table"] = f.read()
                    if target_files[file]["table"].startswith("/*"):
                        target_files[file]["table"] = "*/".join(target_files[file]["table"].split("*/")[1:]).strip()
                    for h in ("\nTable Header:","\nRaw Table Data: Length"):
                        if h in target_files[file]["table"]:
                            target_files[file]["table"] = h.join(target_files[file]["table"].split(h)[:-1]).rstrip()
                            break
                    target_files[file]["lines"] = target_files[file]["table"].split("\n")
                    target_files[file]["scopes"] = self.get_scopes(table=target_files[file])
                    target_files[file]["paths"] = self.get_paths(table=target_files[file])
                with open(os.path.join(temp,file),"rb") as f:
                    table_bytes = f.read()
                    target_files[file]["raw"] = table_bytes
                    target_files[file]["signature"] = table_bytes[0:4]
                    target_files[file]["revision"]  = table_bytes[8]
                    target_files[file]["oem"]       = table_bytes[10:16]
                    target_files[file]["id"]        = table_bytes[16:24]
                    target_files[file]["oem_revision"] = int(binascii.hexlify(table_bytes[24:28][::-1]),16)
                    target_files[file]["length"]    = len(table_bytes)
                    for key in ("signature","oem","id"):
                        unprintable,ascii_string = self.get_ascii_print(target_files[file][key])
                        if unprintable:
                            target_files[file][key+"_ascii"] = ascii_string
                if 2/3==0:
                    target_files[file]["revision"] = int(binascii.hexlify(target_files[file]["revision"]),16)
            for file in to_remove:
                target_files.pop(file,None)
        except Exception as e:
            print(e)
            return ({},failed)
        finally:
            os.chdir(cwd)
            if temp: shutil.rmtree(temp,ignore_errors=True)
        for table in target_files:
            self.acpi_tables[table] = target_files[table]
        return (target_files, failed,)

    def get_latest_iasl(self):
        latest_release = self.github.get_latest_release("acpica", "acpica") or {}
        for line in latest_release.get("body", "").splitlines():
            if "iasl" in line and ".zip" in line:
                return line.split("\"")[1]
        for asset in latest_release.get("assets", []):
            if "/iasl" in asset.get("url") and ".zip" in asset.get("url"):
                return asset.get("url")
        return None
    
    def check_iasl(self, legacy=False, try_downloading=True):
        if sys.platform == "win32":
            targets = (os.path.join(os.path.dirname(os.path.realpath(__file__)), "iasl-legacy.exe" if legacy else "iasl.exe"),)
        else:
            if legacy:
                targets = (os.path.join(os.path.dirname(os.path.realpath(__file__)), "iasl-legacy"),)
            else:
                targets = (
                    os.path.join(os.path.dirname(os.path.realpath(__file__)), "iasl-dev"),
                    os.path.join(os.path.dirname(os.path.realpath(__file__)), "iasl-stable"),
                    os.path.join(os.path.dirname(os.path.realpath(__file__)), "iasl")
                )
        target = next((t for t in targets if os.path.exists(t)),None)
        if target or not try_downloading:
            return target
        temp = tempfile.mkdtemp()
        try:
            if sys.platform == "darwin":
                self._download_and_extract(temp,self.iasl_url_macOS_legacy if legacy else self.iasl_url_macOS)
            elif sys.platform.startswith("linux"):
                self._download_and_extract(temp,self.iasl_url_linux_legacy if legacy else self.iasl_url_linux)
            elif sys.platform == "win32":
                iasl_url_windows = self.iasl_url_windows_legacy if legacy else self.get_latest_iasl()
                if not iasl_url_windows: raise Exception("无法获取适用于 Windows 的最新 iasl")
                self._download_and_extract(temp,iasl_url_windows)
            else: 
                raise Exception("未知操作系统")
        except Exception as e:
            print("发生错误：\n - {}".format(e))
        shutil.rmtree(temp, ignore_errors=True)
        return self.check_iasl(legacy=legacy,try_downloading=False)

    def _download_and_extract(self, temp, url):
        self.u.head("正在收集文件")
        print("")
        print("请等待下载 iasl...")
        print("")
        ztemp = tempfile.mkdtemp(dir=temp)
        zfile = os.path.basename(url)
        self.fetcher.download_and_save_file(url, os.path.join(ztemp,zfile))
        search_dir = ztemp
        if zfile.lower().endswith(".zip"):
            print(" - 正在解压")
            search_dir = tempfile.mkdtemp(dir=temp)
            with zipfile.ZipFile(os.path.join(ztemp,zfile)) as z:
                z.extractall(search_dir)
        script_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)))
        for x in os.listdir(search_dir):
            if x.lower().startswith(("iasl","acpidump")):
                print(" - 找到 {}".format(x))
                if sys.platform != "win32":
                    print("   - 设置可执行权限")
                    self.r.run({"args":["chmod","+x",os.path.join(search_dir,x)]})
                print("   - 复制到 {} 目录".format(os.path.basename(script_dir)))
                shutil.copy(os.path.join(search_dir,x), os.path.join(script_dir,x))

    def dump_tables(self, output, disassemble=False):
        self.u.head("正在转储 ACPI 表")
        print("")
        res = self.check_output(output)
        if os.name == "nt":
            target = os.path.join(os.path.dirname(os.path.realpath(__file__)),"acpidump.exe")
            if os.path.exists(target):
                print("正在将表转储到 {}...".format(res))
                cwd = os.getcwd()
                os.chdir(res)
                out = self.r.run({"args":[target,"-b"]})
                os.chdir(cwd)
                if out[2] != 0:
                    print(" - {}".format(out[1]))
                    return
                if not next((x for x in os.listdir(res) if x.lower().startswith("dsdt.")),None):
                    print(" - 未找到 DSDT，按签名转储...")
                    os.chdir(res)
                    out = self.r.run({"args":[target,"-b","-n","DSDT"]})
                    os.chdir(cwd)
                    if out[2] != 0:
                        print(" - {}".format(out[1]))
                        return
                print("正在更新文件名...")
                for f in os.listdir(res):
                    new_name = f.upper()
                    if new_name.endswith(".DAT"):
                        new_name = new_name[:-4]+".aml"
                    if new_name != f:
                        try:
                            os.rename(os.path.join(res,f),os.path.join(res,new_name))
                        except Exception as e:
                            print(" - {} -> {} 失败：{}".format(f,new_name,e))
                print("转储成功！")
                if disassemble:
                    return self.load(res)
                return res
            else:
                print("找不到 acpidump.exe")
                return
        elif sys.platform.startswith("linux"):
            table_dir = "/sys/firmware/acpi/tables"
            if not os.path.isdir(table_dir):
                print("找不到 {}！".format(table_dir))
                return
            print("正在将表复制到 {}...".format(res))
            copied_files = []
            for table in os.listdir(table_dir):
                if not os.path.isfile(os.path.join(table_dir,table)):
                    continue
                target_path = os.path.join(res,table.upper()+".aml")
                out = self.r.run({"args":["sudo","cp",os.path.join(table_dir,table),target_path]})
                if out[2] != 0:
                    print(" - {}".format(out[1]))
                    return
                out = self.r.run({"args":["sudo","chown",getpass.getuser(), target_path]})
                if out[2] != 0:
                    print(" - {}".format(out[1]))
                    return
            print("转储成功！")
            if disassemble:
                return self.load(res)
            return res

    def check_output(self, output):
        t_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), output)
        if not os.path.isdir(t_folder):
            os.makedirs(t_folder)
        return t_folder

    def get_hex_from_int(self, total, pad_to = 4):
        hex_str = hex(total)[2:].upper().rjust(pad_to,"0")
        return "".join([hex_str[i:i + 2] for i in range(0, len(hex_str), 2)][::-1])

    def get_hex(self, line):
        return line.split(":")[1].split("//")[0].replace(" ","")

    def get_line(self, line):
        line = line.split("//")[0]
        if ":" in line:
            return line.split(":")[1]
        return line

    def get_hex_bytes(self, line):
        return binascii.unhexlify(line)

    def get_str_bytes(self, value):
        if 2/3!=0 and isinstance(value,str):
            value = value.encode()
        return value

    def get_table_with_id(self, table_id):
        table_id = self.get_str_bytes(table_id)
        return next((v for k,v in self.acpi_tables.items() if table_id == v.get("id")),None)

    def get_table_with_signature(self, table_sig):
        table_sig = self.get_str_bytes(table_sig)
        return next((v for k,v in self.acpi_tables.items() if table_sig == v.get("signature")),None)
    
    def get_table(self, table_id_or_sig):
        table_id_or_sig = self.get_str_bytes(table_id_or_sig)
        return next((v for k,v in self.acpi_tables.items() if table_id_or_sig in (v.get("signature"),v.get("id"))),None)

    def get_dsdt(self):
        return self.get_table_with_signature("DSDT")

    def get_dsdt_or_only(self):
        dsdt = self.get_dsdt()
        if dsdt: return dsdt
        if len(self.acpi_tables) != 1:
            return None
        return list(self.acpi_tables.values())[0]

    def find_previous_hex(self, index=0, table=None):
        if not table: table = self.get_dsdt_or_only()
        if not table: return ("",-1,-1)
        start_index = -1
        end_index   = -1
        old_hex = True
        for i,line in enumerate(table.get("lines","")[index::-1]):
            if old_hex:
                if not self.is_hex(line):
                    old_hex = False
                continue
            if self.is_hex(line):
                end_index = index-i
                hex_text,start_index = self.get_hex_ending_at(end_index,table=table)
                return (hex_text, start_index, end_index)
        return ("",start_index,end_index)
    
    def find_next_hex(self, index=0, table=None):
        if not table: table = self.get_dsdt_or_only()
        if not table: return ("",-1,-1)
        start_index = -1
        end_index   = -1
        old_hex = True
        for i,line in enumerate(table.get("lines","")[index:]):
            if old_hex:
                if not self.is_hex(line):
                    old_hex = False
                continue
            if self.is_hex(line):
                start_index = i+index
                hex_text,end_index = self.get_hex_starting_at(start_index,table=table)
                return (hex_text, start_index, end_index)
        return ("",start_index,end_index)

    def is_hex(self, line):
        return self.hex_match.match(line) is not None

    def get_hex_starting_at(self, start_index, table=None):
        if not table: table = self.get_dsdt_or_only()
        if not table: return ("",-1)
        hex_text = ""
        index = -1
        for i,x in enumerate(table.get("lines","")[start_index:]):
            if not self.is_hex(x):
                break
            hex_text += self.get_hex(x)
            index = i+start_index
        return (hex_text, index)

    def get_hex_ending_at(self, start_index, table=None):
        if not table: table = self.get_dsdt_or_only()
        if not table: return ("",-1)
        hex_text = ""
        index = -1
        for i,x in enumerate(table.get("lines","")[start_index::-1]):
            if not self.is_hex(x):
                break
            hex_text = self.get_hex(x)+hex_text
            index = start_index-i
        return (hex_text, index)

    def get_shortest_unique_pad(self, current_hex, index, instance=0, table=None):
        if not table: table = self.get_dsdt_or_only()
        if not table: return None
        try:    left_pad  = self.get_unique_pad(current_hex, index, False, instance, table=table)
        except: left_pad  = None
        try:    right_pad = self.get_unique_pad(current_hex, index, True, instance, table=table)
        except: right_pad = None
        try:    mid_pad   = self.get_unique_pad(current_hex, index, None, instance, table=table)
        except: mid_pad   = None
        if left_pad == right_pad == mid_pad is None: raise Exception("未找到唯一填充！")
        min_pad = None
        for x in (left_pad,right_pad,mid_pad):
            if x is None: continue
            if min_pad is None or len(x[0]+x[1]) < len(min_pad[0]+min_pad[1]):
                min_pad = x
        return min_pad

    def get_unique_pad(self, current_hex, index, direction=None, instance=0, table=None):
        if not table: table = self.get_dsdt_or_only()
        if not table: raise Exception("未传递有效表！")
        start_index = index
        line,last_index = self.get_hex_starting_at(index,table=table)
        if last_index == -1:
            raise Exception("在索引 {} 处未找到十六进制！".format(index))
        first_line = line
        while True:
            if current_hex in line or len(line) >= len(first_line)+len(current_hex):
                break
            new_line,_index,last_index = self.find_next_hex(last_index, table=table)
            if last_index == -1:
                raise Exception("在找到所需十六进制之前到达文件末尾！")
            line += new_line
        if not current_hex in line:
            raise Exception("在表索引 {}-{} 中找不到 {}！".format(start_index,last_index,current_hex))
        padl = padr = ""
        parts = line.split(current_hex)
        if instance >= len(parts)-1:
            raise Exception("实例超出范围！")
        linel = current_hex.join(parts[0:instance+1])
        liner = current_hex.join(parts[instance+1:])
        last_check = True
        while True:
            check_bytes = self.get_hex_bytes(padl+current_hex+padr)
            if table["raw"].count(check_bytes) == 1:
                break
            if direction == True or (direction is None and len(padr)<=len(padl)):
                if not len(liner):
                    liner, _index, last_index = self.find_next_hex(last_index, table=table)
                    if last_index == -1: raise Exception("在找到唯一十六进制之前到达文件末尾！")
                padr  = padr+liner[0:2]
                liner = liner[2:]
                continue
            if direction == False or (direction is None and len(padl)<=len(padr)):
                if not len(linel):
                    linel, start_index, _index = self.find_previous_hex(start_index, table=table)
                    if _index == -1: raise Exception("在找到唯一十六进制之前到达文件末尾！")
                padl  = linel[-2:]+padl
                linel = linel[:-2]
                continue
            break
        return (padl,padr)
    
    def get_devices(self,search=None,types=("Device (","Scope ("),strip_comments=False,table=None):
        if not table: table = self.get_dsdt_or_only()
        if not table: return []
        if search is None:
            return []
        last_device = None
        device_index = 0
        devices = []
        for index,line in enumerate(table.get("lines","")):
            if self.is_hex(line):
                continue
            line = self.get_line(line) if strip_comments else line
            if any ((x for x in types if x in line)):
                last_device = line
                device_index = index
            if search in line:
                devices.append((last_device,device_index,index))
        return devices

    def get_scope(self,starting_index=0,add_hex=False,strip_comments=False,table=None):
        if not table: table = self.get_dsdt_or_only()
        if not table: return []
        brackets = None
        scope = []
        for line in table.get("lines","")[starting_index:]:
            if self.is_hex(line):
                if add_hex:
                    scope.append(line)
                continue
            line = self.get_line(line) if strip_comments else line
            scope.append(line)
            if brackets is None:
                if line.count("{"):
                    brackets = line.count("{")
                continue
            brackets = brackets + line.count("{") - line.count("}")
            if brackets <= 0:
                return scope
        return scope

    def get_scopes(self, table=None):
        if not table: table = self.get_dsdt_or_only()
        if not table: return []
        scopes = []
        for index,line in enumerate(table.get("lines","")):
            if self.is_hex(line): continue
            if any(x in line for x in ("Processor (","Scope (","Device (","Method (","Name (")):
                scopes.append((line,index))
        return scopes

    def get_paths(self, table=None):
        if not table: table = self.get_dsdt_or_only()
        if not table: return []
        path_list  = []
        _path      = []
        brackets = 0
        for i,line in enumerate(table.get("lines",[])):
            if self.is_hex(line):
                continue
            line = self.get_line(line)
            brackets += line.count("{")-line.count("}")
            while len(_path):
                if _path[-1][-1] >= brackets:
                    del _path[-1]
                else:
                    break
            type_match = self.type_match.match(line)
            if type_match:
                _path.append((type_match.group("name"),brackets))
                if type_match.group("type") == "Scope":
                    continue
                path = []
                for p in _path[::-1]:
                    path.append(p[0])
                    p_check = p[0].split(".")[0].rstrip("_")
                    if p_check.startswith("\\") or p_check in ("_SB","_PR"):
                        break
                path = ".".join(path[::-1]).split(".")
                if len(path) and path[0] == "\\": path.pop(0)
                if any("^" in x for x in path):
                    new_path = []
                    for x in path:
                        if x.count("^"):
                            del new_path[-1*x.count("^"):]
                        new_path.append(x.replace("^",""))
                    path = new_path
                if not path:
                    continue
                padded_path = [("\\" if j==0 else"")+x.lstrip("\\").rstrip("_") for j,x in enumerate(path)]
                path_str = ".".join(padded_path)
                path_list.append((path_str,i,type_match.group("type")))
        return sorted(path_list)

    def get_path_of_type(self, obj_type="Device", obj="HPET", table=None):
        if not table: table = self.get_dsdt_or_only()
        if not table: return []
        paths = []
        obj = ".".join([x.rstrip("_").upper() for x in obj.split(".")])
        obj_type = obj_type.lower() if obj_type else obj_type
        for path in table.get("paths",[]):
            path_check = ".".join([x.rstrip("_").upper() for x in path[0].split(".")])
            if (obj_type and obj_type != path[2].lower()) or not path_check.endswith(obj):
                continue
            paths.append(path)
        return sorted(paths)

    def get_device_paths(self, obj="HPET",table=None):
        return self.get_path_of_type(obj_type="Device",obj=obj,table=table)

    def get_method_paths(self, obj="_STA",table=None):
        return self.get_path_of_type(obj_type="Method",obj=obj,table=table)

    def get_name_paths(self, obj="CPU0",table=None):
        return self.get_path_of_type(obj_type="Name",obj=obj,table=table)

    def get_processor_paths(self, obj_type="Processor",table=None):
        return self.get_path_of_type(obj_type=obj_type,obj="",table=table)

    def get_device_paths_with_hid(self, hid="ACPI000E", table=None):
        if not table: table = self.get_dsdt_or_only()
        if not table: return []
        devs = []
        for p in table.get("paths",[]):
            try:
                if p[0].endswith("._HID") and hid.upper() in table.get("lines")[p[1]]:
                    devs.append(p[0][:-len("._HID")])
            except: continue
        devices = []
        for p in table.get("paths",[]):
            if p[0] in devs and p[-1] == "Device":
                devices.append(p)
        return devices