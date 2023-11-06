
import functools
import logging
import re
from lxml import etree





from typing import Union
from .client import AsyncClient


logger = logging.getLogger(__name__)



def _safeXmlstr(s):
    return s.replace("$", "-")


def _str2bytes(v) -> bytes:
    if isinstance(v, bytes):
        return v
    return v.encode('utf-8')


def _stringQuote(s):
    """ quick way to quote string """
    return "{!r}".format(s)


def _strictXPath(xpath: str) -> str:
    """ make xpath to be computer recognized xpath """
    orig_xpath = xpath

    if xpath.startswith('/'):
        pass
    elif xpath.startswith('./'):
        pass
    elif xpath.startswith('@'):
        xpath = '//*[@resource-id={!r}]'.format(xpath[1:])
    elif xpath.startswith('^'):
        xpath = '//*[re:match(@text, {0}) or re:match(@content-desc, {0}) or re:match(@resource-id, {0})]'.format(
            _stringQuote(xpath))
    # elif xpath.startswith("$"):  # special for objects
    #     key = xpath[1:]
    #     return self(self.__alias_get(key), source)
    elif xpath.startswith('%') and xpath.endswith("%"):
        xpath = '//*[contains(@text, {0}) or contains(@content-desc, {0})]'.format(string_quote(xpath[1:-1]))
    elif xpath.startswith('%'):  # ends-with
        text = xpath[1:]
        xpath = '//*[{0} = substring(@text, string-length(@text) - {1} + 1) or {0} = substring(@content-desc, string-length(@text) - {1} + 1)]'.format(
            _stringQuote(text), len(text))
    elif xpath.endswith('%'):  # starts-with
        text = xpath[:-1]
        xpath = "//*[starts-with(@text, {0}) or starts-with(@content-desc, {0})]".format(string_quote(text))
    else:
        xpath = '//*[@text={0} or @content-desc={0} or @resource-id={0}]'.format(
            _stringQuote(xpath))

    logger.debug("xpath %s -> %s", orig_xpath, xpath)
    return xpath


class XPath(object):


    def __init__(self, client: AsyncClient) -> None:
        self.client = client


    
    def __call__(self, xpath: str, source=None):
        return XPathSelector(self, xpath, source)
    




class XPathSelector(object):
    
    def __init__(self, parent: XPath, xpath: Union[list, str], source=None):

        self._parent = parent
        self._client = parent.client
        self._source = source
        self._last_source = None
        self._position = None
        self._fallback = None
        self._xpath_list = []

        self._addXPath(xpath)


    def __str__(self):
        return f"XPathSelector({'|'.join(self._xpath_list)}"


    def _addXPath(self, _xpath: Union[list, tuple, str]):
        if isinstance(_xpath, str):
            _xpath = _strictXPath(_xpath)
            self._xpath_list.append(_xpath)
        elif isinstance(_xpath, (list, tuple)):
            for xp in _xpath:
                self._xpath_list.append(_strictXPath(xp))
        else:
            raise TypeError("Unknown type for value {}".format(_xpath))
        return self


    @property
    async def exists(self):
        elms = await self.all()
        return len(elms) > 0



    async def getLastMatch(self):
        elms = await self.all(self._last_source)
        return elms[0]


    async def all(self, source=None):
        """
        Returns:
            list of XMLElement
        """
        xml_content = source or self._source or await self._client.dumpHierarchy()
        self._last_source = xml_content

        hierarchy = source or self._source

        if hierarchy is None:
            root = etree.fromstring(_str2bytes(xml_content))
        elif isinstance(hierarchy, (str, bytes)):
            root = etree.fromstring(_str2bytes(hierarchy))
        elif isinstance(hierarchy, etree._Element):
            root = hierarchy
        else:
            raise TypeError("Unknown type", type(hierarchy))

        for node in root.xpath("//node"):
            node.tag = _safeXmlstr(node.attrib.pop("class", "")) or "node"

        match_sets = []
        for xpath in self._xpath_list:
            matches = root.xpath(
                xpath,
                namespaces={"re": "http://exslt.org/regular-expressions"})
            match_sets.append(matches)
        # find out nodes which match all xpaths
        match_nodes = functools.reduce(lambda x, y: set(x).intersection(y),
                                       match_sets)
        els = [XMLElement(node, self._parent) for node in match_nodes]
        if not self._position:
            return els

        # 中心点应控制在控件内
        inside_els = []
        px, py = self._position
        wsize = await self._client.windowSize()
        for e in els:
            lpx, lpy, rpx, rpy = e.percent_bounds(wsize=wsize)
            # 中心点偏移百分比不应大于控件宽高的50%
            scale = 1.5

            if abs(px - (lpx + rpx) / 2) > (rpx - lpx) * .5 * scale:
                continue
            if abs(py - (lpy + rpy) / 2) > (rpy - lpy) * .5 * scale:
                continue
            inside_els.append(e)
        return inside_els




