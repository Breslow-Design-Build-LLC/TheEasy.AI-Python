# Project: TheEasy.AI QuoteApp API

## Servers

### Developer Server (Hostinger VPS)
- **SSH**: `ssh root@76.13.26.190`
- **Domain**: api.aibreslow.com
- **App directory**: /opt/quoteapp
- **Repo on VPS**: /opt/quoteapp/repo
- **Deploy command**: `ssh root@76.13.26.190 "bash /opt/quoteapp/repo/deploy/deploy.sh"`
- **Service**: `systemctl restart quoteapp`
- **Logs**: `journalctl -u quoteapp -n 50 --no-pager`
- **Health**: `curl https://api.aibreslow.com/api/v1/health`

## Deploy workflow
1. Commit changes
2. `git push origin main`
3. `ssh root@76.13.26.190 "bash /opt/quoteapp/repo/deploy/deploy.sh"`
