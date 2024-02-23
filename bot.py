"""
Program: bot.py
Author: binarypillow
This is the brain's thalamus where information from sensory system are sorted and sent to the right cortical areas.
"""

import config
import utils
import logging
from telegram import (
    Update,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    PicklePersistence,
    CallbackQueryHandler,
    CallbackContext,
    MessageHandler,
    Filters,
    Updater,
    CommandHandler,
    ConversationHandler,
    InlineQueryHandler,
)
from uuid import uuid4
from re import IGNORECASE
from tinydb import TinyDB, Query

# Define database and its subclasses.
db = TinyDB(config.DATABASE_PATH)
groups = db.table('groups')
interns = db.table('interns')
suggestions = db.table('suggestions')
# Different states in the conversation handler.
MENU, INPUT, ADMIN = range(3)
# Define main menu keyboard.
KEYBOARD = [
    [InlineKeyboardButton(text='--------      Triennale      --------', callback_data='null')],
    [InlineKeyboardButton(text='Gruppi generici', callback_data='B-generic')],
    [
        InlineKeyboardButton(text='1°', callback_data='B-first'),
        InlineKeyboardButton(text='2°', callback_data='B-second'),
        InlineKeyboardButton(text='3°', callback_data='B-third')
    ],
    [InlineKeyboardButton(text='Tirocinio', callback_data='internship')],
    [InlineKeyboardButton(text='--------      Magistrale      --------', callback_data='null')],
    [InlineKeyboardButton(text='Gruppi generici', callback_data='M-generic')],
    [
        InlineKeyboardButton(text='1°', callback_data='M-first'),
        InlineKeyboardButton(text='2°', callback_data='M-second'),
    ],
    [InlineKeyboardButton(text='✏ Suggerisci link', callback_data='suggest')],
    [InlineKeyboardButton(text='❓ FAQ', url='https://t.me/faqbiomedicapolito')],
    [
        InlineKeyboardButton(text='🔎 Info', callback_data='about'),
        InlineKeyboardButton(text='🛠️ Admin', callback_data='admin')
    ],
    [InlineKeyboardButton(text='📝 Partecipa', url=config.FORM_LINK)],
]


# ------
# Bot's chat commands
# ------


# \help command remembers user how to use the bot.
def help_command(update: Update, context: CallbackContext) -> None:
    if update.message.chat.type == 'private':
        update.message.reply_text(text=config.HELP_STRING,
                                  parse_mode='Markdown')


# /start command initializes the conversation.
def start_command(update: Update, context: CallbackContext) -> int:
    if update.message.chat.type == 'private':
        reply_markup = InlineKeyboardMarkup(KEYBOARD)
        update.message.reply_text(text=config.MENU_STRINGS['main'],
                                  reply_markup=reply_markup, parse_mode='Markdown')
        return MENU


