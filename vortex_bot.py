import re
import os
import datetime
# import logging


from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ParseMode, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, \
    InlineKeyboardMarkup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.dispatcher import FSMContext

from vortex import get_connection_pymysql, get_issue

# logging.basicConfig(level=logging.DEBUG)
TOKEN = os.getenv('BOT_VORTEX_TOKEN')

bot = Bot(token=TOKEN)

button_search_by_id = KeyboardButton('По номеру')
button_search_by_name = KeyboardButton('По названию')
button_search_by_assigned = KeyboardButton('Назначенные')
search_kb = ReplyKeyboardMarkup(resize_keyboard=True)
search_kb.add(button_search_by_id, button_search_by_name, button_search_by_assigned)
search_kb.row(KeyboardButton('Вернутся в главное меню'))

button_issue = KeyboardButton('Заявки')
kb = ReplyKeyboardMarkup(resize_keyboard=True)
kb.add(button_issue)

storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


def login_check(**kwargs):
    login = kwargs.get('login')
    password = kwargs.get('password')
    if not login or not password:
        return False
    with get_connection_pymysql() as connection:
        with connection.cursor() as cursor:
            sql = f"""select admin,
       specific_id,
       firstname,
       lastname,
       temp.id,
       director_id,
       director_status,
       hashed_password,
       salt,
       user_groups,
       group_concat(r.id) as roles
from (select admin,
             specific_id,
             firstname,
             lastname,
             temp2.id,
             director_id,
             director_status,
             hashed_password,
             salt,
             group_concat(group_id) as user_groups
      from (select admin,
                   specific_id,
                   firstname,
                   lastname,
                   u.id,
                   group_concat(nd.id)     as director_id,
                   group_concat(nd.status) as director_status,
                   hashed_password,
                   salt
            from users as u
                     left join service_vortex_links on u.id = service_vortex_links.vortex_user_id
                     left join naryad_director nd on u.id = nd.user_id
            where {"login = '" + login + "'" if kwargs.get('service_id') is None else "service_user_id =" + kwargs.get('service_id')}
              and type = 'User') as temp2
               left join groups_users gu on temp2.id = gu.user_id) as temp
         left join members m on temp.id = m.user_id
         left join member_roles mr on m.id = mr.member_id
         left join roles r on mr.role_id = r.id"""
            cursor.execute(sql)
            data = cursor.fetchone()
            if not (data['id'] is not None or kwargs.get('service_id') is not None):
                return None
            else:
                if kwargs.get('service_id') is not None:
                    data['roles'] = [item for item in data['roles'].split(',')]
                    data['groups'] = [item for item in data['user_groups'].split(',')]
                    return data
                hashed_password = get_hashed_password(salt=data.pop('salt'), password=password)
                if data.pop('hashed_password') != hashed_password:
                    return False
                else:
                    data['roles'] = [item for item in data['roles'].split(',')]
                    data['groups'] = [item for item in data['user_groups'].split(',')]
                    return data


def get_assignments(id):
    with get_connection_pymysql() as connection:
        with connection.cursor() as cursor:
            sql = f"""select issues.id as id,
                           trackers.name       as tracker,
                           projects.name       as project,
                           issues.id,
                           subject,
                           null as start_date,
                           done_ratio,
                           issue_statuses.name as status,
                           assigned_to_id,
                           issues.updated_on,
                           issues.icon
                    from issues
                             join trackers on trackers.id = issues.tracker_id
                             join issue_statuses on issue_statuses.id = issues.status_id
                             join projects on projects.id = issues.project_id
                    where (issues.assigned_to_id = {id} or issues.assigned_to_id in (select group_id from groups_users where user_id = {id}) )
                       and issues.status_id != 5 and issues.status_id != 6"""
            cursor.execute(sql)
            return cursor.fetchall()


def get_cf_data(**kwargs):
    """

    :param kwargs:
    :issue_id: int
    :return: dict
    """
    issue_id = kwargs.get('issue_id')
    with get_connection_pymysql() as connection:
        with connection.cursor() as cursor:
            sql = f"""  select cv.value,
                               cf.name,
                               cf.id
                        from issues as i
                                 join custom_values cv on i.id = cv.customized_id
                                 join custom_fields cf on cv.custom_field_id = cf.id
                                 join users u on i.assigned_to_id = u.id
                                 join users us on i.author_id = us.id
                                 join enumerations e on e.id = i.priority_id
                        where i.id = {issue_id}"""
            cursor.execute(sql)
            data = {}
            for result in cursor.fetchall():
                data.update({str(result['id']): {'name': str(result['name']), 'value': str(result['value'])}})
    return data


class MainStates(StatesGroup):
    by_id = State()
    by_name = State()
    by_assignment = State()
    main_menu = State()
    issue = State()
    login_input = State()
    password_input = State()


