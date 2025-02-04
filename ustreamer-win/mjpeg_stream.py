import asyncio
import threading
import time
import json
from collections import deque
from typing import List, Optional, Tuple, Dict
import uuid

import cv2
import logging
import numpy as np
from aiohttp import MultipartWriter, web
from aiohttp.web_runner import GracefulExit

class MjpegStream:

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

        self.name = name.lower().replace(" ", "_")
        self.size = size
        self.quality = max(1, min(quality, 100))
        self.fps = fps
        self._host = host
        self._port = port
        self._device_name = device_name
        self.log_requests = log_requests
        
        self._frame = np.zeros((320, 240, 1), dtype=np.uint8)
        self._lock = asyncio.Lock()
        self._is_online = True
        self._last_repeat_frame_time = time.time()
        self._last_fps_update_time = time.time()
        self._last_frame_data = None
        self.per_second_fps = 0
        self.frame_counter = 0
        
        if not self.log_requests:
            logging.getLogger('aiohttp.access').setLevel(logging.ERROR)

        self._app = web.Application()
        self._app.router.add_route("GET", f"/{self.name}", self._stream_handler)
        self._app.router.add_route("GET", "/state", self._state_handler)
        self._app.router.add_route("GET", "/", self._index_handler)
        self._app.router.add_route("GET", "/snapshot", self._snapshot_handler)
        self._app.is_running = False
        self._clients: Dict[str, Dict] = {}
        self._clients_lock = asyncio.Lock()


    def set_frame(self, frame: np.ndarray) -> None:
        self._frame = frame
        self._is_online = True

    async def _process_frame(self) -> Tuple[np.ndarray, Dict[str, str]]:
        frame = cv2.resize(
            self._frame, self.size or (self._frame.shape[1], self._frame.shape[0])
        )
        success, encoded = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality]
        )

        if not success:
            raise ValueError("Error encoding frame")
        
        current_frame_data = encoded.tobytes()
        current_time = time.time()
        
        if current_frame_data == self._last_frame_data and current_time - self._last_repeat_frame_time < 1:
            return None, {}
        else:
            self._last_frame_data = current_frame_data
            self._last_repeat_frame_time = current_time

        if current_time - self._last_fps_update_time >= 1:
            self.per_second_fps = self.frame_counter
            self.frame_counter = 0
            self._last_fps_update_time = current_time

        self.frame_counter += 1
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
        client_id = request.query.get("client_id", uuid.uuid4().hex[:8])
        client_key = request.query.get("key", "0")
        advance_headers = request.query.get("advance_headers", "0") == "1"

        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "multipart/x-mixed-replace;boundary=frame",
                "Set-Cookie": f"stream_client={client_key}/{client_id}; Path=/; Max-Age=30"
                }
        )
        await response.prepare(request)

        async with self._clients_lock:
            if client_id not in self._clients:
                self._clients[client_id] = {
                    "key": client_key,
                    "advance_headers": advance_headers,
                    "extra_headers": False,
                    "zero_data": False,
                    "fps": 0,
                }
            
        try:
            while True: 
                async with self._lock:
                    frame, headers = await self._process_frame()
                    if frame is None:
                        continue

                #Enable workaround for the Chromium/Blink bug https://issues.chromium.org/issues/41199053
                if advance_headers:
                    headers.pop('Content-Length', None)
                    for k in list(headers.keys()):
                        if k.startswith('X-UStreamer-'):
                            del headers[k]
                    
                with MultipartWriter("image/jpeg", boundary="frame") as mpwriter:
                    part = mpwriter.append(frame.tobytes(), {"Content-Type": "image/jpeg"})
                    for key, value in headers.items():
                        part.headers[key] = value
                    try:
                        await mpwriter.write(response, close_boundary=False)
                    except (ConnectionResetError, ConnectionAbortedError):
                        return web.Response(status=499)
                await response.write(b"\r\n")
                self._clients[client_id]["fps"]=self.per_second_fps
        finally:
            async with self._clients_lock:
                if client_id in self._clients:
                    del self._clients[client_id]


    async def _state_handler(self, request: web.Request) -> web.Response:
        state = {
            "ok": "true",
            "result": {
                "instance_id": "",
                "encoder": {
                    "type": "CPU",
                    "quality": self.quality
                },
                "source": {
                    "resolution": {
                        "width": self.size[0] if self.size else self._frame.shape[1],
                        "height": self.size[1] if self.size else self._frame.shape[0]
                    },
                    "online": self._is_online,
                    "desired_fps": self.fps,
                    "captured_fps": self.fps
                },
                "stream": {
                    "queued_fps": self.fps,
                    "clients": len(self._clients),
                    "clients_stat": self._clients
                }
            }
        }
        return web.Response(
            text=json.dumps(state),
            content_type="application/json"
        )

    async def _index_handler(self, _: web.Request) -> web.Response:
        html = f"""
        <html>
        <head><meta charset="utf-8"><title>uStreamer-Win</title><style>body {{font-family: monospace;}}</style></head>
        <body>
        <h3>uStreamer-Win v0.01 </h3>
        <ul><hr>
            <li><a href='http://{self._host}:{self._port}/{self.name}'>/{self.name}</a>
            <br>Get a live stream. </li><hr><br>
            <li><a href='http://{self._host}:{self._port}/snapshot'>/snapshot</a>
            <br>Get a current actual image from the server.</li><hr><br>
            <li><a href='http://{self._host}:{self._port}/state'>/state</a>
            <br>Get JSON structure with the state of the server.</li><hr><br>
        </ul>
        </body>
        </html>
        """
        return web.Response(text=html, content_type="text/html")

    async def _snapshot_handler(self, request: web.Request) -> web.Response:
        async with self._lock:
            frame, _ = await self._process_frame()
        return web.Response(body=frame.tobytes(), content_type="image/jpeg")

    def start(self) -> None:
        if not self._app.is_running:
            threading.Thread(target=self._run_server, daemon=True).start()
            self._app.is_running = True
            print(f"\nVideo stream URL: http://{self._host}:{self._port}/{self.name}")
        else:
            print("\nServer is already running\n")


    def stop(self) -> None:
        if self._app.is_running:
            self._app.is_running = False
            print("\nStopping server...\n")
            raise GracefulExit()
        print("\nServer is not running\n")

    def _run_server(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        runner = web.AppRunner(self._app)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, self._host, self._port)
        loop.run_until_complete(site.start())
        loop.run_forever() 