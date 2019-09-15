#-*- coding: utf-8 -*-
# Copyright 2019 ibelie, Chen Jie, Joungtao. All rights reserved.
# Use of this source code is governed by The MIT License
# that can be found in the LICENSE file.

from app import route, cookie, response, redirect, config
from logic.account import github
import utils
import app

ANONYMOUSE = 'anonymouse'
SESSION = utils.Session(config.SESSION)

@route
def error(cookies):
	return redirect('http://%(localhost)s' % {'localhost': config.LOCALHOST})

@route
def login(cookies):
	session = SESSION.record(ANONYMOUSE)
	return redirect(github.Login(session), cookie(session = session))

@route
def callback(cookies, code, state):
	session = cookies.get('session')
	session = session and session.value

	if not code or session != state:
		return forward('github/error')

	error, anonymouse = SESSION.get(session)
	if error or anonymouse != ANONYMOUSE:
		return forward('github/error')

	SESSION.discard(session)
	session = github.Authorize(session, code)
	if not session:
		return forward('github/error')

	return redirect('http://%(localhost)s%(url_root)s/project/user_main' % {
		'localhost': config.LOCALHOST,
		'url_root': config.URL_ROOT,
	}, cookie(session = session))
