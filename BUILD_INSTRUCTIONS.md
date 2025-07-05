# Build Instructions for Big Gay Downloader

This document explains how to build the Big Gay Downloader into a single executable file with the following specifications:

- ✅ **Single file executable** (no external dependencies)
- ✅ **No console window** (clean GUI-only interface)
- ✅ **FFmpeg bundled** (included in the exe)
- ✅ **yt-dlp installed on first launch** (not bundled, installed to user's app data)

## Prerequisites

1. **Python 3.8+** installed on your system
2. **All project dependencies** installed:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements_build.txt
   ```

## Required Files Structure

Ensure your project has this structure before building:

```
Big Gay YT Ripper/
├── main.py                          # Main application entry point
├── BigGayDownloader.spec            # PyInstaller specification file
├── build_exe.py                     # Build script (optional)
├── assets/
│   ├── icon.ico                     # Application icon
│   └── ffmpeg/
│       └── ffmpeg.exe               # FFmpeg executable (83MB)
├── core/                            # Core application modules
├── ui/                              # UI modules
└── requirements*.txt                # Dependencies
```

## Build Methods

### Method 1: Using the Build Script (Recommended)

1. **Run the build script:**
   ```bash
   python build_exe.py
   ```

2. **The script will:**
   - Clean previous build artifacts
   - Verify all required files exist
   - Install PyInstaller if needed
   - Build the executable
   - Verify the build was successful

3. **Output:** `dist/Big Gay Downloader.exe`

### Method 2: Manual PyInstaller Build

1. **Clean previous builds:**
   ```bash
   rmdir /s build dist
   ```

2. **Run PyInstaller:**
   ```bash
   pyinstaller BigGayDownloader.spec --clean --noconfirm
   ```

3. **Output:** `dist/Big Gay Downloader.exe`

## What Gets Bundled

### ✅ Included in the Executable:
- **FFmpeg** (`assets/ffmpeg/ffmpeg.exe`) - 83MB bundled
- **Application icon** (`assets/icon.ico`)
- **All Python modules** (`core/`, `ui/`)
- **All dependencies** (tkinter, requests, psutil, etc.)

### ❌ NOT Included (Installed on First Launch):
- **yt-dlp** - Will be downloaded and installed to `%USERPROFILE%\.big_gay_downloader\yt-dlp\`

## How It Works

### First Launch Behavior:
1. User runs the executable
2. Application checks if yt-dlp is installed in app data directory
3. If not found, shows installation dialog
4. Downloads and installs yt-dlp to `%USERPROFILE%\.big_gay_downloader\yt-dlp\`
5. Creates a flag file to mark first launch as complete
6. Application starts normally

### FFmpeg Usage:
- FFmpeg is bundled and extracted to a temporary location when needed
- The `resource_path()` function handles finding the bundled ffmpeg
- No external FFmpeg installation required

## Troubleshooting

### Common Issues:

1. **"Missing required files" error:**
   - Ensure `assets/ffmpeg/ffmpeg.exe` exists (83MB file)
   - Check that all directories (`core/`, `ui/`) are present

2. **Build fails with import errors:**
   - Run `pip install -r requirements.txt` to install all dependencies
   - Ensure you're using Python 3.8+

3. **Executable is too small (< 10MB):**
   - FFmpeg might not be bundled correctly
   - Check that `assets/ffmpeg/ffmpeg.exe` is the correct 83MB file

4. **yt-dlp not found on first run:**
   - This is expected! The app will install yt-dlp automatically
   - Check `%USERPROFILE%\.big_gay_downloader\` for installation logs

### File Size Expectations:
- **Expected size:** ~85-90MB (includes 83MB FFmpeg)
- **If smaller:** FFmpeg may not be bundled correctly
- **If larger:** Normal, includes all dependencies

## Distribution

### Single File Distribution:
- The executable is completely self-contained
- No additional files needed
- Users just need to run the .exe file

### Installation Location:
- **yt-dlp:** `%USERPROFILE%\.big_gay_downloader\yt-dlp\`
- **Configuration:** `%USERPROFILE%\.big_gay_downloader\`
- **Downloads:** User-selected folder (default: Downloads)

## Verification

After building, test the executable:

1. **Run the exe** on a clean machine (no Python installed)
2. **Check first launch behavior** - should install yt-dlp
3. **Test a download** - should work with bundled FFmpeg
4. **Verify no console window** appears

## Advanced Configuration

### Modifying the Spec File:
- **Add more files:** Add to `datas` list
- **Exclude modules:** Add to `excludes` list
- **Change icon:** Modify `icon='assets/icon.ico'`
- **Enable console:** Change `console=False` to `console=True`

### Custom Build Options:
```bash
# Debug build (with console)
pyinstaller BigGayDownloader.spec --debug

# Build without UPX compression
pyinstaller BigGayDownloader.spec --noupx

# Build with specific Python version
pyinstaller BigGayDownloader.spec --python-version 3.9
``` 