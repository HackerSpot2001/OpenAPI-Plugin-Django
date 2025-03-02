from django.http.response import JsonResponse
from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.template.loader import render_to_string
from django.shortcuts import render
from django.conf import settings
from yaml import safe_load
from json import dumps as dumpJson
from importlib import import_module 
from Helpers.Utils import SuccessResp,ErrorResp
import os

class OpenAPIMiddleWare:
    def __init__(self, get_response):
        self.get_response   = get_response
        self.api_spec       = {}
        self.current_dir    = os.path.dirname(__file__)
        self.swagger_paths  = [
            {
                'filepath'  : settings.APISPEC_FILE,
                'reqpath'   : settings.APISPEC_PATH,
                'format'    : 'json',
                'context'   : {}
            },
            {
                'filepath'  : os.path.join( self.current_dir, '../swagger-ui.html' ),
                'reqpath'   : settings.SWAGGER_PATH,
                'format'    : 'html',
                'context'   : { "schema_url" : settings.APISPEC_PATH , 'swagger_title' : "Swagger Dashboard"  }
            },
            {
                'filepath'  : os.path.join( self.current_dir , '../css/swagger-ui.css' ),
                'reqpath'   : '/swagger-ui.css',
                'format'    : 'css',
                'context'   : {}
            },
        ]

        for path in os.listdir( os.path.join( self.current_dir , '../js' ) ):
            self.swagger_paths.append(
                {
                    'filepath'  : os.path.join( self.current_dir , '../js' , path ),
                    'reqpath'   : f"/{path}",
                    'format'    : 'js',
                    'context'   : {}
                }
            )


    def __call__(self, request : HttpRequest ,*args,**kwargs):
        response = self.get_response(request)
        with open(settings.APISPEC_FILE , 'r') as f:
            self.api_spec = safe_load(f)


        for swobj in self.swagger_paths :
            if request.path == swobj['reqpath']:
                if  swobj['format'] == 'html' :
                    response = render_to_string( swobj['filepath'], swobj['context'] , request)
                    response = HttpResponse(response, content_type='text/html' )

                else:
                    with open( swobj['filepath'] ,'r') as f:
                        content = f.read()
                        if (swobj['format'] == 'json' ):
                            content = safe_load(content)
                            response = JsonResponse( content , safe=False)
                        
                        elif swobj['format'] == 'css':
                            response = HttpResponse( content, content_type="text/css" )

                        elif swobj['format'] == 'js':
                            response = HttpResponse( content, content_type="text/javascript" )


        route_obj = dict(self.api_spec['paths']).get(request.path.__str__(),None)
        if ( route_obj != None):
            res = self.execute_route(route_obj, request)
            if res != None : response = res


        if((str(request.method).lower() == 'options') ):
            response = JsonResponse(SuccessResp,safe=False)
            response.status_code = 200


        if (response.status_code == 404) :
            NotFoundResp = ErrorResp
            NotFoundResp['apiresponse']['message'] = 'Route Not Available.'
            response = JsonResponse(NotFoundResp,safe=False)
            response.status_code = 404

        
        req_headers = dict(request.headers)
        response.headers['Access-Control-Allow-Credentials']    = 'true'
        response.headers['Access-Control-Allow-Methods']        = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Origin']         =  req_headers.get('Origin',request.META.get('HTTP_REFERER', request.META['HTTP_HOST']))
        response.headers['Access-Control-Allow-Headers']        = 'access-control-allow-origin,content-type, Origin, Content-Type, Accept, Authorization, X-Requested-With, X-Custom-UniqueTrace-ID, X-Custom-Request-Source'

        return response
    



    def execute_route(self, route_obj:dict, request:HttpRequest):
        method = list(route_obj.keys())[0]
        # for method in route_obj.keys():
        controller = dict(route_obj[method]).get("x-python-to",None)
        if controller == None: return None

        module_name, func_name = controller.rsplit('#',2)
        module = import_module(module_name)
        func = getattr(module, func_name)
        res = func(request)
        del func
        del module
        return res
