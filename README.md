# 3D Video Streaming System

A complete 3D video streaming solution using Python, WebRTC, and Tkinter. This system allows you to stream side-by-side 3D video content and view it in various 3D formats.

## Features

- **Publisher**: Streams side-by-side 3D video files via WebRTC
- **Receiver**: Tkinter-based application with multiple 3D viewing modes
- **Web Interface**: Browser-based testing interface for the publisher
- **Multiple 3D Formats**: Side-by-side, red-cyan anaglyph, green-magenta anaglyph
- **Real-time Streaming**: Low-latency WebRTC streaming
- **Cross-platform**: Works on Windows, macOS, and Linux

## 3D Viewing Modes

1. **Side-by-Side Cross-Eye**: Cross your eyes to view in 3D (no glasses needed)
2. **Side-by-Side Parallel**: Focus beyond the screen to view in 3D (no glasses needed)
3. **Red-Cyan Anaglyph**: Use red-cyan 3D glasses
4. **Green-Magenta Anaglyph**: Use green-magenta 3D glasses

### Offset Control
- **Adjustable offset slider**: Control the 3D depth effect (10-100 pixels)
- **Real-time adjustment**: Change offset while viewing for optimal 3D effect
- **Affects all modes**: Offset applies to both side-by-side and anaglyph modes

## Installation

### Prerequisites

- pip (Python package installer)

### Setup

1. **Clone or download the project files**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Step 1: Start the Publisher

1. **Using a video file**:
   ```bash
   python publisher.py path/to/your/3d_video.mp4
   ```

2. **Using the sample video**:
   ```bash
   python publisher.py sample_3d_video.mp4
   ```

3. **Custom host/port**:
   ```bash
   python publisher.py sample_3d_video.mp4 --host 0.0.0.0 --port 3030
   ```

The publisher will start a web server and display:
```
Publisher running on http://0.0.0.0:3030
```

### Step 2: Start the Receiver

1. **Launch the Tkinter receiver**:
   ```bash
   python receiver.py
   ```

2. **Connect to the publisher**:
   - Enter the publisher URL: `http://localhost:3030`
   - Click "Connect"
   - Select your preferred 3D viewing mode
   - Adjust the offset slider for optimal 3D effect
   - Use F11 or the "Toggle Fullscreen" button for immersive viewing

## Video Format Requirements

The system expects **side-by-side 3D video** where:
- Left half of the frame = left eye view
- Right half of the frame = right eye view
- Total resolution should be even (e.g., 1920x1080, 1280x720)

### Creating Your Own 3D Video

1. **Using the sample generator**:
   ```bash
   python create_sample_video.py my_video.mp4 --duration 30 --fps 30
   ```

2. **Using video editing software**:
   - Export your 3D content in side-by-side format
   - Ensure left and right views are properly aligned
   - Use common formats: MP4, AVI, MOV

## 3D Viewing Instructions

### Side-by-Side Cross-Eye Mode (No Glasses)
1. Look at the center of the screen
2. Cross your eyes until you see three images
3. Focus on the middle image - this is your 3D view
4. It may take practice to achieve the effect

### Side-by-Side Parallel Mode (No Glasses)
1. Look at the center of the screen
2. Focus beyond the screen (as if looking through it)
3. The two images should merge into a single 3D image
4. This technique requires focusing beyond the screen

### Anaglyph Mode (With 3D Glasses)
1. Wear appropriate 3D glasses:
   - Red-cyan glasses for "Red-Cyan Anaglyph" mode
   - Green-magenta glasses for "Green-Magenta Anaglyph" mode
2. The image will appear in 3D automatically

### Adjusting 3D Depth
- Use the offset slider to control the depth effect
- Higher offset values create more pronounced 3D effect
- Lower offset values create subtle depth
- Experiment to find the optimal setting for your content