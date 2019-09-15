#-*- coding: utf-8 -*-
# Copyright 2019 ibelie, Chen Jie, Joungtao. All rights reserved.
# Use of this source code is governed by The MIT License
# that can be found in the LICENSE file.

from functools import wraps
from ruamel import yaml
import threading
import binascii
import struct
import codecs
import signal
import mmap
import time
import sys
import os


class Alarm(object):
	def __init__(self, timeout, error):
		self.timeout = timeout
		self.timer = None
		self.error = error
		self.start()

	def start(self):
		if hasattr(signal, 'SIGALRM') and threading.currentThread().getName() == 'MainThread':
			def handler(signum, frame):
				raise RuntimeError(self.error)
			signal.signal(signal.SIGALRM, handler)
			signal.alarm(self.timeout)
		else:
			def handler(frame, event, arg):
				raise RuntimeError(self.error)

			def set_trace_for_frame_and_parents(frame, trace_func):
				# Note: this only really works if there's a tracing function set in this
				# thread (i.e.: sys.settrace or threading.settrace must have set the
				# function before)
				while frame:
					if frame.f_trace is None:
						frame.f_trace = trace_func
					frame = frame.f_back
				del frame

			def interrupt(thread):
				for thread_id, frame in sys._current_frames().items():
					if thread_id == thread.ident:
						set_trace_for_frame_and_parents(frame, handler)

			sys.settrace(lambda frame, event, arg: None)
			self.timer is not None and self.timer.cancel()
			self.timer = threading.Timer(self.timeout, interrupt, (threading.currentThread(), ))
			self.timer.start()

	def cancel(self):
		if hasattr(signal, 'alarm') and threading.currentThread().getName() == 'MainThread':
			signal.alarm(0)
		else:
			self.timer.cancel()
			self.timer = None


SsIDSZ = 8  # session identity size
SsTMSZ = 8  # session time size
SsNMSZ = 48 # session name size
SsTMOS = SsIDSZ          # session time offset
SsNMOS = SsTMOS + SsTMSZ # session name offset
SsSIZE = SsNMOS + SsNMSZ # session item total size
SsSize = SsSIZE * 10000  # session total size
SsLast = SsSize - SsSIZE # session last item offset
TIMEOUT = 1.5 * 60 * 60

try:
	import fcntl
	def mutex(func):
		@wraps(func)
		def _mutex(self, *args, **kwargs):
			fcntl.flock(self.file.fileno(), fcntl.LOCK_EX)
			result = func(self, *args, **kwargs)
			fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
			return result
		return _mutex
except:
	def mutex(func):
		return func

