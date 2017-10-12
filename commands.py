# TopSupergroupsBot - A telegram bot for telegram public groups leaderboards
# Copyright (C) 2017  Dario <dariomsn@hotmail.it> (github.com/91DarioDev)
#
# TopSupergroupsBot is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# TopSupergroupsBot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with TopSupergroupsBot.  If not, see <http://www.gnu.org/licenses/>.

import utils
import keyboards
import database
import constants
import votelink
import leaderboards
import messages_supergroups
import get_lang
import supported_langs

def start(bot, update, args):
	if len(args) == 0:
		if update.message.chat.type != "private":
			return
		start_no_params(bot, update)
		return
	first_arg = args[0]
	if first_arg.startswith("vote"):
		votelink.send_vote_by_link(bot, update, first_arg)


def start_no_params(bot, update):
	guessed_lang = utils.guessed_user_lang(bot, update)
	query = "UPDATE users SET lang = %s WHERE user_id = %s"
	database.query_w(query, guessed_lang, update.message.from_user.id)
	text = get_lang.get_string(guessed_lang, "help_message")
	update.message.reply_text(text, parse_mode="HTML")


def settings(bot, update):
	if update.message.chat.type == "private":
		settings_private(bot, update)
	elif update.message.chat.type in ['group', 'supergroup']:
		settings_group(bot, update)



@utils.private_only
def vote(bot, update, args):
	user_id = update.message.from_user.id
	lang = utils.get_db_lang(user_id)
	if len(args) != 1:
		text = get_lang.get_string(lang, "insert_param_vote")
		update.message.reply_text(text, parse_mode="HTML")
		return
	username = args[0]
	if username.startswith("@"):
		username = username.replace("@", "")
	
	query = """
	SELECT s.group_id, s_ref.username, s_ref.title, v.vote, v.vote_date
	FROM supergroups_ref AS s_ref
	RIGHT JOIN supergroups AS s
	ON s_ref.group_id = s.group_id
	LEFT OUTER JOIN votes AS v 
	ON v.group_id = s.group_id
	AND v.user_id = %s
	WHERE LOWER(s_ref.username) = LOWER(%s) 
		AND s.bot_inside = TRUE
	"""

	extract = database.query_r(query, user_id, username)

	if len(extract) == 0:
		# the group does not exist otherwise anything is returned and if None is NULL
		text = get_lang.get_string(lang, "cant_vote_this")
		update.message.reply_text(text=text)
		return

	if len(extract) > 1:
		print("error too many")
		return

	extract = extract[0]
	text = get_lang.get_string(lang, "vote_this_group").format(
					extract[0], extract[1], extract[2])
	if extract[3] and extract[4] is not None:
		stars = constants.EMOJI_STAR*extract[3]
		date = extract[4].strftime("%d/%m/%Y")
		text += "\n\n"+get_lang.get_string(lang, "already_voted").format(stars, date)
	reply_markup = keyboards.vote_group_kb(extract[0], lang)
	update.message.reply_text(text=text, reply_markup=reply_markup)



def settings_private(bot, update):
	lang = utils.get_db_lang(update.message.from_user.id)
	reply_markup = keyboards.main_private_settings_kb(lang)
	text = get_lang.get_string(lang, "private_settings")
	update.message.reply_text(text=text, reply_markup=reply_markup)



@utils.admin_command_only
def settings_group(bot, update):
	query_db = "SELECT lang FROM supergroups WHERE group_id = %s"
	lang = database.query_r(query_db, update.message.chat.id, one=True)[0]
	text = get_lang.get_string(lang, "choose_group_lang")
	reply_markup = keyboards.main_group_settings_kb(lang)
	update.message.reply_text(text=text, reply_markup=reply_markup)


@utils.admin_command_only
def groupleaderboard(bot, update):
	if update.message.chat.type == "private":
		update.message.reply_text("Only in groups")
		return
	leaderboards.groupleaderboard(bot, update)


def language(bot, update):
	if update.message.chat.type == "private":
		language_private(bot, update)
	else:
		language_group(bot, update)


