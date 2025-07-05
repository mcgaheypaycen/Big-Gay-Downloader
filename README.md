# Big Gay Downloader 🏳️‍🌈

## 🚨 Recent Updates (2024-06)

- **Full UI Redesign**: The entire interface was redesigned for a modern, classy, and cozy look, with improved spacing, color palette, and usability.
- **CustomTkinter Migration**: The app now uses [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) for a high-tech, modern widget set and better dark mode support.
- **Added Xtube video support*: The app is now able to accept Xvideo links as well as YouTube.
- **No More Mode Toggle**: Users can now paste either YouTube or XVideos links directly—no need to switch modes. The app auto-detects the platform and processes accordingly.
- **Automatic Platform Detection**: The backend now detects whether a link is YouTube or XVideos and validates/handles it appropriately.
- **Improved .gitignore**: The repository now excludes build artifacts, binaries, and cache files for a clean, professional codebase.
- **README & Documentation**: This README and project documentation have been updated to reflect all new features and best practices.

---

A modern, feature-rich YouTube downloader and media converter with a GUI built in Python and Tkinter.

## ✨ Features

### 🎥 YouTube Downloading
- **Multiple Formats**: Download videos in MP4 (video) or MP3 (audio) formats
- **High Quality**: Supports various quality options and compatibility modes
- **Queue Management**: Add multiple videos to download queue with progress tracking
- **Smart Naming**: Automatic filename sanitization and organization
- **Background Processing**: Downloads run in background threads

### 🔄 Media Conversion
- **Format Conversion**: Convert between MP4 and MP3 formats
- **Batch Processing**: Queue multiple files for conversion
- **Quality Control**: Optimized settings for maximum compatibility
- **Progress Tracking**: Real-time conversion progress

### 🎨 Modern UI
- **Dark Theme**: Dark interface with accent colors
- **Responsive Layout**: Fixed sidebar with dual queue system
- **Context Menus**: Right-click options for queue management
- **Real-time Updates**: Live progress bars and status updates

### 🔧 Smart Features
- **Auto yt-dlp Management**: Automatic installation and updates
- **FFmpeg Integration**: Built-in media conversion capabilities
- **File Validation**: Prevents invalid conversions (e.g., MP3 to MP4)
- **Error Handling**: Graceful error recovery and user feedback

## 📋 Requirements

### System Requirements
- **OS**: Windows 10/11 (64-bit)
- **Python**: 3.8 or higher
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 1GB free space for application + download space

### Dependencies
```
yt-dlp>=2023.12.30    # YouTube downloading
psutil>=5.9.0         # System resource monitoring
customtkinter>=5.2.0  # Modern Tkinter widgets
```

### Build Dependencies (for developers)
```
pyinstaller>=5.13.0   # Executable packaging
black>=23.0.0         # Code formatting
ruff>=0.1.0          # Linting
pytest>=7.0.0        # Testing
```

## 🚀 Installation

