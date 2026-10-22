"""Runs every command and presses every button and form against a temporary database.

Checks that each feature still works, that presses work the same after a restart,
that only the right people can press, and the rules in AGENTS.md: no controls kept
in memory, nothing lasting sent privately, pings only where they belong.

    venv\\Scripts\\python.exe scratch\\test_press_everything.py
"""
import asyncio
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fakes import Harness, check, finish, member  # noqa: E402


from Source.Cogs.Dice.RollText import parse_roll  # noqa: E402

random.seed(7)


def pings_nobody(mentions) -> bool:
    return mentions is not None and not mentions.everyone and not mentions.users and not mentions.roles


async def characters(h: Harness, a, b) -> None:

    # A first /set_attributes offers to create a character.
    i = await h.command("set_attributes_command", a)
    panel = i.original
    check(panel.control("create_new_char") is not None, "create view has the create button")
    check(not i.notices(), f"no notices on first /set_attributes: {i.notices()}")

    # Someone else can't use it.
    other = await h.press(panel, "create_new_char", b)
    check(other.notices() == ["Not your menu"], f"another player is refused: {other.notices()}")

    i = await h.press(panel, "create_new_char", a)
    form = await h.submit(i, name_input="Aria", colors=["Red", "Blue", "Yellow"], bonuses=["3", "1", None])
    check(await h.db.get_selected_char(a.id) == "Aria", "the new character is active")
    check(sorted(await h.db.get_character_attributes(a.id, "Aria")) == [("Blue", 1), ("Red", 3), ("Yellow", 0)], "bonuses go with the color in the same place")
    check(await h.db.get_hp(a.id, "Aria") == (10, 10), "new characters start at 10 / 10 HP")
    check("Character created" in panel.text and "**Red** (*None*): +3" in panel.text, "panel redrawn in place")

    i = await h.press(panel, "add_atrs_btn", a)
    await h.submit(i, color=["Green"], bonus="2")
    check(("Green", 2) in await h.db.get_character_attributes(a.id, "Aria"), "attribute added")

    i = await h.press(panel, "edit_attribute_select", a, ["Blue"])
    await h.submit(i, color=["Blue"], bonus="5")
    check(("Blue", 5) in await h.db.get_character_attributes(a.id, "Aria"), "attribute edited")

    i = await h.press(panel, "name_atrs_btn", a)
    await h.submit(i, color=["Red"], name_input="Passion")
    check("(*Passion*)" in panel.text, "attribute titled")

    i = await h.press(panel, "delete_atrs_btn", a)
    await h.submit(i, color=["Green"])
    check("Green" not in dict(await h.db.get_character_attributes(a.id, "Aria")), "attribute deleted")

    # A second character, then switch back from the panel's menu.
    i = await h.press(panel, "create_new_char", a)
    await h.submit(i, name_input="Bram", colors=["Black"], bonuses=["2", None, None])
    check(await h.db.get_selected_char(a.id) == "Bram", "Bram is active")
    await h.press(panel, "change_char_select", a, ["Aria"])
    check(await h.db.get_selected_char(a.id) == "Aria", "switched back to Aria")

    # Deleting asks first; Cancel goes back; deleting Bram keeps Aria active.
    await h.press(panel, "delete_char_select", a, ["Bram"])
    check(panel.control("confirm_delete_char_btn") is not None, "delete asks first")
    check(panel.components[0].accent_colour is not None, "confirm panel has an accent")
    await h.press(panel, "cancel_delete_char_btn", a)
    check(panel.control("edit_attribute_select") is not None, "cancel returns to the panel")
    await h.press(panel, "delete_char_select", a, ["Bram"])
    await h.press(panel, "confirm_delete_char_btn", a)
    check(await h.db.get_all_characters(a.id) == ["Aria"], "Bram deleted")
    check(panel.control("edit_attribute_select") is not None, "back on Aria's panel")

    # Player B gets a character straight in the database.
    await h.db.set_attributes(b.id, "Corin", [("Blue", 2), ("Orange", 1)])
    await h.db.set_selected_char(b.id, "Corin")
    h.panel = panel


