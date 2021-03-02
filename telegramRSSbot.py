import feedparser
import logging
import sqlite3
import os
import yaml
import telegram 
import telegram.ext  
from pathlib import Path
import post

Path("config").mkdir(parents=True, exist_ok=True)

# Docker env
if os.environ.get('TOKEN'):
    Token = os.environ['TOKEN']
    chatid = os.environ['CHATID']
    delay = int(os.environ['DELAY'])
else:
    Token = "X"
    chatid = "X"
    delay = 120
   


if os.environ.get('MANAGER') and os.environ['MANAGER'] != 'X':
    manager = os.environ['MANAGER']
else:
    manager = chatid

if Token == "X":
    print("Token not set!")

with open('config/config.yaml',encoding='utf-8')as f:
    conf=yaml.load(f,Loader=yaml.FullLoader)
    print(conf)
    Token=conf['bot_token']
    delay=conf['update_interval']*60
    groupId=conf['group_id']

groupId=90532269
rss_dict = {}


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.WARNING)
# logging.getLogger('apscheduler.executors.default').propagate = False  # to use this line, set log level to INFO


# 检查是否有管理员权限
def is_manager(update):
    chat = update.message.chat
    userid = str(chat.id)
    username = chat.username

    userid=update.message.from_user.id
    username = update.message.from_user.username
    command = update.message.text
    print(f'\n ({username}/{userid}) attempted to use "{command}", ', end='')
    is_allowed_user =False
    for allowed_user in conf['allowed_users']:
        if str(allowed_user) == userid:
            is_allowed_user=True


    if is_allowed_user==False:
        update.effective_message.reply_text('您没有权限使用这个机器人。')
        print('forbade.')
        raise
    else:
        print('allowed.')


# SQLITE
def sqlite_connect():
    global conn
    conn = sqlite3.connect('config/rss.db', check_same_thread=False)


def sqlite_load_all():
    sqlite_connect()
    c = conn.cursor()
    c.execute('SELECT name,link,last FROM rss')
    rows = c.fetchall()
    conn.close()
    return rows


def sqlite_write(name, link, last, update=False):
    sqlite_connect()
    c = conn.cursor()
    p = [last, name]
    q = [name, link, last]
    if update:
        c.execute('''UPDATE rss SET last = ? WHERE name = ?;''', p)
    else:
        c.execute('''INSERT INTO rss('name','link','last') VALUES(?,?,?)''', q)
    conn.commit()
    conn.close()


# 重新加载RSS订阅到缓存________________________________________
def rss_load():
    # if the dict is not empty, empty it.
    if bool(rss_dict):
        rss_dict.clear()

    for row in sqlite_load_all():
        rss_dict[row[0]] = (row[1], row[2])


def cmd_rss_list(update, context):
    is_manager(update)

    if bool(rss_dict) is False:
        update.effective_message.reply_text('数据库为空')
    else:
        for title, url_list in rss_dict.items():
            update.effective_message.reply_text(
                '标题: ' + title +
                '\nRSS 源: ' + url_list[0] +
                '\n最后检查的文章: ' + url_list[1])


def cmd_rss_add(update, context):
    is_manager(update)

    # try if there are 2 arguments passed
    feed_title=''
    feed_url=''
    try:
        context.args[0]

    except IndexError:
        update.effective_message.reply_text(
            'ERROR: 格式需要为: /add RSS_URL')
        raise

    # try if the url is a valid RSS feed
    try:
        rss_d = feedparser.parse(context.args[0])
        rss_d.entries[0]['title']
        feed_title = rss_d.feed.title
        feed_url = context.args[0]
    except IndexError:
        print(f'\n ({rss_d.feed.title}/{feed_url}) is not rss feed ', end='')
        update.effective_message.reply_text(
            'ERROR: 链接看起来不像是个 RSS 源，或该源不受支持')
        raise
   
    sqlite_write(feed_title, feed_url,
                 str(rss_d.entries[0]['link']))
    rss_load()
    update.effective_message.reply_text(
        '已添加 \n标题: %s\nRSS 源: %s' % (feed_title, feed_url))


def cmd_rss_remove(update, context):
    is_manager(update)

    conn = sqlite3.connect('config/rss.db')
    c = conn.cursor()
    q = (context.args[0],)
    try:
        c.execute("DELETE FROM rss WHERE name = ?", q)
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print('Error %s:' % e.args[0])
    rss_load()
    update.effective_message.reply_text("已移除: " + context.args[0])


def cmd_help(update, context):
    # is_manager(update)
    update.effective_message.reply_text(
        f"""RSS to Telegram bot \\(Weibo Ver\\.\\)
\n成功添加一个 RSS 源后, 机器人就会开始检查订阅，每 {delay} 秒一次。 \\(可修改\\)
\n标题为只是为管理 RSS 源而设的，可随意选取，但不可有空格。
\n命令:
__*/help*__ : 发送这条消息
__*/add 标题 RSS*__ : 添加订阅
__*/remove 标题*__ : 移除订阅
__*/list*__ : 列出数据库中的所有订阅，包括它们的标题和 RSS 源
__*/test RSS 编号\\(可选\\)*__ : 从 RSS 源处获取一条 post \\(编号为 0\\-based, 不填或超出范围默认为 0\\)
\n您的 chatid 是: {chatid}""",
        parse_mode='MarkdownV2'
    )

