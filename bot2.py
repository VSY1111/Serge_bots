import datetime as dt
import logging
import re
from collections import defaultdict
from logging.handlers import RotatingFileHandler

import requests
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# устанавливаем настройки для логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    'bot2_logger.log',
    maxBytes=50000000,
    backupCount=5,
    encoding='utf-8'
)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)

# берем токен бота из локального файла
with open('bot2_token.txt', 'r', encoding="utf-8") as f:
    API_TOKEN = f.read()

# инициализируем бот и диспетчер, настраиваем кнопки
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# url для создания новых записей
record_create_url = 'http://127.0.0.1:8000/api/'

# задаем стартовое сообщение и поля формы
welcome_message = ('Задача нашей платформы подсказать варианты не попасть под отчисления '
    'и не лишиться острочки от армии студентам вузов с задолженностями по экзаменам.\n'
    'Также оказывается консультация для поступления или перевода в аспирантуру или магистратуру.\n'
    'Заполните форму в боте. Можете заполнять лишь пункты которые вам удобны. '
    'На остальных ставить прочерк или неполный ответ. Мы постараемся в 24-48'
    ' часовой срок подсказать вам пути решения задачи в виде перевода в другой вуз или других опций.')

pers_data_text = ('Настоящим я даю свое согласие на обработку '
    'моих персональных данных (включая сбор, запись, '
    'систематизацию, накопление, хранение, извлечение, '
    'использование, обезличивание, блокирование, удаление, '
    'уничтожение персональных данных), к которым, '
    'в частности, относятся данные, внесенные мной в форму '
    'в данном чате, исключительно в целях, необходимых '
    'для содействия в поступлении на обучение в высшие учебные '
    'заведения, проверки достоверности предоставленных '
    'мною данных и с целью обеспечения соблюдения '
    'действующего законодательства.\n\n'
    'Согласие на передачу моих персональных данных '
    'считается полученным с момента нажания мною '
    'кнопки "Согласен на обработку персональных данных".\n\n'
    'Я понимаю, что имею право отозвать данное мною '
    'согласие на обработку персональных данных путем '
    'подачи соответствующего письменного заявления.\n')

default_message = 'Введите /start для отправки формы'
finish_message = 'Мы ищем варианты и свяжемся с вами в ближайшее время☺️'
finish_message_error = 'Спасибо!'
form_fields = {
    1: 'fio',
    2: 'email',
    3: 'phone_number',
    4: 'birth_date',
    5: 'city',
    6: 'vuz',
    7: 'dep',
    8: 'kurs',
    9: 'debts',
    10: 'dismiss_date',
    11: 'ege_score',
    12: 'comment'
}
form_input_text = {
    1: 'Как Вас зовут (ФИО)?',
    2: 'Введите e-mail для связи',
    3: 'Телефон для связи',
    4: 'Введите дату рождения',
    5: 'Ваш город проживания?',
    6: 'Ваш вуз?',
    7: 'Факультет?',
    8: 'На какой курс вы перевелись бы сейчас если бы не было задолженностей?',
    9: 'По каким предметам есть задолженности?',
    10: 'Предполагаемая дата отчисления?',
    11: 'Баллы по ЕГЭ?',
    12: 'Комментарий: дополнительная информация, которую считаете важной'
}

def is_email(str_data):
    return re.search(r'[\w.-]+@[\w.-]+.\w+', str_data)

def is_date(str_data):
    try:
        return bool(dt.datetime.strptime(str_data, '%d-%m-%Y'))
    except ValueError:
        try:
            return bool(dt.datetime.strptime(str_data, '%d/%m/%Y'))
        except ValueError:
            try:
                return bool(dt.datetime.strptime(str_data, '%d.%m.%Y'))
            except ValueError:
                return False

def str_to_date(str_data):
    try:
        return dt.datetime.strptime(str_data, '%d-%m-%Y').strftime('%d/%m/%Y')
    except ValueError:
        try:
            return dt.datetime.strptime(str_data, '%d/%m/%Y').strftime('%d/%m/%Y')
        except ValueError:
            try:
                return dt.datetime.strptime(str_data, '%d.%m.%Y').strftime('%d/%m/%Y')
            except ValueError:
                return False

