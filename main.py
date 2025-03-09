import asyncio
import logging
import json
import re
from telethon import TelegramClient, events

# Your credentials
API_ID = 28451755  # Replace with your API ID
API_HASH = "c888900d408dcd71e8bf31f5aa15ae0e"  # Replace with your API hash

# Initialize the Telegram client
client = TelegramClient("userbot", API_ID, API_HASH)

# File to store mappings
MAPPINGS_FILE = "channel_mappings.json"

# Dictionary to store multiple source and destination mappings with names
channel_mappings = {}
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ForwardBot")

def save_mappings():
    with open(MAPPINGS_FILE, "w") as f:
        json.dump(channel_mappings, f)
    logger.info("Channel mappings saved to file.")

def load_mappings():
    global channel_mappings
    try:
        with open(MAPPINGS_FILE, "r") as f:
            channel_mappings = json.load(f)
        logger.info("Channel mappings loaded from file.")
    except FileNotFoundError:
        logger.info("No existing mappings file found. Starting fresh.")

@client.on(events.NewMessage(pattern='(?i)^/start$'))
async def start(event):
    await event.reply("✅ Bot is running! Use /setpair to configure forwarding.")

@client.on(events.NewMessage(pattern='(?i)^/commands$'))
async def list_commands(event):
    commands = """
    📌 Available Commands:
    /setpair <name> <source> <destination> [remove_mentions]
    /listpairs - List all forwarding pairs
    /pausepair <name> - Pause a forwarding pair
    /startpair <name> - Resume a forwarding pair
    /clearpairs - Clear all forwarding pairs
    /togglementions <name> - Toggle mention removal for a forwarding pair
    """
    await event.reply(commands)

@client.on(events.NewMessage(pattern=r'/setpair (\S+) (\S+) (\S+)(?: (yes|no))?'))
async def set_pair(event):
    pair_name, source, destination, remove_mentions = event.pattern_match.groups()
    user_id = str(event.sender_id)
    remove_mentions = remove_mentions == "yes"

    if user_id not in channel_mappings:
        channel_mappings[user_id] = {}
    channel_mappings[user_id][pair_name] = {
        'source': source,
        'destination': destination,
        'active': True,
        'remove_mentions': remove_mentions
    }
    save_mappings()
    await event.reply(f"✅ Forwarding pair '{pair_name}' added: {source} → {destination} (Remove mentions: {remove_mentions})")

@client.on(events.NewMessage(pattern='(?i)^/togglementions (\S+)$'))
async def toggle_mentions(event):
    pair_name = event.pattern_match.group(1)
    user_id = str(event.sender_id)
    if user_id in channel_mappings and pair_name in channel_mappings[user_id]:
        current_status = channel_mappings[user_id][pair_name]['remove_mentions']
        channel_mappings[user_id][pair_name]['remove_mentions'] = not current_status
        save_mappings()
        status_text = "ENABLED" if not current_status else "DISABLED"
        await event.reply(f"🔄 Mention removal {status_text} for forwarding pair '{pair_name}'.")
    else:
        await event.reply("⚠️ Pair not found.")

@client.on(events.NewMessage(pattern='(?i)^/listpairs$'))
async def list_pairs(event):
    user_id = str(event.sender_id)
    if user_id in channel_mappings and channel_mappings[user_id]:
        pairs_list = "\n".join([
            f"{name}: {data['source']} → {data['destination']} (Active: {data['active']}, Remove Mentions: {data['remove_mentions']})"
            for name, data in channel_mappings[user_id].items()
        ])
        await event.reply(f"📋 Active Forwarding Pairs:\n{pairs_list}")
    else:
        await event.reply("⚠️ No forwarding pairs found.")

@client.on(events.NewMessage(pattern='(?i)^/pausepair (\S+)$'))
async def pause_pair(event):
    pair_name = event.pattern_match.group(1)
    user_id = str(event.sender_id)
    if user_id in channel_mappings and pair_name in channel_mappings[user_id]:
        channel_mappings[user_id][pair_name]['active'] = False
        save_mappings()
        await event.reply(f"⏸️ Forwarding pair '{pair_name}' has been paused.")
    else:
        await event.reply("⚠️ Pair not found.")

@client.on(events.NewMessage(pattern='(?i)^/startpair (\S+)$'))
async def start_pair(event):
    pair_name = event.pattern_match.group(1)
    user_id = str(event.sender_id)
    if user_id in channel_mappings and pair_name in channel_mappings[user_id]:
        channel_mappings[user_id][pair_name]['active'] = True
        save_mappings()
        await event.reply(f"▶️ Forwarding pair '{pair_name}' has been activated.")
    else:
        await event.reply("⚠️ Pair not found.")

