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

// Get QR code for authentication
app.get("/qr", (req, res) => {
  if (clientReady) {
    res.send("<h2>WhatsApp is already connected!</h2>");
    return;
  }
  if (!qrCode) {
    res.send("<h2>Waiting for QR code... Refresh in a few seconds.</h2>");
    return;
  }
  // Render QR as a simple HTML page
  const qrSvgUrl = `https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=${encodeURIComponent(qrCode)}`;
  res.send(`
    <html>
    <head><title>WhatsApp QR Code</title></head>
    <body style="display:flex; flex-direction:column; align-items:center; padding:40px; font-family:sans-serif;">
      <h2>Scan this QR code with WhatsApp</h2>
      <img src="${qrSvgUrl}" width="300" height="300" />
      <p style="margin-top:20px; color:#666;">Open WhatsApp > Settings > Linked Devices > Link a Device</p>
      <script>setTimeout(() => location.reload(), 15000);</script>
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
