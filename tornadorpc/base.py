"""
Copyright 2009 Josh Marshall
Licensed under the Apache License, Version 2.0 (the "License"); 
you may not use this file except in compliance with the License. 
You may obtain a copy of the License at 

   http://www.apache.org/licenses/LICENSE-2.0 

Unless required by applicable law or agreed to in writing, software 
distributed under the License is distributed on an "AS IS" BASIS, 
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. 
See the License for the specific language governing permissions and 
limitations under the License. 

============================
Base RPC Handler for Tornado 
============================
This is a basic server implementation, designed for use within the 
Tornado framework. The classes in this library should not be used
directly, but rather though the XML or JSON RPC implementations.
You can use the utility functions like 'private' and 'start_server'.
"""

from tornado.web import RequestHandler
import types

# Configuration element
class Config(object):
    verbose = True
    short_errors = True

config = Config()

class BaseRPCParser(object):
    """
    This class is responsible for managing the request, dispatch,
    and response formatting of the system. It is tied into the 
    _RPC_ attribute of the BaseRPCHandler (or subclasses) and 
    populated as necessary throughout the request. Use the 
    .faults attribute to take advantage of the built-in error
    codes.
    """
    content_type = 'text/plain'

    def __init__(self, library, encode=None, decode=None):
        # Attaches the RPC library and encode / decode functions.
        self.library = library
        if not encode:
            encode = getattr(library, 'dumps')
        if not decode:
            decode = getattr(library, 'loads')
        self.encode = encode
        self.decode = decode

    @property
    def faults(self):
        # Grabs the fault tree on request
        return Faults(self)

    def run(self, handler, request_body):
        """
        This is the main loop -- it passes the request body to
        the parse_request method, and then takes the resulting
        method(s) and parameters and passes them to the appropriate
        method on the parent Handler class, then parses the response
        into text and returns it to the parent Handler to send back
        to the client.
        """
        self.handler = handler
        try:
            requests = self.parse_request(request_body)
        except:
            self.traceback()
            return self.faults.parse_error()
        if type(requests) is not types.TupleType:
            # SHOULD be the result of a fault call,
            # according tothe parse_request spec below.
            if type(requests) in types.StringTypes:
                # Should be the response text of a fault
                return requests
            elif 'response' in dir(requests):
                # Fault types should have a 'response' method
                return requests.response()
            else:
                # No idea, hopefully the handler knows what it
                # is doing.
                return requests
        responses = []
        for request in requests:
            response = self.dispatch(request[0], request[1])
            responses.append(response)
        responses = tuple(responses)
        response_text = self.parse_responses(responses)
        if type(response_text) not in types.StringTypes:
            # Likely a fault, or something messed up
            response_text = self.encode(response_text)
        return response_text
        
    def dispatch(self, method_name, params):
        """
        This method walks the attribute tree in the method 
        and passes the parameters, either in positional or
        keyword form, into the appropriate method on the
        Handler class. Currently supports only positional
        or keyword arguments, not mixed. 
        """
        if method_name in dir(RequestHandler):
            # Pre-existing, not an implemented attribute
            return self.faults.method_not_found()
        method = self.handler
        method_list = dir(method)
        method_list.sort()
        attr_tree = method_name.split('.')
        try:
            for attr_name in attr_tree:
                method = self.check_method(attr_name, method)
        except AttributeError:
            return self.faults.method_not_found()
        if not callable(method):
            # Not callable, so not a method
            return self.faults.method_not_found()
        if method_name.startswith('_') or \
                ('private' in dir(method) and method.private is True):
            # No, no. That's private.
            return self.faults.method_not_found()
        if type(params) is types.DictType:
            # Keyword arguments
            try:
                response = method(**params)
            except TypeError:
                return self.faults.invalid_params()
            except:
                # We should log here...bare excepts are evil.
                self.traceback(method_name, params)
                return self.faults.internal_error()
            return response
        elif type(params) in (types.ListType, types.TupleType):
            # Positional arguments
            try:
                response = method(*params)
            except TypeError:
                return self.faults.invalid_params()
            except:
                # Once again, we need to log here
                self.traceback(method_name, params)
                return self.faults.internal_error()
            return response
        else:
            # Bad argument formatting?
            return self.faults.invalid_params()

    def traceback(self, method_name='REQUEST', params=[]):
        import traceback
        err_lines = traceback.format_exc().splitlines()
        err_title = "ERROR IN %s" % method_name
        if len(params) > 0:
            err_title += ' - (PARAMS: %s)' % params
        err_sep = ('-'*len(err_title))[:79]
        err_lines = [err_sep, err_title, err_sep]+err_lines
        global config
        if config.verbose == True:
            if len(err_lines) >= 7 and config.short_errors:
                # Minimum number of lines to see what happened
                # Plust title and separators
                print '\n'.join(err_lines[0:4]+err_lines[-3:])
            else:
                print '\n'.join(err_lines)
        # Log here
        return

    def parse_request(self, request_body):
        """
        Extend this on the implementing protocol. If it
        should error out, return the output of the
        'self.faults.fault_name' response. Otherwise, 
        it MUST return a TUPLE of TUPLE. Each entry
        tuple must have the following structure:
        ('method_name', params)
        ...where params is a list or dictionary of
        arguments (positional or keyword, respectively.)
        So, the result should look something like
        the following:
        ( ('add', [5,4]), ('add', {'x':5, 'y':4}) )
        """
        return ([], []) 
    
    def parse_responses(self, responses):
        """
        Extend this on the implementing protocol. It must 
        return a response that can be returned as output to 
        the client.
        """
        return self.encode(responses, methodresponse = True)

    def check_method(self, attr_name, obj):
        """
        Just checks to see whether an attribute is private 
        (by the decorator or by a leading underscore) and 
        returns boolean result.
        """
        if attr_name.startswith('_'):
            raise AttributeError('Private object or method.')
        attr = getattr(obj, attr_name)
        if 'private' in dir(attr) and attr.private == True:
            raise AttributeError('Private object or method.')
        return attr