### Option 1: Download Executable (Recommended)
1. Go to [Releases](https://github.com/mcgaheypaycen/Big_Gay_YT_Ripper/releases)
2. Download the latest `Big Gay Downloader.exe`
3. Run the executable - no installation required!

### Option 2: Run from Source
1. **Clone the repository**:
   ```bash
   git clone https://github.com/mcgaheypaycen/Big_Gay_YT_Ripper.git
   cd Big_Gay_YT_Ripper
   ```
2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Download FFmpeg**:
   - Download from [FFmpeg Official Site](https://ffmpeg.org/download.html)
   - Extract `ffmpeg.exe` to `assets/ffmpeg/` folder
   - Or use the provided download script (see below)
4. **Run the application**:
   ```bash
   python main.py
   ```

## 📁 Project Structure

```
big-gay-yt-ripper/
├── main.py                 # Main application entry point
├── core/                   # Core functionality modules
│   ├── downloader.py       # YouTube downloading logic
│   ├── converter.py        # Media conversion engine
│   ├── queue.py           # Download queue management
│   ├── conversion_queue.py # Conversion queue management
│   ├── utils.py           # Utility functions
│   ├── yt_dlp_installer.py # yt-dlp installation/updates
│   ├── first_launch.py    # First launch setup
│   └── version_manager.py # Version management
├── ui/                     # User interface components
│   ├── sidebar.py         # Main sidebar with controls
│   ├── queue_view.py      # Download queue display
│   ├── conversion_queue_view.py # Conversion queue display
│   └── update_dialog.py   # Update dialogs
├── assets/                 # Application assets
│   ├── icon.ico           # Application icon
│   └── ffmpeg/            # FFmpeg binary (user-provided)
├── requirements.txt        # Python dependencies
├── requirements_build.txt  # Build dependencies
├── test_basic.py          # Basic functionality tests
├── test_installer.py      # Installer tests
└── README.md              # This file
```

## 🎯 Usage Guide

### First Launch
1. **Launch the application**
2. **yt-dlp Installation**: The app will prompt to install yt-dlp if not found
3. **FFmpeg Setup**: Ensure `ffmpeg.exe` is in `assets/ffmpeg/` folder
4. **Configure Output Folder**: Set your preferred download location

### Downloading YouTube or XVideos
1. **Enter URL**: Paste a YouTube or XVideos URL in the sidebar
2. **Select Format**: Choose MP4 (video) or MP3 (audio)
3. **Start Downloads**: Click "Start Downloads" to begin
4. **Monitor Progress**: Watch real-time progress in the queue

### Converting Media Files
1. **Select File**: Use "Browse Files" to select media files
2. **Choose Format**: Select target format (MP4 or MP3)
3. **Start Conversions**: Click "Start Conversions" to begin
4. **Track Progress**: Monitor conversion progress

### Queue Management
- **Right-click Options**: Remove, rename, or cancel jobs
- **Clear Options**: Clear all jobs or only completed ones
- **Pause/Resume**: Stop and restart queue processing
- **Status Tracking**: Real-time status updates

## 🔧 Configuration

### Output Folder
- Set your preferred download location in the sidebar
- Default: User's Downloads folder
- Automatically saved between sessions

### yt-dlp Updates
- Automatic background update checks
- Manual updates via "Update yt-dlp" button
- Installed to: `%USERPROFILE%\.big_gay_downloader\yt-dlp\`

### FFmpeg Integration
- Required for media conversion
- Place `ffmpeg.exe` in `assets/ffmpeg/` folder
- Supports all FFmpeg-compatible formats

## 🛠️ Development

### Setting Up Development Environment
1. **Clone and setup**:
   ```bash
   git clone https://github.com/mcgaheypaycen/Big_Gay_YT_Ripper.git
   cd Big_Gay_YT_Ripper
   python -m venv venv
   venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   pip install -r requirements_build.txt
   ```
2. **Download FFmpeg**:
   ```bash
   # Create assets/ffmpeg directory
   mkdir -p assets/ffmpeg
   # Download ffmpeg.exe to assets/ffmpeg/
   ```
3. **Run tests**:
   ```bash
   pytest test_basic.py
   pytest test_installer.py
   ```

### Building Executable
```bash
pyinstaller --onefile --noconsole --icon=assets/icon.ico main.py
```

### Code Style
- **Formatting**: Black code formatter
- **Linting**: Ruff linter
- **Testing**: pytest framework

## 🐛 Troubleshooting

### Common Issues

**"yt-dlp not found"**
- The app will automatically install yt-dlp on first launch
- Manual installation: Download from [yt-dlp releases](https://github.com/yt-dlp/yt-dlp/releases)

**"FFmpeg not found"**
- Download FFmpeg from [official site](https://ffmpeg.org/download.html)
- Place `ffmpeg.exe` in `assets/ffmpeg/` folder

**"Conversion failed"**
- Ensure input file exists and is valid
- Check FFmpeg installation
- Verify sufficient disk space

**"Download failed"**
- Check internet connection
- Verify YouTube or XVideos URL is valid
- Try updating yt-dlp via sidebar button

### Debug Mode
Enable debug logging by running:
```bash
python main.py --debug
```

## 🔒 Security

This application:
- **No data collection**: Doesn't send any data to external servers
- **Local processing**: All operations performed locally
- **Open source**: Full source code available for review
- **Dependency audit**: Regular security updates for dependencies

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/mcgaheypaycen/Big_Gay_YT_Ripper/issues)
- **Discussions**: [GitHub Discussions](https://github.com/mcgaheypaycen/Big_Gay_YT_Ripper/discussions)
- **Wiki**: [Project Wiki](https://github.com/mcgaheypaycen/Big_Gay_YT_Ripper/wiki)

## 🙏 Acknowledgments

- **yt-dlp**: YouTube downloading engine
- **FFmpeg**: Media conversion capabilities
- **CustomTkinter**: Modern Tkinter widgets
- **Tkinter**: GUI framework
- **Open source community**: For inspiration and support

---

**Made with ❤️ and 🏳️‍🌈 for the community. If this doesn't work sorry I'm just some gay guy.** 
