# Google Calendar Setup

1. Create a Google Cloud project.
2. Enable the Google Calendar API.
3. Create an OAuth client for a desktop app.
4. Save the client secret JSON at `/opt/data/google_client_secret.json`.
5. Run:

```bash
python3 scripts/oob_auth.py url
```

Open the URL, approve access, copy the code, then run:

```bash
python3 scripts/oob_auth.py code PASTE_CODE_HERE
```

The script writes `/opt/data/google_token.json`.

For unattended cron, publish the OAuth app when possible. Testing-mode refresh
tokens can expire quickly.
