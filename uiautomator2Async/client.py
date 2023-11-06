

import asyncio
from dataclasses import dataclass
from functools import cached_property
import re
from typing import Any, List, Optional, Tuple, Union
import httpx
from tenacity import RetryError
import xml.dom.minidom


from .cfg import Config
from .rpc import JSONRpcWrapper
from .utils import list2cmdline

@dataclass
class ShellResponse :
    exitCode: int
    output: str


ACTION_DOWN = 0
ACTION_MOVE = 2
ACTION_UP = 1

SCROLL_STEPS = 55



class AsyncClient(object) :


    def __init__(self, agentUrl: str) -> None:
        self._agentUrl = agentUrl
        self.__axClient = httpx.AsyncClient(base_url=self._agentUrl)


    @property
    async def info(self) -> Any :
        return self.jsonrpc.deviceInfo()


    async def deviceInfo(self) -> dict:
        resp = await self.__axClient.get('/info')
        return resp.json()
    

    @cached_property
    def config(self) -> Config:
        return Config()


    @property
    def http(self) -> httpx.AsyncClient:
        return self.__axClient

    @property
    def jsonrpc(self) :
        return JSONRpcWrapper(self.__axClient)
    

    async def shell(self, cmdargs: Union[str, List[str]], timeout=60) -> Any :
        if isinstance(cmdargs, (list, tuple)):
            cmdline = list2cmdline(cmdargs)
        elif isinstance(cmdargs, str):
            cmdline = cmdargs
        else:
            raise TypeError("cmdargs type invalid", type(cmdargs))
        
        data = dict(command=cmdline, timeout=str(timeout))
        resp = await self.__axClient.post('/shell', data=data, timeout=httpx.Timeout(timeout))
        resp.raise_for_status()

        rData = resp.json()
        exitCode = 1 if rData.get('error') else 0
        exitCode = rData.get('exitCode', exitCode)
        return ShellResponse(exitCode=exitCode, output=rData.get('output'))
    


    async def dumpHierarchy(self, compressed=False, pretty=False) -> str:
        content = await self.jsonrpc.dumpWindowHierarchy(compressed, None)
        if content == "":
            raise RetryError("dump hierarchy is empty")

        if pretty and "\n " not in content:
            xml_text = xml.dom.minidom.parseString(content.encode("utf-8"))
            content = xml_text.decode('utf-8').toprettyxml(indent='  ')
        return content



    async def screenshot(self, fileName: Optional[str] = None):
        if fileName is None :
            resp = await self.__axClient.get('/screenshot/0', timeout=httpx.Timeout(10))
            return resp.content
        else :
            async with self.__axClient.stream('GET', '/screenshot/0') as resp:
                fileOut = open(fileName, 'wb')
                async for chunk in resp.aiter_bytes():
                    fileOut.write(chunk)
                fileOut.close()


    #return  (width, height)
    async def windowSize(self):
        info = await self.http.get('/info').json()
        w, h = info['display']['width'], info['display']['height']
        rotation = await self._getOrientation()
        if (w > h) != (rotation % 2 == 1):
            w, h = h, w
        return w, h


    async def _getOrientation(self):
        """
        Rotaion of the phone
        0: normal
        1: home key on the right
        2: home key on the top
        3: home key on the left
        """
        _DISPLAY_RE = re.compile(
            r'.*DisplayViewport{valid=true, .*orientation=(?P<orientation>\d+), .*deviceWidth=(?P<width>\d+), deviceHeight=(?P<height>\d+).*'
        )
        resp = await self.shell("dumpsys display")
        for line in resp.output.splitlines():
            m = _DISPLAY_RE.search(line, 0)
            if not m:
                continue

            return int(m.group('orientation'))
        return await self.info["displayRotation"]
    


    async def click(self, x: Union[float, int], y: Union[float, int]):
        x, y = await self._posRel2Abs(x, y)
        return self.jsonrpc.click(x, y)
    

    async def doubleClick(self, x: Union[float, int], y: Union[float, int], duration=0.1):
        await self.down(x, y)
        await self.up(x, y)
        await asyncio.sleep(duration)
        return self.click(x, y)


    async def longClick(self, x: Union[float, int], y: Union[float, int], duration: float = 0.5):
        await self.down(x, y)
        await asyncio.sleep(duration)
        await self.up(x, y)
    

    async def down(self, x: Union[float, int], y: Union[float, int]) :
        x, y = await self._posRel2Abs(x, y)
        return self.jsonrpc.injectInputEvent(ACTION_DOWN, x, y, 0)
    

    async def move(self, x: Union[float, int], y: Union[float, int]) :
        x, y = await self._posRel2Abs(x, y)
        return self.jsonrpc.injectInputEvent(ACTION_MOVE, x, y, 0)


    async def up(self, x: Union[float, int], y: Union[float, int]) :
        x, y = await self._posRel2Abs(x, y)
        return self.jsonrpc.injectInputEvent(ACTION_UP, x, y, 0)



    async def swipe(self, fx, fy, tx, ty, duration: Optional[float] = None, steps: Optional[int] = None):
        fx, fy = await self._posRel2Abs(fx, fy)
        tx, ty = await self._posRel2Abs(tx, ty)
        if not duration:
            steps = SCROLL_STEPS
        if not steps:
            steps = int(duration * 200)
        steps = max(2, steps)  # step=1 has no swipe effect
        return self.jsonrpc.swipe(fx, fy, tx, ty, steps)
    


    async def _posRel2Abs(self, x: int, y: int) -> Tuple[int, int]:
        size = []
        if (x < 1 or y < 1) and not size:
            size.extend( await self.windowSize())

        if x < 1:
            x = int(size[0] * x)
        if y < 1:
            y = int(size[1] * y)
        return x, y
