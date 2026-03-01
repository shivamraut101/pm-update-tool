require("dotenv").config();
const { Client, LocalAuth, MessageMedia } = require("whatsapp-web.js");
const express = require("express");
const multer = require("multer");
const axios = require("axios");
const qrcode = require("qrcode-terminal");
const fs = require("fs");
const path = require("path");

// Config
const PORT = process.env.PORT || process.env.WA_BRIDGE_PORT || 3001;
const PM_API_URL = process.env.PM_API_URL || "http://localhost:8000";
const PM_API_KEY = process.env.PM_API_KEY || "";
const AUTHORIZED_NUMBER = process.env.AUTHORIZED_NUMBER || "";

// Express app for receiving send requests from Python backend
const app = express();
app.use(express.json());

// Multer for image uploads
const upload = multer({ dest: path.join(__dirname, "temp_uploads") });

// WhatsApp client
let clientReady = false;
let qrCode = null;

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: path.join(__dirname, ".wwebjs_auth") }),
  puppeteer: {
    headless: true,
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      "--single-process",
      "--no-zygote",
      "--disable-extensions",
      "--disable-background-networking",
      "--disable-default-apps",
      "--disable-sync",
      "--disable-translate",
      "--js-flags=--max-old-space-size=256",
    ],
  },
});

// ---- WhatsApp Events ----

client.on("qr", (qr) => {
  qrCode = qr;
  console.log("\n========================================");
  console.log("  Scan this QR code with WhatsApp:");
  console.log("========================================\n");
  qrcode.generate(qr, { small: true });
  console.log("\nOr visit http://localhost:" + PORT + "/qr to see it again.\n");
});

client.on("ready", () => {
  clientReady = true;
  qrCode = null;
  console.log("\nWhatsApp client ready!");
  console.log("Bridge running on port " + PORT);
});

client.on("authenticated", () => {
  console.log("WhatsApp authenticated successfully.");
});

client.on("auth_failure", (msg) => {
  console.error("WhatsApp auth failed:", msg);
});

client.on("disconnected", (reason) => {
  clientReady = false;
  console.log("WhatsApp disconnected:", reason);
  // Try to reconnect
  setTimeout(() => {
    console.log("Attempting reconnection...");
    client.initialize();
  }, 5000);
});

// Handle incoming messages - forward to Python backend
client.on("message", async (msg) => {
  try {
    // Only process messages from authorized number (if configured)
    const sender = msg.from.replace("@c.us", "");
    if (AUTHORIZED_NUMBER && !sender.includes(AUTHORIZED_NUMBER.replace("+", ""))) {
      return;
    }

    console.log(`Incoming message from ${msg.from}: ${msg.body.substring(0, 50)}...`);

    // Check for media (screenshots)
    let mediaData = null;
    if (msg.hasMedia) {
      const media = await msg.downloadMedia();
      if (media && media.mimetype.startsWith("image/")) {
        mediaData = {
          mimetype: media.mimetype,
          data: media.data, // base64
          filename: media.filename || "screenshot.jpg",
        };
      }
    }

    // Forward to Python backend
    const payload = {
      text: msg.body || "",
      from_number: msg.from,
      has_media: !!mediaData,
      media: mediaData,
      timestamp: msg.timestamp,
    };

    const headers = {};
    if (PM_API_KEY) {
      headers["X-API-Key"] = PM_API_KEY;
    }

    const response = await axios.post(
      `${PM_API_URL}/api/whatsapp/incoming`,
      payload,
      { headers, timeout: 30000 }
    );

    // Send reply back to user
    if (response.data && response.data.reply) {
      await msg.reply(response.data.reply);
    }
  } catch (error) {
    console.error("Error handling incoming message:", error.message);
    try {
      await msg.reply("Got your message, but had trouble processing it. Try again shortly.");
    } catch (e) {
      // ignore reply errors
    }
  }
});

// ---- Express API Routes ----

// Health check
app.get("/health", (req, res) => {
  res.json({
    status: clientReady ? "ready" : "initializing",
    qr_pending: !!qrCode,
  });
});

