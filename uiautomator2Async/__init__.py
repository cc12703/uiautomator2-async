

from functools import cached_property
import re
import httpx
from typing import Any, List, Optional


from .selector import Selector, UiObject
from .client import AsyncClient
from .swipe import SwipeExt
from .xpath import XPath
from .watch import AsyncWatchContext

class AsyncDevice(AsyncClient) :

    def __init__(self, agentUrl: str) :
        super().__init__(agentUrl)



    

    def __call__(self, **kwds: Any) -> UiObject:
        return UiObject(self, Selector(**kwds))
    

    @cached_property
    def xpath(self) -> XPath:
        return XPath(self)


    @cached_property
    def swipeExt(self) -> SwipeExt:
        return SwipeExt(self)
    

    def watchContext(self, autostart: bool = True,
                     builtin: bool = False, interval: float = 2.0) -> AsyncWatchContext:
        wc = AsyncWatchContext(self, builtin=builtin, interval=interval)
        if autostart:
            wc.start()
        return wc
    

    async def appInfo(self, pkgName: str) -> Any :
        resp = await self.http.get(f'/app/{pkgName}/info')
        resp.raise_for_status()

        rData = resp.json()
        if not rData.get('success') :
            raise Exception(rData.get('description', 'unknown'))
        
        return rData.get('data')
    


    async def appStop(self, pkgName: str, userID: str = '0') :
        await self.shell(['am', 'force-stop', '--user', userID, pkgName])


    async def appStart(self, pkgName: str, activity: Optional[str] = None,
                       stop: bool = False, userID: str = '0') :
        if stop :
            await self.appStop(pkgName, userID)

        if not activity:
            info = self.appInfo(pkgName)
            activity = info['mainActivity']
            if activity.find(".") == -1:
                activity = "." + activity

        args = [
            'am', 'start', '-a', 'android.intent.action.MAIN', '-c',
            'android.intent.category.LAUNCHER',
            '-n', f'{pkgName}/{activity}',
            '--user', userID,
        ]
        await self.shell(args)

    
    async def userIDs(self) -> List[str] :
        output, _ = await self.shell(['pm', 'list', 'users'])
        ids = re.findall(r'\tUserInfo{([^:]+):[^:]+:[^:]+} running', output)
        return ids
    
    

    @cached_property
    def swipeExt(self) -> SwipeExt:
        return SwipeExt(self)


async def _fixWifiAddr(addr: str) -> Optional[str] :
    if ':' not in addr :
        addr += ':7912'

    async with httpx.AsyncClient() as client:
        try :
            resp = await client.get(f'http://{addr}/version', timeout=2)
            resp.raise_for_status()
            return "http://" + addr
        except httpx.HTTPStatusError:
            return None




async def connectWifi(addr: str) -> Optional[AsyncDevice] :
    addr = await _fixWifiAddr(addr)
    if addr is None :
        return None
    else :
        return AsyncDevice(addr)
    

