import tbapi
import discord
from ._utils import *
from discord.ext.commands import BadArgument, Group, bot_has_permissions, has_permissions

blurple = discord.Color.blurple()

class tba(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		self.parser = tbapi.TBAParser(bot.config['tba']['team'], bot.config['tba']['application'], bot.config['tba']['version'])
	
	@group(invoke_without_command=False)
	async def tba(self, ctx):
		"""Pulls data on FRC teams from The Blue Alliance."""
		
	tba.example_usage = """
	`{prefix}tba team <team-number>` - Pulls information about an FRC team.
	`{prefix}tba raw <team-number>` - Pulls raw data for an FRC Team.
	"""
	@tba.command()
	@bot_has_permissions(embed_links=True)
	async def team(self, ctx, teamnum):
			teamdata = self.parser.get_team('frc' + teamnum)
			guild = ctx.guild
			e = discord.Embed(color=blurple)
			e.add_field(name='Team Name', value=teamdata.nickname)
			e.add_field(name='Sponsors', value=teamdata.name)
			e.add_field(name='Team Number', value=teamdata.number)
			e.add_field(name='Team Key', value=teamdata.key)
			e.add_field(name='Team Location', value=teamdata.location)
			e.add_field(name='Rookie Year', value=teamdata.rookie_year)
			e.add_field(name='Team Motto', value=teamdata.motto)
			e.add_field(name='Team Website', value=teamdata.website)
			e.add_field(name='TBA Page', value='https://www.thebluealliance.com/team/' + teamnum)
			await ctx.send(embed=e)
	@tba.command(name='raw')
	async def traw(self, ctx, teamnum):
		 teamdata = self.parser.get_team('frc' + teamnum)
		 await ctx.send(teamdata.raw)
		 
def setup(bot):
	bot.add_cog(tba(bot))
