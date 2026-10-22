"""Sentiment's colors, in one place. Pick by meaning, not by mood:

    BRAND   normal replies and success: "Sentiment is talking"
    ACCENT  warnings, pending, "not right now"
    INFO    reference and settings panels (/help, /color_roles)
    MUTED   ended, deleted or disabled states
    ERROR   errors, refusals and delete confirmations only

A character's swing color is content, not decoration: anything about a
character (rolls, cards, HP) uses its swing's color from Constants, and no
accent at all while the character is colorless.
"""

import discord

PINK = 0xEC4899   # not one of the ten swing colors, so it never reads as a swing
AMBER = 0xFBBF24
NAVY = 0x1D335B
SLATE = 0x8C96AC
RED = 0xE5484D

BRAND = discord.Colour(PINK)
ACCENT = discord.Colour(AMBER)
INFO = discord.Colour(NAVY)
MUTED = discord.Colour(SLATE)
ERROR = discord.Colour(RED)