// Get QR code data as JSON (for API polling)
app.get("/qr/data", (req, res) => {
  if (clientReady) {
    return res.json({ status: "connected" });
  }
  if (!qrCode) {
    return res.json({ status: "waiting" });
  }
  return res.json({ status: "qr_ready", qr: qrCode });
});

// Get QR code for authentication
app.get("/qr", (req, res) => {
  res.send(`
    <html>
    <head>
      <title>WhatsApp QR Code</title>
      <script src="https://cdn.jsdelivr.net/npm/qrcode@1.5.3/build/qrcode.min.js"></script>
    </head>
    <body style="display:flex; flex-direction:column; align-items:center; padding:40px; font-family:sans-serif; background:#f5f5f5;">
      <h2 id="title" style="color:#333;">Loading...</h2>
      <canvas id="qr-canvas" style="margin:20px 0;"></canvas>
      <p id="hint" style="color:#666; text-align:center;">Open WhatsApp > Settings > Linked Devices > Link a Device</p>
      <p id="status" style="color:#999; font-size:13px; margin-top:10px;"></p>
      <script>
        let lastQr = null;
        async function pollQR() {
          try {
            const resp = await fetch('/qr/data');
            const data = await resp.json();
            const title = document.getElementById('title');
            const canvas = document.getElementById('qr-canvas');
            const hint = document.getElementById('hint');
            const status = document.getElementById('status');

            if (data.status === 'connected') {
              title.textContent = 'WhatsApp Connected!';
              title.style.color = '#22c55e';
              canvas.style.display = 'none';
              hint.textContent = 'You can close this page.';
              status.textContent = '';
              return; // stop polling
            }

            if (data.status === 'waiting') {
              title.textContent = 'Initializing WhatsApp...';
              canvas.style.display = 'none';
              status.textContent = 'Waiting for QR code. This may take 30-60 seconds on first launch.';
            }

            if (data.status === 'qr_ready' && data.qr) {
              if (data.qr !== lastQr) {
                lastQr = data.qr;
                title.textContent = 'Scan this QR code with WhatsApp';
                canvas.style.display = 'block';
                QRCode.toCanvas(canvas, data.qr, { width: 300, margin: 2 }, function(err) {
                  if (err) console.error(err);
                });
                status.textContent = 'QR refreshes automatically. Scan quickly!';
              }
            }
          } catch(e) {
            document.getElementById('status').textContent = 'Error: ' + e.message;
          }
          setTimeout(pollQR, 3000);
        }
        pollQR();
      </script>
    </body>
    </html>
  `);
});

// Send a text message
app.post("/send", async (req, res) => {
  if (!clientReady) {
    return res.status(503).json({ error: "WhatsApp client not ready" });
  }

  const { to, message } = req.body;
  if (!to || !message) {
    return res.status(400).json({ error: "Missing 'to' or 'message'" });
  }

  try {
    // Format number: ensure it ends with @c.us
    const chatId = to.replace("+", "").replace("@c.us", "") + "@c.us";
    await client.sendMessage(chatId, message);
    res.json({ success: true, to: chatId });
  } catch (error) {
    console.error("Send error:", error.message);
    res.status(500).json({ error: error.message });
  }
});

// Send a message with an image
app.post("/send-image", upload.single("image"), async (req, res) => {
  if (!clientReady) {
    return res.status(503).json({ error: "WhatsApp client not ready" });
  }

  const { to, caption } = req.body;
  if (!to || !req.file) {
    return res.status(400).json({ error: "Missing 'to' or image file" });
  }

  try {
    const chatId = to.replace("+", "").replace("@c.us", "") + "@c.us";
    const media = MessageMedia.fromFilePath(req.file.path);
    await client.sendMessage(chatId, media, { caption: caption || "" });

    // Clean up temp file
    fs.unlinkSync(req.file.path);
    res.json({ success: true, to: chatId });
  } catch (error) {
    console.error("Send image error:", error.message);
    if (req.file && fs.existsSync(req.file.path)) {
      fs.unlinkSync(req.file.path);
    }
    res.status(500).json({ error: error.message });
  }
});

// ---- Start ----

app.listen(PORT, () => {
  console.log(`WhatsApp Bridge API listening on port ${PORT}`);
  console.log("Initializing WhatsApp client...\n");
  client.initialize();
});
