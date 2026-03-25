# Desktop Build Scripts

This directory contains the build scripts and configurations for creating desktop executables for the Zertan project across multiple platforms (Linux, macOS, and Windows).

**Important:** Before building, ensure you install the dependencies listed in [`deploy/src/requirements.txt`](../../src/requirements.txt). These Python packages are required to run the build process.

---

# Linux Build Requirements

This project requires the following dependencies to generate the client build on Linux.

## System Packages (Debian/Ubuntu)

Install with:

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  pkg-config \
  libglib2.0-dev \
  libgtk-3-dev \
  libwebkit2gtk-4.1-dev \
  libxdo-dev \
  libssl-dev \
  libayatana-appindicator3-dev \
  librsvg2-dev \
  libsoup-3.0-dev \
  python3-gi \
  python3-gi-cairo \
  gir1.2-gtk-3.0 \
  gir1.2-webkit2-4.1 \
  libgtk-3-0 \
  libwebkit2gtk-4.1-0 \
  nodejs \
  npm
```

## Rust Toolchain

Install with rustup:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"
rustup update
```

## Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Python Packages

```bash
python -m pip install -r deploy/src/requirements.txt
```

## Build

```bash
python deploy/builds/build.py --version 1.0.0
```

## Verification

```bash
node -v
npm -v
cargo --version
rustc --version
pkg-config --version
python --version
```
