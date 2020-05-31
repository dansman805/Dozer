import datetime
import aiohttp
from .AbstractSources import DataBasedSource
import discord
import logging

DOZER_LOGGER = logging.getLogger('dozer')


class RedditSource(DataBasedSource):

    full_name = "Reddit"
    short_name = "reddit"
    base_url = "https://reddit.com/"
    description = "Gets latest posts from any given subreddit"

    token_url = "https://www.reddit.com/api/v1/access_token"
    api_url = "https://oauth.reddit.com/"
    backup_api_url = "https://reddit.com/"
    color = discord.Color.from_rgb(255, 69, 0)

    class SubReddit(DataBasedSource.DataPoint):
        def __init__(self, name, url, color):
            super().__init__(name, url)
            self.name = name
            self.url = url
            self.color = color

    def __init__(self, aiohttp_session, bot):
        super().__init__(aiohttp_session, bot)
        self.access_token = None
        self.expiry_time = None
        self.oauth_disabled = False
        self.subreddits = {}
        self.seen_posts = set()

    async def get_token(self):
        client_id = self.bot.config['news']['reddit']['client_id']
        client_secret = self.bot.config['news']['reddit']['client_secret']
        params = {
            'grant_type': 'client_credentials'
        }
        auth = aiohttp.BasicAuth(client_id, client_secret)
        response = await self.http_session.post(self.token_url, params=params, auth=auth)
        response = await response.json()
        try:
            self.access_token = response['access_token']
        except KeyError:
            DOZER_LOGGER.critical(f"Error in {self.full_name} Token Get: {response['message']}. Switching to "
                                  f"non-OAuth API")
            self.oauth_disabled = True
            return

        expiry_seconds = response['expires_in']
        time_delta = datetime.timedelta(seconds=expiry_seconds)
        self.expiry_time = datetime.datetime.now() + time_delta

    async def request(self, url, headers=None, *args, **kwargs):
        if headers is None:
            headers = {}
        headers['Authorization'] = f"Bearer {self.access_token}"
        headers['User-Agent'] = "Dozer/Discord by /u/bkeeneykid"

        if self.oauth_disabled:
            url = f"{self.backup_api_url}/{url}"
        else:
            url = f"{self.api_url}/{url}"

        response = await self.http_session.get(url, headers=headers, *args, **kwargs)

        if response.status == 401:
            if 'www-authenticate' in response.headers:
                DOZER_LOGGER.info("Reddit token expired when request made, requesting new token and retrying.")
                await self.get_token()
                return await self.request(url, headers, *args, **kwargs)

        json = await response.json()
        return json

    def create_subreddit_obj(self, data):
        color = data['key_color']
        if "#" in color:
            color = color.replace("#", "")

        try:
            color = discord.Color(int(color, 16))
        except ValueError:
            color = self.color

        return RedditSource.SubReddit(data['display_name'], data['url'], color)

    async def clean_data(self, text):
        try:
            return self.subreddits[text]
        except KeyError:
            subreddit_about = await self.request(f"r/{text}/about.json")

            if "error" in subreddit_about:
                err = subreddit_about['message']
                raise DataBasedSource.InvalidDataException(f"Error in getting info on subreddit: {err}")

            if subreddit_about['kind'] == "t5":
                # Exact subreddit match found
                return self.create_subreddit_obj(subreddit_about['data'])


            elif subreddit_about['kind'] == "Listing":
                # Reddit "helpfully" redirected us to subreddit search. Let's get some helful error messages out of
                # this...
                search = subreddit_about['data']['children']
                if len(search) == 0:
                    raise DataBasedSource.InvalidDataException(f"No subreddit found for search string {text}")
                elif len(search) > 1:
                    subreddits = [subreddit['data']['display_name'] for subreddit in search
                                  if not subreddit['data']['over18']]
                    raise DataBasedSource.InvalidDataException(f"No exact match was found, but multiple similar "
                                                               f"subredidts found. Did you mean any of the following:"
                                                               f"{', '.join(subreddits)}")
                else:
                    # Search only returned one result, so let's assume that's what the user wanted and return the one
                    return self.create_subreddit_obj(subreddit_about['data'])

    async def add_data(self, obj):
        self.subreddits[obj.name] = obj
        return True

    async def remove_data(self, obj):
        try:
            del self.subreddits[obj.name]
            return True
        except KeyError:
            return False

    async def first_run(self, data=None):
        await self.get_token()

        if not data:
            return

        for subreddit in data:
            try:
                subreddit_obj = await self.clean_data(subreddit)
            except DataBasedSource.InvalidDataException:
                DOZER_LOGGER.error(f"Subreddit {subreddit} failed. Database won't be updated right now but this "
                                   f"subreddit won't be checked from now on.")
                continue
            self.subreddits[subreddit_obj.name] = subreddit_obj
        await self.get_new_posts(first_time=True)

    async def get_new_posts(self, first_time=False):
        if datetime.datetime.now() > self.expiry_time:
            DOZER_LOGGER.info(f"Refreshing Reddit token due to expiry time")
            await self.get_token()

        if len(self.subreddits) == 0:
            return {}

        json = await self.request(f"r/{'+'.join(self.subreddits)}/new.json")
        print(json)

        posts = {}
        for post in json['data']['children']:
            if post['data']['name'] not in self.seen_posts:
                self.seen_posts.add(post['data']['name'])
                if first_time:
                    continue

                embed = self.generate_embed(post['data'])
                plain = self.generate_plain_text(post['data'])
                posts[post['data']['subreddit']] = {
                    'embed': [embed],
                    'plain': [plain]
                }

        return posts

    def generate_embed(self, data):
        embed = discord.Embed()
        embed.title = f"New post on {data['subreddit_name_prefixed']}!"

        embed.colour = self.subreddits[data['subreddit']].color

        embed.description = data['title']

        embed.url = f"https://reddit.com{data['permalink']}"

        embed.set_author(name=f"/u/{data['author']}", url=f"https://reddit.com/u/{data['author']}")

        if data['selftext'] != "":
            embed.add_field(name="Text", value=data['selftext'])
        else:
            if data["post_hint"] == "image":
                embed.set_image(url=data['url'])
            elif "thumbnail" in data:
                embed.set_image(url=data['thumbnail'])

        time = datetime.datetime.utcfromtimestamp(data['created_utc'])
        embed.timestamp = time

        return embed

    def generate_plain_text(self, data):
        return f"New post on {data['subreddit_name_prefixed']}: {data['title']}\n" \
               f"Read more at https://reddit.com{data['permalink']}"
