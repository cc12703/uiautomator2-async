
import logging
import asyncio
from collections import OrderedDict
import time
from typing import Callable


from .utils import inject_call
from .client import AsyncClient
from .xpath import XPath


logger = logging.getLogger(__name__)



class AsyncWatchContext:


    def __init__(self, client: AsyncClient,
                 builtin: bool = False, interval: float = 2.0):
        self._client = client
        self.__interval = interval
        self._callbacks = OrderedDict()
        self.__xpath_list = []
        self._xpath = XPath(client)

        self.__isRunning = False

        if builtin:
            self.when("继续使用").click()
            self.when("移入管控").when("取消").click()
            self.when("^立即(下载|更新)").when("取消").click()
            self.when("同意").click()
            self.when("^(好的|确定)").click()
            self.when("继续安装").click()
            self.when("安装").click()
            self.when("Agree").click()
            self.when("ALLOW").click()


    def when(self, xpath: str):
        """ 当条件满足时,支持 .when(..).when(..) 的级联模式"""
        self.__xpath_list.append(xpath)
        return self


    def click(self):
        self.call(lambda el : el.click())


    def call(self, fn: Callable):
        """
        Args:
            fn: support args (d: Device, el: Element)
                see _run_callback function for more details
        """
        xpath_list = tuple(self.__xpath_list)
        self.__xpath_list = []
        assert xpath_list, "when should be called before"

        self._callbacks[xpath_list] = fn


    async def start(self):
        if self.__isRunning:
            return
        
        self.__isRunning = True
        try:
            while not self.__isRunning:
                await self._run()
                await asyncio.sleep(self.__interval)
        finally:
            pass


    def stop(self):
        self.__isRunning = False


    async def __aenter__(self):
        return self

    async def __aexit__(self, type, value, traceback):
        logger.info("context closed")
        self.stop()

    
    async def _run(self) -> bool:
        logger.debug("watch check")
        source = await self._client.dumpHierarchy()
        for xpaths, func in self._callbacks.items():
            ok = True
            last_match = None
            for xpath in xpaths:
                sel = self._xpath(xpath, source=source)
                if not sel.exists:
                    ok = False
                    break
                last_match = sel.getLastMatch()
                logger.debug("match: %s", xpath)
            if ok:
                # 全部匹配
                logger.debug("watchContext xpath matched: %s", xpaths)
                self._run_callback(func, last_match)
                return True
        return False
    

    def _run_callback(self, func, element):
        inject_call(func, d=self._d, el=element)
        self.__trigger_time = time.time()
