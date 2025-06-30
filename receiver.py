import tkinter as tk
from tkinter import ttk, messagebox
import asyncio
import threading
import cv2
import numpy as np
from PIL import Image, ImageTk
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaPlayer, MediaRecorder
import av
import fractions
import time
import json
import logging
import websockets
import ssl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoReceiver:
    def __init__(self, root):
        self.root = root
        self.root.title("3D Video Receiver")
        self.root.geometry("1200x800")
        
        # WebRTC variables
        self.pc = None
        self.video_track = None
        self.remote_video = None
        
        # Video display variables
        self.current_frame = None
        self.is_playing = False
        
        # Setup UI
        self.setup_ui()
        
        # Start async event loop in separate thread
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.run_async_loop, daemon=True)
        self.thread.start()
    
    def setup_ui(self):
        """Setup the user interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Connection frame
        conn_frame = ttk.LabelFrame(main_frame, text="Connection", padding="5")
        conn_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        
        # Publisher URL
        ttk.Label(conn_frame, text="Publisher URL:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.url_var = tk.StringVar(value="ws://localhost:3030")
        self.url_entry = ttk.Entry(conn_frame, textvariable=self.url_var, width=40)
        self.url_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        
        # Connect button
        self.connect_btn = ttk.Button(conn_frame, text="Connect", command=self.connect_to_publisher)
        self.connect_btn.grid(row=0, column=2, padx=(0, 10))
        
        # Disconnect button
        self.disconnect_btn = ttk.Button(conn_frame, text="Disconnect", command=self.disconnect, state=tk.DISABLED)
        self.disconnect_btn.grid(row=0, column=3)
        
        # Status label
        self.status_var = tk.StringVar(value="Disconnected")
        self.status_label = ttk.Label(conn_frame, textvariable=self.status_var, foreground="red")
        self.status_label.grid(row=1, column=0, columnspan=4, sticky=tk.W, pady=(5, 0))
        
        # Video display frame
        video_frame = ttk.LabelFrame(main_frame, text="3D Video Display", padding="5")
        video_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        video_frame.columnconfigure(0, weight=1)
        video_frame.rowconfigure(0, weight=1)
        
        # Video canvas
        self.video_canvas = tk.Canvas(video_frame, bg="black", width=800, height=600)
        self.video_canvas.grid(row=0, column=0, sticky="nsew")
        
        # Controls frame
        controls_frame = ttk.Frame(main_frame)
        controls_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        
        # 3D mode selection
        ttk.Label(controls_frame, text="3D Mode:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.mode_var = tk.StringVar(value="side_by_side_cross_eye")
        mode_combo = ttk.Combobox(controls_frame, textvariable=self.mode_var, 
                                 values=["side_by_side_cross_eye", "side_by_side_parallel", "anaglyph_red_cyan", "anaglyph_green_magenta"],
                                 state="readonly", width=20)
        mode_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        # Offset slider
        ttk.Label(controls_frame, text="Offset:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.offset_var = tk.IntVar(value=20)
        self.offset_slider = ttk.Scale(controls_frame, from_=10, to=100, variable=self.offset_var, 
                                      orient=tk.HORIZONTAL, length=150, command=self.on_offset_change)
        self.offset_slider.grid(row=0, column=3, sticky=tk.W, padx=(0, 10))
        
        # Offset value label
        self.offset_label = ttk.Label(controls_frame, text="20")
        self.offset_label.grid(row=0, column=4, sticky=tk.W, padx=(0, 20))
        
        # Fullscreen button
        self.fullscreen_btn = ttk.Button(controls_frame, text="Toggle Fullscreen", command=self.toggle_fullscreen)
        self.fullscreen_btn.grid(row=0, column=5, padx=(0, 10))
        
        # Info label
        self.info_var = tk.StringVar(value="Ready to connect")
        self.info_label = ttk.Label(controls_frame, textvariable=self.info_var)
        self.info_label.grid(row=0, column=6, sticky=tk.W)
        
        # Bind window events
        self.root.bind('<Escape>', lambda e: self.exit_fullscreen())
        self.root.bind('<F11>', lambda e: self.toggle_fullscreen())
    
    def run_async_loop(self):
        """Run async event loop in separate thread"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    def connect_to_publisher(self):
        """Connect to the publisher"""
        url = self.url_var.get()
        if not url:
            messagebox.showerror("Error", "Please enter a publisher URL")
            return
        
        # Run connection in async loop
        asyncio.run_coroutine_threadsafe(self._connect_async(url), self.loop)
    
    async def _connect_async(self, url):
        """Async connection to publisher"""
        try:
            self.status_var.set("Connecting...")
            self.connect_btn.config(state=tk.DISABLED)
            
            # Create WebRTC peer connection
            self.pc = RTCPeerConnection()
            
            # Add transceiver to receive video
            self.pc.addTransceiver("video", direction="recvonly")
            
            # Handle incoming video track
            @self.pc.on("track")
            async def on_track(track):
                logger.info(f"Received {track.kind} track")
                if track.kind == "video":
                    self.video_track = track
                    await self.handle_video_track(track)
            
            # Create offer
            offer = await self.pc.createOffer()
            await self.pc.setLocalDescription(offer)
            
            # Send offer to publisher via WebSocket
            uri = url.replace("ws://", "http://").replace("wss://", "https://")
            offer_url = f"{uri}/offer"
            
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(offer_url, json={
                    "sdp": self.pc.localDescription.sdp,
                    "type": self.pc.localDescription.type
                }) as response:
                    if response.status == 200:
                        answer_data = await response.json()
                        answer = RTCSessionDescription(
                            sdp=answer_data["sdp"],
                            type=answer_data["type"]
                        )
                        await self.pc.setRemoteDescription(answer)
                        
                        # Update UI
                        self.root.after(0, self._update_connection_status, True)
                    else:
                        raise Exception(f"Failed to connect: {response.status}")
                        
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.root.after(0, self._update_connection_status, False, str(e))
    
    def _update_connection_status(self, connected, error_msg=None):
        """Update connection status in UI thread"""
        if connected:
            self.status_var.set("Connected")
            self.status_label.config(foreground="green")
            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
            self.info_var.set("Receiving video stream...")
        else:
            self.status_var.set(f"Connection failed: {error_msg}")
            self.status_label.config(foreground="red")
            self.connect_btn.config(state=tk.NORMAL)
            self.disconnect_btn.config(state=tk.DISABLED)
            self.info_var.set("Connection failed")
    
    async def handle_video_track(self, track):
        """Handle incoming video track"""
        self.is_playing = True
        
        while self.is_playing:
            try:
                frame = await track.recv()
                
                # Convert frame to numpy array
                img = frame.to_ndarray(format="rgb24")
                
                # Process frame for 3D display
                processed_img = self.process_3d_frame(img)
                
                # Update display in UI thread
                self.root.after(0, self._update_video_display, processed_img)
                
            except Exception as e:
                logger.error(f"Error processing video frame: {e}")
                break
        
        self.is_playing = False
    
    def process_3d_frame(self, frame):
        """Process frame for 3D display based on selected mode"""
        height, width = frame.shape[:2]
        half_width = width // 2
        
        mode = self.mode_var.get()
        
        if mode == "side_by_side_cross_eye":
            # Create side-by-side cross-eye 3D with offset
            height, width = frame.shape[:2]
            
            # Create output frame with same dimensions
            side_by_side = np.zeros_like(frame)
            
            # Apply offset - trim from different sides for each eye
            offset = self.offset_var.get()
            
            # Left half: right eye view (trimmed from left side)
            left_half = frame[:, offset:, :]  # Trim from left
            # Calculate new height to maintain aspect ratio
            new_height = int((width//2) * height / (width - offset))
            # Resize to fit left half while maintaining aspect ratio
            left_half_resized = cv2.resize(left_half, (width//2, new_height))
            # Center the resized video in the left half
            y_offset = (height - new_height) // 2
            side_by_side[y_offset:y_offset+new_height, :width//2] = left_half_resized
            
            # Right half: left eye view (trimmed from right side)
            right_half = frame[:, :-offset, :]  # Trim from right
            # Calculate new height to maintain aspect ratio
            new_height = int((width//2) * height / (width - offset))
            # Resize to fit right half while maintaining aspect ratio
            right_half_resized = cv2.resize(right_half, (width//2, new_height))
            # Center the resized video in the right half
            y_offset = (height - new_height) // 2
            side_by_side[y_offset:y_offset+new_height, width//2:] = right_half_resized
            
            return side_by_side
        
        elif mode == "side_by_side_parallel":
            # Create side-by-side parallel 3D with offset
            height, width = frame.shape[:2]
            
            # Create output frame with same dimensions
            side_by_side = np.zeros_like(frame)
            
            # Apply offset - trim from different sides for each eye
            offset = self.offset_var.get()
            
            # Left half: left eye view (trimmed from right side)
            left_half = frame[:, :-offset, :]  # Trim from right
            # Calculate new height to maintain aspect ratio
            new_height = int((width//2) * height / (width - offset))
            # Resize to fit left half while maintaining aspect ratio
            left_half_resized = cv2.resize(left_half, (width//2, new_height))
            # Center the resized video in the left half
            y_offset = (height - new_height) // 2
            side_by_side[y_offset:y_offset+new_height, :width//2] = left_half_resized
            
            # Right half: right eye view (trimmed from left side)
            right_half = frame[:, offset:, :]  # Trim from left
            # Calculate new height to maintain aspect ratio
            new_height = int((width//2) * height / (width - offset))
            # Resize to fit right half while maintaining aspect ratio
            right_half_resized = cv2.resize(right_half, (width//2, new_height))
            # Center the resized video in the right half
            y_offset = (height - new_height) // 2
            side_by_side[y_offset:y_offset+new_height, width//2:] = right_half_resized
            
            return side_by_side
        
        elif mode == "anaglyph_red_cyan":
            # Create red-cyan anaglyph with proper offset
            # Use the full frame and create offset between left and right eye views
            height, width = frame.shape[:2]
            
            # Create anaglyph with the same dimensions as original
            anaglyph = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Convert to grayscale
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            
            # Apply offset - shift the right eye view slightly to the right
            offset = self.offset_var.get()
            
            # Red channel (left eye) - use original position
            anaglyph[:, :, 0] = gray_frame
            
            # Green and Blue channels (right eye) - apply offset
            # Shift the right eye view to create depth
            right_shifted = np.zeros_like(gray_frame)
            right_shifted[:, offset:] = gray_frame[:, :-offset] if offset > 0 else gray_frame
            anaglyph[:, :, 1] = right_shifted  # Green channel
            anaglyph[:, :, 2] = right_shifted  # Blue channel
            
            return anaglyph
        
        elif mode == "anaglyph_green_magenta":
            # Create green-magenta anaglyph with proper offset
            height, width = frame.shape[:2]
            
            # Create anaglyph with the same dimensions as original
            anaglyph = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Convert to grayscale
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            
            # Apply offset - shift the right eye view slightly to the right
            offset = self.offset_var.get()
            
            # Green channel (left eye) - use original position
            anaglyph[:, :, 1] = gray_frame
            
            # Red and Blue channels (right eye) - apply offset
            right_shifted = np.zeros_like(gray_frame)
            right_shifted[:, offset:] = gray_frame[:, :-offset] if offset > 0 else gray_frame
            anaglyph[:, :, 0] = right_shifted  # Red channel
            anaglyph[:, :, 2] = right_shifted  # Blue channel
            
            return anaglyph
        
        return frame
    
    def _update_video_display(self, frame):
        """Update video display in UI thread"""
        try:
            # Convert numpy array to PIL Image
            height, width = frame.shape[:2]
            
            # Resize frame to fit canvas
            canvas_width = self.video_canvas.winfo_width()
            canvas_height = self.video_canvas.winfo_height()
            
            if canvas_width > 1 and canvas_height > 1:
                # Calculate aspect ratio
                frame_aspect = width / height
                canvas_aspect = canvas_width / canvas_height
                
                if frame_aspect > canvas_aspect:
                    # Frame is wider, fit to width
                    new_width = canvas_width
                    new_height = int(canvas_width / frame_aspect)
                else:
                    # Frame is taller, fit to height
                    new_height = canvas_height
                    new_width = int(canvas_height * frame_aspect)
                
                # Resize frame
                frame_resized = cv2.resize(frame, (new_width, new_height))
                
                # Convert to PIL Image
                pil_image = Image.fromarray(frame_resized)
                self.current_frame = ImageTk.PhotoImage(pil_image)
                
                # Update canvas
                self.video_canvas.delete("all")
                x = (canvas_width - new_width) // 2
                y = (canvas_height - new_height) // 2
                self.video_canvas.create_image(x, y, anchor=tk.NW, image=self.current_frame)
                
        except Exception as e:
            logger.error(f"Error updating video display: {e}")
    
    def disconnect(self):
        """Disconnect from publisher"""
        self.is_playing = False
        
        if self.pc:
            asyncio.run_coroutine_threadsafe(self.pc.close(), self.loop)
            self.pc = None
        
        self.status_var.set("Disconnected")
        self.status_label.config(foreground="red")
        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.info_var.set("Ready to connect")
        
        # Clear video display
        self.video_canvas.delete("all")
        self.current_frame = None
    
    def on_offset_change(self, value):
        """Handle offset slider change"""
        offset_value = int(float(value))
        self.offset_label.config(text=str(offset_value))
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        self.root.attributes('-fullscreen', not self.root.attributes('-fullscreen'))
    
    def exit_fullscreen(self):
        """Exit fullscreen mode"""
        self.root.attributes('-fullscreen', False)
    
    def on_closing(self):
        """Handle window closing"""
        self.disconnect()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.root.destroy()

def main():
    root = tk.Tk()
    app = VideoReceiver(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main() 