@utils.private_only
def region(bot, update):
	query = "SELECT lang, region FROM users WHERE user_id = %s"
	extract = database.query_r(query, update.message.from_user.id, one=True)
	lang = extract[0]
	region = extract[1]
	text = get_lang.get_string(lang, "choose_region")
	reply_markup = keyboards.private_region_kb(lang, region)
	update.message.reply_text(text=text, reply_markup=reply_markup)


@utils.creator_command_only
def language_group(bot, update):
	messages_supergroups.choose_group_language(bot, update)


# this does not need the only private decorator cause the command has the same
# name for groups
def language_private(bot, update):
	query = "SELECT lang FROM users WHERE user_id = %s"
	extract = database.query_r(query, update.message.from_user.id, one=True)
	lang = extract[0]
	text = get_lang.get_string(lang, "choose_your_lang")
	reply_markup = keyboards.private_language_kb(lang, back=False)
	update.message.reply_text(text=text, reply_markup=reply_markup)


@utils.private_only
def aboutyou(bot, update):
	user_id = update.message.from_user.id

	query = """
	SELECT main.group_id, s_ref.title, s_ref.username, main.m_per_group, main.pos, u.lang 
	FROM (
		SELECT user_id, group_id, COUNT(user_id) AS m_per_group,
			RANK() OVER (
				PARTITION BY group_id
				ORDER BY COUNT(group_id) DESC
				) AS pos 
		FROM messages
		WHERE message_date > date_trunc('week', now())
		GROUP BY group_id, user_id
	) AS main 
	LEFT OUTER JOIN supergroups_ref AS s_ref
	USING (group_id)
	RIGHT JOIN users AS u
	ON u.user_id = main.user_id
	WHERE main.user_id = %s
	ORDER BY m_per_group DESC
	"""
	extract = database.query_r(query, user_id)

	if len(extract) == 0:
		text = "This week you didn't sent messages in groups yet"

	else:
		lang = extract[0][5]
		text = "This week you alrady sent:\n\n"
		for i in extract:
			title = i[1]
			username = i[2]
			m_per_group = i[3]
			pos_per_group = i[4]
			add_t = get_lang.get_string(lang, "messages_in_groups_position")
			add_t = add_t.format(m_per_group, username, pos_per_group)
			text += add_t
		text += about_you_world(user_id)

	utils.send_message_long(bot, chat_id=user_id, text=text)




def about_you_world(user_id):
	# thank https://stackoverflow.com/a/46437403/8372336 for the help in creating the query
	query = """
	SELECT  main.num_msgs, main.num_grps, main.rnk
	FROM (
	SELECT
	    user_id,
	    num_grps,
	    num_msgs,
	    RANK() OVER(ORDER BY num_msgs DESC, num_grps DESC, user_id DESC) rnk
	FROM (
	    SELECT
	        user_id,
	        COUNT(distinct group_id) AS num_grps,
	        COUNT(*)                 AS num_msgs
	    FROM messages
	    WHERE message_date > date_trunc('week', now())
	    GROUP BY user_id
	    ) AS sub
	) AS main
	WHERE main.user_id = %s
	"""

	extract = database.query_r(query, user_id, one=True)

	text = "\nYou globally already sent {} messages in {} groups during this week. Position: {}"
	text = text.format(extract[0], extract[1], extract[2])
	return text


@utils.private_only
def leaderboard(bot, update):
	query = "SELECT lang, region FROM users WHERE user_id = %s"
	extract = database.query_r(query, update.message.from_user.id, one=True)
	lang = extract[0]
	region = extract[1]
	text = get_lang.get_string(lang, "generic_leaderboard").format(supported_langs.COUNTRY_FLAG[region])
	reply_markup = keyboards.generic_leaderboard_kb(lang, region)
	update.message.reply_text(text=text, reply_markup=reply_markup, parse_mode="HTML")


@utils.private_only
def help(bot, update):
	lang = utils.get_db_lang(update.message.from_user.id)
	text = get_lang.get_string(lang, "help_message")
	update.message.reply_text(text=text, parse_mode="HTML")