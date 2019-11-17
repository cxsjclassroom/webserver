#-*- coding: utf-8 -*-
# Copyright 2019 ibelie, Chen Jie, Joungtao. All rights reserved.
# Use of this source code is governed by The MIT License
# that can be found in the LICENSE file.

from __future__ import print_function

import os
import re
import imp
import sys
import json
import codecs
import config
import traceback

if sys.version_info[0] == 3:
	from urllib import parse as urlparse
	from urllib.parse import quote, urlencode
	from urllib.request import Request, urlopen
	from http.cookies import SimpleCookie
	def encodeUTF8(s): return s.encode('utf-8', 'replace')
else:
	import urlparse
	from urllib import quote, urlencode
	from urllib2 import Request, urlopen
	from Cookie import SimpleCookie
	def encodeUTF8(s): return s

def exec_delegate(code, globals):
	exec(code, globals)

# ooooooooo.     .oooooo.   ooooo     ooo ooooooooooooo oooooooooooo
# `888   `Y88.  d8P'  `Y8b  `888'     `8' 8'   888   `8 `888'     `8
#  888   .d88' 888      888  888       8       888       888
#  888ooo88P'  888      888  888       8       888       888oooo8
#  888`88b.    888      888  888       8       888       888    "
#  888  `88b.  `88b    d88'  `88.    .8'       888       888       o
# o888o  o888o  `Y8bood8P'     `YbodP'        o888o     o888ooooood8
#
TEMPLATE_EXT = '.py.html'

ROUTE_RESPONSE = 0
ROUTE_REDIRECT = 1
ROUTE_FORWARD  = 2

def cookie(**args):
	result = SimpleCookie(args)
	for k in args:
		result[k]['path'] = config.URL_ROOT
	return result

def response(cookie = None, **args):
	return ROUTE_RESPONSE, cookie, args

def redirect(path, cookie = None):
	return ROUTE_REDIRECT, cookie, path

def forward(path, cookie = None, **args):
	return ROUTE_FORWARD, cookie, (path, args)

def route(path = '', useCookies = False, useSubmit = False):
	if callable(path):
		func = path
		func.____useCookies__ = useCookies
		func.____useSubmit__ = useSubmit
		func.____template__ = None
		func.____isRoute__ = True
		return func
	elif not path:
		def _route(func):
			func.____useCookies__ = useCookies
			func.____useSubmit__ = useSubmit
			func.____template__ = None
			func.____isRoute__ = True
			return func
		return _route

	assert path.endswith(TEMPLATE_EXT), 'template "%s" should ends with "%s"!' % (path, TEMPLATE_EXT)

	def _route(func):
		if not path.startswith('/'):
			func.____template__ = '/%s/%s' % (func.__module__.rpartition('.')[-1], path)
		else:
			func.____template__ = path
		func.____useCookies__ = useCookies
		func.____useSubmit__ = useSubmit
		func.____isRoute__ = True
		return func

	return _route


