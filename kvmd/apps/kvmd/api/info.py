# ========================================================================== #
#                                                                            #
#    KVMD - The main PiKVM daemon.                                           #
#                                                                            #
#    Copyright (C) 2018-2024  Maxim Devaev <mdevaev@gmail.com>               #
#                                                                            #
#    This program is free software: you can redistribute it and/or modify    #
#    it under the terms of the GNU General Public License as published by    #
#    the Free Software Foundation, either version 3 of the License, or       #
#    (at your option) any later version.                                     #
#                                                                            #
#    This program is distributed in the hope that it will be useful,         #
#    but WITHOUT ANY WARRANTY; without even the implied warranty of          #
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the           #
#    GNU General Public License for more details.                            #
#                                                                            #
#    You should have received a copy of the GNU General Public License       #
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.  #
#                                                                            #
# ========================================================================== #


import os
from aiohttp import ClientConnectionError, ClientSession
from aiohttp import UnixConnector
from aiohttp.web import Request
from aiohttp.web import Response
from aiohttp.web import HTTPForbidden
from aiohttp.web import HTTPNotFound
from aiohttp.web import FileResponse
from aiohttp.web import HTTPInternalServerError

from aiohttp.web import StreamResponse
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from ....htserver import exposed_http
from ....htserver import make_json_response

from ....validators.kvm import valid_info_fields

from ..info import InfoManager


# =====
class InfoApi:
    def __init__(self, info_manager: InfoManager) -> None:
        self.__info_manager = info_manager
        self.static_dir = 'kvmd_data/usr/share/kvmd/web'
        self.target_stream_server = 'http://127.0.0.1:8081'

    # =====


    @exposed_http("GET", "/api/info")
    async def __common_state_handler(self, req: Request) -> Response:
        fields = self.__valid_info_fields(req)
        return make_json_response(await self.__info_manager.get_state(fields))

    def __valid_info_fields(self, req: Request) -> list[str]:
        available = self.__info_manager.get_subs()
        return sorted(valid_info_fields(
            arg=req.query.get("fields", ",".join(available)),
            variants=available,
        ) or available)
    
    @exposed_http("GET", "/streamer/stream")
    async def proxy_stream_handler(self, request):
        socket_path = '/home/mofeng/One-KVM/kvmd_data/run/kvmd/ustreamer.sock'
        query_string = urlencode(request.query)
        headers = request.headers.copy()
        try:
            async with ClientSession(connector=UnixConnector(path=socket_path)) as session:
                backend_url = f'http://localhost/stream?{query_string}' if query_string else 'http://localhost/stream'
                async with session.get(backend_url, headers=headers) as resp:
                    response = StreamResponse(status=resp.status, reason=resp.reason, headers=resp.headers)
                    await response.prepare(request)
                    while True:
                        chunk = await resp.content.read(512000)
                        if not chunk:
                            break
                        await response.write(chunk)
                    return response
        except ClientConnectionError:
            return Response(status=500, text="Client connection was closed")


    @exposed_http("GET", "/{path:.*}", auth_required=False)
    async def __html_file_handler(self, req: Request) -> Response:
        path = req.match_info['path']
        full_path = os.path.normpath(os.path.join(self.static_dir, path))
        print("---------------")
        print(full_path)

        # 安全检查：确保请求的文件在允许的基础目录内
        if not full_path.startswith(self.static_dir):
            raise HTTPForbidden(text="Access denied.")

        if os.path.isdir(full_path):
            index_path = os.path.join(full_path, 'index.html')
            if os.path.isfile(index_path):
                full_path = index_path
            else:
                raise HTTPNotFound(text="Directory does not contain an index.html file.")
        
        # 检查调整后的路径是否为现有文件
        if not (os.path.exists(full_path) and os.path.isfile(full_path)):
            raise HTTPNotFound(text="File not found.")

        try:
            return FileResponse(full_path)
        except IOError as e:
            raise HTTPInternalServerError(text=str(e))
        