# Bring back the conversation to the starting point.
def start_over(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    reply_markup = InlineKeyboardMarkup(KEYBOARD)
    query.edit_message_text(text=config.MENU_STRINGS['main'],
                            reply_markup=reply_markup, parse_mode='Markdown')
    return MENU


# Handle keyboard buttons linked to groups' pages.
def groups_page(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    group = Query()
    uncategorized = groups.search((group.type == query.data) & (group.semester == 'zero'))
    first_semester = groups.search((group.type == query.data) & (group.semester == 'one'))
    second_semester = groups.search((group.type == query.data) & (group.semester == 'two'))
    keyboard = []
    if uncategorized:
        for group in uncategorized:
            keyboard.append([InlineKeyboardButton(text=group['text'], url=group['url'])])
    if first_semester:
        keyboard.append([InlineKeyboardButton(text='-----     primo semestre     -----', callback_data='null')])
        for group in first_semester:
            keyboard.append([InlineKeyboardButton(text=group['text'], url=group['url'])])
    if second_semester:
        keyboard.append([InlineKeyboardButton(text='-----     secondo semestre     -----', callback_data='null')])
        for group in second_semester:
            keyboard.append([InlineKeyboardButton(text=group['text'], url=group['url'])])

    keyboard.append([InlineKeyboardButton(text='🔙 Indietro', callback_data='start_over')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=config.MENU_STRINGS[query.data],
                            reply_markup=reply_markup, parse_mode='Markdown')
    return MENU


# Handle keyboard buttons linked to placeholders' and suggestions' pages.
def misc_page(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    if query.data != 'suggest':
        return MENU
    context.user_data['status'] = query.data
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(text='🔙 Indietro', callback_data='start_over')]])
    query.edit_message_text(text=config.MENU_STRINGS[query.data],
                            reply_markup=reply_markup, parse_mode='Markdown')
    return INPUT


# Handle keyboard buttons linked to admins' pages.
def admins_page(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    if utils.check_admin(query.from_user.id, config.BOT_GROUP_ID, context.bot):
        query.answer(f'Benvenuto {query.from_user.first_name}.')
        keyboard = [
            [InlineKeyboardButton(text='Cancella suggerimenti', callback_data='clear')],
            [
                InlineKeyboardButton(text='Aggiungi', callback_data='add_group'),
                InlineKeyboardButton(text='Rimuovi', callback_data='remove_group'),
            ],
            [InlineKeyboardButton(text='🔙 Indietro', callback_data='start_over')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text=utils.create_list(suggestions.all(), config.ADMIN_STRINGS['main']),
                                reply_markup=reply_markup, parse_mode='Markdown')
        return ADMIN
    else:
        query.answer('Non autorizzato.')
        return MENU


# Handle admins' utilities.
def admins_utils(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(text='🔙 Indietro', callback_data='start_over')]])
    query.answer()
    context.user_data['status'] = query.data
    answer = ''
    if query.data == 'clear':
        answer = config.ADMIN_STRINGS[query.data].format(text=config.ADMIN_CONFIRMATION)
    elif query.data == 'add_group':
        answer = config.ADMIN_STRINGS[query.data]
    elif query.data == 'remove_group':
        answer = utils.create_list(groups.all(), config.ADMIN_STRINGS[query.data])
    query.edit_message_text(text=answer,
                            reply_markup=reply_markup, parse_mode="Markdown")
    return INPUT


# Handle admins' utilities.
def get_input(update: Update, context: CallbackContext) -> None:
    status = context.user_data['status']
    message = update.message.text
    entry = ''
    error = False
    # New backup file.
    utils.backup(context.bot)
    if status == 'suggest':
        suggestion = Query()
        user_id = str(update.message.from_user.id)
        if suggestions.count(suggestion.user_id == user_id) < config.SUGGESTIONS_MAXNUM:
            suggestions.insert({'user_id': user_id, 'text': f'{update.message.from_user.first_name} -- '
                                                            f'{message[:config.SUGGESTIONS_MAXCHAR]}'})
        else:
            error = True
    if status == 'clear':
        if message == config.ADMIN_CONFIRMATION:
            suggestions.truncate()
            message = ''
        else:
            error = True
    if status == 'add_group':
        entry = utils.check_format(message)
        if entry:
            groups.insert(entry)
            message = entry['text']
        else:
            error = True
    if status == 'remove_group':
        group = Query()
        if groups.contains(group.text == message):
            groups.remove(group.text == message)
        else:
            error = True

    if error:
        update.message.reply_text(text=config.ERROR_STRINGS[status],
                                  parse_mode='Markdown')
    else:
        update.message.reply_text(text=config.INPUT_STRINGS[status],
                                  parse_mode='Markdown')
        context.bot.send_message(text=config.LOGS_STRINGS[status]
                                 .format(name=update.message.from_user.id, text=message[:config.SUGGESTIONS_MAXCHAR]),
                                 chat_id=config.BOT_GROUP_ID, parse_mode='Markdown')
        if status == 'add_group':
            context.bot.send_message(text=config.LOGS_STRINGS['notice']
                                     .format(text=entry['text'], url=entry['url']),
                                     chat_id=config.GENERAL_GROUP_ID, parse_mode='Markdown')


# ------
# Bot's internship commands
# ------


# /internship [period] command creates a new list.
def new_intern(update: Update, context: CallbackContext) -> None:
    if utils.check_admin(update.message.from_user.id, config.INTERNSHIP_GROUP_ID, context.bot) \
            and update.message.chat.id == config.INTERNSHIP_GROUP_ID:
        # New backup file.
        utils.backup(context.bot)
        interns.truncate()
        update.message.reply_text(text=config.INTERNSHIP_STRINGS['new'],
                                  quote=False, parse_mode='Markdown')
        msg = update.message.reply_text(text=f"\n{utils.create_list(interns.all(), config.INTERNSHIP_STRINGS['list'])}\n"
                                             f"{config.INTERNSHIP_STRINGS['info']}",
                                        quote=False, parse_mode='Markdown')
        if db.all():
            db.update({'id': msg.message_id}, Query().id.exists())
        else:
            db.insert({'id': msg.message_id})


# /add command adds a new user-associated entry to the list.
def add_intern(update: Update, context: CallbackContext) -> None:
    if update.message.chat.id != config.INTERNSHIP_GROUP_ID:
        return
    if len(context.args) >= 1:
        entry_text = utils.escape_chars(' '.join([str(elem) for elem in context.args]).lower())
        entry = entry_text[:250]
        user_id = str(update.message.from_user.id)
        intern = Query()
        message = 'add'
        if interns.contains(intern.id == user_id):
            message = 'edit'
            interns.remove(intern.id == user_id)
            utils.send_list(
                context.bot,
                update.message,
                interns.all(),
                config.INTERNSHIP_STRINGS['list']
            )
        user_text = f"{utils.escape_chars(update.message.from_user.first_name)} " \
                    f"(@{utils.escape_chars(update.message.from_user.username)})\n{entry}"
        interns.insert({'id': user_id, 'text': user_text})
        utils.send_list(
            context.bot,
            update.message,
            interns.all(),
            config.INTERNSHIP_STRINGS['list']
        )
        update.message.reply_text(text=config.INTERNSHIP_STRINGS[message].format(
            name=utils.escape_chars(update.message.from_user.first_name)),
                                  quote=False, parse_mode='Markdown', reply_to_message_id=db.all()[0]['id'])
    else:
        update.message.reply_text(text=config.INTERNSHIP_STRINGS['error_message'],
                                  parse_mode='Markdown')


# /remove command deletes the user-associated entry from the list.
def remove_intern(update: Update, context: CallbackContext) -> None:
    if update.message.chat.id != config.INTERNSHIP_GROUP_ID:
        return
    user_id = str(update.message.from_user.id)
    intern = Query()
    if interns.contains(intern.id == user_id):
        interns.remove(intern.id == user_id)
        utils.send_list(
            context.bot,
            update.message,
            interns.all(),
            config.INTERNSHIP_STRINGS['list']
        )
        update.message.reply_text(text=config.INTERNSHIP_STRINGS['remove'].format(
            name=utils.escape_chars(update.message.from_user.first_name)),
                                  quote=False, parse_mode='Markdown', reply_to_message_id=db.all()[0]['id'])


# ------
# Bot's inline queries
# ------


# Handle inline queries.
def inlinequery(update: Update, context: CallbackContext) -> None:
    query = update.inline_query.query
    group = Query()
    groups_list = groups.search(group.text.search(query, flags=IGNORECASE))
    results = [
        InlineQueryResultArticle(
            id=str(uuid4()),
            title=group['text'],
            input_message_content=InputTextMessageContent(
                '[{}]({})'.format(group['text'], group['url']),
                parse_mode='Markdown',
                disable_web_page_preview=True,
            ),
            url=group['url'],
            thumb_url="https://raw.githubusercontent.com/electrogram-project/encephalogram/main/brain128px.png",
        )
        for group in groups_list
    ]

    update.inline_query.answer(results)


# ------
# Bot's logs
# ------


# Create basic logs. New log file each month.
logging.basicConfig(filename=config.LOGS_PATH, level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main() -> None:
    # Create the Updater and pass the token.
    persistence = PicklePersistence(filename='enc_cache')
    updater = Updater(config.TOKEN, persistence=persistence)
    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher
    # Create conversation pattern
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_command)],
        states={
            MENU: [
                CallbackQueryHandler(groups_page, pattern='^' + 'B-generic' + '$'),
                CallbackQueryHandler(groups_page, pattern='^' + 'B-first' + '$'),
                CallbackQueryHandler(groups_page, pattern='^' + 'B-second' + '$'),
                CallbackQueryHandler(groups_page, pattern='^' + 'B-third' + '$'),
                CallbackQueryHandler(groups_page, pattern='^' + 'about' + '$'),
                CallbackQueryHandler(groups_page, pattern='^' + 'internship' + '$'),
                CallbackQueryHandler(groups_page, pattern='^' + 'M-generic' + '$'),
                CallbackQueryHandler(groups_page, pattern='^' + 'M-first' + '$'),
                CallbackQueryHandler(groups_page, pattern='^' + 'M-second' + '$'),
                CallbackQueryHandler(misc_page, pattern='^' + 'suggest' + '$'),
                CallbackQueryHandler(admins_page, pattern='^' + 'admin' + '$'),
                CallbackQueryHandler(misc_page, pattern='^' + 'null' + '$'),
                CallbackQueryHandler(start_over, pattern='^(?!.*(B-generic|B-first|B-second|B-third|about|internship'
                                                         '|M-generic|M.first|M-second|suggest|admin|null)).*$'),
            ],
            ADMIN: [
                CallbackQueryHandler(admins_utils, pattern='^' + 'clear' + '$'),
                CallbackQueryHandler(admins_utils, pattern='^' + 'add_group' + '$'),
                CallbackQueryHandler(admins_utils, pattern='^' + 'remove_group' + '$'),
                CallbackQueryHandler(start_over, pattern='^(?!.*(B-generic|B-first|B-second|B-third|about|internship'
                                                         '|M-generic|M.first|M-second|suggest|admin|null)).*$'),
            ],
            INPUT: [
                MessageHandler(Filters.text & ~Filters.command, get_input),
                CallbackQueryHandler(start_over, pattern='^' + 'start_over' + '$'),
            ],

        },
        fallbacks=[CommandHandler('start', start_command)],
        name="my_conv",
        persistent=True,
    )
    dispatcher.add_handler(conv_handler)
    # Help command
    dispatcher.add_handler(CommandHandler('help', help_command))
    # Internship commands
    dispatcher.add_handler(CommandHandler('new', new_intern))
    dispatcher.add_handler(CommandHandler('add', add_intern))
    dispatcher.add_handler(CommandHandler('remove', remove_intern))
    # Inline queries
    dispatcher.add_handler(InlineQueryHandler(inlinequery))

    # Start the Bot.
    updater.start_polling()
    # Run the bot until the user presses Ctrl-C or the process receives SIGINT, SIGTERM or SIGABRT.
    updater.idle()


if __name__ == '__main__':
    main()
