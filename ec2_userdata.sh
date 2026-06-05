#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# WeatherVault - EC2 User Data Script
# Ubuntu 22.04 LTS | t2.micro
# ═══════════════════════════════════════════════════════════════
# This script runs automatically on EC2 first boot.
# It installs all dependencies, clones the repo, sets up
# the Flask app with systemd, and configures Nginx.
#
# IMPORTANT: Replace GITHUB_REPO_URL below with your actual
# GitHub repository URL before pasting into EC2 User Data.
# ═══════════════════════════════════════════════════════════════

set -e
exec > /var/log/weather-app-setup.log 2>&1

echo "════════════════════════════════════════════════════════"
echo "  WeatherVault EC2 Setup - Starting..."
echo "  Timestamp: $(date)"
echo "════════════════════════════════════════════════════════"

# ─── Step 1: System Update ───────────────────────────────────
echo "[1/12] Updating system packages..."
apt-get update -y
apt-get upgrade -y

# ─── Step 2: Install Dependencies ────────────────────────────
echo "[2/12] Installing Python3, Git, Nginx, Curl..."
apt-get install -y python3 python3-pip python3-venv git nginx curl

# ─── Step 3: Clone Repository ────────────────────────────────
echo "[3/12] Cloning repository..."
cd /home/ubuntu
git clone GITHUB_REPO_URL weather-dashboard

# ─── Step 4: Setup Python Virtual Environment ────────────────
echo "[4/12] Setting up Python virtual environment..."
cd /home/ubuntu/weather-dashboard/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# ─── Step 5: Fix Permissions ─────────────────────────────────
echo "[5/12] Setting file ownership..."
chown -R ubuntu:ubuntu /home/ubuntu/weather-dashboard

# ─── Step 6: Create Systemd Service ──────────────────────────
echo "[6/12] Creating systemd service for WeatherVault..."
cat > /etc/systemd/system/weatherapp.service << 'EOF'
[Unit]
Description=WeatherVault Flask App
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/weather-dashboard/backend
Environment=PATH=/home/ubuntu/weather-dashboard/backend/venv/bin
ExecStart=/home/ubuntu/weather-dashboard/backend/venv/bin/python3 app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# ─── Step 7: Enable and Start Flask Service ───────────────────
echo "[7/12] Starting WeatherVault service..."
systemctl daemon-reload
systemctl enable weatherapp
systemctl start weatherapp

# ─── Step 8: Remove Default Nginx Config ─────────────────────
echo "[8/12] Removing default Nginx configuration..."
rm -f /etc/nginx/sites-enabled/default

# ─── Step 9: Create Nginx Config ─────────────────────────────
echo "[9/12] Creating Nginx configuration..."
cat > /etc/nginx/sites-available/weatherapp << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        root /home/ubuntu/weather-dashboard/frontend;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
    }
}
EOF

# ─── Step 10: Enable Nginx Config ────────────────────────────
echo "[10/12] Enabling Nginx site configuration..."
ln -s /etc/nginx/sites-available/weatherapp /etc/nginx/sites-enabled/weatherapp

# ─── Step 11: Test and Restart Nginx ─────────────────────────
echo "[11/12] Testing and restarting Nginx..."
nginx -t
systemctl enable nginx
systemctl restart nginx

# ─── Step 12: Print Completion Info ──────────────────────────
echo "[12/12] Setup complete!"
echo ""
echo "════════════════════════════════════════════════════════"
echo "  WeatherVault - Setup Complete!"
echo "════════════════════════════════════════════════════════"
echo ""
echo "Setup complete!"
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
echo "Public IP: $PUBLIC_IP"
echo "App URL: http://$PUBLIC_IP"
echo "Health: http://$PUBLIC_IP/api/health"
echo "Logs: sudo journalctl -u weatherapp -f"
echo ""
echo "════════════════════════════════════════════════════════"
