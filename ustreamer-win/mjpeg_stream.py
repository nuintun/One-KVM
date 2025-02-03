import asyncio
import threading
import time
import json
from collections import deque
from typing import List, Optional, Tuple, Union, Dict, Any

import aiohttp
import cv2
import logging
import numpy as np
from aiohttp import MultipartWriter, web
from aiohttp.web_runner import GracefulExit

class MjpegStream:
    """MJPEG video stream class for handling video frames and providing HTTP streaming service"""
    
    def __init__(
        self,
        name: str,
        size: Optional[Tuple[int, int]] = None,
        quality: int = 50,
        fps: int = 30,
        host: str = "localhost",
        port: int = 8000,
        device_name: str = "Unknown Camera",
        log_requests: bool = True
    ) -> None:
        """
        Initialize MJPEG stream
        
        Args:
            name: Stream name
            size: Video size (width, height)
            quality: JPEG compression quality (1-100)
            fps: Target frame rate
            host: Server host address
            port: Server port
            device_name: Camera device name
            log_requests: Whether to log stream requests
        """
        self.name = name.lower().replace(" ", "_")
        self.size = size
        self.quality = max(1, min(quality, 100))
        self.fps = fps
        self._host = host
        self._port = port
        self._device_name = device_name
        self.log_requests = log_requests
        
        # Video frame and synchronization
        self._frame = np.zeros((320, 240, 1), dtype=np.uint8)
        self._lock = asyncio.Lock()
        self._byte_frame_window = deque(maxlen=30)
        self._bandwidth_last_modified_time = time.time()
        self._is_online = True
        self._last_frame_time = time.time()
        

        # 设置日志级别为ERROR，以隐藏HTTP请求日志
        if not self.log_requests:
            logging.getLogger('aiohttp.access').setLevel(logging.ERROR)

        # Server setup
        self._app = web.Application()
        self._app.router.add_route("GET", f"/{self.name}", self._stream_handler)
        self._app.router.add_route("GET", "/state", self._state_handler)
        self._app.router.add_route("GET", "/", self._index_handler)
        self._app.is_running = False

    def set_frame(self, frame: np.ndarray) -> None:
        """Set the current video frame"""
        self._frame = frame
        self._last_frame_time = time.time()
        self._is_online = True

    def get_bandwidth(self) -> float:
        """Get current bandwidth usage (bytes/second)"""
        if time.time() - self._bandwidth_last_modified_time >= 1:
            self._byte_frame_window.clear()
        return sum(self._byte_frame_window)

    async def _process_frame(self) -> Tuple[np.ndarray, Dict[str, str]]:
        """Process video frame (resize and JPEG encode)"""
        frame = cv2.resize(
            self._frame, self.size or (self._frame.shape[1], self._frame.shape[0])
        )
        success, encoded = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality]
        )
        if not success:
            raise ValueError("Error encoding frame")
            
        self._byte_frame_window.append(len(encoded.tobytes()))
        self._bandwidth_last_modified_time = time.time()

        # Add KVMD-compatible header information
        headers = {
            "X-UStreamer-Online": str(self._is_online).lower(),
            "X-UStreamer-Width": str(frame.shape[1]),
            "X-UStreamer-Height": str(frame.shape[0]),
            "X-UStreamer-Name": self._device_name,
            "X-Timestamp": str(int(time.time() * 1000)),
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "Expires": "0",
        }
        
        return encoded, headers

    async def _stream_handler(self, request: web.Request) -> web.StreamResponse:
        """Handle MJPEG stream requests"""
        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={"Content-Type": "multipart/x-mixed-replace;boundary=frame"}
        )
        await response.prepare(request)

        if self.log_requests:
            print(f"Stream request received: {request.path}")
            

        while True:
            await asyncio.sleep(1 / self.fps)
            
            # Check if the device is online
            if time.time() - self._last_frame_time > 5:
                self._is_online = False
            
            async with self._lock:
                frame, headers = await self._process_frame()
                
            with MultipartWriter("image/jpeg", boundary="frame") as mpwriter:
                part = mpwriter.append(frame.tobytes(), {"Content-Type": "image/jpeg"})
                for key, value in headers.items():
                    part.headers[key] = value
                try:
                    await mpwriter.write(response, close_boundary=False)
                except (ConnectionResetError, ConnectionAbortedError):
                    return web.Response(status=499)
            await response.write(b"\r\n")

    async def _state_handler(self, request: web.Request) -> web.Response:
        """Handle /state requests and return device status information"""
        state = {
            "result": {
                "instance_id": "",
                "encoder": {
                    "type": "CPU",
                    "quality": self.quality
                },
                "h264": {
                    "bitrate": 4875,
                    "gop": 60,
                    "online": self._is_online,
                    "fps": self.fps
                },
                "sinks": {
                    "jpeg": {
                        "has_clients": False
                    },
                    "h264": {
                        "has_clients": False
                    }
                },
                "source": {
                    "resolution": {
                        "width": self.size[0] if self.size else self._frame.shape[1],
                        "height": self.size[1] if self.size else self._frame.shape[0]
                    },
                    "online": self._is_online,
                    "desired_fps": self.fps,
                    "captured_fps": 0  # You can update this with actual captured fps if needed
                },
                "stream": {
                    "queued_fps": 2,  # Placeholder value, update as needed
                    "clients": 1,  # Placeholder value, update as needed
                    "clients_stat": {
                        "70bf63a507f71e47": {
                            "fps": 2,  # Placeholder value, update as needed
                            "extra_headers": False,
                            "advance_headers": True,
                            "dual_final_frames": False,
                            "zero_data": False,
                            "key": "tIR9TtuedKIzDYZa"  # Placeholder key, update as needed
                        }
                    }
                }
            }
        }
        return web.Response(
            text=json.dumps(state),
            content_type="application/json"
        )

    async def _index_handler(self, _: web.Request) -> web.Response:
        """Handle root path requests and display available streams"""
        html = f"""
        <h2>Available Video Streams:</h2>
        <ul>
            <li><a href='http://{self._host}:{self._port}/{self.name}'>/{self.name}</a></li>
            <li><a href='http://{self._host}:{self._port}/state'>/state</a></li>
        </ul>
        """
        return web.Response(text=html, content_type="text/html")

    def start(self) -> None:
        """Start the stream server"""
        if not self._app.is_running:
            threading.Thread(target=self._run_server, daemon=True).start()
            self._app.is_running = True
            print(f"\nVideo stream URL: http://{self._host}:{self._port}/{self.name}")
        else:
            print("\nServer is already running\n")

    def stop(self) -> None:
        """Stop the stream server"""
        if self._app.is_running:
            self._app.is_running = False
            print("\nStopping server...\n")
            raise GracefulExit()
        print("\nServer is not running\n")

    def _run_server(self) -> None:
        """Run the server in a new thread"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        runner = web.AppRunner(self._app)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, self._host, self._port)
        loop.run_until_complete(site.start())
        loop.run_forever() 