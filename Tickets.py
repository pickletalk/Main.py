import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta, timezone
import io
import asyncio
from discord import app_commands
import chat_exporter
import json
from keep_alive import keep_alive

# Flask setup for keeping bot alive
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=4000)

def keep_alive():
    server = Thread(target=run)
    server.daemon = True
    server.start()

# Bot setup with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="/", intents=intents)

# Configuration
TOKEN = "MTM2MzI1MzM4MDk3MzMzMDUyMw.GOoaUj.gKxJzk-6WMM8y78o6eyGb46KfLDoGdC30FNte4"
GUILD_ID = 1361968509621637243
STAFF_ROLE_ID = 1362006485575532544
SPECIAL_ROLE_ID = 1361969514170024006
PARTNER_MANAGER_ROLE_ID = 1369415348377616424
TRANSCRIPT_CHANNEL_ID = 1365301557650001980
PANEL_CHANNEL_ID = 1361976454081941626
GWS = 1364475838237769738
QDS = 1364476242539319316
INVITE = 1362110597298262228
MODERATOR_ROLE_ID = 1372782448093560906
LOG_CHANNEL_ID = 1363055877845680168
WELCOME_CHANNEL_ID = 1361968510946771068
gmt8 = timezone(timedelta(hours=8))
now = datetime.now(gmt8)
timestamp = now.strftime("%B %d, %Y %H:%M GMT+8")
NO_TEXT_CHANNEL_ID = 1378923709594861618
ALLOWED_MESSAGE_ID = 1378924379156774932

# Category limits (changeable)
CATEGORY_LIMITS = {
    "Support": 1,
    "Giveaway": 7,
    "Partnerships": 1,
    "Trusted Approval": 1
}

# Blacklist storage
blacklisted_users = set()

# Ticket timers storage
ticket_timers = {}

# Ticket category data with proper mapping
category_data = {
    "support": {
        "id": 1362173535795024012,
        "display_name": "Support",
        "questions": [{"q": "How may we help you?", "ph": "team invitation"}]
    },
    "giveaway": {
        "id": 1364253706866130954,
        "display_name": "Giveaway",
        "questions": [
            {"q": "What's your ign?", "ph": "ex. PickleTalk"},
            {"q": "Who hosted?", "ph": "ex. PickleTalk"},
            {"q": "How much prize you won?", "ph": "ex. 100k"},
            {"q": "Show proof on ticket", "ph": "No proof/ping = No payment"}
        ]
    },
    "partnership": {
        "id": 1364253525722533990,
        "display_name": "Partnerships",
        "questions": [
            {"q": "How many members?", "ph": "ex. 100"},
            {"q": "What ping you want?", "ph": "ex. both member"},
            {"q": "Ad", "ph": "`Send your ad here`"}
        ]
    },
    "trusted": {
        "id": 1364253628642230425,
        "display_name": "Sell Skelly",
        "questions": [
            {"q": "What's your ign?", "ph": "ex. in PickleTalk"},
            {"q": "How much skelly?", "ph": "ex. 20"},
            {"q": "Do you agree were not going first?", "ph": "If nope we will not buy"}
        ]
    }
}

def load_blacklist():
            """Load blacklist from file with improved error handling"""
            global blacklisted_users
            try:
                with open('blacklist.json', 'r') as f:
                    content = f.read().strip()
                    if not content:  # Handle empty file
                        print("Blacklist file is empty, initializing with empty set")
                        blacklisted_users = set()
                        return

                    data = json.loads(content)
                    if isinstance(data, list):
                        blacklisted_users = set(data)
                        print(f"Loaded {len(blacklisted_users)} blacklisted users")
                    else:
                        print("Invalid blacklist format, initializing with empty set")
                        blacklisted_users = set()

            except FileNotFoundError:
                print("Blacklist file not found, creating new one")
                blacklisted_users = set()
                save_blacklist()  # Create the file
            except json.JSONDecodeError as e:
                print(f"Error reading blacklist file: {e}")
                print("Backing up corrupted file and creating new one")

                # Backup the corrupted file
                try:
                    import shutil
                    shutil.copy('blacklist.json', 'blacklist.json.backup')
                    print("Corrupted file backed up as blacklist.json.backup")
                except:
                    pass

                # Initialize with empty set and create new file
                blacklisted_users = set()
                save_blacklist()
            except Exception as e:
                print(f"Unexpected error loading blacklist: {e}")
                blacklisted_users = set()

