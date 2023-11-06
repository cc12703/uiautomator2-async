



import asyncio
from typing import Any

from . import utils
from .exception import RpcTimeout, UiObjectNotFoundError
from .client import AsyncClient


class Selector(dict):
    """The class is to build parameters for UiSelector passed to Android device.
    """
    __fields = {
        "text": (0x01, None),  # MASK_TEXT,
        "textContains": (0x02, None),  # MASK_TEXTCONTAINS,
        "textMatches": (0x04, None),  # MASK_TEXTMATCHES,
        "textStartsWith": (0x08, None),  # MASK_TEXTSTARTSWITH,
        "className": (0x10, None),  # MASK_CLASSNAME
        "classNameMatches": (0x20, None),  # MASK_CLASSNAMEMATCHES
        "description": (0x40, None),  # MASK_DESCRIPTION
        "descriptionContains": (0x80, None),  # MASK_DESCRIPTIONCONTAINS
        "descriptionMatches": (0x0100, None),  # MASK_DESCRIPTIONMATCHES
        "descriptionStartsWith": (0x0200, None),  # MASK_DESCRIPTIONSTARTSWITH
        "checkable": (0x0400, False),  # MASK_CHECKABLE
        "checked": (0x0800, False),  # MASK_CHECKED
        "clickable": (0x1000, False),  # MASK_CLICKABLE
        "longClickable": (0x2000, False),  # MASK_LONGCLICKABLE,
        "scrollable": (0x4000, False),  # MASK_SCROLLABLE,
        "enabled": (0x8000, False),  # MASK_ENABLED,
        "focusable": (0x010000, False),  # MASK_FOCUSABLE,
        "focused": (0x020000, False),  # MASK_FOCUSED,
        "selected": (0x040000, False),  # MASK_SELECTED,
        "packageName": (0x080000, None),  # MASK_PACKAGENAME,
        "packageNameMatches": (0x100000, None),  # MASK_PACKAGENAMEMATCHES,
        "resourceId": (0x200000, None),  # MASK_RESOURCEID,
        "resourceIdMatches": (0x400000, None),  # MASK_RESOURCEIDMATCHES,
        "index": (0x800000, 0),  # MASK_INDEX,
        "instance": (0x01000000, 0)  # MASK_INSTANCE,
    }
    __mask, __childOrSibling, __childOrSiblingSelector = "mask", "childOrSibling", "childOrSiblingSelector"

    def __init__(self, **kwargs):
        super(Selector, self).__setitem__(self.__mask, 0)
        super(Selector, self).__setitem__(self.__childOrSibling, [])
        super(Selector, self).__setitem__(self.__childOrSiblingSelector, [])
        for k in kwargs:
            self[k] = kwargs[k]

    def __str__(self):
        """ remove useless part for easily debugger """
        selector = self.copy()
        selector.pop('mask')
        for key in ('childOrSibling', 'childOrSiblingSelector'):
            if not selector.get(key):
                selector.pop(key)
        args = []
        for (k, v) in selector.items():
            args.append(k + '=' + repr(v))
        return 'Selector [' + ', '.join(args) + ']'

    def __setitem__(self, k, v):
        if k in self.__fields:
            super(Selector, self).__setitem__(k, v)
            super(Selector,
                  self).__setitem__(self.__mask,
                                    self[self.__mask] | self.__fields[k][0])
        else:
            raise ReferenceError("%s is not allowed." % k)

    def __delitem__(self, k):
        if k in self.__fields:
            super(Selector, self).__delitem__(k)
            super(Selector,
                  self).__setitem__(self.__mask,
                                    self[self.__mask] & ~self.__fields[k][0])

    def clone(self):
        kwargs = dict((k, self[k]) for k in self if k not in [
            self.__mask, self.__childOrSibling, self.__childOrSiblingSelector
        ])
        selector = Selector(**kwargs)
        for v in self[self.__childOrSibling]:
            selector[self.__childOrSibling].append(v)
        for s in self[self.__childOrSiblingSelector]:
            selector[self.__childOrSiblingSelector].append(s.clone())
        return selector

    def child(self, **kwargs):
        self[self.__childOrSibling].append("child")
        self[self.__childOrSiblingSelector].append(Selector(**kwargs))
        return self

    def sibling(self, **kwargs):
        self[self.__childOrSibling].append("sibling")
        self[self.__childOrSiblingSelector].append(Selector(**kwargs))
        return self

    def update_instance(self, i):
        # update inside child instance
        if self[self.__childOrSiblingSelector]:
            self[self.__childOrSiblingSelector][-1]['instance'] = i
        else:
            self['instance'] = i



