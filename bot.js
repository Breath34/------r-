// Use puppeteer-extra with plugins for ad blocking and stealth
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const AdblockerPlugin = require('puppeteer-extra-plugin-adblocker');

// Add stealth plugin to avoid detection
puppeteer.use(StealthPlugin());

// Add adblocker plugin with aggressive blocking
puppeteer.use(AdblockerPlugin({
  blockTrackers: true,  // Block trackers
  blockTrackersAndAnnoyances: true,  // Block additional annoyances
  interceptResolutionPriority: 0  // Higher priority for intercepting requests
}));

// Configuration
const config = {
  baseUrl: 'https://gpanel.eternalzero.cloud',
  serverUrl: `https://gpanel.eternalzero.cloud/server/${process.env.SERVER_ID || '2005f497'}`,
  // Session cookie to use instead of logging in
  sessionCookie: process.env.PTERODACTYL_SESSION || 'eyJpdiI6IjdMNXloQnZBcjZtZkU0VnB3bGNmNnc9PSIsInZhbHVlIjoiWjhZNFBwMWNlOThuMjFKaDF1ZjJTbWl2QWdOWFNDbitDcTRORzVjSVZZeTU5bkJUU3g2NEJKUHRkZFcvQ1NXaldRZERFamtQZmc1bisyQ01DM1Bia2pKSVcraVB5SWhrU1BkbTRadWtyMkdnQWNEb0FsMlZlY1crS2FrNExJakIiLCJtYWMiOiI3MDRjNzAxZTBkOGZhZmIzZTczODUxZTc1ZTk2Zjc3M2VjYWUwN2VhNDAwZTViNDIxMGFhMTI0MDg2NDRjZjBiIiwidGFnIjoiIn0%3D',
  selectors: {
    renewButton: 'button:has-text("ADD 4H")'  // Will use page.evaluate for text-based selection
  },
  // Check if running in CI/CD environment
  isCI: process.env.CI === 'true' || process.env.GITHUB_ACTIONS === 'true'
};

