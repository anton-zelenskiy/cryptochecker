# Cryptochecker

Simple tg bot for checking cryptocurrencies price.


How to run local:
1. set API_TOKEN
2. set WEBHOOK_HOST (ngrok)
3. `docker-compose -f docker-compose.local.yml up -d`
4. https://<WEBHOOK_HOST>>/<API_TOKEN>/set/
5. success!

# ci/cd
Guide:
https://levelup.gitconnected.com/automated-deployment-using-docker-github-actions-and-webhooks-54018fc12e32

Prepare server

* Install webhook
```shell
sudo apt-get install webhook
```
* Create hooks.json conf file for webhook
```shell
sudo nano /home/webhooks/hooks.json
```

```json
[
  {
    "id": "cryptochecker_redeploy",
    "execute-command": "/home/webhooks/cryptochecker_redeploy.sh",
    "command-working-directory": "/home/webhooks"
  }
]
```
* Create redeploy script
```shell
nano /home/webhooks/cryptochecker_redeploy.sh
chmod +x /home/webhooks/cryptochecker_redeploy.sh
```
```shell
#!/bin/bash

cd /home/cryptochecker
git pull
docker-compose stop app && docker-compose up -d --build app
```
* run webhook for test
```shell
webhook -hooks /home/webhooks/hooks.json
```
* Add DEPLOY_WEBHOOK_URL secret to your github repo:
```
http://<ip>:<port>/hooks/cryptochecker_redeploy
```
* We need to run webhook as daemon. Install supervisor
```shell
sudo apt-get install supervisor
```
* Add config to supervisor for running our program (webhook)
```shell
nano /etc/supervisor/conf.d/run_webhook.conf
```
with content:
```
[program:webhook]
command=webhook -hooks /home/webhooks/hooks.json -verbose
user=root
autosart=true
autorestart=true
startretries=5
stdout_logfile=/var/log/supervisor/run_webhook.log
```
* Restart supervisor
```shell
sudo supervisorctl reload
```
* For testing try to call api http://<ip>:<port>/hooks/cryptochecker_redeploy