class Session(object):
	def __init__(self, path):
		if not os.path.isfile(path):
			if not os.path.isdir(os.path.dirname(path)):
				os.makedirs(os.path.dirname(path))
			with open(path, 'wb') as f:
				f.write(b'\0' * SsSize)
		self.file = open(path, 'r+b')
		self.mmap = mmap.mmap(self.file.fileno(), SsSize, access = mmap.ACCESS_WRITE)

	def search(self, session):
		lo = 0
		hi = SsSize // SsSIZE
		session = int(session, 16)
		while lo < hi:
			mid = (lo + hi) // 2
			i, = struct.unpack('Q', self.mmap[SsSIZE * mid: SsSIZE * mid + SsIDSZ])
			if i == 0 or i > session:
				hi = mid
			elif i < session:
				lo = mid + 1
			else:
				return SsSIZE * mid, True
		return SsSIZE * lo, False

	def _update(self):
		c = time.time()
		index = 0
		while index < SsSize:
			i, = struct.unpack('Q', self.mmap[index: index + SsIDSZ])
			if i == 0: break
			t, = struct.unpack('d', self.mmap[index + SsTMOS: index + SsNMOS])
			if c - t > TIMEOUT:
				self.mmap.move(index, index + SsSIZE, SsLast - index)
				self.mmap[SsLast: SsSize] = b'\0' * SsSIZE
			else:
				index += SsSIZE

	@mutex
	def __str__(self):
		data = {}
		for index in range(0, SsSize, SsSIZE):
			i, = struct.unpack('Q', self.mmap[index: index + SsIDSZ])
			if i == 0: break
			t, = struct.unpack('d', self.mmap[index + SsTMOS: index + SsNMOS])
			u = self.mmap[index + SsNMOS: index + SsSIZE].strip(b'\0').decode()
			data[i] = (t, u)
		return str(data)

	@mutex
	def record(self, username):
		self._update()
		session = binascii.hexlify(os.urandom(SsIDSZ)).decode('ascii')
		index, exist = self.search(session)
		while exist:
			session = binascii.hexlify(os.urandom(SsIDSZ)).decode('ascii')
			index, exist = self.search(session)
		if index >= SsSize:
			index = SsLast
		elif index < SsLast:
			self.mmap.move(index + SsSIZE, index, SsLast - index)
		self.mmap[index: index + SsNMOS] = struct.pack('Qd', int(session, 16), time.time())
		self.mmap[index + SsNMOS: index + SsSIZE] = username.encode().ljust(SsNMSZ, b'\0')
		self.mmap.flush()
		return session

	@mutex
	def get(self, session):
		index, exist = self.search(session)
		if not exist:
			return 'no session!', None

		t, = struct.unpack('d', self.mmap[index + SsTMOS: index + SsNMOS])
		c = time.time()
		if c - t > TIMEOUT:
			self.mmap.move(index, index + SsSIZE, SsLast - index)
			self.mmap[SsLast: SsSize] = b'\0' * SsSIZE
			self.mmap.flush()
			return 'session timeout!', None

		self.mmap[index + SsTMOS: index + SsNMOS] = struct.pack('d', c)
		u = self.mmap[index + SsNMOS: index + SsSIZE].strip(b'\0').decode()
		self.mmap.flush()
		return '', u

	@mutex
	def discard(self, session):
		index, exist = self.search(session)
		if exist:
			self.mmap.move(index, index + SsSIZE, SsLast - index)
			self.mmap[SsLast: SsSize] = b'\0' * SsSIZE
			self.mmap.flush()


def saveData(path, data):
	folder = os.path.dirname(path)
	not os.path.isdir(folder) and os.makedirs(folder)
	with codecs.open(path, 'w', 'utf-8') as f:
		yaml.dump(data, f, Dumper = yaml.RoundTripDumper)

def readData(path):
	if not os.path.isfile(path):
		return {}

	try:
		with codecs.open(path, 'r', 'utf-8') as f:
			return yaml.load(f, Loader = yaml.RoundTripLoader)
	except:
		return {}

def markdown(text):
	import pymdownx.emoji
	import markdown

	extensions = [
		'markdown.extensions.sane_lists',
		'markdown.extensions.tables',
		'pymdownx.magiclink',
		'pymdownx.betterem',
		'pymdownx.tilde',
		'pymdownx.emoji',
		'pymdownx.tasklist',
		'pymdownx.superfences'
	]

	extension_configs = {
		"pymdownx.magiclink": {
			"repo_url_shortener": True,
			"repo_url_shorthand": True,
			"provider": "github",
			"user": "facelessuser",
			"repo": "pymdown-extensions"
		},
		"pymdownx.tilde": {
			"subscript": False
		},
		"pymdownx.emoji": {
			"emoji_index": pymdownx.emoji.gemoji,
			"emoji_generator": pymdownx.emoji.to_png,
			"alt": "short",
			"options": {
				"attributes": {
					"align": "absmiddle",
					"height": "20px",
					"width": "20px"
				},
				"image_path": "https://assets-cdn.github.com/images/icons/emoji/unicode/",
				"non_standard_image_path": "https://assets-cdn.github.com/images/icons/emoji/"
			}
		}
	}

	return markdown.markdown(text, output_format = 'html5',
		extensions = extensions, extension_configs = extension_configs)
