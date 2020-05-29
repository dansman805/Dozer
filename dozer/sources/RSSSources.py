import re
import datetime
import xml.etree.ElementTree

import aiohttp
import discord

from .AbstractSources import Source


def clean_html(raw_html):
    """Clean all HTML tags.
    From https://stackoverflow.com/questions/9662346/python-code-to-remove-html-tags-from-a-string"""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext


class RSSSource(Source):
    url = None
    color = discord.colour.Color.blurple()
    date_formats = ["%a, %d %b %Y %H:%M:%S %z",
                    "%a, %d %b %Y %H:%M:%S %Z"]  # format for datetime.strptime()
    base_url = None

    def __init__(self, aiohttp_session: aiohttp.ClientSession, bot):
        super().__init__(aiohttp_session, bot)
        self.guids_seen = set()

    async def first_run(self):
        response = await self.fetch()
        self.parse(response, True)

    async def get_new_posts(self):
        response = await self.fetch()
        items = self.parse(response)
        new_posts = {
            'source': {
                'embed': [],
                'plain': []
            }
        }
        for item in items:
            data = self.get_data(item)
            new_posts['source']['embed'].append(self.generate_embed(data))
            new_posts['source']['plain'].append(self.generate_plain_text(data))
        return new_posts

    async def fetch(self):
        response = await self.http_session.get(url=self.url)
        return await response.text()

    def parse(self, response, first_time=False):
        new_items = set()
        root = xml.etree.ElementTree.fromstring(response)
        channel = root[0]
        for child in channel:
            if child.tag == 'item':
                guid = child.find('guid')
                if first_time:
                    self.guids_seen.add(guid.text)
                    continue
                new = self.determine_if_new(guid.text)
                if new:
                    new_items.add(child)
        return new_items

    def determine_if_new(self, guid):
        """Given a RSS item's guid, determine if this item is new or not. Store GUID if new."""
        if guid not in self.guids_seen:
            self.guids_seen.add(guid)
            return True
        else:
            return False

    def get_data(self, item):
        types = {
            'title': 'title',
            'url': 'url',
            '{http://purl.org/dc/elements/1.1/}creator': 'author',
            'description': 'description'
        }
        data = {}
        for key, value in types.items():
            element = item.find(key)
            if element is not None:
                data[value] = element.text
            else:
                data[value] = None

        if data['url'] is None:
            if item.find('link') is not None:
                data['url'] = item.find('link').text
            elif item.find('guid').attrib['isPermaLink'] == 'true':
                data['url'] = item.find('guid').text

        date_string = item.find('pubDate')
        if date_string is not None:
            for date_format in self.date_formats:
                try:
                    data['date'] = datetime.datetime.strptime(date_string.text, date_format)
                except ValueError:
                    continue
        else:
            data['date'] = datetime.datetime.now()

        data['description'] = clean_html(data['description'])[0:1024]

        return data

    def generate_embed(self, data):
        embed = discord.Embed()
        embed.title = f"New Post From {self.full_name}!"
        embed.colour = self.color

        embed.description = f"[{data['title']}]({data['url']})"

        embed.url = self.base_url

        embed.add_field(name="Description", value=data['description'])

        embed.set_author(name=data['author'])

        embed.timestamp = data['date']

        return embed

    def generate_plain_text(self, data):
        return f"New Post from {self.full_name} from {data['author']}:\n" \
               f"{data['title']}\n" \
               f">>> {data['description']}\n" \
               f"Read more at {data['url']}"


class FRCBlogPosts(RSSSource):
    url = "https://www.firstinspires.org/robotics/frc/blog-rss"
    base_url = "https://www.firstinspires.org/robotics/frc/blog/"
    full_name = "FRC Blog Posts"
    short_name = "frc"
    description = "Official blog posts from the FIRST Robotics Competition"
    color = discord.colour.Color.dark_blue()


class CDLatest(RSSSource):
    url = "https://www.chiefdelphi.com/latest.rss"
    base_url = "https://www.chiefdelphi.com/latest"
    full_name = "Chief Delphi"
    short_name = "cd"
    description = "Latest topics from a very popular FIRST forum"
    color = discord.colour.Color.orange()


class TestSource(RSSSource):
    url = "http://lorem-rss.herokuapp.com/feed?unit=second&interval=10"
    base_url = "http://lorem-rss.herokuapp.com"
    full_name = "Test Source"
    short_name = "test"
    description = "Test Source Please Ignore"