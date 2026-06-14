# DigitalOcean Production Deployment Guide

This guide explains how to deploy the Tesla Nord Pool backend, database, and telemetry infrastructure to a DigitalOcean Droplet using GitHub Actions for fully automated CI/CD.

## Architecture
We use a single Droplet to run all application containers via `docker-compose.prod.yml`, and a separate Managed Database:
1. **Caddy**: A reverse proxy that automatically provisions Let's Encrypt SSL certificates for your API.
2. **Managed Postgres**: The database hosted via DigitalOcean Managed Databases.
3. **Backend**: The FastAPI Python application.
4. **MQTT**: The Mosquitto broker for internal telemetry message routing.
5. **Fleet Telemetry**: The Tesla Go binary, listening on port `4443` for incoming mTLS connections from the cars.

## Step 1: Create the Managed Database
For production reliability, backups, and point-in-time recovery, we use a Managed Database instead of a Docker container:
1. Go to your DigitalOcean dashboard.
2. Click **Create** -> **Databases**.
3. Choose **PostgreSQL**.
4. Choose the smallest plan (e.g., $15/mo) to start.
5. Click **Create Database Cluster**.
6. Once provisioned, find the "Connection Details" string and copy the `Connection String` (starts with `postgresql://...`). You will place this in your Droplet's `.env` file as `DATABASE_URL`.

## Step 2: Create the Droplet
1. Go to your DigitalOcean dashboard.
2. Click **Create** -> **Droplets**.
3. Choose a region closest to your users.
4. Under **Choose an image**, click the **Marketplace** tab and search for **Docker** (this provisions a server with Docker and Docker Compose pre-installed).
5. Choose a basic plan (e.g., $6/mo Regular Intel).
6. Under Authentication, select **SSH Key** and add your personal SSH key.
7. Click **Create Droplet**.

## Step 3: Configure DNS
Once the Droplet is created, copy its IPv4 address.
Go to your domain registrar (e.g., GoDaddy, Cloudflare) and create two **A Records** pointing to the Droplet's IP:
- `api.charging.clankersystems.com`
- `telemetry.charging.clankersystems.com`

## Step 4: First-time Server Setup
SSH into your new Droplet from your terminal:
```bash
ssh root@<DROPLET_IP>
```

1. **Create the deployment directory:**
   ```bash
   mkdir -p /opt/teslacharger
   cd /opt/teslacharger
   ```
2. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/teslacharger.git .
   ```
   *(Note: If your repo is private, you will need to generate an SSH key on the Droplet using `ssh-keygen` and add it to your GitHub Repository's "Deploy Keys").*

3. **Copy your secrets:**
   You must securely copy your `.env` file and your generated Tesla `.pem` keys into `/opt/teslacharger/backend/` and your telemetry certificates into `/opt/teslacharger/telemetry/certs/`. DO NOT commit these to git!

4. **Start the server manually the first time:**
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```
   *Note: Because we removed the Postgres container from the production compose file, the backend will automatically connect to your Managed Database using the `DATABASE_URL` you provided in `.env`.*
   
   Caddy will automatically fetch your SSL certificates for `api.charging...`.

## Step 5: GitHub Actions Setup
Now we want GitHub to automatically SSH into the server and run the deploy script every time you push to the `main` branch.

1. Go to your repository on GitHub.
2. Go to **Settings** -> **Secrets and variables** -> **Actions**.
3. Click **New repository secret**.
4. Add the following two secrets:
   - **`DROPLET_IP`**: The IPv4 address of your Droplet.
   - **`DROPLET_SSH_KEY`**: The raw text of the *private* SSH key (`~/.ssh/id_rsa`) that you used to create the Droplet in Step 2.

## Step 6: You're Done!
From now on, whenever you run:
```bash
git push origin main
```
GitHub Actions will automatically run the `.github/workflows/deploy.yml` pipeline. It will SSH into your server, pull the latest code, and restart the Docker containers in the background with zero downtime!