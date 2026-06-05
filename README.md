# WeatherVault - AWS Weather Dashboard

A full-stack, AWS-powered real-time weather dashboard with secure credential management, cloud storage, and a stunning dark glassmorphism UI.

---

## Architecture

```
┌─────────────┐       ┌─────────────────────────────────────┐
│             │       │          EC2 (Ubuntu 22.04)         │
│   Browser   │──────▶│  ┌───────────┐    ┌──────────────┐ │
│  (Frontend) │       │  │   Nginx   │───▶│  Flask API   │ │
│             │◀──────│  │  (port 80)│    │  (port 5000) │ │
└─────────────┘       │  └───────────┘    └──────┬───────┘ │
                      └──────────────────────────┼─────────┘
                                                 │
                      ┌──────────────────────────┼─────────┐
                      │         AWS Services     │         │
                      │                          ▼         │
                      │  ┌──────────────────────────────┐  │
                      │  │      Secrets Manager         │  │
                      │  │  (API keys & credentials)    │  │
                      │  └──────────────────────────────┘  │
                      │                                    │
                      │  ┌──────────────────────────────┐  │
                      │  │           S3 Bucket           │  │
                      │  │  (configs, logs, assets)      │  │
                      │  └──────────────────────────────┘  │
                      │                                    │
                      │  ┌──────────────────────────────┐  │
                      │  │     OpenWeatherMap API        │  │
                      │  │   (weather data provider)     │  │
                      │  └──────────────────────────────┘  │
                      └────────────────────────────────────┘
```

**Flow:** Browser → Nginx → Flask → Secrets Manager → OpenWeatherMap API → S3 (log) → Response

---

## AWS Services Used

| Service | Details | Purpose |
|---------|---------|---------|
| **EC2** | t2.micro, Ubuntu 22.04 LTS | Hosts Flask API + Nginx reverse proxy |
| **S3** | Standard bucket | Stores app config, weather logs, assets |
| **Secrets Manager** | Single secret | Stores API keys & credentials securely |

---

## Project Structure

```
weather-dashboard/
├── README.md
├── .gitignore
├── setup_secrets.py          # One-time: create secret in AWS
├── ec2_userdata.sh           # EC2 bootstrap script
│
├── backend/
│   ├── app.py                # Flask REST API (11 routes)
│   ├── secrets_manager.py    # Singleton secrets client + cache
│   ├── s3_manager.py         # S3 operations + cache
│   └── requirements.txt      # Python dependencies
│
├── frontend/
│   ├── index.html            # Dashboard UI
│   ├── style.css             # Dark glassmorphism styles
│   └── app.js                # Frontend logic (async/await)
│
└── s3_setup/
    ├── setup_s3.py           # One-time: create bucket + upload configs
    ├── cities.json           # Featured cities data
    └── upload_assets.py      # Upload images/assets to S3
```

---

## Prerequisites

- **AWS Account** with IAM user or role having:
  - `SecretsManagerReadWrite`
  - `AmazonS3FullAccess`
- **OpenWeatherMap** free API key → [Get one here](https://openweathermap.org/api)
- **Python 3.10+**
- **AWS CLI** configured (`aws configure`)

---

## Local Setup (Step by Step)

### Step 1: Clone Repository

```bash
git clone YOUR_REPO_URL
cd weather-dashboard
```

### Step 2: Install Dependencies

```bash
cd backend
pip install -r requirements.txt
cd ..
```

### Step 3: Configure AWS Credentials Locally

```bash
aws configure
```

Enter your:
- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., `us-east-1`)
- Output format: `json`

### Step 4: Create Secret in AWS Secrets Manager

Open `setup_secrets.py` and replace these placeholders:

| Placeholder | Replace With |
|-------------|-------------|
| `PASTE_YOUR_OPENWEATHERMAP_KEY` | Your OpenWeatherMap API key |
| `PASTE_YOUR_BUCKET_NAME` | Your S3 bucket name (e.g., `my-weather-app-bucket-12345`) |

Then run:

```bash
python setup_secrets.py
```

### Step 5: Create S3 Bucket and Upload Configs

Open `s3_setup/setup_s3.py` and replace:

| Placeholder | Replace With |
|-------------|-------------|
| `PASTE_YOUR_BUCKET_NAME_HERE` | Your S3 bucket name (same as Step 4) |

Then run:

```bash
python s3_setup/setup_s3.py
```

### Step 6: Run Locally

```bash
cd backend
python app.py
```

Then open `frontend/index.html` with VS Code **Live Server** extension or any local HTTP server.

> **Note:** The Flask API runs on `http://localhost:5000`. The frontend `app.js` is configured to use this URL by default.

---

## EC2 Ubuntu Deployment (Step by Step)

### Step 1: Push This Repo to GitHub

