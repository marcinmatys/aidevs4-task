# Using ngrok for Tasks

Some tasks (like `S01E03`) require a public endpoint for the Hub to communicate with your local machine. This is where **ngrok** comes in.

## 1. Installation & Setup

1. **Install ngrok** (if not already installed):
   - **Windows (via Chocolatey):** `choco install ngrok`
   - **Manual:** Download from [ngrok dashboard](https://dashboard.ngrok.com/get-started/setup/windows).

2. **Upgrade** (optional):
   ```powershell
   choco upgrade ngrok
   ```

3. **Authenticate**:
   Get your authtoken from the ngrok dashboard and run:
   ```powershell
   ngrok config add-authtoken YOUR_AUTHTOKEN
   ```

## 2. Start the Tunnel

Start a tunnel on the port used by your local proxy server (default is `5000`):

```powershell
ngrok http 5000
```

Once started, ngrok will provide a **Forwarding** URL, for example: `https://xxxx-xxxx.ngrok-free.app`.

## 3. Configuration

Copy the **Forwarding URL** and paste it into your `.env` file:

```env
PROXY_BASE_URL=https://xxxx-xxxx.ngrok-free.app
```

## 4. Running a Task with Proxy

### Step 1: Start the Proxy Server
Each task that requires ngrok will have a `proxy_server.py`. Run it in a separate terminal:

```powershell
uv run tasks/S01E03/proxy_server.py
```

### Step 2: Run the Main Task
In another terminal, run the task as usual:

```powershell
uv run main.py --dict "S01E03" --task "S01E03"
```

---
**Note:** Keep both the `ngrok` tunnel and the `proxy_server.py` running while the task is being executed.
