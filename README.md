# web server

#### **nginx**

1. `yum install -y nginx`

2. `vi /etc/nginx/nginx.conf`

```
user ibelie;

#        location / {
#        }
```

3. `vi /etc/nginx/default.d/webserver.conf`

```
location / {
    alias /home/ibelie/webserver/web/;
    index index.html;
}

location /app {
    include uwsgi_params;
    uwsgi_read_timeout 3600;
    uwsgi_pass 127.0.0.1:5554;
}

location /properform {
    include uwsgi_params;
    uwsgi_read_timeout 3600;
    uwsgi_pass 127.0.0.1:5556;
}
```

4. systemctl restart nginx


#### **uwsgi**

`pip install uwsgi`

```
uwsgi --ini /home/ibelie/webserver/server/uwsgi.ini
uwsgi --reload /home/ibelie/webserver/server/uwsgi.pid
uwsgi --stop /home/ibelie/webserver/server/uwsgi.pid
uwsgi --ini /home/ibelie/webserver/properform/uwsgi.ini
uwsgi --reload /home/ibelie/webserver/properfor/uwsgi.pid
uwsgi --stop /home/ibelie/webserver/properform/uwsgi.pid
```

#### **rsyslog**

1. `vi /etc/rsyslog.d/processor.conf`

```
$template ProcessorFile,"/var/log/processor-%syslogtag:R,ERE,1,DFLT:\[([0-9a-zA-Z]+)\]--end%"
:programname, isequal, "Processor"	action(type="omfile"
	FileOwner="ibelie"
	FileGroup="ibelie"
	DynaFile="ProcessorFile")
& ~
```

2. `systemctl restart rsyslog`
