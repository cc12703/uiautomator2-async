

import sys
import os
import fire


sys.path.insert(0, os.getcwd())



import uiautomator2Async as u2s





async def dev_info() :
    d = await u2s.connectWifi("localhost")
    info = await d.deviceInfo()
    print(info)


async def info() :
    d = await u2s.connectWifi("localhost")
    info = await d.info
    print(info)


async def widgetInfo() :
    d = await u2s.connectWifi("localhost")
    tObj = d(text="我的设备")

    print(await tObj.info)
    print(await tObj.getText())


if __name__ == '__main__':
    fire.Fire()