async def rolls(h: Harness, a, b) -> None:

    i = await h.command("roll_to_dye", a)
    dye = i.original
    check(not dye.ephemeral, "Roll to Dye is public")
    state = parse_roll(dye.text)
    check(state.kind == "dye" and state.display_name == "Aria" and len(state.dice) == 3, f"Roll to Dye reads back: {state}")
    tracked = await h.db.get_tracked_view(dye.id)
    check(tracked == (a.id, "RollToDyeView", "Aria"), f"roll tracked: {tracked}")

    # After a restart nothing is in memory; Set Swing still offers this roll's dice.
    await h.restart()
    other = await h.press(dye, "set_swing_btn", b)
    check(other.notices() == ["Not your menu"], f"another player can't change the roll: {other.notices()}")
    i = await h.press(dye, "set_swing_btn", a)
    check(i.modal is not None and [d.color for d in i.modal.choices] == [d.color for d in state.dice], "Set Swing offers the rolled dice")
    red = next(d for d in state.dice if d.color == "Red")
    await h.submit(i, color=["Red"])
    check(await h.db.get_swing(a.id, "Aria") == ("Red", red.roll), "Swing saved with the die's result")
    after = parse_roll(dye.text)
    check([d.color for d in after.dice if d.is_swing] == ["Red"], "roll redrawn with the Swing marked")
    check(f"### Total: {sum(d.roll for d in state.dice) + 3}" in dye.text, "the Swing's bonus is added to the total (rulebook example)")

    # Support: B sends a die to A, pinging A only.
    i = await h.command("support", b, a)
    check(i.modal is not None, "support opens a form")
    sent = await h.submit(i, color=["Blue"])
    message = sent.sent[0]
    check(message.text.startswith(f"<@{a.id}>"), "the ally is pinged on its own line")
    check([u.id for u in message.allowed_mentions.users] == [a.id], "only the ally is pinged")
    check(await h.db.get_active_shared_out_dice(b.id, "Corin") == ["Blue"], "the die is lent out")

    # Roll to Do with the Swing, then apply the support die.
    i = await h.command("roll_to_do", a)
    do = i.original
    do_state = parse_roll(do.text)
    check(do_state.swing is not None and do_state.swing[0] == "Red" and do_state.swing[3] == 3, f"Roll to Do uses the Swing: {do_state.swing}")
    check(do.control("apply_support_btn") is not None, "support button shown while a die waits")
    await h.restart()
    await h.press(do, "apply_support_btn", a)
    do_after = parse_roll(do.text)
    check(len(do_after.support) == 1 and do_after.support[0].color == "Blue" and do_after.support[0].from_char == "Corin", f"support die added: {do_after.support}")
    check(do_after.d20 == do_state.d20, "the d20 is kept")
    check(do.control("apply_support_btn") is None, "no more support dice to apply")
    check("Blue" in await h.db.get_locked(b.id, "Corin"), "the support die comes back Locked")

    # 0 HP: the steps follow the rulebook order.
    i = await h.command("hp_damage", a, 25)
    text = i.original.text
    check(text.index("/roll_to_recover") < text.index("/wound_die"), "Roll to Recover comes before Wounding")
    check(await h.db.get_hp(a.id, "Aria") == (0, 10), "damage stops at 0")

    i = await h.command("roll_to_recover", a)
    recover = i.original
    rec = parse_roll(recover.text)
    check(rec.kind == "recover" and rec.hp and rec.hp[0] == 0, f"Roll to Recover reads back: {rec.hp}")
    total = sum(d.roll + (d.bonus or 0) for d in rec.dice)
    check(rec.hp[1] == min(10, total), "at 0 HP the total becomes HP")
    await h.restart()
    i = await h.press(recover, "set_swing_btn", a)
    await h.submit(i, color=["Blue"])
    check(parse_roll(recover.text).hp == rec.hp, "HP line kept after picking a Swing")
    check((await h.db.get_swing(a.id, "Aria"))[0] == "Blue", "new Swing from Roll to Recover")

    i = await h.command("hp_heal", a, 3)
    check("Healed" in i.original.text, "heal posts a result")

    # Dice states through their forms.
    i = await h.command("lock_die", a)
    await h.submit(i, color=["Blue"])
    check("Blue" in await h.db.get_locked(a.id, "Aria") and await h.db.get_swing(a.id, "Aria") is None, "Locking the Swing die drops the Swing")
    i = await h.command("unlock_die", a)
    await h.submit(i, color=["Blue"])
    check("Blue" not in await h.db.get_locked(a.id, "Aria"), "unlocked")
    await h.db.lock_die(a.id, "Aria", "Yellow")
    i = await h.command("wound_die", a)
    card = await h.submit(i, color=["Red"])
    check(await h.db.get_wounded(a.id, "Aria") == ["Red"] and await h.db.get_locked(a.id, "Aria") == [], "a Wound Unlocks every die")
    check(pings_nobody(card.sent[0].allowed_mentions), "the card doesn't ping")
    i = await h.command("unwound_die", a)
    await h.submit(i, color=["Red"])
    check(await h.db.get_wounded(a.id, "Aria") == [], "healed")

    # Nothing to unlock: a private notice, no form.
    i = await h.command("unlock_die", a)
    check(i.modal is None and i.notices() == ["Nothing to change"], f"nothing to unlock: {i.notices()}")

    h.dye = dye