def check_login(login):
    with get_connection_pymysql() as connection:
        with connection.cursor() as cursor:
            sql = f"""select * from users where login = '{login}'"""
            cursor.execute(sql)
            return False if cursor.fetchone() is None else True


def get_user_data(login):
    with get_connection_pymysql() as connection:
        with connection.cursor() as cursor:
            sql = f"""select admin, firstname, lastname, id from users 
                where login = '{login}' and type = 'User'"""
            cursor.execute(sql)
            data = cursor.fetchone()
            sql = f"""select r.id from members as m
                        join member_roles mr on m.id = mr.member_id
                        join roles r on mr.role_id = r.id
                        where user_id = {data['id']}"""
            cursor.execute(sql)
            data['roles'] = []
            for temp in cursor.fetchall():
                data['roles'].append(temp['id'])
            sql = f"""select group_id from groups_users
                        where user_id = {data['id']}"""
            cursor.execute(sql)
            data['groups'] = []
            for temp in cursor.fetchall():
                data['groups'].append(temp['group_id'])
            return data


def get_user_for_tg():
    with get_connection_pymysql() as connection:
        with connection.cursor() as cursor:
            sql = f"""select * from user_for_tg"""
            cursor.execute(sql)
            temp = cursor.fetchall()
            data = {}
            for item in temp:
                data[item['tg_user_id']] = item['login']
    return data


def get_status(issue_id):
    with get_connection_pymysql() as connection:
        with connection.cursor() as cursor:
            sql = f"""select name from issue_statuses where id = (
                      select status_id from issues where id = {issue_id})"""
            cursor.execute(sql)
            return cursor.fetchone()['name']


async def send_issue(data):
    if type(data) is types.Message:
        message = data
        if re.fullmatch(r'\d{1,5}', message.text):
            issue = get_issue(issue_id=message.text)[0]
            await message.answer(
                f"<b>{issue['tracker']} #{issue['id']}</b>\n{issue['subject']}\n{issue['description'].replace('<p>', '').replace('</p>', '').replace('<br>', '')}\n",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton('Подробнее', callback_data='issue_full/' + str(issue['id']))))
        else:
            await message.answer('Введен некорректный номер заявки',
                                 reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add('Назад'))
    elif type(data) is types.CallbackQuery:
        callback_query = data
        text = callback_query.data.split('/')[1]
        if re.fullmatch(r'\d{1,5}', text):
            issue = get_issue(issue_id=text)[0]
            await callback_query.message.answer(
                f"{issue['tracker']} {issue['id']}\n{issue['subject']}\n{issue['description'].replace('<p>', '').replace('</p>', '').replace('<br>', '')}\n",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton('Подробнее', callback_data='issue_full/' + str(issue['id'])),
                    InlineKeyboardButton('Подробнее', callback_data='issue_full/' + str(issue['id']))).add(InlineKeyboardButton('Подробнее', callback_data='issue_full/' + str(issue['id']))))
            await callback_query.answer()
        else:
            await callback_query.message.answer('Введен некорректный номер заявки',
                                                reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add('Назад'))
            await callback_query.answer()


@dp.message_handler(state=None)
async def message_rp(message: types.Message, state: FSMContext):
    user = message.from_user.id
    users = get_user_for_tg()
    if user in users.keys():
        async with state.proxy() as data:
            data['user_data'] = get_user_data(users[user])
            await message.answer('Главное меню', reply_markup=kb)
            await state.set_state(MainStates.main_menu.state)
    else:
        await start(message)


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer('Введите ваше логин')
    await MainStates.login_input.set()


@dp.message_handler(state=MainStates.login_input)
async def input_nick(message: types.Message, state: FSMContext):
    if not check_login(message.text):
        await message.answer("Введен неправильный логин")
        return
    async with state.proxy() as data:
        data['login'] = message.text
    await message.answer('Введите пароль')
    await state.set_state(MainStates.password_input.state)


@dp.message_handler(state=MainStates.password_input)
async def input_pass(message: types.Message, state: FSMContext):
    user = message.from_user.id
    async with state.proxy() as data:
        check = login_check(login=data['login'], password=message.text)

        if not check:
            await message.answer('Введен неверный пароль')
            return

        data['user_data'] = check
        with get_connection_pymysql() as connection:
            with connection.cursor() as cursor:
                sql = f"""select login, tg_user_id from user_for_tg where login = '{data['login']}' and tg_user_id = '{user}'"""
                cursor.execute(sql)
                if cursor.fetchone() is None:
                    sql = f"""insert into user_for_tg (login, tg_user_id)
                    values ('{data['login']}', '{user}')"""
                    cursor.execute(sql)
            connection.commit()
        await message.answer(
            'Авторизация успешно завершена.\nВы вошли как ' + data['user_data']['firstname'] + ' ' + data['user_data'][
                'lastname'])
    await message.answer('Главное меню', reply_markup=kb)
    await state.set_state(MainStates.main_menu.state)


