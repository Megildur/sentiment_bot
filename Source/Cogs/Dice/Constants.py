import discord

COLOR_EMOJIS = {
    "Red": "🔴",
    "Yellow": "🟡",
    "Green": "🟢",
    "Blue": "🔵",
    "Purple": "🟣",
    "Orange": "🟠",
    "Grey": "<:grey_circle:1551035782993551415>",
    "Black": "⚫",
    "White": "⚪",
    "Clear": "💎"
}

COLOR_DISCORD_COLORS = {
    "Red": discord.Color.red(),
    "Yellow": discord.Color.gold(),
    "Green": discord.Color.green(),
    "Blue": discord.Color.blue(),
    "Purple": discord.Color.purple(),
    "Orange": discord.Color.orange(),
    "Grey": discord.Color.light_grey(),
    "Black": discord.Color.from_rgb(45, 45, 45),
    "White": discord.Color.from_rgb(245, 245, 245),
    "Clear": discord.Color.teal()
}

COLOR_ORDER = ["Red", "Yellow", "Green", "Blue", "Purple", "Orange", "Grey", "Black", "White", "Clear"]