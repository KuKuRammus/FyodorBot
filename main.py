import sys
import re
import json
import discord
import firebase_admin
from hashlib import sha256
from firebase_admin import credentials
from firebase_admin import firestore

class FyodorBot(discord.Client):

    database = None
    messages_collection = None
    channel_ids = []
    ignored_user_ids = []
    violation_reaction_emoji = "💩"

    def set_database(self, db):
        self.database = db
        self.messages_collection = self.database.collection(u"messages")

    def add_channel_id(self, channel_id):
        self.channel_ids.append(channel_id)

    def add_ignored_user_id(self, user_id):
        self.ignored_user_ids.append(user_id)

    def set_violation_reaction_emoji(self, emoji):
        self.violation_reaction_emoji = emoji

    async def on_ready(self):
        print("Logged in as", self.user)

    async def on_message(self, message):
        # Skip self and bot users
        if message.author == self.user or message.author.bot == True:
            return

        # Do not process empty messages
        if len(message.content) == 0:
            return

        # Ensure channel id is allowed
        if not message.channel.id in self.channel_ids:
            return

        # Normalize message
        normalized_message = message.content.lower()
        normalized_message = re.sub("<((@!)|(#))\\d{5,20}>", "", normalized_message)
        normalized_message = re.sub("[1234567890!@#$%^&*()_+\"№;:?=-]", "", normalized_message)
        normalized_message = re.sub("\s+", " ", normalized_message)
        normalized_message = normalized_message.strip()
        if len(normalized_message) == 0:
            return

        # Calculate hash
        message_hash = sha256(normalized_message.encode("utf-8")).hexdigest()

        # Check if hash already present in firebase collection
        is_violation = False
        messages_hash_matches = self.messages_collection.where(u'hash', u'==', message_hash).stream()
        for record in messages_hash_matches:
            is_violation = True
            break

        # Save message to database
        new_record_ref = self.messages_collection.document()
        new_record_ref.set({
            u'author_id': message.author.id,
            u'content': normalized_message,
            u'created_at': message.created_at,
            u'hash': message_hash,
            u'is_violation': is_violation
        })

        # React to message if violation detected
        if is_violation:
            await message.add_reaction("💩")

        return


def main():
    # Load config
    if len(sys.argv) < 2:
        print("Please provide path to json config file")
        return
    config = {}
    with open(sys.argv[1], 'r') as configFile:
        config = json.load(configFile)

    # Create bot instance
    bot = FyodorBot()

    # Attach firebase db
    if not 'g_credentials_path' in config:
        print("Make sure 'g_credentials_path' is present in config file!")
        return
    service_account = credentials.Certificate(config['g_credentials_path'])
    firebase_admin.initialize_app(service_account)
    bot.set_database(firestore.client())

    # Set channel ids
    if 'channel_ids' in config:
        for channel_id in config['channel_ids']:
            bot.add_channel_id(channel_id)

    # Set ignored user ids
    if 'ignored_user_ids' in config:
        for ignored_user_id in config['ignored_user_ids']:
            bot.add_ignored_user_id(ignored_user_id)

    # Set emoji
    if 'violation_reaction_emoji' in config:
        bot.set_violation_reaction_emoji(config['violation_reaction_emoji'])

    # Start bot
    if not 'discord_bot_token' in config:
        print("Make sure 'discord_bot_token' is present in config file!")
        return
    bot.run(config['discord_bot_token'])

if __name__ == "__main__":
    main()
