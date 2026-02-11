# Online Access Setup

This guide explains how to make your Aeroponic Database accessible from the internet so that others (e.g., a professor or remote team) can access it.

## Overview

| Method | Free | Signup Required | Permanent URL | Recommended |
|--------|------|-----------------|---------------|-------------|
| Cloudflare Tunnel | Yes | No | No | Best |
| Ngrok | Yes (limited) | Yes | No | Alternative |

---

## Method 1: Cloudflare Tunnel (Recommended)

### Advantages
- 100% free with no usage limits
- No account signup required
- Automatic HTTPS
- Already integrated into the application

### Installation

`start.sh` automatically downloads cloudflared during setup. If you need to install it manually:

```bash
# x86_64 (PC/Server)
wget -q "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64" -O src/cloudflared

# Raspberry Pi (ARM64)
wget -q "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64" -O src/cloudflared

# Raspberry Pi (ARM32)
wget -q "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm" -O src/cloudflared

chmod +x src/cloudflared
```

### Usage

**Option A: Use the web interface (easiest)**
1. Start the server: `bash start.sh`
2. Open https://localhost:8443/online
3. Click **Start Online Access**
4. Copy the generated URL and share it

**Option B: Use the command line**
```bash
./src/cloudflared tunnel --url http://localhost:8443
```
The tunnel URL will appear in the output (e.g., `https://random-words.trycloudflare.com`).

### Share with Others
- Copy the tunnel URL and send it to anyone who needs access
- The URL changes each time the tunnel is restarted
- The tunnel only works while `cloudflared` is running

---

## Method 2: Ngrok

### Limitations (Free Tier)
- Requires account signup
- URL changes on each restart
- Connection limits apply

### Installation

1. Go to https://ngrok.com/download and sign up
2. Download and extract `ngrok`
3. Add your auth token:
   ```bash
   ngrok config add-authtoken YOUR_TOKEN_FROM_DASHBOARD
   ```

### Usage

1. Start the Flask server first: `bash start.sh`
2. In a second terminal:
   ```bash
   ngrok http 8443
   ```
3. Copy the URL from the ngrok output

---

## Folder Watcher (Auto-Import)

The folder watcher monitors a directory and automatically imports new images.

```bash
source .venv/bin/activate

# Watch a folder and auto-import new images
python scripts/folder_watcher.py --watch "/path/to/camera/output" --category "Aeroponic System 1"

# Scan existing files first, then watch for new ones
python scripts/folder_watcher.py --watch "/path/to/photos" --category "Tray A" --scan
```

### Options

| Option | Description |
|--------|-------------|
| `--watch, -w` | Folder to monitor |
| `--category, -c` | Category name for imported images |
| `--scan, -s` | Scan existing files before watching |
| `--quiet, -q` | Silent mode |

---

## Full Production Setup

To run all services simultaneously:

1. **Terminal 1:** Start the Flask server
   ```bash
   bash start.sh
   ```

2. **Terminal 2:** Start the Cloudflare Tunnel (optional, for online access)
   ```bash
   ./src/cloudflared tunnel --url http://localhost:8443
   ```

3. **Terminal 3:** Start the Folder Watcher (optional, for auto-import)
   ```bash
   source .venv/bin/activate
   python scripts/folder_watcher.py --watch "/path/to/images" --category "System 1"
   ```

---

## FAQ

**Q: Does the URL change every time I restart the tunnel?**
A: Yes. For a permanent URL, you need a paid Cloudflare plan or a custom domain.

**Q: Does the system still work if I turn off my computer?**
A: No. The server and tunnel must be running for online access.

**Q: Can I run multiple Folder Watchers?**
A: Yes. Open separate terminals for each watched folder.

**Q: What file types are supported?**
A: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`