// Utility function to wait
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function autoRenewServer() {
  let browser;
  
  try {
    console.log('🚀 Starting server auto-renewal bot with ad blocker...');
    console.log('🛡️ Ad blocker and stealth mode enabled');
    
    if (config.isCI) {
      console.log('📦 Running in CI/CD environment (headless mode)');
    }
    
    // Launch browser with enhanced options
    browser = await puppeteer.launch({
      headless: config.isCI ? 'new' : true, // Use 'new' headless mode in CI, visible browser locally
      defaultViewport: null,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--no-first-run',
        '--no-zygote',
        '--disable-gpu',
        '--disable-web-security',
        '--disable-features=IsolateOrigins,site-per-process',
        '--disable-blink-features=AutomationControlled'
      ]
    });

    const page = await browser.newPage();
    
    // Additional stealth configurations
    await page.evaluateOnNewDocument(() => {
      // Remove webdriver property
      Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
      });
      
      // Mock plugins and languages
      Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5]
      });
      
      Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en']
      });
    });
    
    // Set user agent to avoid detection
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
    
    // Log blocked ads count (optional)
    page.on('request', (request) => {
      if (request.isInterceptResolutionHandled()) {
        const url = request.url();
        if (url.includes('doubleclick') || url.includes('googleads') || url.includes('googlesyndication')) {
          console.log('🚫 Blocked ad:', url.substring(0, 50) + '...');
        }
      }
    });
    
    // Step 1: Set the session cookie to bypass login
    console.log('🍪 Setting Pterodactyl session cookie...');
    await page.setCookie({
      name: 'pterodactyl_session',
      value: decodeURIComponent(config.sessionCookie), // Decode the URL-encoded cookie value
      domain: 'gpanel.eternalzero.cloud',
      path: '/',
      httpOnly: true,
      secure: true,
      sameSite: 'Lax'
    });
    console.log('✅ Session cookie set successfully');
    
    // Step 2: Navigate directly to server page
    console.log('📍 Navigating to server page...');
    console.log(`🔗 Server URL: ${config.serverUrl}`);
    await page.goto(config.serverUrl, {
      waitUntil: 'networkidle2',
      timeout: 30000
    });
    
    // Wait for page to load completely
    await delay(3000);
    
    // Step 3: Find and click the "ADD 4H" button
    console.log('🔍 Looking for renewal button...');
    
    // Try multiple methods to find and click the button
    const buttonClicked = await page.evaluate(() => {
      // Method 1: Find button by text content
      const buttons = Array.from(document.querySelectorAll('button'));
      const renewButton = buttons.find(button => 
        button.textContent.includes('ADD 4H') || 
        button.innerText.includes('ADD 4H')
      );
      
      if (renewButton) {
        // Check if button is disabled
        if (renewButton.disabled) {
          console.log('⚠️ Renewal button is disabled. It might not be time to renew yet.');
          return { clicked: false, disabled: true };
        }
        renewButton.click();
        return { clicked: true, disabled: false };
      }
      
      // Method 2: Try with the specific class
      const buttonByClass = document.querySelector('.RenewBox__RenewButton-sc-1inh2rq-6');
      if (buttonByClass) {
        if (buttonByClass.disabled) {
          console.log('⚠️ Renewal button is disabled. It might not be time to renew yet.');
          return { clicked: false, disabled: true };
        }
        buttonByClass.click();
        return { clicked: true, disabled: false };
      }
      
      return { clicked: false, disabled: false, notFound: true };
    });
    
    if (buttonClicked.clicked) {
      console.log('✅ Successfully clicked the renewal button!');
      // Wait for the action to complete
      await delay(5000);
      
      // Take a screenshot for confirmation
      await page.screenshot({ 
        path: 'renewal-confirmation.png',
        fullPage: true 
      });
      console.log('📸 Screenshot saved as renewal-confirmation.png');
    } else if (buttonClicked.disabled) {
      console.log('⚠️ Renewal button is disabled. The server might not need renewal at this time.');
      await page.screenshot({ 
        path: 'renewal-button-disabled.png',
        fullPage: true 
      });
      console.log('📸 Screenshot saved as renewal-button-disabled.png');
    } else if (buttonClicked.notFound) {
      console.log('❌ Could not find the renewal button on the page.');
      await page.screenshot({ 
        path: 'renewal-button-not-found.png',
        fullPage: true 
      });
      console.log('📸 Screenshot saved as renewal-button-not-found.png');
    }
    
    console.log('✨ Bot execution completed!');
    
  } catch (error) {
    console.error('❌ An error occurred:', error.message);
    console.error('Stack trace:', error.stack);
    
    // Try to take a screenshot of the error state
    if (browser) {
      const pages = await browser.pages();
      if (pages.length > 0) {
        await pages[0].screenshot({ 
          path: 'error-screenshot.png',
          fullPage: true 
        }).catch(() => console.log('Could not take error screenshot'));
      }
    }
  } finally {
    // Close browser
    if (browser) {
      console.log('🔚 Closing browser...');
      await browser.close();
    }
  }
}

// Main execution
if (require.main === module) {
  console.log('━'.repeat(50));
  console.log('🤖 EternalZero Server Auto-Renewal Bot');
  console.log('━'.repeat(50));
  
  // Log configuration (without sensitive data)
  console.log('📋 Configuration:');
  console.log(`  • Authentication: Using Pterodactyl session cookie`);
  console.log(`  • Server URL: ${config.serverUrl}`);
  console.log(`  • Environment: ${config.isCI ? 'CI/CD' : 'Local'}`);
  console.log('━'.repeat(50));
  
  // Run the bot
  autoRenewServer()
    .then(() => {
      console.log('━'.repeat(50));
      console.log('✅ Bot execution completed successfully');
      process.exit(0);
    })
    .catch((error) => {
      console.error('━'.repeat(50));
      console.error('❌ Bot execution failed:', error);
      process.exit(1);
    });
}

// Export for testing
module.exports = { autoRenewServer };

// Schedule to run periodically (optional)
// To enable scheduling:
// 1. Install node-cron: npm install node-cron
// 2. Uncomment and use the following code:
//
// const schedule = require('node-cron');
//
// // Run every 3 hours
// schedule.schedule('0 */3 * * *', () => {
//   console.log('⏰ Running scheduled renewal...');
//   autoRenewServer().catch(console.error);
// });
//
// console.log('📅 Scheduler started. Bot will run every 3 hours.');
// console.log('🏃 Running initial check...');
// autoRenewServer().catch(console.error);