async def card_and_hp(h: Harness, a, b) -> None:
    i = await h.command("character_card", a)
    card = i.original
    check(f"<@{a.id}>" in card.text and pings_nobody(card.allowed_mentions), "card names the player without pinging")

    await h.press(card, "manage_max_hp_btn", a)
    check(card.control("pot_flat_hp_btn") is not None, "Max HP panel opened in place")
    cur, mx = await h.db.get_hp(a.id, "Aria")
    await h.press(card, "pot_flat_hp_btn", a)
    check(await h.db.get_hp(a.id, "Aria") == (cur + 5, mx + 5), "flat Potential: +5 Max HP and current HP")
    await h.press(card, "pot_roll_hp_btn", a)
    check((await h.db.get_hp(a.id, "Aria"))[1] > mx + 5, "rolled Potential raises Max HP")
    i = await h.press(card, "custom_adj_max_hp_btn", a)
    await h.submit(i, exact_input="25", delta_input="")
    check((await h.db.get_hp(a.id, "Aria"))[1] == 25, "exact Max HP")
    i = await h.press(card, "custom_adj_max_hp_btn", a)
    bad = await h.submit(i, exact_input="", delta_input="lots")
    check(bad.notices() == ["Not a number"], f"bad number refused: {bad.notices()}")

    other = await h.press(card, "pot_flat_hp_btn", b)
    check(other.notices() == ["Not your menu"], "Max HP buttons are the player's only")
    await h.press(card, "back_to_card_btn", a)
    check(card.control("change_card_char_select") is not None, "back to the card")
    await h.press(card, "close_menu_button", a)
    check(card.deleted and await h.db.get_tracked_view(card.id) is None, "closing deletes and forgets the message")

    # The 60+ bracket can't roll.
    await h.db.set_hp(a.id, "Aria", 60, 60)
    i = await h.command("hp_max", a)
    roll_button = i.original.control("pot_roll_hp_btn")
    check(roll_button is not None and roll_button.disabled, "no roll at 60+ Max HP")


async def switching(h: Harness, a, b) -> None:
    # A new active character greys out rolls for the old one and redraws panels.
    await h.db.set_attributes(a.id, "Bram", [("White", 1)])
    i = await h.command("change_active_character", a, "Bram")
    check(i.notices() == ["Active character changed"], f"switched: {i.notices()}")
    check(h.dye.control("set_swing_btn").disabled, "the old character's roll is greyed out")
    check("*Bram*" in h.panel.text, "the setup panel follows the new active character")
    check(await h.db.get_tracked_view(h.dye.id) is None, "the old roll is forgotten")

    i = await h.command("change_active_character", a, "Nobody")
    check(i.notices() == ["Character not found"], "unknown character refused privately")