def save_blacklist():
            """Save blacklist to file with error handling"""
            try:
                with open('blacklist.json', 'w') as f:
                    json.dump(list(blacklisted_users), f, indent=2)
                print(f"Saved {len(blacklisted_users)} blacklisted users to file")
            except Exception as e:
                print(f"Error saving blacklist: {e}")

@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return
    
    # Check if message is in the monitored channel
    if message.channel.id == NO_TEXT_CHANNEL_ID:
        # Check if this is NOT the allowed message
        if message.id != ALLOWED_MESSAGE_ID:
            try:
                await message.delete()
                print(f"Deleted message from {message.author}: {message.content[:50]}...")
            except discord.errors.NotFound:
                print("Message was already deleted")
            except discord.errors.Forbidden:
                print("Bot doesn't have permission to delete messages")
            except Exception as e:
                print(f"Error deleting message: {e}")
    
    # Check if message is in a ticket channel and cancel auto-close timer
    if message.channel.topic and "UserID:" in message.channel.topic:
        channel_id = message.channel.id
        if channel_id in ticket_timers:
            ticket_timers[channel_id].cancel()
            del ticket_timers[channel_id]
            print(f"Auto-close timer cancelled for {message.channel.name}")
    
    # Process other commands
    await bot.process_commands(message)

@bot.event
async def on_member_remove(member):
    """Handle when a member leaves the server"""
    guild = member.guild
    
    # Find all tickets created by this user
    for category_key, category_info in category_data.items():
        category = guild.get_channel(category_info["id"])
        if category:
            for channel in category.channels:
                if channel.topic and f"UserID: {member.id}" in channel.topic:
                    # Close ticket with auto-close message
                    await auto_close_ticket(channel, "User Left Server", "AutoClose System")

async def auto_close_ticket(channel, reason, closed_by):
    """Auto close ticket function"""
    try:
        user_id = None
        
        # Extract user ID from channel topic
        if channel.topic and "UserID:" in channel.topic:
            try:
                user_id = int(channel.topic.split("UserID:")[1].strip())
            except:
                pass
        
        # Generate transcript file
        transcript_file = await generate_transcript_file(channel)
        
        # Send DM to user if they're still in the server
        if user_id:
            try:
                user = await bot.fetch_user(user_id)
                
                dm_embed = discord.Embed(
                    title="Ticket Closed",
                    description=f"Hello {user.mention}, your ticket has been closed in the **{channel.guild.name}** discord!",
                    color=discord.Color.red()
                )
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                dm_embed.add_field(name="Closed by", value=closed_by, inline=False)
                
                if transcript_file:
                    # Create a copy of the file for DM
                    transcript_file.fp.seek(0)
                    dm_file = discord.File(io.BytesIO(transcript_file.fp.read()), filename=transcript_file.filename)
                    await user.send(embed=dm_embed, file=dm_file)
                else:
                    await user.send(embed=dm_embed)
                
                print(f"Auto-close DM sent successfully to user {user.name}")
                
            except Exception as e:
                print(f"Failed to DM user in auto-close: {e}")

        # Log to transcript channel
        transcript_channel = bot.get_channel(TRANSCRIPT_CHANNEL_ID)
        if transcript_channel:
            try:
                log_embed = discord.Embed(
                    title=f"Ticket Auto-Closed: {channel.name}",
                    description=f"**Reason:** {reason}\n**Closed by:** {closed_by}",
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )
                
                if transcript_file:
                    transcript_file.fp.seek(0)
                    log_file = discord.File(io.BytesIO(transcript_file.fp.read()), filename=transcript_file.filename)
                    await transcript_channel.send(embed=log_embed, file=log_file)
                else:
                    log_embed.add_field(name="Transcript", value="Failed to generate transcript", inline=False)
                    await transcript_channel.send(embed=log_embed)
                    
                print("Auto-close transcript logged successfully")
            except Exception as e:
                print(f"Failed to log auto-close to transcript channel: {e}")

        # Delete the channel
        await asyncio.sleep(3)
        try:
            await channel.delete(reason=f"Ticket auto-closed: {reason}")
            print(f"Channel {channel.name} auto-deleted successfully")
        except Exception as e:
            print(f"Failed to auto-delete channel: {e}")
        
    except Exception as e:
        print(f"Error in auto_close_ticket: {e}")

