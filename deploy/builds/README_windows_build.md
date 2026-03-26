# Windows Setup Guide — Zertan Client Build

This document explains how to set up a Windows environment to successfully build the Zertan client (Tauri + Rust + Node + Python).

---

## 1. Python Setup

Use Python **3.12** (avoid newer versions like 3.14 due to compatibility issues).

Create and activate virtual environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

```cmd
.venv\Scripts\Activate.bat
```

Install dependencies:

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r app/requirements.txt
```

---

## 2. Node.js Setup

Install Node.js (LTS recommended):

```powershell
winget install -e --id OpenJS.NodeJS.LTS
```

Ensure it's available:

```powershell
node -v
npm -v
```

If not detected in VS Code, restart it or manually add:

```powershell
$env:Path += ";C:\Program Files\nodejs"
```

---

## 3. Rust Setup

Install Rust via rustup:

```powershell
winget install -e --id Rustlang.Rustup
```

### Important: Use Compatible Toolchain

Latest Rust (1.94) breaks older dependencies.
Set a compatible version:

```powershell
rustup toolchain install 1.88.0
rustup override set 1.88.0
```

Verify:

```powershell
rustc -V
cargo -V
```

---

## 4. Visual Studio Build Tools

Install required C++ toolchain:

```powershell
winget install -e --id Microsoft.VisualStudio.2022.BuildTools
```

Then open **Visual Studio Installer** and ensure:

* ✅ Desktop development with C++
* ✅ Windows SDK

---

## 5. Use Correct Terminal

Use one of the following:

* **x64 Native Tools Command Prompt for VS 2022** (recommended)
* Or ensure environment variables are loaded properly

Check tools:

```powershell
where cl
where link
```

---

## 6. Windows Security (Critical Step)

Disable Smart App Control:

```
Windows Security → App & Browser Control → Smart App Control → OFF
```

> ⚠️ This is required because Rust build scripts generate executables that Windows may block.

---

## 7. Build Rust Project (Test Step)

Navigate to Tauri project:

```powershell
cd deploy\src\client\src-tauri
cargo build
```

Expected result:

```
Finished dev profile
```

---

## 8. Full Build

From project root:

```powershell
cd C:\Users\xxx\Desktop\codes\Zertan
.\.venv\Scripts\Activate.ps1
python deploy\builds\build.py --version x.y.z
```

If you are using `Developer Command Prompt for VS 2022`:

```cmd
cd C:\Users\xxx\Desktop\codes\Zertan
.venv\Scripts\Activate.bat
python deploy\builds\build.py --version x.y.z
```

---

## Notes

* Do **not** modify `Cargo.toml` or `Cargo.lock` for compatibility fixes unless strictly necessary.
* The issue was resolved by:

  * Fixing Windows environment
  * Using Rust 1.88.0
  * Disabling Smart App Control
* Linux and macOS builds remain unaffected.

---

## Summary

Required stack:

* Python 3.12
* Node.js (LTS)
* Rust 1.88.0 (override)
* Visual Studio Build Tools (C++)
* Smart App Control disabled

---

You're now ready to build Zertan on Windows.
