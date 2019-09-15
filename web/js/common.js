// Copyright 2018 ibelie, Chen Jie, Joungtao. All rights reserved.
// Use of this source code is governed by The MIT License
// that can be found in the LICENSE file.

function test() {
	$.ajax({
		url: '/app/github/get?asdf=1&xxx=qwer',
		type: 'GET',
		error: function(r, t, e) {
			alert(t + ': ' + e);
		},
		success : function(data) {
			if (data.error) {
				alert(data.error);
			} else {
				console.info(data);
			}
		},
	});
	// $.ajax({
	// 	url: '/app/test/post',
	// 	type: 'POST',
	// 	data: JSON.stringify({
	// 		asdf: 123,
	// 	}),
	// 	error: function(r, t, e) {
	// 		alert(t + ': ' + e);
	// 	},
	// 	success : function(data) {
	// 		if (data.error) {
	// 			alert(data.error);
	// 		} else {
	// 			console.info(data);
	// 		}
	// 	},
	// });
}
