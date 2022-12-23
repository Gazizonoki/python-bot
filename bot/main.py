from telebot.async_telebot import AsyncTeleBot
import ydb
from random import randint
from enum import Enum


class BotState(Enum):
    chill = 1
    find_username = 2
    register_username = 3
    register_photo = 4
    battle_choose = 5


token_file = open("token", "r")
bot = AsyncTeleBot(token_file.read())
token_file.close()

current_chat_id = ""
user_id = ""
user_name = ""
battle_first_name = ""
battle_second_name = ""
state = BotState.chill

driver_config = ydb.DriverConfig("grpc://database:2136", "/local", credentials=ydb.AnonymousCredentials())


def run():
    global driver_config
    driver = ydb.Driver(driver_config)
    driver.wait(timeout=5, fail_fast=True)
    return driver.table_client.session().create()


def running_commands_check():
    global state
    if state != BotState.chill:
        return True
    return False


def check_chat(message):
    global current_chat_id
    if current_chat_id == "":
        bot.send_message(message.chat.id, 'Совсем дурак? Сначала напиши /start, а потом бота юзай, ну и ну.')
        return True
    if message.chat.id != current_chat_id:
        bot.send_message(message.chat.id, 'Вы кто такие? Я вас не звал!')
        return True
    return False


def finish_command():
    global user_id, user_name, state, battle_first_name, battle_second_name
    user_id = ""
    user_name = ""
    battle_first_name = ""
    battle_second_name = ""
    state = BotState.chill


def find_user(name, session, message):
    file = open("find_user.yql", "r")
    query = session.prepare(file.read())
    result_sets = session.transaction(ydb.SerializableReadWrite()).execute(
        query, {
            '$user_name': name
        },
        commit_tx=True
    )
    file.close()
    if len(result_sets[0].rows) == 0:
        bot.send_message(message.chat.id, 'Это кто?')
        finish_command()
        return

    bot.send_message(message.chat.id, 'Рейтинг: ' + str(result_sets[0].rows[0].rating))
    bot.send_photo(message.chat.id, result_sets[0].rows[0].photo)


def is_table_exists(driver):
    try:
        return driver.scheme_client.describe_path("local/users_table").is_table()
    except ydb.SchemeError:
        return False


@bot.message_handler(commands=["start"])
async def start(message):
    global current_chat_id, driver_config
    if current_chat_id != "":
        await bot.send_message(message.chat.id, 'Упс, бот запущен в другом чатике(')
        return True
    if running_commands_check():
        await bot.send_message(message.chat.id, "Ты че сделал? Еще раз увижу, иуп получишь!")
        return
    driver = ydb.Driver(driver_config)
    driver.wait(timeout=5, fail_fast=True)
    if not is_table_exists(driver):
        file = open("create_table.yql", "r")
        driver.table_client.session().create().execute_scheme(file.read())
        file.close()
    current_chat_id = message.chat.id
    await bot.send_message(message.chat.id, 'Сейчас мы узнаем, кто главный петух в этом чатике.')


@bot.message_handler(commands=["stop"])
async def stop(message):
    global current_chat_id, state
    if check_chat(message):
        return
    if running_commands_check():
        await bot.send_message(message.chat.id, "Ты че сделал? Еще раз увижу, иуп получишь!")
        return
    await bot.send_message(message.chat.id, 'Пока')
    current_chat_id = ""
    finish_command()


@bot.message_handler(commands=["register"])
async def register(message):
    global user_id, state
    if check_chat(message):
        return
    if running_commands_check():
        await bot.send_message(message.chat.id, "Ты че сделал? Еще раз увижу, иуп получишь!")
        return
    await bot.send_message(message.chat.id, 'Введи имя этого петушка:')
    user_id = message.from_user.id
    state = BotState.register_username


@bot.message_handler(commands=["find"])
async def find(message):
    global user_id, state, user_id
    if check_chat(message):
        return
    if running_commands_check():
        await bot.send_message(message.chat.id, "Ты че сделал? Еще раз увижу, иуп получишь!")
        return
    await bot.send_message(message.chat.id, 'Введи имя этого петушка:')
    user_id = message.from_user.id
    state = BotState.find_username


@bot.message_handler(commands=["battle"])
async def battle(message):
    global user_id, state, battle_first_name, battle_second_name
    if check_chat(message):
        return
    if running_commands_check():
        await bot.send_message(message.chat.id, "Ты че сделал? Еще раз увижу, иуп получишь!")
        return
    session = run()
    file = open("get_names.yql", "r")
    result_set = session.transaction().execute(file.read(), commit_tx=True)
    file.close()
    if len(result_set[0].rows) <= 1:
        await bot.send_message(message.chat.id, "Маловато человек(")
        return
    first_index = randint(1, len(result_set[0].rows) - 1)
    second_index = randint(0, first_index - 1)
    battle_first_name = result_set[0].rows[first_index].name
    battle_second_name = result_set[0].rows[second_index].name
    find_user(battle_first_name, session, message)
    find_user(battle_second_name, session, message)
    await bot.send_message(message.chat.id, "Кто больший петух? Напиши '1' или '2'.")
    user_id = message.from_user.id
    state = BotState.battle_choose


@bot.message_handler(commands=["force_stop"])
async def force_stop(message):
    global current_chat_id, state
    if message.from_user.id != 313814979:
        await bot.send_message(message.chat.id, "Недостаточно прав.")
        return
    session = run()
    session.drop_table('local/users_table')
    current_chat_id = ""
    finish_command()


@bot.message_handler(content_types=["text"])
async def text_process(message):
    global user_name, user_id, state, current_chat_id, battle_first_name, battle_second_name
    if message.chat.id != current_chat_id:
        return
    if user_id != message.from_user.id:
        return
    if state == BotState.register_username:
        user_name = message.text
        await bot.send_message(message.chat.id, 'Введи фотку рожи этого петушка:')
        state = BotState.register_photo
        return
    if state == BotState.find_username:
        name = message.text
        session = run()
        find_user(name, session, message)
        finish_command()
        return
    if state == BotState.battle_choose:
        choice = message.text
        if choice == "1":
            name = battle_first_name
        elif choice == "2":
            name = battle_second_name
        else:
            await bot.send_message(message.chat.id, "По-русски написано, введи '1' или '2'. Давай по новой.")
            return
        session = run()
        file = open("update_rating.yql", "r")
        query = session.prepare(file.read())
        session.transaction(ydb.SerializableReadWrite()).execute(
            query, {
                '$user_name': name
            },
            commit_tx=True
        )
        file.close()
        await bot.send_message(message.chat.id, "Спасибо за ответ, ваш голос очень важен для нас.")
        finish_command()
        return


@bot.message_handler(content_types=["photo"])
async def photo_process(message):
    global user_name, user_id, state, current_chat_id
    if message.chat.id != current_chat_id:
        return
    if user_id != message.from_user.id:
        return
    if state == BotState.register_photo:
        photo_info = await bot.get_file(message.photo[len(message.photo) - 1].file_id)
        photo = await bot.download_file(photo_info.file_path)
        session = run()
        file = open("add_user.yql", "r")
        query = session.prepare(file.read())
        session.transaction().execute(
            query, {
                '$user_name': user_name,
                '$photo': photo
            },
            commit_tx=True
        )
        file.close()
        finish_command()
        await bot.send_message(message.chat.id, 'Оки-доки, петушок добавлен.')


bot.infinity_polling()