#测试指定RSS源
def cmd_test(update, context):
    is_manager(update)

    # try if there are 2 arguments passed
    try:
        context.args[0]
    except IndexError:
        update.effective_message.reply_text(
            'ERROR: 格式需要为: /test RSS_URL ')
        raise

    url = context.args[0]
    rss_d = feedparser.parse(url)
    #if(rss_d.entries 
    #    and len(rss_d.entries) > 0 )
    post.send(chatid, rss_d.entries[0]['summary'], rss_d.feed.title, rss_d.entries[0]['link'], context)
    #else

def cmd_set_group(update, context):

    global groupId
    print(groupId)
    #update.effective_message.reply_text("已设置审核群" )
    context.bot.send_message(update.message.chat_id,
                             text="已设置本群为审稿群")
    groupId=update.message.chat_id
    print(groupId)


def inlinekeyboard1(update: telegram.Update, context: telegram.ext.CallbackContext) -> None:
    keyboard = [
        [
            telegram.InlineKeyboardButton("Option 1", callback_data='1'),
            telegram.InlineKeyboardButton("Option 2", callback_data='2'),
        ],
        [telegram.InlineKeyboardButton("Option 3", callback_data='3')],
    ]

    reply_markup = telegram.InlineKeyboardMarkup(keyboard)

    update.message.reply_text('Please choose:', reply_markup=reply_markup)
    
def inlinekeyboard2(update: telegram.Update, context: telegram.ext.CallbackContext) -> None:
    """Show new choice of buttons"""
    query = update.callback_query
    query.answer()
    keyboard = [[telegram.InlineKeyboardButton("Option 1", callback_data='1'),
                 telegram.InlineKeyboardButton("Option 2", callback_data='2')],
                [telegram.InlineKeyboardButton("Option 3", callback_data='3')],
                [telegram.InlineKeyboardButton(text="Source code", url="https://github.com/DcSoK/ImgurPlus")]]
    reply_markup = telegram.InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        text="Second CallbackQueryHandler, Choose a route", reply_markup=reply_markup
    )
def button(update: telegram.Update, context: telegram.ext.CallbackContext) -> None:
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    query.answer()

    query.edit_message_text(text=f"Selected option: {query.data}")

    
def rss_monitor(context):
    update_flag = False
    for name, url_list in rss_dict.items():
        rss_d = feedparser.parse(url_list[0])
        if not rss_d.entries:
            # print(f'Get {name} feed failed!')
            print('x', end='')
            break
        if url_list[1] == rss_d.entries[0]['link']:
            print('-', end='')
        else:
            print('\nUpdating', name)
            update_flag = True
            # workaround, avoiding deleted weibo causing the bot send all posts in the feed
            # TODO: log recently sent weibo, so deleted weibo won't be harmful. (If a weibo was deleted while another
            #  weibo was sent between delay duration, the latter won't be fetched.) BTW, if your bot has stopped for
            #  too long that last fetched post do not exist in current RSS feed, all posts won't be fetched and last
            #  fetched post will be reset to the newest post (through it is not fetched).
            last_flag = False
            for entry in rss_d.entries[::-1]:  # push all messages not pushed
                if last_flag:
                    # context.bot.send_message(chatid, rss_d.entries[0]['link'])
                    print('\t- Pushing', entry['link'])
                    message_info=post.send(chatid, entry['summary'], rss_d.feed.title, entry['link'], context)
                    global groupId
                    message_info=post.send(groupId, entry['summary'], rss_d.feed.title, entry['link'], context)
                    
                    #context.bot.forward_message(groupId,message_info.chat.id,True,message_info.message_id)
                    print(message_info)
                if url_list[1] == entry['link']:  # a sent post detected, the rest of posts in the list will be sent
                    last_flag = True

            sqlite_write(name, url_list[0], str(rss_d.entries[0]['link']), True)  # update db

    if update_flag:
        print('Updated.')
        rss_load()  # update rss_dict


def init_sqlite():
    conn = sqlite3.connect('config/rss.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE rss (id INTEGER PRIMARY KEY AUTOINCREMENT,name text, link text, last text)''')


def main():
    print(f'CHATID: {chatid}\nMANAGER: {manager}\nDELAY: {delay}s\n')

    updater = telegram.ext.Updater(token=Token, use_context=True)
    job_queue = updater.job_queue
    dp = updater.dispatcher

    dp.add_handler(telegram.ext.CommandHandler("add", cmd_rss_add))
    dp.add_handler(telegram.ext.CommandHandler("start", cmd_help))
    dp.add_handler(telegram.ext.CommandHandler("help", cmd_help))
    dp.add_handler(telegram.ext.CommandHandler("test", cmd_test, ))
    dp.add_handler(telegram.ext.CommandHandler("list", cmd_rss_list))
    dp.add_handler(telegram.ext.CommandHandler("remove", cmd_rss_remove))
    dp.add_handler(telegram.ext.CommandHandler("setgroup", cmd_set_group))
    dp.add_handler(telegram.ext.CommandHandler("test1", inlinekeyboard1))
    dp.add_handler(telegram.ext.CallbackQueryHandler(button))

    # try to create a database if missing
    try:
        init_sqlite()
    except sqlite3.OperationalError:
        pass
    rss_load()

    job_queue.run_repeating(rss_monitor, delay)
    rss_monitor(updater)

    updater.start_polling()
    updater.idle()
    conn.close()


if __name__ == '__main__':
    main()
