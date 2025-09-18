# Camera Dashboard

A self-hosted web application for managing and viewing IP camera streams. This dashboard provides a central interface to monitor multiple cameras, record clips, and control ONVIF-compatible cameras.

## Key Features

- **Centralized Dashboard:** View all your camera streams in a single, clean interface.
- **ONVIF Support:** Connect to and control ONVIF-compatible cameras for features like PTZ (Pan-Tilt-Zoom).
- **Stream Processing:** Uses FFmpeg to process RTSP streams and provide them as HLS streams for easy web viewing.
- **Recording:** Manually trigger recordings of camera streams.
- **Motion Detection:** (Optional) Configure motion detection to trigger recordings automatically.
- **Secure API:** The backend API is secured with a shared token, and the application is designed to be run behind a reverse proxy like a Cloudflare Tunnel for secure external access.
- **Cross-Platform:** The application is written in Python and can be run on both Windows (via WSL) and Linux.

## Setup and Installation

This guide provides instructions for setting up the application on Windows (using WSL) and on a dedicated Ubuntu Server.

### Option 1: Running on Windows with WSL (Windows Subsystem for Linux)

These instructions assume you have WSL installed with an Ubuntu distribution.

**1. Prerequisites:**
   - Windows 10 or 11 with WSL2 installed.
   - An Ubuntu distribution installed from the Microsoft Store.
   - `git` installed in your Ubuntu environment (`sudo apt update && sudo apt install git`).

**2. Install System Dependencies:**
   Open your Ubuntu terminal and install Python, pip, and FFmpeg.
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-pip python3-venv ffmpeg
   ```

**3. Clone the Repository:**
   Clone this repository to a location of your choice within your Ubuntu environment.
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

**4. Set Up a Python Virtual Environment:**
   It is highly recommended to use a virtual environment to manage dependencies.
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
   Your terminal prompt should now be prefixed with `(.venv)`.

**5. Install Python Dependencies:**
   Install the required Python packages using pip.
   ```bash
   pip install -r requirements.txt
   ```

**6. Configure the Application:**
   The application uses a single `API_TOKEN` for securing the API. You need to create a `.env` file to store this token.

   First, generate a secure random token:
   ```bash
   python3 -c 'import secrets; print(secrets.token_hex(32))'
   ```
   Copy the generated token.

   Now, create the `.env` file:
   ```bash
   nano .env
   ```
   Add the following line to the file, replacing `<your-generated-token>` with the token you just copied:
   ```
   API_TOKEN=<your-generated-token>
   ```
   Save the file and exit (Ctrl+X, then Y, then Enter).

**7. Run the Application:**
   You can now start the Flask web server.
   ```bash
   python3 main.py
   ```
   The application will be running at `http://localhost:5000`. Open this URL in your web browser on Windows.

### Option 2: Running on a Dedicated Ubuntu Server

The process for a dedicated Ubuntu Server is very similar to the WSL setup.

**1. Prerequisites:**
   - A server running Ubuntu Server 20.04 LTS or later.
   - SSH access to the server.
   - `git` installed (`sudo apt update && sudo apt install git`).

**2. Install System Dependencies:**
   Connect to your server via SSH and install Python, pip, and FFmpeg.
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-pip python3-venv ffmpeg
   ```

**3. Clone the Repository:**
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

**4. Set Up a Python Virtual Environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

**5. Install Python Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

**6. Configure the Application:**
   Generate and configure the `API_TOKEN` in a `.env` file, just as in the WSL instructions.
   ```bash
   python3 -c 'import secrets; print(secrets.token_hex(32))'
   # Copy the token
   nano .env
   # Add API_TOKEN=<your-token> to the file and save
   ```

**7. Run the Application:**
   For development or testing, you can run the application directly:
   ```bash
   python3 main.py
   ```
   The application will be running on `http://<your-server-ip>:5000`.

   **For Production:**
   For long-term use, it is recommended to run the application as a systemd service to ensure it runs automatically on boot and restarts if it crashes. You would typically use a production-ready WSGI server like Gunicorn or uWSGI for this. A full guide for setting this up is beyond the scope of this README, but it would involve creating a systemd service file and configuring a WSGI server.
