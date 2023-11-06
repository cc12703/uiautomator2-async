

import hashlib
import time
from typing import Any, List
import httpx


from .exception import JSONRPCError, RpcTimeout


class JSONRpcWrapper(object) :

    def __init__(self, axClient: httpx.AsyncClient) -> None:
        self.method = None
        self.axClient = axClient


    def __getattr__(self, method):
        self.method = method
        return self
    

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        params = args if args else kwargs
        return self._callJsonRpc(self.method, params)



    async def _callJsonRpc(self, method: str, params: List = []) -> Any :
        data = {
            "jsonrpc": "2.0",
            "id": self._jsonrpcID(method),
            "method": method,
            "params": params,
        }
        try :
            resp = await self.axClient.post('/jsonrpc/0', json=data, timeout=httpx.Timeout(60))
            resp.raise_for_status()
        except httpx.ReadTimeout :
            raise RpcTimeout()


        jsondata = resp.json()
        error = jsondata.get('error')
        if not error:
            return jsondata.get('result')
        

        raise JSONRPCError(error, method)


    def _jsonrpcID(self, method):
        m = hashlib.md5()
        m.update(("%s at %f" % (method, time.time())).encode("utf-8"))
        return m.hexdigest()
