#-*- coding: utf-8 -*-
# Copyright 2019 ibelie, Chen Jie, Joungtao. All rights reserved.
# Use of this source code is governed by The MIT License
# that can be found in the LICENSE file.

from app import route, response, redirect, config
from logic.account import github
import utils

SESSION = utils.Session(config.SESSION)

@route
def error(cookies):
	return redirect('http://%(localhost)s' % {'localhost': config.LOCALHOST})

@route('/user_main.py.html')
def user_main(cookies):
	session = cookies.get('session')
	session = session and session.value
	error, account = SESSION.get(session)
	account = github.Account(account)
	assert account, 'Only support github account now!!!'

	return response(**account.user)

@route('/project_item.py.html')
def item(cookies, project):
	session = SESSION.record(ANONYMOUSE)

	return redirect('https://github.com/login/oauth/authorize?client_id=%(client_id)s&scope=%(scope)s&state=%(state)s&redirect_uri=%(callback)s' % {
		'client_id': 'c5386ab37c7dc7f436fb',
		'scope': 'user,public_repo',
		'state': session,
		'callback': quote('http://%(localhost)s%(app)s/github/callback' % {
			'localhost': config.LOCALHOST,
			'url_root': config.URL_ROOT,
		}),
	}, cookie(session = session))
