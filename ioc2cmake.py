#!/usr/bin/python3

import argparse
import os
import json
import shutil

def loadIOC(filename):
    conf = {}
    with open(filename) as f:
        while True:
            line = f.readline().strip()
            if not line:
                break
            if line[0] == '#':
                continue
            vals = line.split('=', 2)
            if len(vals) < 2:
                continue
            conf[vals[0]] = vals[1]
    return conf


def getCore(mcuName):
    coreTable = {
        "STM32F0": "cortex-m0",
        "STM32F1": "cortex-m3",
        "STM32F2": "cortex-m3",
        "STM32F3": "cortex-m4",
        "STM32F4": "cortex-m4",
        "STM32F7": "cortex-m7",
        "STM32H7": "cortex-m7",
        "STM32L0": "cortex-m0",
        "STM32L1": "cortex-m3",
        "STM32L4": "cortex-m4",
    }
    for key, value in coreTable.items():
        if mcuName.startswith(key):
            return value


def getFpu(mcuName):
    # TODO in case of m7 core, check if it has single or double precision fpu
    fpuTable = {
        "cortex-m0": None,
        "cortex-m3": None,
        "cortex-m4": "fpv4-sp-d16",
        "cortex-m7": "fpv5-d16"
    }
    for key, value in fpuTable.items():
        if getCore(mcuName) == key:
            return value

def joinFwdSlash(*args):
    # CMake doesn't like paths with backslashes on Windows
    return os.path.join(*args).replace('\\', '/')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create CMake and vscode config files from CubeMX .ioc project file")
    parser.add_argument("srcPath", help="Source path")
    parser.add_argument("iocFile", help="CubeMX .ioc project file")
    parser.add_argument("-s", help="additional source folder", action="append")
    parser.add_argument("-i", help="additional include folder", action="append")
    parser.add_argument("-v", help="enable vscode properties setup", action="store_true")
    parser.add_argument("-t", help="toolchain location")
    args = parser.parse_args()

    iocConf = loadIOC(args.iocFile)

    cmakeConf = {
        "CUBEMX_PROJNAME": iocConf["ProjectManager.ProjectName"],
        "CUBEMX_MCUFAMILY": iocConf["Mcu.Family"] + "xx",
        "CUBEMX_MCUNAME": iocConf["Mcu.UserName"],
        "CUBEMX_MCULINE": iocConf["Mcu.UserName"][0:9] + "xx",
        "CUBEMX_LDFILE": joinFwdSlash(args.srcPath,
                                      iocConf["Mcu.UserName"] + "_FLASH.ld"),
        "CUBEMX_CPUTYPE": getCore(iocConf["Mcu.Family"]),
        "CUBEMX_TOOLCHAIN": joinFwdSlash(args.t, "bin/") if args.t else ""
    }

    cmakeConf["CUBEMX_STARTUPFILE"] = \
        joinFwdSlash(args.srcPath,
                     "startup_" + cmakeConf["CUBEMX_MCULINE"].lower() + ".s")

    core = getCore(iocConf["Mcu.Family"])
    mcuFlags = f"-mcpu={core} -mthumb"

    fpu = getFpu(iocConf["Mcu.Family"])
    mcuFlags += f" -mfpu={fpu} -mfloat-abi=hard" \
                if fpu is not None else " -mfloat-abi=soft"

    cmakeConf["CUBEMX_MCUFLAGS"] = mcuFlags

    cdefs = [
        "USE_FULL_LL_DRIVER",
        f"HSE_VALUE={iocConf['RCC.HSE_VALUE']}",
        f"HSI_VALUE={iocConf['RCC.HSI_VALUE']}",
        f"LSI_VALUE={iocConf['RCC.LSI_VALUE']}",
        cmakeConf["CUBEMX_MCULINE"]
    ]
    cmakeConf["CUBEMX_CDEFS"] = "\n".join([f"-D{cdef}" for cdef in cdefs])

    cmsisDir = joinFwdSlash(args.srcPath, "Drivers", "CMSIS")
    deviceDir = joinFwdSlash(cmsisDir,
                             "Device", "ST", cmakeConf["CUBEMX_MCUFAMILY"])
    halDir = joinFwdSlash(args.srcPath,
                          "Drivers", cmakeConf["CUBEMX_MCUFAMILY"] + "_HAL_Driver")

    sourceDirs = [
        joinFwdSlash(args.srcPath, "Src"),
        joinFwdSlash(halDir, "Src"),
    ]
    if args.s:
        sourceDirs += args.s
    cmakeConf["CUBEMX_SOURCEDIRS"] = "\n".join(sourceDirs)

    includeDirs = [
        joinFwdSlash(args.srcPath, "Inc"),
        joinFwdSlash(cmsisDir, "Include"),
        joinFwdSlash(deviceDir, "Include"),
        joinFwdSlash(halDir, "Inc"),
    ]
    if args.i:
        includeDirs += args.i
    cmakeConf["CUBEMX_INCLUDEDIRS"] = "\n".join(includeDirs)

    for key, value in cmakeConf.items():
        print(f"{key}={value};", end="")

    if args.v:
        compilerName = "arm-none-eabi-gcc"
        defaultPath = os.path.join(args.t, "bin") if args.t else None
        # Create vscode properties
        vscodeProps = {
            "c_cpp_properties.json": {
                "configurations": [
                    {
                        "name": "Linux",
                        "includePath": includeDirs,
                        "defines": cdefs,
                        "compilerPath": shutil.which(compilerName, path=defaultPath).replace('\\', '/'),
                        "cStandard": "c11",
                        "intelliSenseMode": "gcc-x64"
                    }
                ],
                "version": 4
            },
            "launch.json": {
                "configurations": [
                    {
                        "name": "Cortex Debug",
                        "cwd": "${workspaceRoot}",
                        "executable": f"${{workspaceRoot}}/build/{iocConf['ProjectManager.ProjectName']}.elf",
                        "request": "attach",
                        "type": "cortex-debug",
                        "servertype": "openocd",
                        "device": iocConf["Mcu.UserName"],
                        "configFiles": [
                            "${workspaceRoot}/openocd.cfg"
                        ]
                    }
                ]
            },
            "settings.json": {
                "cortex-debug.armToolchainPath": joinFwdSlash(args.t, "bin") if args.t else ""
            }
        }

        os.makedirs(os.path.join(args.srcPath, ".vscode"), exist_ok=True)
        for k, v in vscodeProps.items():
            with open(os.path.join(args.srcPath, ".vscode", k), 'w') as outfile:
                json.dump(v, outfile, sort_keys=True, indent=4)