@client.on(events.NewMessage(pattern='(?i)^/clearpairs$'))
async def clear_pairs(event):
    user_id = str(event.sender_id)
    if user_id in channel_mappings:
        channel_mappings[user_id] = {}
        save_mappings()
        await event.reply("🗑️ All forwarding pairs have been cleared.")
    else:
        await event.reply("⚠️ No forwarding pairs found.")

@client.on(events.NewMessage)
async def forward_messages(event):
    for user_id, pairs in channel_mappings.items():
        for pair_name, mapping in pairs.items():
            if mapping['active'] and event.chat_id == int(mapping['source']):
                # Get message content
                message_text = event.message.text or event.message.raw_text or ""

                # Remove mentions if enabled
                if mapping['remove_mentions'] and message_text:
                    # More comprehensive regex to remove mentions, handles multiple formats
                    # This will match standard @username mentions and linked mentions
                    message_text = re.sub(r'@[a-zA-Z0-9_]+|\[([^\]]+)\]\(tg://user\?id=\d+\)', '', message_text)
                    # Clean up extra spaces
                    message_text = re.sub(r'\s+', ' ', message_text).strip()
                    logger.info(f"Removed mentions from message: {message_text[:30]}...")

                # Check if there's media
                has_media = event.message.media is not None

                # Handle reply preservation
                reply_to = None
                if hasattr(event.message, 'reply_to') and event.message.reply_to:
                    # Try to find the corresponding message in the destination channel
                    source_reply_id = event.message.reply_to.reply_to_msg_id
                    logger.info(f"Found reply to message ID: {source_reply_id}")
                    try:
                        # Get the original replied message from source
                        replied_msg = await client.get_messages(
                            int(mapping['source']), 
                            ids=source_reply_id
                        )

                        if replied_msg and hasattr(replied_msg, 'text') and replied_msg.text:
                            # Store this message ID for future reference
                            # This is a simple approach - in a full solution, you might want to use a database
                            reply_mapping_key = f"{mapping['source']}:{source_reply_id}"

                            # For logging purposes
                            logger.info(f"Looking for reply message with content: {replied_msg.text[:30]}...")

                            # Create a simple message ID mapping system
                            # This dictionary will track the last 50 forwarded messages
                            if not hasattr(client, 'forwarded_messages'):
                                client.forwarded_messages = {}
                            
                            # Check if we have this source message ID in our mapping
                            mapping_key = f"{mapping['source']}:{source_reply_id}"
                            if mapping_key in client.forwarded_messages:
                                reply_to = client.forwarded_messages[mapping_key]
                                logger.info(f"Found mapped reply message, ID: {reply_to}")
                            else:
                                # Try to find by content as fallback
                                if replied_msg.text:
                                    dest_msgs = await client.get_messages(
                                        int(mapping['destination']),
                                        search=replied_msg.text[:20],  # Use first part of text to search
                                        limit=10  # Limit to recent messages to avoid long searches
                                    )
    
                                    if dest_msgs and len(dest_msgs) > 0:
                                        # Use the most recent matching message as reply target
                                        reply_to = dest_msgs[0].id
                                        logger.info(f"Found matching reply message by content, ID: {reply_to}")
                    except Exception as e:
                        logger.error(f"Error finding reply message: {str(e)}")
                        # Continue without the reply if there's an error

                # Forward with media or without
                sent_message = None
                if has_media:
                    # If there's media, forward the whole message
                    sent_message = await client.send_message(
                        int(mapping['destination']),
                        message_text,
                        file=event.message.media,
                        reply_to=reply_to
                    )
                else:
                    # If text only, just send the text
                    sent_message = await client.send_message(
                        int(mapping['destination']),
                        message_text,
                        reply_to=reply_to
                    )

                # Store the sent message for future reply mapping
                try:
                    if hasattr(event.message, 'id'):
                        # Add message to tracking
                        if not hasattr(client, 'forwarded_messages'):
                            client.forwarded_messages = {}
                            
                        # Create tracking dictionary with a maximum of 50 entries
                        # First, remove oldest entry if we have 50 already
                        if len(client.forwarded_messages) >= 50:
                            oldest_key = list(client.forwarded_messages.keys())[0]
                            client.forwarded_messages.pop(oldest_key)
                            
                        # Add the new mapping - source message ID to destination message ID
                        source_msg_id = event.message.id
                        client.forwarded_messages[f"{mapping['source']}:{source_msg_id}"] = sent_message.id
                        logger.info(f"Stored message mapping: {mapping['source']}:{source_msg_id} -> {sent_message.id}")
                except Exception as e:
                    logger.error(f"Error storing message mapping: {str(e)}")
                
                logger.info(f"Message forwarded from {mapping['source']} to {mapping['destination']} with text: {message_text[:30]}...")
                logger.info(f"Reply status: {reply_to is not None}")
                return

async def main():
    load_mappings()
    print("🚀 Bot is running! Use /setpair to configure forwarding.")
    await client.run_until_disconnected()

client.start()
client.loop.run_until_complete(main())