async def start_auto_close_timer(channel):
    """Start 10-minute auto-close timer for new tickets"""
    async def timer_callback():
        await asyncio.sleep(600)  # 10 minutes
        if channel.id in ticket_timers:
            await auto_close_ticket(channel, "No Response In 10 Minutes", "AutoClose System")
            del ticket_timers[channel.id]
    
    timer = asyncio.create_task(timer_callback())
    ticket_timers[channel.id] = timer
    print(f"Auto-close timer started for {channel.name}")

# Optional: Command to check bot status
@bot.command(name='status')
async def status(ctx):
    """Check if the bot is working and show configuration"""
    if ctx.author.guild_permissions.manage_messages:  # Only for users with manage messages permission
        embed = discord.Embed(title="Auto-Delete Bot Status", color=0x00ff00)
        embed.add_field(name="Status", value="✅ Active", inline=False)
        embed.add_field(name="Monitored Channel", value=f"<#{NO_TEXT_CHANNEL_ID}>", inline=False)
        embed.add_field(name="Allowed Message ID", value=str(ALLOWED_MESSAGE_ID), inline=False)
        await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print('bot has logged in!')
    
    # Add persistent views
    load_blacklist()
    bot.add_view(TicketView())
    bot.add_view(TicketControlView())

    try:
        # Clear existing commands first
        bot.tree.clear_commands(guild=discord.Object(id=GUILD_ID))
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print("Cleared existing commands")
        
        # Wait a moment
        await asyncio.sleep(1)
        
        # Force sync to guild again
        bot.tree.add_command(ticket_close)
        guild = discord.Object(id=GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        print(f"Force synced {len(synced)} command(s) to guild")

        # Print all available commands
        print("Available slash commands:")
        for command in bot.tree.get_commands():
            print(f"- /{command.name}")
            
    except Exception as e:
        print(f"Failed to sync commands: {e}")

def get_ordinal(n):
    """Convert number to ordinal (1st, 2nd, 3rd, etc.)"""
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"

def count_user_tickets(guild, user_id, category_id):
    """Count how many tickets a user has in a specific category"""
    category = guild.get_channel(category_id)
    if not category:
        return 0
    
    count = 0
    for channel in category.channels:
        if channel.topic and f"UserID: {user_id}" in channel.topic:
            count += 1
    return count

@bot.tree.command(name="setup-ticket", description="Setup the ticket panel")
async def setup_ticket(interaction: discord.Interaction):
    print(f"setup-ticket command called by {interaction.user}")
    
    # Check permissions
    if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
        
    embed = discord.Embed(
        title="Ticket Support",
        description="""
📨 **Support**
Open a ticket only if you need assistance with one of the following:
- General Support
- Claiming the OG Role
- Interested in Joining the Team

🎉 **Giveaway Claim**
Won a giveaway? Congrats!
Create a ticket only if you're claiming a prize.

🤝 **Partnerships**
Want to partner with us?
Open a ticket to discuss the details.

🦴 **Sell Skelly**
Looking for expensive skelly buyer?
Open a ticket here to get started.

**Note:** Misusing tickets may lead to a blacklist.""",
        color=discord.Color.green()
    )
    embed.set_image(url="https://media.discordapp.net/attachments/1283861398488744057/1284963435980918807/support.png")

    view = TicketView()
    await interaction.channel.send(embed=embed, view=view)

@bot.tree.command(name="ticket-close", description="Close a ticket with optional reason", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(reason="Reason for closing the ticket")
async def ticket_close(interaction: discord.Interaction, reason: str = None):
    # Check if user has permission
    if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
        await interaction.response.send_message("You don't have permission to close tickets.", ephemeral=True)
        return
    
    # Check if this is a ticket channel
    channel = interaction.channel
    if not channel.topic or "UserID:" not in channel.topic:
        await interaction.response.send_message("This command can only be used in ticket channels.", ephemeral=True)
        return
    
    # Use the reason provided or default
    close_reason = reason if reason else "No reason provided"
    
    # Use the same close logic as the button
    control_view = TicketControlView()
    await control_view.close_ticket(interaction, close_reason)

@bot.tree.command(name="set-limit", description="Set ticket limit for a category")
@app_commands.describe(category="Category name", limit="New limit")
@app_commands.choices(category=[
    app_commands.Choice(name="Support", value="Support"),
    app_commands.Choice(name="Giveaway", value="Giveaway"),
    app_commands.Choice(name="Partnerships", value="Partnerships"),
    app_commands.Choice(name="Trusted Approval", value="Trusted Approval")
])
async def set_limit(interaction: discord.Interaction, category: str, limit: int):
    # Check permissions
    if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    if limit < 1:
        await interaction.response.send_message("Limit must be at least 1.", ephemeral=True)
        return
    
    CATEGORY_LIMITS[category] = limit
    
    embed = discord.Embed(
        title="Category Limit Updated",
        description=f"**{category}** ticket limit has been set to **{limit}**",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="blacklist", description="Blacklist a user from creating tickets")
@app_commands.describe(user="User to blacklist")
async def blacklist_user(interaction: discord.Interaction, user: discord.Member):
    # Check permissions
    if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    if user.id in blacklisted_users:
        await interaction.response.send_message(f"{user.mention} is already blacklisted.", ephemeral=True)
        return
    
    blacklisted_users.add(user.id)
    save_blacklist()
    
    embed = discord.Embed(
        title="User Blacklisted",
        description=f"**{user.display_name}** has been successfully blacklisted from creating tickets.",
        color=discord.Color.red()
    )
    embed.add_field(name="User", value=user.mention, inline=True)
    embed.add_field(name="Blacklisted by", value=interaction.user.mention, inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="unblacklist", description="Remove a user from the blacklist")
@app_commands.describe(user="User to unblacklist")
async def unblacklist_user(interaction: discord.Interaction, user: discord.Member):
    # Check permissions
    if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    if user.id not in blacklisted_users:
        await interaction.response.send_message(f"{user.mention} is not blacklisted.", ephemeral=True)
        return
    
    blacklisted_users.remove(user.id)
    save_blacklist()
    
    embed = discord.Embed(
        title="User Unblacklisted",
        description=f"**{user.display_name}** has been successfully removed from the blacklist.",
        color=discord.Color.green()
    )
    embed.add_field(name="User", value=user.mention, inline=True)
    embed.add_field(name="Unblacklisted by", value=interaction.user.mention, inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📨 Support", style=discord.ButtonStyle.secondary, custom_id="support_btn")
    async def support_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_ticket_modal(interaction, "support")

    @discord.ui.button(label="🎉 Giveaway Claim", style=discord.ButtonStyle.danger, custom_id="giveaway_btn")
    async def giveaway_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_ticket_modal(interaction, "giveaway")

    @discord.ui.button(label="🤝 Partnerships", style=discord.ButtonStyle.primary, custom_id="partnership_btn")
    async def partnership_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_ticket_modal(interaction, "partnership")

    @discord.ui.button(label="🦴 Sell Skelly", style=discord.ButtonStyle.success, custom_id="trusted_btn")
    async def trusted_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_ticket_modal(interaction, "trusted")

    async def open_ticket_modal(self, interaction: discord.Interaction, ticket_type: str):
        try:
            # Check if user is blacklisted
            if interaction.user.id in blacklisted_users:
                embed = discord.Embed(
                    title="Access Denied",
                    description="You are blacklisted from creating tickets.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Check category limits
            category_info = category_data[ticket_type]
            category_display_name = category_info["display_name"]
            limit = CATEGORY_LIMITS.get(category_display_name, 1)
            
            user_ticket_count = count_user_tickets(interaction.guild, interaction.user.id, category_info["id"])
            
            if user_ticket_count >= limit:
                await interaction.response.send_message(
                    f"You have reached the maximum limit of {limit} ticket(s) for **{category_display_name}**. Please close your existing ticket(s) before creating a new one.",
                    ephemeral=True
                )
                return
            
            modal = TicketModal(ticket_type)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            print(f"Error in open_ticket_modal: {e}")
            await interaction.response.send_message("An error occurred while processing your request.", ephemeral=True)

class TicketModal(discord.ui.Modal):
    def __init__(self, ticket_type):
        super().__init__(title=f"{ticket_type.capitalize()} Ticket")
        self.ticket_type = ticket_type
        questions = category_data[ticket_type]["questions"]
        
        for i, q in enumerate(questions):
            self.add_item(discord.ui.TextInput(
                label=q["q"],
                placeholder=q["ph"],
                custom_id=f"q{i}",
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=1000
            ))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            category = interaction.guild.get_channel(category_data[self.ticket_type]["id"])
            if not category:
                await interaction.response.send_message("Category not found.", ephemeral=True)
                return

            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                interaction.guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, manage_channels=True),
                interaction.guild.get_role(SPECIAL_ROLE_ID): discord.PermissionOverwrite(
                    view_channel=True, send_messages=True)
            }

            # Add Partner Manager role if partnership ticket
            if self.ticket_type == "partnership":
                partner_role = interaction.guild.get_role(PARTNER_MANAGER_ROLE_ID)
                if partner_role:
                    overwrites[partner_role] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=True)

            # Send the initial response first
            await interaction.response.send_message("Creating ticket...", ephemeral=True)

            channel = await interaction.guild.create_text_channel(
                name=f"{self.ticket_type}-{interaction.user.name}".replace(" ", "-"),
                category=category,
                topic=f"UserID: {interaction.user.id}",
                overwrites=overwrites
            )
            
            # Start auto-close timer
            await start_auto_close_timer(channel)
            
            # Edit the response to show success
            await interaction.edit_original_response(content=f"Ticket created successfully! {channel.mention}")
              
            welcome_embed = discord.Embed(
                title="Support Team",
                description=f"""Hello {interaction.user.mention},
Thank you for reaching out to our support team!
A staff member will be with you shortly.

🔧 **Please provide additional details if needed**

📌 **Do not ping staff** - We'll respond ASAP
Thank you for your patience!""",
                color=discord.Color.green()
            )

            qa_embed = discord.Embed(color=discord.Color.green())
            for i, q in enumerate(category_data[self.ticket_type]["questions"]):
                qa_embed.add_field(name=q["q"], value=f"{self.children[i].value}", inline=False)

            view = TicketControlView()
                 
            # Ping appropriate roles
            if self.ticket_type == "partnership":
                ping_msg = f"{interaction.user.mention}, {interaction.guild.get_role(PARTNER_MANAGER_ROLE_ID).mention}, {interaction.guild.get_role(SPECIAL_ROLE_ID).mention}"
            else:
                ping_msg = f"{interaction.user.mention}, {interaction.guild.get_role(STAFF_ROLE_ID).mention}, {interaction.guild.get_role(SPECIAL_ROLE_ID).mention}"
                
            await channel.send(ping_msg)
            await channel.send(embed=welcome_embed)
            qa_message = await channel.send(embed=qa_embed, view=view)
                
            try:
                await qa_message.pin()
            except:
                pass
                
        except Exception as e:
            print(f"Error creating ticket: {e}")
            try:
                await interaction.edit_original_response(content="Failed to create ticket. Please try again.")
            except:
                await interaction.followup.send("Failed to create ticket. Please try again.", ephemeral=True)

class CloseReasonModal(discord.ui.Modal):
    def __init__(self, control_view):
        super().__init__(title="Close Ticket With Reason")
        self.control_view = control_view
        self.add_item(discord.ui.TextInput(
            label="Reason",
            placeholder="Enter the reason for closing this ticket...",
            style=discord.TextStyle.paragraph,
            required=True
        ))

    async def on_submit(self, interaction: discord.Interaction):
        await self.control_view.close_ticket(interaction, self.children[0].value)

async def generate_transcript_file(channel):
    try:
        print(f"Generating transcript for channel: {channel.name}")
        
        transcript = await chat_exporter.export(
            channel,
            limit=None,
            tz_info="UTC",
            guild=channel.guild,
            bot=bot
        )
        
        if not transcript:
            print("Failed to generate transcript")
            return None
        
        # Create file object
        file_name = f"transcript-{interaction.user.name}.html"
        file_data = io.BytesIO(transcript.encode('utf-8'))
        file_obj = discord.File(file_data, filename=file_name)
        
        return file_obj
        
    except Exception as e:
        print(f"Transcript generation error: {e}")
        return None

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def close_ticket(self, interaction: discord.Interaction, reason: str):
        try:
            channel = interaction.channel
            user_id = None
            
            # Cancel auto-close timer if exists
            if channel.id in ticket_timers:
                ticket_timers[channel.id].cancel()
                del ticket_timers[channel.id]
            
            # Extract user ID from channel topic
            if channel.topic and "UserID:" in channel.topic:
                try:
                    user_id = int(channel.topic.split("UserID:")[1].strip())
                except:
                    pass
            
            # Send initial response
            await interaction.response.send_message("Ticket will be closed in 3 seconds...", ephemeral=True)
            
            # Generate transcript file
            transcript_file = await generate_transcript_file(channel)
            
            # Send DM to user
            if user_id:
                try:
                    user = await bot.fetch_user(user_id)
                    
                    dm_embed = discord.Embed(
                        title="Ticket Closed",
                        description=f"Hello {user.mention}, your ticket has been closed in the **{interaction.guild.name}** discord!",
                        color=discord.Color.green()
                    )
                    dm_embed.add_field(name="Reason", value=reason, inline=False)
                    dm_embed.add_field(name="Closed by", value=interaction.user.display_name, inline=False)
                    
                    if transcript_file:
                        # Create a copy of the file for DM
                        transcript_file.fp.seek(0)
                        dm_file = discord.File(io.BytesIO(transcript_file.fp.read()), filename=transcript_file.filename)
                        await user.send(embed=dm_embed, file=dm_file)
                    else:
                        await user.send(embed=dm_embed)
                    
                    print(f"DM sent successfully to user {user.name}")
                    
                except Exception as e:
                    print(f"Failed to DM user: {e}")

            # Log to transcript channel
            transcript_channel = bot.get_channel(TRANSCRIPT_CHANNEL_ID)
            if transcript_channel:
                try:
                    log_embed = discord.Embed(
                        title=f"Ticket Closed: {channel.name}",
                        description=f"**Reason:** {reason}\n**Closed by:** {interaction.user.mention}",
                        color=discord.Color.green(),
                        timestamp=datetime.utcnow()
                    )
                    
                    if transcript_file:
                        transcript_file.fp.seek(0)
                        log_file = discord.File(io.BytesIO(transcript_file.fp.read()), filename=transcript_file.filename)
                        await transcript_channel.send(embed=log_embed, file=log_file)
                    else:
                        log_embed.add_field(name="Transcript", value="Failed to generate transcript", inline=False)
                        await transcript_channel.send(embed=log_embed)
                        
                    print("Transcript logged successfully")
                except Exception as e:
                    print(f"Failed to log to transcript channel: {e}")

            # Delete the channel
            await asyncio.sleep(3)
            try:
                await channel.delete(reason=f"Ticket closed by {interaction.user.name}: {reason}")
                print(f"Channel {channel.name} deleted successfully")
            except Exception as e:
                print(f"Failed to delete channel: {e}")
            
        except Exception as e:
            print(f"Error in close_ticket: {e}")

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("You don't have permission to close tickets.", ephemeral=True)
            return
        await self.close_ticket(interaction, "No reason provided")

    @discord.ui.button(label="Close With Reason", style=discord.ButtonStyle.secondary, custom_id="close_reason_btn")
    async def close_with_reason_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("You don't have permission to close tickets.", ephemeral=True)
            return
        await interaction.response.send_modal(CloseReasonModal(self))

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary, custom_id="claim_ticket_btn")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("You don't have permission to claim tickets.", ephemeral=True)
            return
            
        try:
            channel = interaction.channel
            current_topic = channel.topic or ""
            user_id = None
            
            # Cancel auto-close timer when ticket is claimed
            if channel.id in ticket_timers:
                ticket_timers[channel.id].cancel()
                del ticket_timers[channel.id]
                print(f"Auto-close timer cancelled for claimed ticket: {channel.name}")
            
            if "UserID:" in current_topic:
                try:
                    user_id = int(current_topic.split("UserID:")[1].strip())
                except:
                    pass

            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True),
                interaction.guild.get_role(SPECIAL_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True)
            }

            if user_id:
                try:
                    member = await interaction.guild.fetch_member(user_id)
                    overwrites[member] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
                except:
                    pass

            new_topic = f"Claimed by {interaction.user.name}" + (f" | UserID: {user_id}" if user_id else "")
            await channel.edit(topic=new_topic, overwrites=overwrites)
            await interaction.response.send_message(f"{interaction.user.mention} has claimed this ticket.")
            
        except Exception as e:
            print(f"Error claiming ticket: {e}")
            await interaction.response.send_message("Failed to claim ticket.", ephemeral=True)

# Start the bot
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
