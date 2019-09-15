#-*- coding: utf-8 -*-
# Copyright 2019 ibelie, Chen Jie, Joungtao. All rights reserved.
# Use of this source code is governed by The MIT License
# that can be found in the LICENSE file.

import os
import app
import json
import utils
import uuid
import codecs
from ruamel import yaml

SESSION = utils.Session(app.config.SESSION)

def Login(session):
	return 'https://github.com/login/oauth/authorize?client_id=%(client_id)s&state=%(state)s&redirect_uri=%(callback)s' % {
		'client_id': Account.CLIENT,
		'state': session,
		'callback': app.quote('http://%(localhost)s%(url_root)s/github/callback' % {
			'localhost': app.config.LOCALHOST,
			'url_root': app.config.URL_ROOT,
		}),
	}

def Authorize(session, code):
	request = app.Request('https://github.com/login/oauth/access_token', app.urlencode({
		'client_id': Account.CLIENT,
		'client_secret': Account.SECRET,
		'redirect_uri': 'http://%(localhost)s%(url_root)s/github/callback' % {
			'localhost': app.config.LOCALHOST,
			'url_root': app.config.URL_ROOT,
		},
		'state': session,
		'code': code,
	}).encode('utf-8'), {
		'Accept': 'application/json',
	})

	access_token = json.loads(app.urlopen(request).read()).get('access_token')
	if access_token:
		return SESSION.record(Account.PREFIX + access_token)
	else:
		return None


class Account(object):
	CLIENT = '377e80b782a0455c51c3'
	SECRET = 'ccb0de98fe5ac8383c8d329e1c03721463699663'
	PREFIX = 'github:'
	USERINFO = 'data/users'

	def __init__(self, account):
		self.isValid = account.startswith(self.PREFIX)
		if self.isValid:
			self.access_token = account[len(self.PREFIX):]

	def __nonzero__(self):
		return self.isValid

	@property
	def user(self):
		if not os.path.isdir(self.USERINFO): os.makedirs(self.USERINFO)

		request = app.Request('https://api.github.com/user?access_token=%(access_token)s' % {
			'access_token': self.access_token,
		}, headers = {
			'Accept': 'application/json',
		})
		data = json.loads(app.urlopen(request).read())

		url = data['url']
		token = ''.join(str(uuid.uuid5(uuid.NAMESPACE_URL, url if isinstance(url, str) else url.encode('utf-8', 'replace'))).split('-'))
		filepath = os.path.join(self.USERINFO, '%s.yml' % token)
		if not os.path.isfile(filepath):
			with codecs.open(filepath, 'w', 'utf-8') as f:
				yaml.dump({
					'type': self.__module__.rpartition('.')[-1],
					'user': data['login'],
					'access_token': self.access_token,
					'information': data,
				}, f, Dumper = yaml.RoundTripDumper)

		return {
			'user_name': data['name'],
			'token': token,
		}
