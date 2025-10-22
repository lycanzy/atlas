# Experiment Tracking App - Technical Deployment Guide

**For IT Team** - Step-by-step deployment instructions

---

## System Requirements

### Minimum Specifications
- **OS**: Ubuntu 22.04/24.04 LTS, RHEL 8/9, or Windows Server 2019+
- **CPU**: 2 cores
- **RAM**: 4GB
- **Disk**: 20GB
- **Python**: 3.9 or higher (tested with 3.13)

---

## Deployment Steps (Linux/Ubuntu)

### 1. Install System Dependencies

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Python and dependencies
sudo apt-get install -y python3.11 python3-pip python3-venv
sudo apt-get install -y nginx
sudo apt-get install -y git

# Optional: Install PostgreSQL (if migrating from SQLite later)
# sudo apt-get install -y postgresql postgresql-contrib
```

### 2. Create Application User & Directory

```bash
# Create dedicated user for application
sudo useradd -m -s /bin/bash experiment-app
sudo usermod -aG www-data experiment-app

# Create application directory
sudo mkdir -p /opt/experiment-app
sudo chown experiment-app:experiment-app /opt/experiment-app
```

### 3. Deploy Application Code

```bash
# Switch to application user
sudo su - experiment-app

# Navigate to application directory
cd /opt/experiment-app

# Option A: Upload files via SCP/SFTP
# scp -r experiment_app/ experiment-app@server:/opt/experiment-app/

# Option B: Clone from Git (if using version control)
# git clone <your-repo-url> .

# Your application structure should look like:
# /opt/experiment-app/
#   ├── experiment_app/
#   │   ├── manage.py
#   │   ├── db.sqlite3
#   │   ├── experiment_app/
#   │   │   └── settings.py
#   │   └── experiment_flow/
#   └── exptrack/ (if copying virtual environment)
```

### 4. Set Up Python Virtual Environment

```bash
# Create virtual environment
cd /opt/experiment-app
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Django and dependencies
pip install django==5.2.7
pip install gunicorn

# Or install from requirements.txt if provided
# pip install -r requirements.txt
```

### 5. Configure Application

```bash
# Edit settings.py
nano /opt/experiment-app/experiment_app/experiment_app/settings.py

# Update these settings:
# ALLOWED_HOSTS = ['your-server-hostname.internal', 'ip-address']
# DEBUG = False
# SECRET_KEY = '<generate new key>'
```

**Generate a new SECRET_KEY:**
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### 6. Initialize Database

```bash
cd /opt/experiment-app/experiment_app

# Apply migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create admin user
python manage.py createsuperuser
# Enter username, email, and password when prompted
```

### 7. Test Application

```bash
# Test that application runs
python manage.py runserver 0.0.0.0:8000

# Open browser to http://server-ip:8000
# You should see the login page
# Press Ctrl+C to stop
```

### 8. Configure Gunicorn Service

```bash
# Exit from experiment-app user
exit

# Create Gunicorn systemd service file
sudo nano /etc/systemd/system/experiment-app.service
```

**Paste this configuration:**
```ini
[Unit]
Description=Experiment Tracking App - Gunicorn
After=network.target

[Service]
Type=notify
User=experiment-app
Group=www-data
WorkingDirectory=/opt/experiment-app/experiment_app
Environment="PATH=/opt/experiment-app/venv/bin"
ExecStart=/opt/experiment-app/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/opt/experiment-app/experiment_app.sock \
    --timeout 60 \
    --access-logfile /var/log/experiment-app/access.log \
    --error-logfile /var/log/experiment-app/error.log \
    experiment_app.wsgi:application

[Install]
WantedBy=multi-user.target
```

**Create log directory:**
```bash
sudo mkdir -p /var/log/experiment-app
sudo chown experiment-app:www-data /var/log/experiment-app
```

**Enable and start service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable experiment-app
sudo systemctl start experiment-app
sudo systemctl status experiment-app
```

### 9. Configure Nginx

```bash
# Create Nginx configuration
sudo nano /etc/nginx/sites-available/experiment-app
```

**Paste this configuration:**
```nginx
server {
    listen 80;
    server_name experiment-app.yourlab.edu;  # Change to your hostname

    client_max_body_size 10M;

    # Static files
    location /static/ {
        alias /opt/experiment-app/experiment_app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files (if any)
    location /media/ {
        alias /opt/experiment-app/experiment_app/media/;
        expires 7d;
    }

    # Proxy to Gunicorn
    location / {
        proxy_pass http://unix:/opt/experiment-app/experiment_app.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

**Enable site and restart Nginx:**
```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/experiment-app /etc/nginx/sites-enabled/

# Test Nginx configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

### 10. Configure Firewall (if applicable)

```bash
# Allow HTTP traffic
sudo ufw allow 80/tcp

# If using HTTPS
sudo ufw allow 443/tcp

# Check firewall status
sudo ufw status
```

### 11. Set Up Automated Backups

```bash
# Create backup script
sudo nano /usr/local/bin/backup-experiment-app.sh
```

**Paste this script:**
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/experiment-app"
APP_DIR="/opt/experiment-app/experiment_app"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
cp $APP_DIR/db.sqlite3 $BACKUP_DIR/db_$DATE.sqlite3

# Optional: Backup entire application
# tar -czf $BACKUP_DIR/app_$DATE.tar.gz $APP_DIR

# Keep only last 30 days
find $BACKUP_DIR -name "db_*.sqlite3" -mtime +30 -delete

echo "Backup completed: $DATE"
```

**Make script executable:**
```bash
sudo chmod +x /usr/local/bin/backup-experiment-app.sh
```

**Add to crontab (daily at 2 AM):**
```bash
sudo crontab -e

