#!/bin/bash

# --- SYSTEM OPTIMIZATION (Essential for 1GB RAM) ---
echo "🚀 Optimizing system for 1GB RAM (Adding 2GB Swap)..."
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# --- UPDATE & INSTALL DEPENDENCIES ---
echo "🔄 Updating system and installing dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv postgresql postgresql-contrib libpq-dev build-essential

# --- SETUP DATABASE ---
echo "🐘 Setting up local PostgreSQL..."
sudo -u postgres psql -c "CREATE USER river_user WITH PASSWORD 'river_password_123';"
sudo -u postgres psql -c "CREATE DATABASE river_levels OWNER river_user;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE river_levels TO river_user;"

# --- SETUP APP DIRECTORY ---
echo "📁 Setting up application directory..."
mkdir -p ~/app
# (Files will be uploaded via SCP in the next step)

echo "✅ System ready! Please upload your project files from your Mac now."
echo "Use this command on your Mac: scp -r -i ~/.ssh/river-key.pem ./* azureuser@$(hostname -I | awk '{print $1}'):~/app"