form_check_func = {
    1: lambda a : True,
    2: lambda a : True,
    3: lambda a : True,
    4: lambda a : True,
    5: lambda a : True,
    6: lambda a : True,
    7: lambda a : True,
    8: lambda a : True,
    9: lambda a : True,
    10: lambda a : True,
    11: lambda a : True,
    12: lambda a : True
}
form_process_func = {
    1: lambda a : a,
    2: lambda a : a,
    3: lambda a : a,
    4: lambda a : a,
    5: lambda a : a,
    6: lambda a : a,
    7: lambda a : a,
    8: lambda a : a,
    9: lambda a : a,
    10: lambda a : a,
    11: lambda a : a,
    12: lambda a : a
}
form_error_message = {
    2: 'Введите e-mail в корректном формате!',
    4: 'Введите дату в корректном формате (dd.mm.yyyy)!',
    10: 'Введите дату в корректном формате (dd.mm.yyyy)!'
}
form_start_message = 'Ответьте на 10 вопросов'

# инлайн клавиатура для стартового сообщения
fill_form_btn = InlineKeyboardButton('Заполнить форму', callback_data='fill_form')
inline_kb_start = InlineKeyboardMarkup().add(fill_form_btn)

# инлайн клавиатура после заполнения формы
main_menu_btn = InlineKeyboardButton('Главное меню', callback_data='main_menu')
inline_kb_end = InlineKeyboardMarkup().add(main_menu_btn)

# инлайн клавиатура для согласия на обработку персональных данных
pers_data_btn = InlineKeyboardButton(
    'Согласен на обработку персональных данных',
    callback_data='pers_data'
)
inline_kb_pd = InlineKeyboardMarkup().add(pers_data_btn)

# сообщение при запуске бота
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    logger.info(f'Получили команду /start от ID: {message.from_user.id}')
    await bot.send_message(
        message.from_user.id, welcome_message,
        reply_markup=inline_kb_start
    )

# обработка инлайн кнопок
@dp.callback_query_handler(lambda c: c.data == 'fill_form' or c.data == 'main_menu' or c.data == 'pers_data')
async def process_callback_button(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username
    logger.info(f'Нажата кнопка {callback_query.data} от: {username}')
    global form_status
    global student_record
    if callback_query.data == 'pers_data':
        form_status[user_id] = 1
        student_record[user_id] = {}
        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(user_id, form_start_message)
        await bot.send_message(
            user_id,
            form_input_text[form_status[user_id]]
        )
    elif callback_query.data == 'main_menu':
        await bot.send_message(
            user_id, pers_data_text,
            reply_markup=inline_kb_start
        )
    else:
        await bot.send_message(
            user_id, pers_data_text,
            reply_markup=inline_kb_pd
        )


# обработка сообщений кнопок
@dp.message_handler(content_types=['text'])
async def text_processing(message: types.Message):
    global form_status
    global student_record
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f'Сообщение {message.text} от: {username}')
    if form_status[user_id] == 0:
        await bot.send_message(user_id, default_message)
    else:
        if form_check_func[form_status[user_id]](message.text):
            student_record[user_id][form_fields[form_status[user_id]]] = form_process_func[form_status[user_id]](message.text)
            form_status[user_id] += 1
            if form_status[user_id] < 13:
                await bot.send_message(
                    user_id,
                    form_input_text[form_status[user_id]]
                )
        else:
            await message.reply(form_error_message[form_status[user_id]])
    if form_status[user_id] == 13:
        student_record[user_id]['tgname'] = str(message.from_user.first_name) + ' ' + str(message.from_user.last_name)
        student_record[user_id]['tgusername'] = str(message.from_user.username)
        try:
            response = requests.post(url=record_create_url, json=student_record[user_id])
            logger.info(f'Отправили форму от: {username}')
            form_status[user_id] = 0
            await bot.send_message(
                user_id, finish_message,
                reply_markup=inline_kb_end
            )
        except:
            logger.info(f'Не получилось отправить форму от: {username}')
            await bot.send_message(
                user_id, finish_message_error,
                reply_markup=inline_kb_end
            )

if __name__ == '__main__':
    form_status = defaultdict(int)
    student_record = {}
    executor.start_polling(dp, skip_updates=True)
