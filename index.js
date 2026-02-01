import { Telegraf } from 'telegraf';
import { message } from 'telegraf/filters';
import dotenv from 'dotenv';
import { performOCR } from './services/ocr.js';
import { saveToSheet, checkDuplicateTransaction } from './services/sheets.js';
import { extractPaymentData } from './services/extraction.js';
import { loadConfig } from './config/index.js';

dotenv.config();

const bot = new Telegraf(process.env.TELEGRAM_BOT_TOKEN);

// Message buffer for collecting multiple messages from same user
const userMessageBuffers = new Map();
const userBufferTimers = new Map();

const MESSAGE_BUFFER_DELAY = 30000; // 30 seconds
const EDIT_MODE_DELAY = 60000; // 60 seconds

// Load configuration
const config = await loadConfig();

console.log('✅ Bot starting...');
console.log(`📊 Loaded ${config.groups.length} group(s)`);

// Helper: Buffer messages from user
function bufferMessage(ctx, messageData) {
  const userId = ctx.from.id;
  const chatId = ctx.chat.id;
  const bufferKey = `${chatId}:${userId}`;

  if (!userMessageBuffers.has(bufferKey)) {
    userMessageBuffers.set(bufferKey, []);
  }

  userMessageBuffers.get(bufferKey).push(messageData);
  console.log(`📥 Buffered message from user ${userId} in chat ${chatId} (total: ${userMessageBuffers.get(bufferKey).length})`);

  // Reset timer
  if (userBufferTimers.has(bufferKey)) {
    clearTimeout(userBufferTimers.get(bufferKey));
  }

  // Set new timer to process buffer
  const timer = setTimeout(() => processBuffer(ctx, chatId, userId), MESSAGE_BUFFER_DELAY);
  userBufferTimers.set(bufferKey, timer);
}

// Process buffered messages
async function processBuffer(ctx, chatId, userId) {
  const bufferKey = `${chatId}:${userId}`;
  const messages = userMessageBuffers.get(bufferKey);

  if (!messages || messages.length === 0) {
    return;
  }

  console.log(`🔄 Processing ${messages.length} buffered messages from user ${userId}`);

  // Separate OCR text from user-typed text
  const ocrTexts = [];
  const userTexts = [];
  const captions = [];

  for (const msg of messages) {
    if (msg.isOCR) {
      ocrTexts.push(msg.text);
    } else if (msg.text) {
      userTexts.push(msg.text);
    }
    if (msg.caption) {
      captions.push(msg.caption);
    }
  }

  const allUserText = userTexts.join(' ');
  const allOCRText = ocrTexts.join('\n');
  const allCaptions = captions.join(' ');
  const combinedText = allUserText + '\n' + allOCRText;

  console.log(`User text: ${allUserText.length} chars, OCR: ${allOCRText.length} chars`);

  try {
    // Extract payment data
    const data = extractPaymentData(combinedText, allUserText, allCaptions, chatId, config);

    console.log(`Extracted: House=${data.houseNumber}, Amount=${data.amount}, Month=${data.month}`);

    // Check for duplicate transaction ID
    if (data.transactionId) {
      const isDuplicate = await checkDuplicateTransaction(data.transactionId, chatId, config);
      if (isDuplicate) {
        await ctx.reply(
          `⚠️ ይህ ደረሰኝ ከዚህ በፊት ተልኳል እና ተመዝግቧል\n\n` +
          `This receipt has been sent before and recorded.\n\n` +
          `🔖 Transaction ID: ${data.transactionId}`
        );
        return;
      }
    }

    // Validate beneficiary if configured
    if (data.beneficiary && config.authorizedBeneficiaries) {
      const isValid = validateBeneficiary(data.beneficiary, config.authorizedBeneficiaries);
      if (!isValid) {
        await ctx.reply(`❌ Invalid beneficiary: ${data.beneficiary}`);
        return;
      }
    }

    // Save to Google Sheets
    await saveToSheet(data, chatId, config);

    // Send success reaction and message
    await ctx.react('👍');
    await ctx.reply(
      `✅ ተመዝግቧል!\n\n` +
      `🏠 ቤት: ${data.houseNumber}\n` +
      `💰 መጠን: ${data.amount} ብር\n` +
      `📅 ወር: ${data.month}\n` +
      `✅ ምክንያት: ${data.reason}`
    );

  } catch (error) {
    console.error('Error processing messages:', error);
    await ctx.reply(`❌ Error: ${error.message}`);
  } finally {
    // Clean up buffer
    userMessageBuffers.delete(bufferKey);
    userBufferTimers.delete(bufferKey);
  }
}

// Handle text messages
bot.on(message('text'), async (ctx) => {
  const chatId = ctx.chat.id;
  const threadId = ctx.message.message_thread_id;

  // Find group configuration
  const groupConfig = config.groups.find(g => g.chatId === chatId);
  if (!groupConfig) {
    console.log(`⏭️ Ignoring message from unconfigured group: ${chatId}`);
    return;
  }

  // Check if message is in correct topic/thread
  if (groupConfig.topicId && threadId !== groupConfig.topicId) {
    console.log(`⏭️ Ignoring message from wrong topic. Expected: ${groupConfig.topicId}, Got: ${threadId}`);
    return;
  }

  // Buffer the text message
  bufferMessage(ctx, {
    text: ctx.message.text,
    isOCR: false,
    caption: null
  });
});

// Handle photo messages
bot.on(message('photo'), async (ctx) => {
  const chatId = ctx.chat.id;
  const threadId = ctx.message.message_thread_id;

  // Find group configuration
  const groupConfig = config.groups.find(g => g.chatId === chatId);
  if (!groupConfig) {
    return;
  }

  // Check topic
  if (groupConfig.topicId && threadId !== groupConfig.topicId) {
    return;
  }

  console.log(`📸 Processing image from user ${ctx.from.id}...`);

  try {
    // Get the largest photo
    const photo = ctx.message.photo[ctx.message.photo.length - 1];
    const fileLink = await ctx.telegram.getFileLink(photo.file_id);

    console.log(`📸 Running OCR...`);
    const ocrText = await performOCR(fileLink.href);
    console.log(`✓ OCR done: ${ocrText.length} chars`);

    // Buffer the OCR result
    bufferMessage(ctx, {
      text: ocrText,
      isOCR: true,
      caption: ctx.message.caption || null
    });

  } catch (error) {
    console.error('OCR Error:', error);
    await ctx.reply(`❌ OCR failed: ${error.message}`);
  }
});

// Helper: Validate beneficiary
function validateBeneficiary(beneficiary, authorizedList) {
  const beneficiaryTokens = beneficiary.toUpperCase().split(/\s+/);
  const authorizedTokens = authorizedList.flatMap(name => 
    name.toUpperCase().split(/\s+/)
  );

  return beneficiaryTokens.some(token => authorizedTokens.includes(token));
}

// Error handling
bot.catch((err, ctx) => {
  console.error(`Error for ${ctx.updateType}:`, err);
});

// Start bot
bot.launch().then(() => {
  console.log('✅ Bot is running!');
});

// Enable graceful stop
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