@dp.message_handler(lambda message: message.text == 'Заявки', state=MainStates.main_menu)
async def temp_search(message: types.Message, state: FSMContext):
    await state.set_state(MainStates.issue.state)
    await message.answer('Выберите тип поиска', reply_markup=search_kb)


@dp.message_handler(state=MainStates.issue)
async def search_issue(message: types.Message, state: FSMContext):
    if message.text == 'По номеру':
        await message.answer('Выбран поиск по номеру',
                             reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add('Назад'))
        await state.set_state(MainStates.by_id.state)
    elif message.text == 'По названию':
        await message.answer('Выбран поиск по имени',
                             reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add('Назад'))
        await state.set_state(MainStates.by_name.state)
    elif message.text == 'Назначенные':
        await message.answer('Выбрано отображение назначенных заявок',
                             reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add('Назад'))
        await state.set_state(MainStates.by_assignment.state)
        async with state.proxy() as data:
            issues = get_assignments(id=data['user_data']['id'])
            inline_kb1 = InlineKeyboardMarkup()
            for issue in issues:
                inline_btn_1 = InlineKeyboardButton(str(issue['id']) + ' ' + issue['subject'],
                                                    callback_data='issue_id/' + str(issue['id']))
                inline_kb1.add(inline_btn_1)
            await message.answer('Полученные результаты', reply_markup=inline_kb1)
    elif message.text == 'Вернутся в главное меню':
        await message.answer('Главное меню', reply_markup=kb)
        await state.set_state(MainStates.main_menu.state)


@dp.message_handler(state=MainStates.by_id)
async def search_by_id(message: types.Message, state: FSMContext):
    if message.text == 'Назад':
        await message.answer('Выберите тип поиска', reply_markup=search_kb)
        await state.set_state(MainStates.issue.state)
    else:
        await send_issue(message)


@dp.message_handler(state=MainStates.by_name)
async def search_by_name(message: types.Message, state: FSMContext):
    if message.text == 'Назад':
        await message.answer('Выберите тип поиска', reply_markup=search_kb)
        await state.set_state(MainStates.issue.state)
    else:
        ids = get_issue(search_text=message.text)
        inline_kb1 = InlineKeyboardMarkup()
        for id in ids:
            inline_btn_1 = InlineKeyboardButton(str(id['id']) + ' ' + id['subject'],
                                                callback_data='issue_id/' + str(id['id']))
            inline_kb1.add(inline_btn_1)
        await message.answer('Полученные результаты', reply_markup=inline_kb1)


@dp.message_handler(state=MainStates.by_assignment)
async def search_by_assigment(message: types.Message, state: FSMContext):
    if message.text == 'Назад':
        await message.answer('Выберите тип поиска', reply_markup=search_kb)
        await state.set_state(MainStates.issue.state)
    else:
        async with state.proxy() as data:
            issues = get_assignments(id=data['user_data']['id'], groups=data['user_data']['groups'])
            inline_kb1 = InlineKeyboardMarkup()
            for issue in issues:
                inline_btn_1 = InlineKeyboardButton(str(issue['id']) + ' ' + issue['subject'],
                                                    callback_data='issue_id/' + str(issue['id']))
                inline_kb1.add(inline_btn_1)
            await message.answer('Полученные результаты', reply_markup=inline_kb1)


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('issue_id'),
                           state=[MainStates.by_assignment, MainStates.by_name])
async def send_issue_handle(callback_query: types.CallbackQuery):
    await send_issue(callback_query)


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('issue_full'),
                           state="*")
async def send_issue_full_handle(callback_query: types.CallbackQuery):
    issue_id = callback_query.data.split('/')[1]
    cfs = get_cf_data(issue_id=issue_id)
    answer = f"Статус: {get_status(issue_id)}\n"
    for cf in cfs.values():
        if cf['name'] == 'Координаты':
            answer = answer + re.search(r'http(s)?://.+\b', cf['value']).group(0)
        else:
            answer = answer + f"{cf['name']}: {cf['value']}\n"
    await callback_query.message.edit_text(answer, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup().add(
        InlineKeyboardButton('История изменений', callback_data='issue_history/' + str(issue_id))))
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('issue_history'),
                           state="*")
async def send_issue_history(callback_query: types.CallbackQuery):
    answer = 'Тест'
    await callback_query.message.edit_text(answer, reply_markup=InlineKeyboardMarkup().add(
        InlineKeyboardButton('История', callback_data='test')))
    await callback_query.answer()


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