# Add this line:
0 2 * * * /usr/local/bin/backup-experiment-app.sh >> /var/log/experiment-app/backup.log 2>&1
```

---

## Optional: Configure HTTPS with SSL

### Using Let's Encrypt (Free SSL)

```bash
# Install Certbot
sudo apt-get install -y certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d experiment-app.yourlab.edu

# Certbot will automatically configure Nginx for HTTPS
# Certificates auto-renew via systemd timer
```

### Using Internal CA Certificate

If your organization has internal SSL certificates:

```bash
# Place certificate files
sudo mkdir -p /etc/ssl/experiment-app
sudo cp your-cert.crt /etc/ssl/experiment-app/
sudo cp your-key.key /etc/ssl/experiment-app/
sudo chmod 600 /etc/ssl/experiment-app/your-key.key
```

Update Nginx configuration:
```nginx
server {
    listen 443 ssl;
    server_name experiment-app.yourlab.edu;

    ssl_certificate /etc/ssl/experiment-app/your-cert.crt;
    ssl_certificate_key /etc/ssl/experiment-app/your-key.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # ... rest of configuration
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name experiment-app.yourlab.edu;
    return 301 https://$server_name$request_uri;
}
```

---

## Monitoring & Maintenance

### Check Application Status

```bash
# Check Gunicorn service
sudo systemctl status experiment-app

# Check Nginx
sudo systemctl status nginx

# View application logs
sudo tail -f /var/log/experiment-app/error.log
sudo tail -f /var/log/experiment-app/access.log

# View Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Restart Services

```bash
# Restart application
sudo systemctl restart experiment-app

# Restart Nginx
sudo systemctl restart nginx

# Reload Nginx (no downtime)
sudo systemctl reload nginx
```

### Common Troubleshooting

**502 Bad Gateway**
- Check if Gunicorn is running: `sudo systemctl status experiment-app`
- Check socket file exists: `ls -l /opt/experiment-app/experiment_app.sock`
- Check logs: `sudo journalctl -u experiment-app -n 50`

**Static files not loading**
- Verify collectstatic was run: `python manage.py collectstatic`
- Check Nginx static path matches settings.STATIC_ROOT
- Check file permissions: `sudo chown -R experiment-app:www-data /opt/experiment-app/`

**Database locked errors**
- SQLite limitation with concurrent writes
- Consider migrating to PostgreSQL if this occurs frequently

---

## Security Checklist

- [ ] DEBUG = False in settings.py
- [ ] Strong SECRET_KEY generated and set
- [ ] ALLOWED_HOSTS configured correctly
- [ ] Firewall configured (only ports 80/443 open)
- [ ] Application runs as non-root user
- [ ] File permissions set correctly (644 for files, 755 for directories)
- [ ] Database file not world-readable
- [ ] Backups scheduled and tested
- [ ] HTTPS configured (if required)
- [ ] Security headers configured in Nginx

---

## Performance Tuning (Optional)

### If you experience slow performance:

**1. Adjust Gunicorn workers:**
```ini
# In /etc/systemd/system/experiment-app.service
# Workers = (2 × CPU cores) + 1
--workers 5  # For 2 CPU cores
```

**2. Enable gzip compression in Nginx:**
```nginx
gzip on;
gzip_vary on;
gzip_types text/plain text/css application/json application/javascript text/xml;
```

**3. Add caching headers:**
```nginx
location /static/ {
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

---

## Updating the Application

```bash
# 1. Backup database first!
sudo /usr/local/bin/backup-experiment-app.sh

# 2. Switch to application user
sudo su - experiment-app

# 3. Activate virtual environment
cd /opt/experiment-app
source venv/bin/activate

# 4. Pull new code (if using Git)
cd /opt/experiment-app
git pull

# 5. Install any new dependencies
pip install -r requirements.txt

# 6. Run migrations
cd experiment_app
python manage.py migrate

# 7. Collect static files
python manage.py collectstatic --noinput

# 8. Exit and restart services
exit
sudo systemctl restart experiment-app
```

---

## Rollback Procedure

If something goes wrong:

```bash
# 1. Stop application
sudo systemctl stop experiment-app

# 2. Restore database backup
sudo cp /var/backups/experiment-app/db_YYYYMMDD_HHMMSS.sqlite3 \
       /opt/experiment-app/experiment_app/db.sqlite3

# 3. Restore previous code version (if using Git)
sudo su - experiment-app
cd /opt/experiment-app
git checkout <previous-commit>

# 4. Restart application
exit
sudo systemctl start experiment-app
```

---

## Contact & Support

**Application Developer**: [Your Name]  
**Email**: [your.email@institution.edu]  
**Phone**: [Your Phone]

**For urgent issues**: Available during business hours (9 AM - 5 PM)

---

## Appendix: File Permissions Reference

```bash
# Correct ownership and permissions
sudo chown -R experiment-app:www-data /opt/experiment-app/
sudo chmod -R 755 /opt/experiment-app/
sudo chmod 644 /opt/experiment-app/experiment_app/db.sqlite3
sudo chmod 755 /opt/experiment-app/experiment_app/
```

## Appendix: System Resource Usage

**Expected resource usage for 10 concurrent users:**
- CPU: 5-10%
- RAM: 200-300MB
- Disk I/O: Minimal (mostly reads)
- Network: <1 Mbps

**Database growth estimate:**
- ~1MB per 100 experiments
- ~10-50MB per year for typical lab

---

*Deployment tested on Ubuntu 22.04 LTS and RHEL 8*