async def gm(h: Harness, a, b, c) -> None:
    i = await h.command("set_gm_c", c, b)
    check(i.notices() == ["Permission needed"] and await h.db.get_gm() is None, "members without Manage Server can't choose the GM")

    i = await h.command("set_gm_c", a, b)
    check(await h.db.get_gm() == b.id, "A (Manage Server) made B the GM")
    check([u.id for u in i.original.allowed_mentions.users] == [b.id], "the new GM is pinged")

    i = await h.command("set_gm_c", b, c)
    prompt = i.original
    check(prompt.control("confirm_dm") is not None and pings_nobody(prompt.allowed_mentions), "changing the GM asks first, without pinging")
    other = await h.press(prompt, "confirm_dm", a)
    check(other.notices() == ["Not your menu"], "only whoever ran /set_gm confirms")
    await h.restart()
    confirm = await h.press(prompt, "confirm_dm", b)
    check(await h.db.get_gm() == c.id, "GM changed after confirming")
    check(prompt.control("confirm_dm").disabled, "the prompt is greyed out")
    check(confirm.sent and f"<@{c.id}>" in confirm.sent[0].text, "the new GM is announced")

    # The GM can use any player's panel and rolls, and mark NPCs on their own panel.
    i = await h.press(h.panel, "add_atrs_btn", c)
    check(i.modal is not None and i.modal.user_id == a.id, "the GM edits the player's character")
    await h.db.set_attributes(c.id, "Villain", [("Purple", 4)])
    await h.db.set_selected_char(c.id, "Villain")
    i = await h.command("set_attributes_command", c)
    gm_panel = i.original
    check(gm_panel.control("toggle_npc_btn") is not None, "the GM's panel offers NPC marking")
    await h.press(gm_panel, "toggle_npc_btn", c)
    check(await h.db.get_char_display_name("Villain") == "Villain (NPC)", "marked as NPC")
    other = await h.press(gm_panel, "toggle_npc_btn", a)
    check(other.notices() in (["Not your menu"], ["GM only"]), f"only the GM marks NPCs: {other.notices()}")


async def help_pages(h: Harness, a) -> None:
    i = await h.command("help_command", a)
    page = i.original
    check("Page 1/" in page.control("paginator_indicator").label, "help opens on page 1")
    await h.restart()
    await h.press(page, "paginator_next", a)
    check("Page 2/" in page.control("paginator_indicator").label, "next page after a restart")
    await h.press(page, "paginator_prev", a)
    check("Page 1/" in page.control("paginator_indicator").label and page.control("paginator_prev").disabled, "back to page 1")


async def color_roles(h: Harness, a, b) -> None:
    i = await h.command("color_roles", a)
    panel = i.original
    check("Swing color roles" in panel.text, "panel posted")

    staff_only = await h.press(panel, "auto_setup_color_roles_btn", b)
    check(staff_only.notices() == ["Permission needed"], f"setup needs Manage Roles or GM: {staff_only.notices()}")
    await h.press(panel, "auto_setup_color_roles_btn", a)
    check(len(await h.db.get_guild_color_roles(h.guild.id)) == 10, "all 10 roles set up")

    await h.press(panel, "color_select_comp", b, ["Blue"])
    check("**Blue:**" in panel.text, "anyone can switch the color shown")
    await h.press(panel, "reset_color_role_btn", a)
    check("Blue" not in await h.db.get_guild_color_roles(h.guild.id), "the selected color (read from the message) was reset")

    await h.db.set_swing(a.id, "Aria", "Red", 4)
    await h.db.set_selected_char(a.id, "Aria")
    i = await h.press(panel, "sync_my_swing_role_btn", a)
    check(i.notices() == ["Role synced"], f"sync my role: {i.notices()}")
    red = h.guild.get_role((await h.db.get_guild_color_roles(h.guild.id))["Red"])
    check(red in h.guild.get_member(a.id).roles, "A has the Red role")

    i = await h.command("drop_swing", a)
    check(red not in h.guild.get_member(a.id).roles, "dropping the Swing removes the role")


async def main() -> None:
    h = await Harness().start()
    a = member(h, 101, manage_guild=True, manage_roles=True)
    b = member(h, 102)
    c = member(h, 103)

    try:
        await characters(h, a, b)
        await rolls(h, a, b)
        await card_and_hp(h, a, b)
        await switching(h, a, b)
        await gm(h, a, b, c)
        await help_pages(h, a)
        await color_roles(h, a, b)
    finally:
        # Closes the database thread, or a failure would leave the process hanging.
        await h.cog.cog_unload()
    finish()


asyncio.run(main())
