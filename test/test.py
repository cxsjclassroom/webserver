#-*- coding: utf-8 -*-

import os
import email.utils
import mimetypes
import posixpath
from wsgiref.simple_server import make_server

import config
config.LOCALHOST = 'localhost'

from logic.account import github
github.Account.CLIENT = '377e80b782a0455c51c3'
github.Account.SECRET = 'ccb0de98fe5ac8383c8d329e1c03721463699663'

from app import application

import imp
try:
	properform = imp.load_source('properform', 'properform/app.py').application
except:
	properform = None

LOCATIONS = {
	'/': 'web',
	'/app': application,
	'/properform': properform,
}

EXTENSIONS = None

def send_error(code, message, start_response):
	start_response('%d %s' % (code, message), [('Content-Type', 'text/html')])
	return [("""\
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
""" % {'code': code, 'message': message}).encode('UTF-8', 'replace')]


def send_file(path, start_response):
	global EXTENSIONS
	if EXTENSIONS is None:
		if not mimetypes.inited:
			mimetypes.init() # try to read system mime.types
		EXTENSIONS = mimetypes.types_map.copy()

	if not os.path.isfile(path):
		if not os.path.isdir(path):
			return send_error(404, 'File "%s" not found' % path, start_response)
		path = os.path.join(path, 'index.html')
		if not os.path.isfile(path):
			return send_error(404, 'File "%s" not found' % path, start_response)

	filename, ext = posixpath.splitext(path)
	if ext not in EXTENSIONS:
		ext = ext.lower()
		if ext not in EXTENSIONS:
			return send_error(404, 'File "%s" not found' % path, start_response)

	try:
		# Always read in binary mode. Opening files in text mode may cause
		# newline translations, making the actual size of the content
		# transmitted *less* than the content-length!
		with open(path, 'rb') as f:
			fs = os.fstat(f.fileno())
			content = f.read()
			length = str(fs[6])
			mtime = email.utils.formatdate(fs.st_mtime, usegmt=True)
	except:
		return send_error(404, 'File "%s" not found' % path, start_response)

	start_response('200 OK', [
		('Content-Type', EXTENSIONS[ext]),
		('Content-Length', length),
		('Last-Modified', mtime),
	])
	return [content]


def _application(env, start_response):
	preLen = 0
	global LOCATIONS
	for k, v in LOCATIONS.items():
		path = env['PATH_INFO']
		if k == path:
			app = v if isinstance(v, str) else v
			break
		elif path.startswith(k) and len(k) > preLen:
			app = os.path.join(v, path[len(k):]) if isinstance(v, str) else v
			preLen = len(k)

	if isinstance(app, str):
		return send_file(app, start_response)
	else:
		return app(env, start_response)


httpd = make_server(config.LOCALHOST, 80, _application)
print('Serving HTTP on port 80...')
httpd.serve_forever()