class UiObject(object):

    def __init__(self, client: AsyncClient, sel: Selector) :
        self.client = client
        self.sel = sel
        


    async def exists(self) -> Any :
        return self.client.jsonrpc.exist(self.sel)
    
    @property
    async def info(self) -> Any :
        return self.client.jsonrpc.objInfo(self.sel)
    


    async def wait(self, exists: bool = True, timeout: int = None) -> bool :
        if timeout is None:
            timeout = self.client.config['wait_timeout']
        waitTime = timeout + 10

        if exists:
            try :
                return await self.client.jsonrpc.waitForExists(self.sel, int(timeout * 1000), http_timeout=waitTime)
            except RpcTimeout :
                return await self.exists()
        else :
            try :
                return await self.client.jsonrpc.waitUntilGone(self.sel, int(timeout * 1000), http_timeout=waitTime)
            except RpcTimeout :
                return not await self.exists()


    async def mustWait(self, exists: bool = True, timeout: int = None) :
        if not await self.wait(exists, timeout):
            raise UiObjectNotFoundError({'code': -32002, 'data': str(self.sel), 'method': 'wait'})
        

    async def waitGone(self, timeout: int = UiObjectNotFoundError) -> bool :
        timeout = timeout or self.client.config['wait_timeout']
        return await self.wait(exists=False, timeout=timeout)
    

    async def getText(self, timeout: int = None):
        await self.mustWait(timeout=timeout)
        return await self.client.jsonrpc.getText(self.sel)
    

    async def setText(self, text, timeout=None):
        await self.mustWait(timeout=timeout)
        if not text:
            return self.client.jsonrpc.clearTextField(self.sel)
        else:
            return self.client.jsonrpc.setText(self.sel, text)

    async def clearText(self, timeout=None):
        await self.mustWait(timeout=timeout)
        return self.client.jsonrpc.clearTextField(self.sel)
    


    async def clickGone(self, maxretry=10, interval=1.0):
        """
        Click until element is gone

        Args:
            maxretry (int): max click times
            interval (float): sleep time between clicks

        Return:
            Bool if element is gone
        """
        await self.clickExists()
        while maxretry > 0:
            await asyncio.sleep(interval)
            if not await self.exists():
                return True

            await self.clickExists()
            maxretry -= 1
        return False


    async def clickExists(self, timeout=0):
        try:
            await self.click(timeout=timeout)
            return True
        except UiObjectNotFoundError:
            return False
        

    async def longClick(self, duration: float = 0.5, timeout=None, offset=None) :
        await self.mustWait(timeout=timeout)
        x, y = self.center(offset=offset)
        return self.client.longClick(x, y, duration=duration)


    async def click(self, timeout=None, offset=None):
        await self.mustWait(timeout=timeout)
        x, y = self.center(offset=offset)
        return self.client.click(x, y)
    

    async def swipe(self, direction, steps=10):
        """
        Performs the swipe action on the UiObject.
        Swipe from center

        Args:
            direction (str): one of ("left", "right", "up", "down")
            steps (int): move steps, one step is about 5ms
            percent: float between [0, 1]

        Note: percent require API >= 18
        # assert 0 <= percent <= 1
        """
        assert direction in ("left", "right", "up", "down")

        await self.mustWait()
        info = await self.info
        bounds = info.get('visibleBounds') or info.get("bounds")
        lx, ly, rx, ry = bounds['left'], bounds['top'], bounds['right'], bounds['bottom']  # yapf: disable
        cx, cy = (lx + rx) // 2, (ly + ry) // 2
        if direction == 'up':
            return self.client.swipe(cx, cy, cx, ly, steps=steps)
        elif direction == 'down':
            return self.client.swipe(cx, cy, cx, ry - 1, steps=steps)
        elif direction == 'left':
            return self.client.swipe(cx, cy, lx, cy, steps=steps)
        elif direction == 'right':
            return self.client.swipe(cx, cy, rx - 1, cy, steps=steps)


    async def bounds(self):
        """
        Returns:
            left_top_x, left_top_y, right_bottom_x, right_bottom_y
        """
        info = await self.info
        bounds = info.get('visibleBounds') or info.get("bounds")
        lx, ly, rx, ry = bounds['left'], bounds['top'], bounds['right'], bounds['bottom']  # yapf: disable
        return (lx, ly, rx, ry)


    async def center(self, offset=(0.5, 0.5)):
        """
        Args:
            offset: optional, (x_off, y_off)
                (0, 0) means left-top, (0.5, 0.5) means middle(Default)
        Return:
            center point (x, y)
        """
        lx, ly, rx, ry = await self.bounds()
        if offset is None:
            offset = (0.5, 0.5)  # default center
        xoff, yoff = offset
        width, height = rx - lx, ry - ly
        x = lx + width * xoff
        y = ly + height * yoff
        return (x, y)


    def child(self, **kwargs):
        return UiObject(self.client, self.sel.clone().child(**kwargs))

    def sibling(self, **kwargs):
        return UiObject(self.client, self.sel.clone().sibling(**kwargs))
    

    async def right(self, **kwargs):
        def onrightof(rect1, rect2):
            left, top, right, bottom = utils.intersect(rect1, rect2)
            return rect2["left"] - rect1["right"] if top < bottom else -1

        return self.__viewBeside(onrightof, **kwargs)

    async def left(self, **kwargs):
        def onleftof(rect1, rect2):
            left, top, right, bottom = utils.intersect(rect1, rect2)
            return rect1["left"] - rect2["right"] if top < bottom else -1

        return self.__viewBeside(onleftof, **kwargs)

    async def up(self, **kwargs):
        def above(rect1, rect2):
            left, top, right, bottom = utils.intersect(rect1, rect2)
            return rect1["top"] - rect2["bottom"] if left < right else -1

        return self.__viewBeside(above, **kwargs)

    async def down(self, **kwargs):
        def under(rect1, rect2):
            left, top, right, bottom = utils.intersect(rect1, rect2)
            return rect2["top"] - rect1["bottom"] if left < right else -1

        return self.__viewBeside(under, **kwargs)


    async def __viewBeside(self, onsideof, **kwargs):
        bounds = self.info["bounds"]
        min_dist, found = -1, None
        for uiObj in UiObject(self.client, Selector(**kwargs)):
            dist = onsideof(bounds, (await uiObj.info)["bounds"])
            if dist >= 0 and (min_dist < 0 or dist < min_dist):
                min_dist, found = dist, uiObj
        return found
    


    @property
    def fling(self):
        """
        Args:
            dimention (str): one of "vert", "vertically", "vertical", "horiz", "horizental", "horizentally"
            action (str): one of "forward", "backward", "toBeginning", "toEnd", "to"
        """
        jsonrpc = self.client.jsonrpc
        selector = self.sel

        class _Fling(object):
            def __init__(self):
                self.vertical = True
                self.action = 'forward'

            def __getattr__(self, key):
                if key in ["horiz", "horizental", "horizentally"]:
                    self.vertical = False
                    return self
                if key in ['vert', 'vertically', 'vertical']:
                    self.vertical = True
                    return self
                if key in [
                        "forward", "backward", "toBeginning", "toEnd", "to"
                ]:
                    self.action = key
                    return self
                raise ValueError("invalid prop %s" % key)

            async def __call__(self, max_swipes=500, **kwargs):
                if self.action == "forward":
                    return jsonrpc.flingForward(selector, self.vertical)
                elif self.action == "backward":
                    return jsonrpc.flingBackward(selector, self.vertical)
                elif self.action == "toBeginning":
                    return jsonrpc.flingToBeginning(selector, self.vertical,
                                                    max_swipes)
                elif self.action == "toEnd":
                    return jsonrpc.flingToEnd(selector, self.vertical,
                                              max_swipes)

        return _Fling()
    

    @property
    async def count(self):
        return await self.client.jsonrpc.count(self.sel)

    async def __len__(self):
        return await self.count

    def __iter__(self):
        obj, length = self, self.count

        class Iter(object):
            def __init__(self):
                self.index = -1

            def next(self):
                self.index += 1
                if self.index < length:
                    return obj[self.index]
                else:
                    raise StopIteration()

            __next__ = next

        return Iter()
