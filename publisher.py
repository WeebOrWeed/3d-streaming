import asyncio
import cv2
import numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaPlayer, MediaRecorder
import av
import fractions
import time
import argparse
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SideBySideVideoTrack(VideoStreamTrack):
    """
    A video track that reads a side-by-side video file and streams it
    """
    def __init__(self, video_path):
        super().__init__()
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")
        
        # Get video properties
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        logger.info(f"Video loaded: {self.width}x{self.height} @ {self.fps}fps, {self.frame_count} frames")
        
        # Calculate timing
        self.frame_duration = 1.0 / self.fps
        self.start_time = None
        self.frame_index = 0
        
        # Set track properties
        self.kind = "video"

    async def recv(self):
        if self.start_time is None:
            self.start_time = time.time()
        
        # Calculate current time
        current_time = time.time() - self.start_time
        target_frame = int(current_time * self.fps)
        
        # Loop video if needed
        if target_frame >= self.frame_count:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.start_time = time.time()
            target_frame = 0
        
        # Set frame position
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        
        # Read frame
        ret, frame = self.cap.read()
        if not ret:
            # If reading fails, restart video
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
        
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Create PyAV frame
        av_frame = av.VideoFrame.from_ndarray(frame_rgb, format="rgb24")
        av_frame.pts = int(target_frame * self.frame_duration * 90000)  # 90kHz clock
        av_frame.time_base = fractions.Fraction(1, 90000)
        
        return av_frame

    def __del__(self):
        if hasattr(self, 'cap'):
            self.cap.release()

class WebRTCPublisher:
    def __init__(self, video_path, host="0.0.0.0", port=3030):
        self.video_path = video_path
        self.host = host
        self.port = port
        self.pc = None
        self.video_track = None
        self._connection_lock = asyncio.Lock()
        
    async def _reset_connection(self):
        """Reset the WebRTC connection completely"""
        if self.pc is not None:
            try:
                await self.pc.close()
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
            finally:
                self.pc = None
        
        if self.video_track is not None:
            self.video_track = None
        
        # Small delay to ensure cleanup
        await asyncio.sleep(0.1)
        
    async def _create_new_connection(self):
        """Create a fresh WebRTC connection"""
        await self._reset_connection()
        
        logger.info("Creating new WebRTC connection...")
        self.pc = RTCPeerConnection()
        
        # Add connection state change handler
        pc = self.pc
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"Connection state: {pc.connectionState}")
            if pc.connectionState == "failed":
                logger.error("Connection failed")
            elif pc.connectionState == "closed":
                logger.info("Connection closed")
        
        @pc.on("signalingstatechange")
        async def on_signalingstatechange():
            logger.info(f"Signaling state: {pc.signalingState}")
        
        logger.info("Creating new video track...")
        self.video_track = SideBySideVideoTrack(self.video_path)
        
        # Create a transceiver with explicit direction
        transceiver = self.pc.addTransceiver(self.video_track, direction="sendonly")
        
        logger.info("WebRTC connection created successfully")
        return self.pc
    
    async def create_offer(self):
        """Create WebRTC offer"""
        self.pc = await self._create_new_connection()
        
        # Create offer
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        
        return offer
    
    async def handle_answer(self, answer_sdp):
        """Handle answer from receiver"""
        if self.pc is None:
            logger.error("Peer connection not initialized")
            return
            
        answer = RTCSessionDescription(sdp=answer_sdp, type="answer")
        await self.pc.setRemoteDescription(answer)
        logger.info("WebRTC connection established")
    
    async def run(self):
        """Run the publisher"""
        from aiohttp import web
        import json
        
        async def offer_handler(request):
            """Handle offer requests"""
            async with self._connection_lock:
                try:
                    logger.info("Received offer request")
                    params = await request.json()
                    logger.info(f"Received params: {list(params.keys())}")
                    
                    # Validate SDP data
                    if "sdp" not in params or "type" not in params:
                        raise ValueError("Missing required SDP parameters")
                    
                    sdp_data = params["sdp"]
                    sdp_type = params["type"]
                    # logger.info(f"SDP type: {sdp_type}")
                    # logger.info(f"SDP length: {len(sdp_data) if sdp_data else 0}")
                    # logger.info(f"SDP preview: {sdp_data[:200] if sdp_data else 'None'}...")
                    
                    offer = RTCSessionDescription(
                        sdp=sdp_data,
                        type=sdp_type
                    )
                    
                    logger.info("Creating new peer connection...")
                    # Create new peer connection
                    self.pc = await self._create_new_connection()
                    
                    # Use local variable to ensure type safety
                    pc = self.pc
                    if pc is None:
                        raise RuntimeError("Failed to initialize peer connection")
                    
                    logger.info(f"Setting remote description... (signaling state: {pc.signalingState})")
                    logger.info(f"Remote offer SDP: {offer.sdp[:200]}...")
                    await pc.setRemoteDescription(offer)
                    logger.info(f"Remote description set (signaling state: {pc.signalingState})")
                    
                    logger.info("Creating answer...")
                    answer = await pc.createAnswer()
                    logger.info(f"Answer created, SDP: {answer.sdp[:200]}...")
                    logger.info("Setting local description...")
                    await pc.setLocalDescription(answer)
                    logger.info(f"Local description set (signaling state: {pc.signalingState})")
                    
                    return web.Response(
                        content_type="application/json",
                        text=json.dumps({
                            "sdp": pc.localDescription.sdp,
                            "type": pc.localDescription.type
                        })
                    )
                except Exception as e:
                    logger.error(f"Offer handler error: {e}")
                    logger.error(f"Error type: {type(e)}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    return web.Response(status=500, text=str(e))
        
        async def answer_handler(request):
            """Handle answer from receiver"""
            try:
                params = await request.json()
                if self.pc is not None:
                    await self.handle_answer(params["sdp"])
                return web.Response(text="OK")
            except Exception as e:
                logger.error(f"Answer handler error: {e}")
                return web.Response(status=500, text=str(e))
        
        # Create web server
        app = web.Application()
        app.router.add_post("/offer", offer_handler)
        app.router.add_post("/answer", answer_handler)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        
        logger.info(f"Publisher running on http://{self.host}:{self.port}")
        await site.start()
        
        # Keep running
        while True:
            await asyncio.sleep(1)

async def main():
    parser = argparse.ArgumentParser(description="3D Video Publisher")
    parser.add_argument("video_path", help="Path to side-by-side video file")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=3030, help="Port to bind to")
    
    args = parser.parse_args()
    
    publisher = WebRTCPublisher(args.video_path, args.host, args.port)
    await publisher.run()

if __name__ == "__main__":
    asyncio.run(main()) 