class BaseRPCHandler(RequestHandler):
    """
    This is the base handler to be subclassed by the actual
    implementations and by the end user. The only attribute
    this adds to the Tornado request handler is '_RPC_', which
    is what holds the RPC Parser subclassed from the
    BaseRPCParser above.
    """
    _RPC_ = None
    
    def post(self):
        # Very simple -- dispatches request body to the parser
        # and returns the output
        request_body = self.request.body
        response_text = self._RPC_.run(self, request_body)
        self.set_header('Content-Type', self._RPC_.content_type)
        self.write(response_text)
        return        
    
class FaultMethod(object):
    """
    This is the 'dynamic' fault method so that the message can
    be changed on request from the parser.faults call.
    """
    def __init__(self, fault, code, message):
        self.fault = fault
        self.code = code
        self.message = message

    def __call__(self, message=None):
        if message:
            self.message = message
        return self.fault(self.code, self.message)

class Faults(object):
    """
    This holds the codes and messages for the RPC implementation.
    It is attached (dynamically) to the Parser when called via the
    parser.faults query, and returns a FaultMethod to be called so
    that the message can be changed. If the 'dynamic' attribute is
    not a key in the codes list, then it will error.
    
    USAGE:
        parser.fault.parse_error('Error parsing content.')
        
    If no message is passed in, it will check the messages dictionary
    for the same key as the codes dict. Otherwise, it just prettifies
    the code 'key' from the codes dict.
    
    """
    codes = { 
        'parse_error': -32700,
        'method_not_found': -32601,
        'invalid_request': -32600,
        'invalid_params': -32602,
        'internal_error': -32603
    }

    messages = {}
  
    def __init__(self, parser, fault=None):
        self.library = parser.library
        self.fault = fault
        if not self.fault:
            self.fault = getattr(self.library, 'Fault')
            
    def __getattr__(self, attr):
        message = 'Error'
        if attr in self.messages.keys():
            message = self.messages[attr]
        else:
            message = ' '.join(map(str.capitalize, attr.split('_')))
        fault = FaultMethod(self.fault, self.codes[attr], message)
        return fault

"""
Utility Functions
"""

def private(obj):
    """
    Use this to make a method private.
    It is intended to be used as a decorator.
    If you wish to make a method tree private, just
    create and set the 'private' variable to True 
    on the tree object itself.
    """
    class PrivateMethod(object):
        def __init__(self):
            self.private = True
        __call__ = obj
    return PrivateMethod()

def start_server(handler, route=r'/', port=8080):
    """
    This is just a friendly wrapper around the default
    Tornado instantiation calls. It simplifies the imports
    and setup calls you'd make otherwise.
    USAGE:
        start_server(handler_class, route=r'/', port=8181)
    """
    import tornado.web
    import tornado.ioloop
    import tornado.httpserver

    routes = [(route, handler),]
    if not route.endswith('/'):
        route = r'%s/' % route
    routes.append(('%sRPC2' % route, handler)) 

    application = tornado.web.Application(routes)
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(port)
    tornado.ioloop.IOLoop.instance().start()


"""
The following is a test implementation which should work
for both the XMLRPC and the JSONRPC clients.
"""

class TestMethodTree(object):
    def power(self, x, y=2):
        return pow(x, y)

    @private
    def private(self):
        # Shouldn't be called
        return False

class TestRPCHandler(BaseRPCHandler):

    _RPC_ = None

    def add(self, x, y):
        return x+y

    def ping(self, x):
        return x

    tree = TestMethodTree()

    def _private(self):
        # Shouldn't be called
        return False

    @private
    def private(self):
        # Also shouldn't be called
        return False