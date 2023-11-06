


class BaseError(Exception):
    pass


class RpcTimeout(BaseError) :
    pass


class JSONRPCError(BaseError):

    @staticmethod
    def formatErrcode(errcode):
        m = {
            -32700: 'Parse error',
            -32600: 'Invalid Request',
            -32601: 'Method not found',
            -32602: 'Invalid params',
            -32603: 'Internal error',
            -32001: 'Jsonrpc error',
            -32002: 'Client error',
        }
        if errcode in m:
            return m[errcode]
        if errcode >= -32099 and errcode <= -32000:
            return 'Server error'
        return 'Unknown error'

    def __init__(self, error: dict = {}, method=None):
        self.code = error.get('code')
        self.message = error.get('message', '')
        self.data = error.get('data', '')
        self.method = method
        if isinstance(self.data, dict):
            self.exception_name = self.data.get("exceptionTypeName")
        else:
            self.exception_name = None

    def __str__(self):
        return '%d %s: <%s> data: %s, method: %s' % (
            self.code, self.formatErrcode(
                self.code), self.message, self.data, self.method)

    def __repr__(self):
        return repr(str(self))



class UiObjectNotFoundError(JSONRPCError):
    """ 控件没找到 """