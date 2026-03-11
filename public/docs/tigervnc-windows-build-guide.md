# TigerVNC 1.16.0 Windows 源码构建指南

> 适用于在 Windows 上从源码编译并运行 TigerVNC 1.16.0。
>
> 本指南以 `C:\Users\25901\Desktop\tigervnc-1.16.0` 为示例路径，请将其替换为你自己的实际解压目录。

---

## 目录

1. [前置依赖安装](#1-前置依赖安装)
2. [安装 vcpkg 并获取依赖库](#2-安装-vcpkg-并获取依赖库)
3. [生成 Visual Studio 构建文件](#3-生成-visual-studio-构建文件)
4. [编译源码](#4-编译源码)
5. [运行 TigerVNC](#5-运行-tigervnc)
6. [常见问题](#6-常见问题)

---

## 1. 前置依赖安装

在开始之前，请确保已安装以下工具：

### 1.1 CMake（必须 ≥ 3.17）

1. 访问 <https://cmake.org/download/>，下载 Windows 安装包（`.msi`）。
2. 安装时勾选 **"Add CMake to the system PATH for all users"**。
3. 安装完成后打开命令提示符验证：
   ```cmd
   cmake --version
   ```
   预期输出类似 `cmake version 3.28.x`。

### 1.2 Visual Studio 2022（含 C++ 桌面开发工作负载）

1. 访问 <https://visualstudio.microsoft.com/downloads/>，下载 **Visual Studio 2022 Community**（免费）。
2. 安装时在"工作负载"页面勾选：
   - ✅ **使用 C++ 的桌面开发**
3. 点击安装，等待完成（约 6–10 GB）。

> 如果只需要命令行编译工具，也可以仅安装 **Visual Studio Build Tools 2022**，选中 **"C++ build tools"** 工作负载即可。

### 1.3 Git（可选，用于 vcpkg）

1. 访问 <https://git-scm.com/download/win>，下载并安装。
2. 安装时选择 **"Git from the command line and also from 3rd-party software"**。

---

## 2. 安装 vcpkg 并获取依赖库

TigerVNC 依赖 libjpeg-turbo、zlib、openssl 等第三方库，推荐使用 [vcpkg](https://github.com/microsoft/vcpkg) 统一管理。

### 2.1 安装 vcpkg

打开 **开发者命令提示符（Developer Command Prompt for VS 2022）**，执行以下命令：

```cmd
cd C:\
git clone https://github.com/microsoft/vcpkg.git
cd vcpkg
bootstrap-vcpkg.bat
vcpkg integrate install
```

### 2.2 安装 TigerVNC 所需依赖

```cmd
vcpkg install libjpeg-turbo:x64-windows
vcpkg install zlib:x64-windows
vcpkg install openssl:x64-windows
vcpkg install pixman:x64-windows
vcpkg install gettext:x64-windows
vcpkg install gnutls:x64-windows
```

> 首次安装时间较长（约 10–30 分钟，视网络状况而定）。

---

## 3. 生成 Visual Studio 构建文件

打开 **开发者命令提示符（Developer Command Prompt for VS 2022）**，执行以下命令：

```cmd
cd C:\Users\25901\Desktop\tigervnc-1.16.0

mkdir build
cd build

cmake .. ^
  -G "Visual Studio 17 2022" ^
  -A x64 ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DCMAKE_TOOLCHAIN_FILE=C:/vcpkg/scripts/buildsystems/vcpkg.cmake ^
  -DVCPKG_TARGET_TRIPLET=x64-windows
```

**参数说明：**

| 参数 | 说明 |
|------|------|
| `-G "Visual Studio 17 2022"` | 使用 VS 2022 生成器；如果安装的是 VS 2019，改为 `"Visual Studio 16 2019"` |
| `-A x64` | 生成 64 位项目 |
| `-DCMAKE_BUILD_TYPE=Release` | 生成发布版本 |
| `-DCMAKE_TOOLCHAIN_FILE=...` | 告知 CMake 使用 vcpkg 工具链 |

CMake 运行完成后，`build/` 目录中会生成 `tigervnc.sln` 解决方案文件。

---

## 4. 编译源码

### 方法一：命令行编译（推荐）

在 `build/` 目录下执行：

```cmd
cmake --build . --config Release --parallel
```

- `--config Release`：编译发布版本（也可改为 `Debug`）
- `--parallel`：并行编译，加快速度

编译成功后，可执行文件位于：

```
C:\Users\25901\Desktop\tigervnc-1.16.0\build\Release\
```

### 方法二：Visual Studio IDE 编译

1. 打开 `C:\Users\25901\Desktop\tigervnc-1.16.0\build\tigervnc.sln`。
2. 在菜单栏选择配置：**Release** / **x64**。
3. 点击菜单 **生成 → 生成解决方案**（快捷键 `Ctrl+Shift+B`）。

---

## 5. 运行 TigerVNC

编译完成后，进入输出目录：

```cmd
cd C:\Users\25901\Desktop\tigervnc-1.16.0\build\Release
```

### 5.1 启动 VNC 查看器（客户端）

```cmd
vncviewer.exe
```

或者直接指定要连接的服务器地址和端口：

```cmd
vncviewer.exe 192.168.1.100:5900
```

### 5.2 启动 VNC 服务器（WinVNC）

```cmd
winvnc4.exe -run
```

或者以服务方式安装并启动：

```cmd
winvnc4.exe -install
net start winvnc4
```

> **注意：** WinVNC 在 Windows 上运行需要管理员权限。右键命令提示符，选择"以管理员身份运行"。

### 5.3 快捷方式

也可以双击以下文件直接运行（无需命令行）：

- **VNC 查看器：** `build\Release\vncviewer.exe`
- **VNC 服务器：** `build\Release\winvnc4.exe`

---

## 6. 常见问题

### Q1：CMake 找不到依赖库（"Could not find package XXX"）

**解决方案：**
- 确认 vcpkg 已正确安装对应的库（见[第2步](#2-安装-vcpkg-并获取依赖库)）。
- 确认 `-DCMAKE_TOOLCHAIN_FILE` 路径指向正确的 vcpkg 安装目录。
- 如果 vcpkg 安装在其他位置，修改路径：
  ```cmd
  -DCMAKE_TOOLCHAIN_FILE=D:/tools/vcpkg/scripts/buildsystems/vcpkg.cmake
  ```

### Q2：编译报错 "error C2220"（警告被视为错误）

**解决方案：** 在 CMake 配置时添加以下参数关闭警告-即-错误：

```cmd
cmake .. -DCMAKE_CXX_FLAGS="/W3 /WX-" ...
```

### Q3：提示找不到 `JAVA_HOME` 或 Java 相关错误

TigerVNC 的 Java 支持是可选的，可在 CMake 配置时禁用：

```cmd
cmake .. -DBUILD_JAVA=OFF ...
```

### Q4：运行 `vncviewer.exe` 时提示缺少 DLL

**解决方案：** 将 vcpkg 安装的运行时库复制到 `Release/` 目录：

```cmd
cd C:\vcpkg
vcpkg export --triplet=x64-windows --raw --output=C:\tigervnc-runtime libjpeg-turbo zlib openssl
```

然后将导出目录中 `bin/` 内的所有 `.dll` 文件复制到：

```
C:\Users\25901\Desktop\tigervnc-1.16.0\build\Release\
```

### Q5：需要生成 32 位版本

将 `-A x64` 改为 `-A Win32`，并将 vcpkg triplet 改为 `x86-windows`：

```cmd
cmake .. -G "Visual Studio 17 2022" -A Win32 ^
  -DCMAKE_TOOLCHAIN_FILE=C:/vcpkg/scripts/buildsystems/vcpkg.cmake ^
  -DVCPKG_TARGET_TRIPLET=x86-windows
```

---

## 快速参考命令

```cmd
:: 进入源码目录
cd C:\Users\25901\Desktop\tigervnc-1.16.0

:: 创建并进入构建目录
mkdir build && cd build

:: 配置（使用 VS 2022，x64，Release）
cmake .. -G "Visual Studio 17 2022" -A x64 -DCMAKE_BUILD_TYPE=Release -DCMAKE_TOOLCHAIN_FILE=C:/vcpkg/scripts/buildsystems/vcpkg.cmake -DVCPKG_TARGET_TRIPLET=x64-windows

:: 编译
cmake --build . --config Release --parallel

:: 运行 VNC 查看器
.\Release\vncviewer.exe

:: 运行 VNC 服务器（需管理员权限）
.\Release\winvnc4.exe -run
```

---

*参考：[TigerVNC 官方 GitHub](https://github.com/TigerVNC/tigervnc) · [TigerVNC 官网](https://tigervnc.org)*
