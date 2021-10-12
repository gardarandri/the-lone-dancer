"""
Author MikkMakk88, morgaesis et al.

(c)2021
"""

import os
import re
import configparser
import logging
import asyncio

import discord  # pylint: disable=import-error

import queue
import pafy
from youtubesearchpython import VideosSearch


class MusicBot(discord.Client):
    """
    The main bot functionality
    """

    COMMAND_PREFIX = "!"

    def __init__(self):
        self.handlers = {}

        self.register_command("hello", handler=self.hello)
        self.register_command("countdown", handler=self.countdown)
        self.register_command("dinkster", handler=self.dinkster)
        self.register_command("play", handler=self.play)
        self.register_command("stop", handler=self.stop)
        self.register_command("pause", handler=self.pause)
        self.register_command("resume", handler=self.resume)
        self.register_command("skip", handler=self.skip)

        self.voice_client = None
        self.song_queue = queue.Queue()
        self.url_regex = re.compile(
            "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        )

        super().__init__()

    def next_in_queue(self, error):
        if self.song_queue.empty() == False:
            self.voice_client.stop()
            self.voice_client.play(self.song_queue.get(), after=self.next_in_queue)

    def register_command(self, command_name, handler=None):
        """Register a command with the name 'command_name'.

        Arguments:
          command_name: String. The name of the command to register. This is
            what users should use to run the command.
          handler: A function. This function should accept two arguments:
            discord.Message and a string. The messageris the message being
            processed by the handler and command_content is the string
            contents of the command passed by the user.
        """
        assert handler
        assert command_name not in self.handlers
        self.handlers[command_name] = handler

    def get_command_handler(self, message_content):
        """Tries to parse message_content as a command and fetch the corresponding handler for the command.

        Arguments:
          message_content: Contents of the message to parse. Assumed to start with COMMAND_PREFIX.

        Returns:
          handler: Function to handle the command.
          command_content: The message contents with the prefix and command named stripped.
          error_msg: String or None. If not None it signals that the command was
            unknown. The value will be an error message displayable to the user which
            says the command was not recognized.
        """
        if message_content[0] != "!":
            raise ValueError(
                f"Message '{message_content}' does not begin with '{MusicBot.COMMAND_PREFIX}'"
            )

        content_split = message_content[1:].split(" ", 1)
        command_name = content_split[0]
        command_content = ""
        if len(content_split) == 2:
            command_content = content_split[1]

        if command_name not in self.handlers:
            return None, None, f"Command {command_name} not recognized."

        return self.handlers[command_name], command_content, None

    async def hello(self, message, command_content):
        await message.channel.send("Hello!")

    async def countdown(self, message, command_content):
        try:
            seconds = int(command_content)
            while seconds > 0:
                await message.channel.send(seconds)
                await asyncio.sleep(1)
                seconds -= 1
            await message.channel.send("BOOOM!!!")
        except ValueError:
            await message.channel.send(f"{command_content} is not an integer.")

    async def dinkster(self, message, command_content):
        for channel in await message.guild.fetch_channels():
            if isinstance(channel, discord.VoiceChannel):
                voice_client = await channel.connect()
                audio_source = await discord.FFmpegOpusAudio.from_probe("Dinkster.ogg")
                voice_client.play(audio_source)
                await asyncio.sleep(10)
                await voice_client.disconnect()

    async def play(self, message, command_content):
        video_metadata = None

        if self.url_regex.match(command_content):
            video_metadata = pafy.new(command_content)
        else:
            search_result = VideosSearch(command_content).result()
            video_metadata = pafy.new(search_result["result"][0]["id"])

        logging.info("Pafy found", self.user)
        logging.info(str(video_metadata))
        audio_url = video_metadata.getbestaudio().url

        if self.voice_client is None:
            self.voice_client = await message.author.voice.channel.connect()

        audio_source = discord.FFmpegPCMAudio(audio_url)

        if self.voice_client.is_playing():
            self.song_queue.put(audio_source)
            await message.channel.send("Added to Queue: " + video_metadata.title)
        else:
            self.voice_client.play(audio_source, after=self.next_in_queue)
            await message.channel.send("Now Playing: " + video_metadata.title)


    async def stop(self, message, command_content):
        if self.voice_client:
            self.voice_client.stop()

    async def pause(self, message, command_content):
        if self.voice_client:
            self.voice_client.pause()

    async def resume(self, message, command_content):
        if self.voice_client:
            self.voice_client.resume()

    async def skip(self, message, command_content):
        self.next_in_queue(None)

    _discord_helper = discord.Client()

    @_discord_helper.event
    async def on_ready(self):
        """Login and loading handling"""
        logging.info("we have logged in as %s", self.user)

    @_discord_helper.event
    async def on_message(self, message):
        """Handler for receiving messages"""
        if message.author == self.user:
            return

        if not message.content:
            return

        if message.content[0] != MusicBot.COMMAND_PREFIX:
            # Message not attempting to be a command.
            return

        handler, command_content, error_msg = self.get_command_handler(message.content)

        # The command was not recognized
        if error_msg:
            return await message.channel.send(error_msg)

        # Execute the command.
        await handler(message, command_content)


if __name__ == "__main__":
    print("Starting Discord bot")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    token = os.getenv("TOKEN")
    if token is None:
        config = configparser.ConfigParser()
        config.read("bot.conf")
        token = config["secrets"]["TOKEN"]

    logging.info("Starting bot")
    MusicBot().run(token)