class XMLElement(object):
    def __init__(self, elem, parent: XPath):
        self.elem = elem
        self._parent = parent
        self._client = parent.client

    def __hash__(self):
        compared_attrs = ("text", "resource-id", "package", "content-desc")
        values = [self.attrib.get(name) for name in compared_attrs]
        root = self.elem.getroottree()
        fullpath = root.getpath(self.elem)
        fullpath = re.sub(r'\[\d+\]', '', fullpath)  # remove indexes
        values.append(fullpath)
        return hash(tuple(values))

    def __eq__(self, value):
        return self.__hash__() == hash(value)

    def __repr__(self):
        x, y = self.center()
        return "<xpath.XMLElement [{tag!r} center:({x}, {y})]>".format(tag=self.elem.tag, x=x, y=y)
    


    def __call__(self, xpath: str):
        return XPathSelector(self._parent, xpath, self.elem)


    def center(self):
        """
        Returns:
            (x, y)
        """
        return self.offset(0.5, 0.5)

    def offset(self, px: float = 0.0, py: float = 0.0):
        """
        Offset from left_top

        Args:
            px (float): percent of width
            py (float): percent of height

        Example:
            offset(0.5, 0.5) means center
        """
        x, y, width, height = self.rect
        return x + int(width * px), y + int(height * py)

    def click(self):
        """
        click element, 100ms between down and up
        """
        x, y = self.center()
        return self._client.click(x, y)

    def longClick(self):
        """
        Sometime long click is needed, 400ms between down and up
        """
        x, y = self.center()
        return self._client.longClick(x, y)



    @property
    def bounds(self):
        """
        Returns:
            tuple of (left, top, right, bottom)
        """
        bounds = self.elem.attrib.get("bounds")
        lx, ly, rx, ry = map(int, re.findall(r"\d+", bounds))
        return (lx, ly, rx, ry)
    

    @property
    def rect(self):
        """
        Returns:
            (left_top_x, left_top_y, width, height)
        """
        lx, ly, rx, ry = self.bounds
        return lx, ly, rx - lx, ry - ly

    @property
    def text(self):
        return self.elem.attrib.get("text")

    @property
    def attrib(self):
        return self.elem.attrib

    @property
    def info(self):
        ret = {}
        for key in ("text", "focusable", "enabled", "focused", "scrollable",
                    "selected", "clickable"):
            ret[key] = self.attrib.get(key)
        ret["className"] = self.elem.tag
        lx, ly, rx, ry = self.bounds
        ret["bounds"] = {'left': lx, 'top': ly, 'right': rx, 'bottom': ry}
        ret["contentDescription"] = self.attrib.get("content-desc")
        ret["longClickable"] = self.attrib.get("long-clickable")
        ret["packageName"] = self.attrib.get("package")
        ret["resourceName"] = self.attrib.get("resource-id")
        ret["resourceId"] = self.attrib.get("resource-id") # this is better than resourceName
        ret["childCount"] = len(self.elem.getchildren())
        return ret