```bash
git init
git add .
git commit -m "Initial commit - WeatherVault"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### Step 2: Create EC2 Instance in AWS Console

1. Go to **EC2 Dashboard → Launch Instance**
2. Configure:

| Setting | Value |
|---------|-------|
| **Name** | WeatherVault-Server |
| **AMI** | Ubuntu 22.04 LTS (Free tier eligible) |
| **Instance type** | t2.micro (Free tier) |
| **Key pair** | Create new → Download `.pem` file |
| **Security Group** | Create new with these inbound rules: |

**Security Group Inbound Rules:**

| Type | Port | Source |
|------|------|--------|
| SSH | 22 | My IP |
| HTTP | 80 | 0.0.0.0/0 |
| Custom TCP | 5000 | 0.0.0.0/0 |

3. **IAM Instance Profile:** Click "Advanced details" → IAM instance profile → Select/create a role with:
   - `SecretsManagerReadWrite`
   - `AmazonS3FullAccess`

4. **User Data:** In "Advanced details" → User data, paste the contents of `ec2_userdata.sh`

   ⚠️ **IMPORTANT:** First replace `GITHUB_REPO_URL` in the script with your actual GitHub repo URL:
   ```
   git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git weather-dashboard
   ```

5. Click **Launch Instance**

### Step 3: Update Frontend API URL

Before pushing to GitHub, edit `frontend/app.js` line 1:

```javascript
// Change FROM:
const API = 'http://localhost:5000/api';

// Change TO:
const API = 'http://YOUR_EC2_PUBLIC_IP/api';
```

Then push the change:

```bash
git add .
git commit -m "Update API URL for EC2 deployment"
git push
```

### Step 4: Wait for EC2 to Boot

Wait approximately **5 minutes** for the EC2 instance to:
- Boot up
- Run the user data script
- Install dependencies
- Clone your repo
- Start Flask and Nginx

### Step 5: Visit Your App

Open in browser:

```
http://YOUR_EC2_PUBLIC_IP
```

### Step 6: Check Logs if Issues

SSH into the instance:

```bash
ssh -i your-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

Check logs:

```bash
# User data script log
cat /var/log/weather-app-setup.log

# Flask app logs
sudo journalctl -u weatherapp -f

# Nginx logs
sudo journalctl -u nginx -f
```

---

## API Routes

| Method | Route | Description | Source |
|--------|-------|-------------|--------|
| `GET` | `/api/health` | EC2, Secrets Manager, S3 status | All services |
| `GET` | `/api/weather/current?city=London` | Current weather for a city | Secrets Manager → OpenWeatherMap → S3 |
| `GET` | `/api/weather/forecast?city=London` | 5-step forecast | Secrets Manager → OpenWeatherMap |
| `GET` | `/api/cities` | Featured cities list | S3 |
| `GET` | `/api/weather-tip?condition=rainy` | Weather tip for condition | S3 |
| `GET` | `/api/s3/info` | Bucket stats & folder breakdown | S3 |
| `GET` | `/api/s3/weather-history` | All recent search logs | S3 |
| `GET` | `/api/s3/files?prefix=` | List files with prefix filter | S3 |
| `GET` | `/api/secrets/info` | Secret metadata (never values!) | Secrets Manager |
| `POST` | `/api/cache/clear` | Clear Secrets + S3 caches | Internal |
| `GET` | `/api/app-info` | App metadata from S3 | S3 |

---

## Useful Commands on EC2

```bash
# Check Flask service status
sudo systemctl status weatherapp

# Restart Flask service
sudo systemctl restart weatherapp

# Check Nginx status
sudo systemctl status nginx

# Follow Flask logs in real-time
sudo journalctl -u weatherapp -f

# View user data setup log
cat /var/log/weather-app-setup.log
```

---

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| **502 Bad Gateway** | Flask not running | `sudo systemctl restart weatherapp` |
| **Secret not found** | Secret not created | Run `python setup_secrets.py` first |
| **S3 permission denied** | Missing IAM permissions | Attach `AmazonS3FullAccess` to EC2 IAM role |
| **Weather API 401** | API key not activated | Wait 15 minutes for OpenWeatherMap key activation |
| **Port 5000 not reachable** | Security group missing rule | Add Custom TCP port 5000 inbound rule |
| **App not starting** | Wrong Python path | Check venv path in systemd service file |
| **Nginx test fails** | Config syntax error | Run `sudo nginx -t` to see the error |
| **Clone fails** | Wrong repo URL | Verify GITHUB_REPO_URL in ec2_userdata.sh |

---

## Placeholders Quick Reference

| File | Placeholder | Replace With |
|------|-------------|-------------|
| `setup_secrets.py` | `PASTE_YOUR_OPENWEATHERMAP_KEY` | Your OpenWeatherMap API key |
| `setup_secrets.py` | `PASTE_YOUR_BUCKET_NAME` | Your S3 bucket name |
| `s3_setup/setup_s3.py` | `PASTE_YOUR_BUCKET_NAME_HERE` | Your S3 bucket name |
| `s3_setup/upload_assets.py` | `PASTE_YOUR_BUCKET_NAME_HERE` | Your S3 bucket name |
| `ec2_userdata.sh` | `GITHUB_REPO_URL` | Your GitHub repo URL |
| `frontend/app.js` | `http://localhost:5000/api` | `http://YOUR_EC2_PUBLIC_IP/api` (for EC2) |

---

## Tech Stack

- **Backend:** Python Flask 3.0
- **Frontend:** Vanilla HTML + CSS + JavaScript
- **Cloud:** AWS (EC2 + S3 + Secrets Manager)
- **Weather API:** OpenWeatherMap
- **Server:** Nginx + Flask (Gunicorn-ready)
- **OS:** Ubuntu 22.04 LTS

---

*Built with ❤️ and powered by AWS*
