// ===========================
//      CONFIGURATION
// ===========================

const CONFIG = {
    baseUrl: "https://gpanel.eternalzero.cloud",
    
    // Your working token
    pteroSession: "eyJpdiI6InVmNWxHbjg4VmNmcEkzR05aSi9yUlE9PSIsInZhbHVlIjoiZUtNWHFNYW1hcDBLR0ZRNFdZbUNhNVlqT09nUWdHejcvY0kvTWFnSlR3dksvTDU2blRsSE92NWIyOHVxanZKalZsbThNaUFGaGVuR1p2blVSbnFkckR2Q0EzcEJOdDFDdWVSaXRKTzhUWFlpV1hrZHEyZzQvNzI4eUg3R3NJYi8iLCJtYWMiOiI5ODYwNzkyYzQwYTk0NjBhZmFlMTQ0ZWNmNDNmODg2YzNhNTQwMWFkMWYxZDRjZDAyOTNlMzE4OWJmMWYwYzgxIiwidGFnIjoiIn0%3D",
    
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
};

// ===========================
//      LOGIC
// ===========================

async function run() {
    console.log(`[Bot] Initializing Parallel Mode...`);

    // 1. HANDSHAKE
    const handshakeReq = await fetch(CONFIG.baseUrl, {
        method: "GET",
        headers: {
            "Cookie": `pterodactyl_session=${CONFIG.pteroSession}`,
            "User-Agent": CONFIG.userAgent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        },
        redirect: "manual"
    });

    const setCookies = handshakeReq.headers.getSetCookie();
    const xsrfCookieRaw = setCookies.find(c => c.startsWith("XSRF-TOKEN="));

    if (!xsrfCookieRaw) {
        console.error("❌ Handshake Failed: Invalid Session.");
        return;
    }

    const xsrfToken = xsrfCookieRaw.split(';')[0].replace("XSRF-TOKEN=", "");
    const xsrfTokenDecoded = decodeURIComponent(xsrfToken);

    console.log("✅ Handshake Successful.");

    // 2. SETUP HEADERS
    const apiHeaders = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Cookie": `pterodactyl_session=${CONFIG.pteroSession}; XSRF-TOKEN=${xsrfToken}`,
        "X-Requested-With": "XMLHttpRequest",
        "X-XSRF-TOKEN": xsrfTokenDecoded,
        "User-Agent": CONFIG.userAgent,
        "Origin": CONFIG.baseUrl,
        "Referer": `${CONFIG.baseUrl}/`
    };

    // 3. FETCH LIST
    console.log("📂 Fetching server list...");
    const listRes = await fetch(`${CONFIG.baseUrl}/api/client?page=1`, { headers: apiHeaders });
    
    if (!listRes.ok) {
        console.error(`❌ List Fetch Failed: ${listRes.status}`);
        return;
    }

    const data = await listRes.json();
    const servers = data.data || [];

    console.log(`🔎 Found ${servers.length} servers. Launching parallel requests...`);

    // 4. PARALLEL EXECUTION (The Fast Part)
    // We map every server to a renewal Promise and fire them all at once.
    const renewalPromises = servers.map(async (server) => {
        const name = server.attributes.name;
        const uuid = server.attributes.uuid;

        try {
            const res = await fetch(`${CONFIG.baseUrl}/api/client/freeservers/${uuid}/renew`, {
                method: "POST",
                body: "{}",
                headers: apiHeaders
            });

            if (res.ok) {
                console.log(`   ✅ RENEWED: ${name}`);
            } else {
                console.log(`   ⚠️ FAILED: ${name} (Status: ${res.status})`);
            }
        } catch (err) {
            console.log(`   ❌ ERROR: ${name} - ${err.message}`);
        }
    });

    // Wait for all the bullets to hit
    await Promise.all(renewalPromises);
    
    console.log("👋 All operations finished.");
}

run();
