# objtodu.evescientist.net deployment

Live .obj -> DU blueprint web UI. Thin Flask wrapper over the /home/du pipeline.

- **App files:** deployed to `/var/www/vhosts/evescientist.net/objtodu.evescientist.net/`
  (`app.py`, `templates/index.html`). This `webapp/` dir is the version-controlled copy.
- **Service:** `objtodu.service` (systemd) runs `gunicorn -b 127.0.0.1:5002 -w 2 --timeout 180
  app:app` as user `claude`, `PYTHONPATH=/home/du`. `sudo systemctl restart objtodu` after
  editing app.py OR any /home/du pipeline module (the app imports them).
- **Proxy chain:** nginx (:443, public IP) -> Apache (:7081) -> gunicorn (:5002).
  - Apache reverse-proxy: `conf/vhost.conf` (HTTP) + `conf/vhost_ssl.conf` (HTTPS) under
    `/var/www/vhosts/system/objtodu.evescientist.net/` (ProxyPass / -> 127.0.0.1:5002,
    `/.well-known` excluded).
  - nginx timeout: `conf/vhost_nginx.conf` (proxy_read/send_timeout 300s; server-level, NO
    `location /` -- that duplicates Plesk's and breaks reconfigure).
  - Apply config changes: `sudo plesk sbin httpdmng --reconfigure-domain objtodu.evescientist.net`
- **Uploads:** Plesk client_max_body_size = 128MB; Flask MAX_CONTENT_LENGTH = 64MB.