#       .o.       ooooooooo.   ooooooooo.
#      .888.      `888   `Y88. `888   `Y88.
#     .8"888.      888   .d88'  888   .d88'
#    .8' `888.     888ooo88P'   888ooo88P'
#   .88ooo8888.    888          888
#  .8'     `888.   888          888
# o88o     o8888o o888o        o888o
#
class application(object):
	CACHE = {}
	MODULES = {}

	def __init__(self, env, start_response):
		self.env = env
		self.start_response = start_response

	def __iter__(self):
		params = {k: v if len(v) > 1 else v[0] for k, v in urlparse.parse_qs(self.env['QUERY_STRING']).items()}

		assert self.env['PATH_INFO'].startswith(config.URL_ROOT)
		route = self.dispatch(self.env['PATH_INFO'][len(config.URL_ROOT):])
		if not callable(route): return route

		if route.____useSubmit__:
			params['submit'] = self.input_reader()
		elif self.env['REQUEST_METHOD'] == 'POST':
			L = []
			for chunk in self.input_reader():
				L.append(chunk)
			params = json.loads(b''.join(L))

		try:
			return self.handle_route(route, params, SimpleCookie(self.env.get('HTTP_COOKIE')), None)
		except Exception as e:
			return self.print_trace(e)


	# ooooo   ooooo       .o.       ooooo      ooo oooooooooo.   ooooo        oooooooooooo
	# `888'   `888'      .888.      `888b.     `8' `888'   `Y8b  `888'        `888'     `8
	#  888     888      .8"888.      8 `88b.    8   888      888  888          888
	#  888ooooo888     .8' `888.     8   `88b.  8   888      888  888          888oooo8
	#  888     888    .88ooo8888.    8     `88b.8   888      888  888          888    "
	#  888     888   .8'     `888.   8       `888   888     d88'  888       o  888       o
	# o888o   o888o o88o     o8888o o8o        `8  o888bood8P'   o888ooooood8 o888ooooood8
	#
	def input_reader(self):
		# Get arguments by reading body of request.
		# We read this in chunks to avoid straining
		# socket.read(); around the 10 or 15Mb mark, some platforms
		# begin to have problems (bug #792570).
		max_chunk_size = 10*1024*1024
		size_remaining = int(self.env['CONTENT_LENGTH'])
		while size_remaining:
			chunk_size = min(size_remaining, max_chunk_size)
			chunk = self.env['wsgi.input'].read(chunk_size)
			if not chunk:
				break
			size_remaining -= len(chunk)
			yield chunk

	def dispatch(self, path):
		"""Common code for GET and POST commands to dispatch request."""
		moduleName, routeName = list(filter(None, path.split('/')))[:2]

		# load module
		if moduleName not in self.MODULES:
			try:
				path = os.path.join(config.APP_ROUTE, moduleName + '.py')
				mod = imp.load_source(moduleName, path)
				self.MODULES[moduleName] = {k: getattr(mod, k) for k in dir(mod)
					if getattr(getattr(mod, k), '____isRoute__', False)}
			except IOError:
				return self.send_error(404, 'Route module "%s" not found' % moduleName)
			except Exception as e:
				return self.print_trace(e)

		module = self.MODULES[moduleName]
		if routeName not in module:
			return self.send_error(404, 'Route "%s" not found' % routeName)
		return module[routeName]

	def handle_route(self, route, params, cookies, set_cookie):
		"""Common code for GET and POST commands to handle route and send json result."""
		if route.____useCookies__:
			t, cookie, result = route(cookies = cookies, **params)
		else:
			t, cookie, result = route(**params)

		cookie is not None and cookies.load(cookie)
		if set_cookie:
			if cookie is None:
				cookie = SimpleCookie(set_cookie)
			else:
				cookie.load(set_cookie)

		if t == ROUTE_REDIRECT:
			return self.redirect(result, cookie)
		elif t == ROUTE_FORWARD:
			route = self.dispatch(result[0])
			return callable(route) and route or self.handle_route(route, result[1], cookies, cookie)

		if route.____template__ is None:
			content_type = 'text/json'
			result = json.dumps(result)
		else:
			content_type = 'text/html'
			result = self.template(route.____template__, result)
		result = encodeUTF8(result)

		headers = [('Content-type', content_type)]
		if cookie is not None:
			for key, value in sorted(cookie.items()):
				headers.append(('Set-Cookie', value.OutputString()))
		self.start_response('200 OK', headers)
		return iter([result])


	# oooooooooooo ooooooooo.   ooooooooo.     .oooooo.   ooooooooo.
	# `888'     `8 `888   `Y88. `888   `Y88.  d8P'  `Y8b  `888   `Y88.
	#  888          888   .d88'  888   .d88' 888      888  888   .d88'
	#  888oooo8     888ooo88P'   888ooo88P'  888      888  888ooo88P'
	#  888    "     888`88b.     888`88b.    888      888  888`88b.
	#  888       o  888  `88b.   888  `88b.  `88b    d88'  888  `88b.
	# o888ooooood8 o888o  o888o o888o  o888o  `Y8bood8P'  o888o  o888o
	#
	def send_error(self, code, message):
		self.start_response('%d %s' % (code, message), [('Content-Type', 'text/html')])
		return iter([encodeUTF8("""\
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"
        "http://www.w3.org/TR/html4/strict.dtd">
<html>
    <head>
        <meta http-equiv="Content-Type" content="text/html;charset=utf-8">
        <title>Error response</title>
    </head>
    <body>
        <h1>Error response</h1>
        <p>Error code: %(code)d</p>
        <p>Message: %(message)s.</p>
    </body>
</html>
""" % {'code': code, 'message': message})])

	def print_trace(self, e):
		# internal error, report as HTTP server error
		print(traceback.format_exc())
		print(e)
		headers = []
		if config.DEBUG:
			headers.append(('X-exception', str(e)))
			headers.append(('X-traceback', traceback.format_exc()))
		headers.append(('Content-length', '0'))
		self.start_response('500 Internal Error', headers)
		return iter([''.encode()])

	def redirect(self, url, cookie):
		# internal error, report as HTTP server error
		headers = []
		headers.append(('Content-Type', 'text/html'))
		headers.append(('Content-length', '0'))
		if cookie is not None:
			for key, value in sorted(cookie.items()):
				headers.append(('Set-Cookie', value.OutputString()))
		if not url.startswith('http'):
			url = 'http://' + url
		headers.append(('Location', url if isinstance(url, str) else url.encode('utf-8')))
		self.start_response('302 Found', headers)
		return iter([''.encode()])


	# ooooooooooooo oooooooooooo ooo        ooooo ooooooooo.   ooooo              .o.       ooooooooooooo oooooooooooo
	# 8'   888   `8 `888'     `8 `88.       .888' `888   `Y88. `888'             .888.      8'   888   `8 `888'     `8
	#      888       888          888b     d'888   888   .d88'  888             .8"888.          888       888
	#      888       888oooo8     8 Y88. .P  888   888ooo88P'   888            .8' `888.         888       888oooo8
	#      888       888    "     8  `888'   888   888          888           .88ooo8888.        888       888    "
	#      888       888       o  8    Y     888   888          888       o  .8'     `888.       888       888       o
	#     o888o     o888ooooood8 o8o        o888o o888o        o888ooooood8 o88o     o8888o     o888o     o888ooooood8
	#
	TEMPLATE_SEGMENT = re.compile(r'\s*<\?python[^\?]+\?>', re.I)

	class TemplateOutput(object):
		def __init__(self):
			object.__setattr__(self, 'content', '')

		def __getitem__(self, content):
			object.__setattr__(self, 'content', self.content + str(content))

		def __setattr__(self, key, value):
			object.__setattr__(self, 'content', self.content + '<script type="text/javascript">var %s = %s;</script>' % (key, json.dumps(value) or "null"))

	def template(self, path, data):
		path = os.path.join(config.TEMPLATE, path.lstrip('/'))
		if not config.DEBUG and path in self.CACHE:
			content, template = self.CACHE[path]
		else:
			with codecs.open(path, 'r', 'utf-8') as f:
				content = f.read()

			text_segs = self.TEMPLATE_SEGMENT.split(content)
			code_segs = self.TEMPLATE_SEGMENT.findall(content)

			template = ['_["""%s"""]' % text_segs[0].replace('"', '\\"')]
			for i , code_seg in enumerate(code_segs):
				prefix, code_seg = code_seg[:-2].split('<?python')
				prefix = prefix.lstrip('\r\n')
				codes = code_seg.split('\n')
				for code in codes:
					code = code.strip('\r\n')
					if not code.strip(): continue
					assert code.startswith(prefix), (prefix, code)
					code = code[len(prefix):].rstrip()
					indent = code[:-len(code.lstrip())]
					template.append(code)
					if code.endswith(':'):
						indent += '\t'

				text = text_segs[i + 1]
				template.append('%s_["""%s"""]' % (indent, text.replace('"', '\\"')))
			template = compile('\n'.join(template), path, 'exec')
			self.CACHE[path] = content, template

		output = self.TemplateOutput()
		globals = {'_': output}
		globals.update(data)
		exec_delegate(template, globals)
		return output.content
