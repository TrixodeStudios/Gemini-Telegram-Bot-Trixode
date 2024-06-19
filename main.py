import argparse
import traceback
import asyncio
import google.generativeai as genai
import re
import telebot
import requests
from telebot.async_telebot import AsyncTeleBot
from telebot.types import  Message, ReplyKeyboardMarkup, KeyboardButton

gemini_player_dict = {}
gemini_pro_player_dict = {}
default_model_dict = {}

error_info="⚠️⚠️⚠️\nSomething went wrong !\nplease try to change your prompt or contact the admin !"
before_generate_info="🤖Generating🤖"
download_pic_notify="🤖Loading picture🤖"

n = 30  #Number of historical records to keep

generation_config = {
    "temperature": 1,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE"
    },
    {   "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE"
    },
]

def find_all_index(str, pattern):
    index_list = [0]
    for match in re.finditer(pattern, str, re.MULTILINE):
        if match.group(1) != None:
            start = match.start(1)
            end = match.end(1)
            index_list += [start, end]
    index_list.append(len(str))
    return index_list

def replace_all(text, pattern, function):
    poslist = [0]
    strlist = []
    originstr = []
    poslist = find_all_index(text, pattern)
    for i in range(1, len(poslist[:-1]), 2):
        start, end = poslist[i : i + 2]
        strlist.append(function(text[start:end]))
    for i in range(0, len(poslist), 2):
        j, k = poslist[i : i + 2]
        originstr.append(text[j:k])
    if len(strlist) < len(originstr):
        strlist.append("")
    else:
        originstr.append("")
    new_list = [item for pair in zip(originstr, strlist) for item in pair]
    return "".join(new_list)

def escapeshape(text):
    return "▎*" + text.split()[1] + "*"

def escapeminus(text):
    return "\\" + text

def escapebackquote(text):
    return r"\`\`"

def escapeplus(text):
    return "\\" + text

def escape(text, flag=0):
    # In all other places characters
    # _ * [ ] ( ) ~ ` > # + - = | { } . !
    # must be escaped with the preceding character '\'.
    text = re.sub(r"\\\[", "@->@", text)
    text = re.sub(r"\\\]", "@<-@", text)
    text = re.sub(r"\\\(", "@-->@", text)
    text = re.sub(r"\\\)", "@<--@", text)
    if flag:
        text = re.sub(r"\\\\", "@@@", text)
    text = re.sub(r"\\", r"\\\\", text)
    if flag:
        text = re.sub(r"\@{3}", r"\\\\", text)
    text = re.sub(r"_", "\_", text)
    text = re.sub(r"\*{2}(.*?)\*{2}", "@@@\\1@@@", text)
    text = re.sub(r"\n{1,2}\*\s", "\n\n• ", text)
    text = re.sub(r"\*", "\*", text)
    text = re.sub(r"\@{3}(.*?)\@{3}", "*\\1*", text)
    text = re.sub(r"\!?\[(.*?)\]\((.*?)\)", "@@@\\1@@@^^^\\2^^^", text)
    text = re.sub(r"\[", "\[", text)
    text = re.sub(r"\]", "\]", text)
    text = re.sub(r"\(", "\(", text)
    text = re.sub(r"\)", "\)", text)
    text = re.sub(r"\@\-\>\@", "\[", text)
    text = re.sub(r"\@\<\-\@", "\]", text)
    text = re.sub(r"\@\-\-\>\@", "\(", text)
    text = re.sub(r"\@\<\-\-\@", "\)", text)
    text = re.sub(r"\@{3}(.*?)\@{3}\^{3}(.*?)\^{3}", "[\\1](\\2)", text)
    text = re.sub(r"~", "\~", text)
    text = re.sub(r">", "\>", text)
    text = replace_all(text, r"(^#+\s.+?$)|```[\D\d\s]+?```", escapeshape)
    text = re.sub(r"#", "\#", text)
    text = replace_all(
        text, r"(\+)|\n[\s]*-\s|```[\D\d\s]+?```|`[\D\d\s]*?`", escapeplus
    )
    text = re.sub(r"\n{1,2}(\s*)-\s", "\n\n\\1• ", text)
    text = re.sub(r"\n{1,2}(\s*\d{1,2}\.\s)", "\n\n\\1", text)
    text = replace_all(
        text, r"(-)|\n[\s]*-\s|```[\D\d\s]+?```|`[\D\d\s]*?`", escapeminus
    )
    text = re.sub(r"```([\D\d\s]+?)```", "@@@\\1@@@", text)
    text = replace_all(text, r"(``)", escapebackquote)
    text = re.sub(r"\@{3}([\D\d\s]+?)\@{3}", "```\\1```", text)
    text = re.sub(r"=", "\=", text)
    text = re.sub(r"\|", "\|", text)
    text = re.sub(r"{", "\{", text)
    text = re.sub(r"}", "\}", text)
    text = re.sub(r"\.", "\.", text)
    text = re.sub(r"!", "\!", text)
    return text

# Prevent "create_convo" function from blocking the event loop.
async def make_new_gemini_convo():
    loop = asyncio.get_running_loop()

    def create_convo():
        model = genai.GenerativeModel(
            model_name="models/gemini-1.5-flash-latest",
            generation_config=generation_config,
            safety_settings=safety_settings,
        )
        convo = model.start_chat()
        return convo

    # Run the synchronous "create_convo" function in a thread pool
    convo = await loop.run_in_executor(None, create_convo)
    return convo

async def make_new_gemini_pro_convo():
    loop = asyncio.get_running_loop()

    def create_convo():
        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro-latest",
            generation_config=generation_config,
            safety_settings=safety_settings,
        )
        convo = model.start_chat()
        return convo

    # Run the synchronous "create_convo" function in a thread pool
    convo = await loop.run_in_executor(None, create_convo)
    return convo

# Prevent "send_message" function from blocking the event loop.
async def send_message(player, message):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, player.send_message, message)
    
# Prevent "model.generate_content" function from blocking the event loop.
async def async_generate_content(model, contents):
    loop = asyncio.get_running_loop()

    def generate():
        return model.generate_content(contents=contents)

    response = await loop.run_in_executor(None, generate)
    return response

async def gemini(bot,message,m):
    player = None
    if str(message.from_user.id) not in gemini_player_dict:
        player = await make_new_gemini_convo()
        gemini_player_dict[str(message.from_user.id)] = player
    else:
        player = gemini_player_dict[str(message.from_user.id)]
    if len(player.history) > n:
        player.history = player.history[2:]
    try:
        sent_message = await bot.reply_to(message, before_generate_info)
        await send_message(player, m)
        try:
            await bot.edit_message_text(escape(player.last.text), chat_id=sent_message.chat.id, message_id=sent_message.message_id, parse_mode="MarkdownV2")
        except:
            await bot.edit_message_text(escape(player.last.text), chat_id=sent_message.chat.id, message_id=sent_message.message_id)

    except Exception:
        traceback.print_exc()
        await bot.edit_message_text(error_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)

async def gemini_pro(bot,message,m):
    player = None
    if str(message.from_user.id) not in gemini_pro_player_dict:
        player = await make_new_gemini_pro_convo()
        gemini_pro_player_dict[str(message.from_user.id)] = player
    else:
        player = gemini_pro_player_dict[str(message.from_user.id)]
    if len(player.history) > n:
        player.history = player.history[2:]
    try:
        sent_message = await bot.reply_to(message, before_generate_info)
        await send_message(player, m)
        try:
            await bot.edit_message_text(escape(player.last.text), chat_id=sent_message.chat.id, message_id=sent_message.message_id, parse_mode="MarkdownV2")
        except:
            await bot.edit_message_text(escape(player.last.text), chat_id=sent_message.chat.id, message_id=sent_message.message_id)

    except Exception:
        traceback.print_exc()
        await bot.edit_message_text(error_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)

async def main():
    # Init args
    parser = argparse.ArgumentParser()
    parser.add_argument("tg_token", help="telegram token")
    parser.add_argument("GOOGLE_GEMINI_KEY", help="Google Gemini API key")
    options = parser.parse_args()
    print("Arg parse done.")

    genai.configure(api_key=options.GOOGLE_GEMINI_KEY)

    # Init bot
    bot = AsyncTeleBot(options.tg_token)
    await bot.delete_my_commands(scope=None, language_code=None)
    await bot.set_my_commands(
        commands=[
            telebot.types.BotCommand("start", "Start"),
            telebot.types.BotCommand("gemini", "Use gemini-1.5-flash"),
            telebot.types.BotCommand("gemini_pro", "Use gemini-1.5-pro"),
            telebot.types.BotCommand("clear", "Clear all history"),
            telebot.types.BotCommand("switch","Switch default model"),
            telebot.types.BotCommand("social", "Our Social Media"),
            telebot.types.BotCommand("terms", "Terms and Conditions of Infinitys"), 
        ],
    )
    print("Bot init done.")
    
    async def send_welcome_message(message: Message):
        # Create a keyboard with language buttons
        markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(KeyboardButton("English"), KeyboardButton("Español"), 
                   KeyboardButton("Русский"), KeyboardButton("Français"))

        await bot.send_message(message.chat.id, "👋 ¡Hola! Bonjour! привет! Hello! \n" 
                                               "Please select your preferred language:", 
                                               reply_markup=markup)

    @bot.message_handler(commands=['start'])
    async def handle_start(message: Message):
        await send_welcome_message(message)

    @bot.message_handler(func=lambda message: message.text in ["English", "Español", "Русский", "Français"])
    async def handle_language_selection(message: Message):
        language = message.text

       # welcome_messages = {
       #  "English": "Welcome to the Infinitys-App test pilot! 🙌 \nThank you for being part of Infinitys' pilot plan.\nTry asking something interesting, like: What is the colour of the Universe?",
       #  "Español": "¡Bienvenido al piloto de pruebas de la aplicación Infinitys! 🙌 \nGracias por ser parte del plan piloto de Infinitys.\nComienza por preguntar algo divertido, como: Que sabor de helado es el mas popular en la luna?",
       #  "Русский": "Добро пожаловать в тестовую программу приложения Infinitys! 🙌 \nСпасибо за участие в пилотном проекте Infinitys.\nПопробуйте спросить что-нибудь интересное, например: Какого цвета Вселенная?",
       #  "Français": "Bienvenue dans le programme pilote de l'application Infinitys ! 🙌 \nMerci de faire partie du plan pilote d'Infinitys.\nEssayez de demander quelque chose d'intéressant, par exemple : Quelle est la couleur de l'Univers ?"
       # }

 welcome_messages = {
            "English": "Welcome to the Infinitys-App test pilot! 🙌 \nThank you for being part of Infinitys' pilot plan.",
            "Español": "¡Bienvenido al piloto de pruebas de la aplicación Infinitys! 🙌 \nGracias por ser parte del plan piloto de Infinitys.",
            "Русский": "Добро пожаловать в тестовую программу приложения Infinitys! 🙌 \nСпасибо за участие в пилотном проекте Infinitys.",
            "Français": "Bienvenue dans le programme pilote de l'application Infinitys ! 🙌 \nMerci de faire partie du plan pilote d'Infinitys."
        }

        selected_message = welcome_messages.get(language, "Invalid language selection") # Default if language not found
        await bot.send_message(message.chat.id, escape(selected_message), parse_mode="MarkdownV2")

    # --- Social Media Command ---

    @bot.message_handler(commands=["social"])
    async def social_media_handler(message: Message):
        # Replace with your actual social media links
        social_media_message = (
            "Find us on social media:\n"
            "- [Instagram](https://www.instagram.com/trixode_studios/)\n"
            "- [Website](https://www.trixode-studios.com/)\n"
            "- [Facebook](https://www.facebook.com/profile.php?id=61560187936462)"
        )
        await bot.send_message(message.chat.id, social_media_message, parse_mode="Markdown") 

    # --- Terms and Conditions Command ---

    @bot.message_handler(commands=["terms"])
    async def terms_conditions_handler(message: Message):
        # Either provide a link to your terms and conditions or display them directly
        terms_message = (
            "Please review our [Terms and Conditions](https://trixodestudios.my.canva.site/pilot-trixode)."
        )
        await bot.send_message(message.chat.id, terms_message, parse_mode="Markdown") 

    # Init commands
    # @bot.message_handler(commands=["start"])
    # async def gemini_handler(message: Message):
    #     try:
    #         await bot.reply_to( message , escape("Welcome to the Infinitys-App test pilot!. 🙌 \nGracias por ser parte del plan piloto de Infinitys.\nThank you for being part of Infinitys' pilot plan.\nСпасибо за участие в пилотном проекте Infinitys.\nMerci de faire partie du plan pilote d'Infinitys.\nTry searching something fun: `What is my cat dreaming? 😸`"), parse_mode="MarkdownV2")
    #     except IndexError:
    #         await bot.reply_to(message, error_info)

    @bot.message_handler(commands=["gemini"])
    async def gemini_handler(message: Message):
        try:
            m = message.text.strip().split(maxsplit=1)[1].strip()
        except IndexError:
            await bot.reply_to( message , escape("Please add what you want to say after /gemini. \nFor example: `/gemini Who is john lennon?`"), parse_mode="MarkdownV2")
            return
        await gemini(bot,message,m)

    @bot.message_handler(commands=["gemini_pro"])
    async def gemini_handler(message: Message):
        try:
            m = message.text.strip().split(maxsplit=1)[1].strip()
        except IndexError:
            await bot.reply_to( message , escape("Please add what you want to say after /gemini_pro. \nFor example: `/gemini_pro Who is john lennon?`"), parse_mode="MarkdownV2")
            return
        await gemini_pro(bot,message,m)
            
    @bot.message_handler(commands=["clear"])
    async def gemini_handler(message: Message):
        # Check if the player is already in gemini_player_dict.
        if (str(message.from_user.id) in gemini_player_dict):
            del gemini_player_dict[str(message.from_user.id)]
        if (str(message.from_user.id) in gemini_pro_player_dict):
            del gemini_pro_player_dict[str(message.from_user.id)]
        await bot.reply_to(message, "Your history has been cleared")

    @bot.message_handler(commands=["switch"])
    async def gemini_handler(message: Message):
        if message.chat.type != "private":
            await bot.reply_to( message , "This command is only for private chat !")
            return
        # Check if the player is already in default_model_dict.
        if str(message.from_user.id) not in default_model_dict:
            default_model_dict[str(message.from_user.id)] = False
            await bot.reply_to( message , "Now you are using gemini-1.5-pro")
            return
        if default_model_dict[str(message.from_user.id)] == True:
            default_model_dict[str(message.from_user.id)] = False
            await bot.reply_to( message , "Now you are using gemini-1.5-pro")
        else:
            default_model_dict[str(message.from_user.id)] = True
            await bot.reply_to( message , "Now you are using gemini-1.5-flash")
        
    
    
    @bot.message_handler(func=lambda message: message.chat.type == "private", content_types=['text'])
    async def gemini_private_handler(message: Message):
        m = message.text.strip()

        if str(message.from_user.id) not in default_model_dict:
            default_model_dict[str(message.from_user.id)] = True
            await gemini(bot,message,m)
        else:
            if default_model_dict[str(message.from_user.id)]:
                await gemini(bot,message,m)
            else:
                await gemini_pro(bot,message,m)


    @bot.message_handler(content_types=["photo"])
    async def gemini_photo_handler(message: Message) -> None:
        if message.chat.type != "private":
            s = message.caption
            if not s or not (s.startswith("/gemini")):
                return
            try:
                prompt = s.strip().split(maxsplit=1)[1].strip() if len(s.strip().split(maxsplit=1)) > 1 else ""
                file_path = await bot.get_file(message.photo[-1].file_id)
                sent_message = await bot.reply_to(message, download_pic_notify)
                downloaded_file = await bot.download_file(file_path.file_path)
            except Exception:
                traceback.print_exc()
                await bot.reply_to(message, error_info)
            model = genai.GenerativeModel("gemini-1.5-flash-latest")
            contents = {
                "parts": [{"mime_type": "image/jpeg", "data": downloaded_file}, {"text": prompt}]
            }
            try:
                await bot.edit_message_text(before_generate_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                response = await async_generate_content(model, contents)
                await bot.edit_message_text(response.text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
            except Exception:
                traceback.print_exc()
                await bot.edit_message_text(error_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
        else:
            s = message.caption if message.caption else ""
            try:
                prompt = s.strip()
                file_path = await bot.get_file(message.photo[-1].file_id)
                sent_message = await bot.reply_to(message, download_pic_notify)
                downloaded_file = await bot.download_file(file_path.file_path)
            except Exception:
                traceback.print_exc()
                await bot.reply_to(message, error_info)
            model = genai.GenerativeModel("gemini-pro-vision")
            contents = {
                "parts": [{"mime_type": "image/jpeg", "data": downloaded_file}, {"text": prompt}]
            }
            try:
                await bot.edit_message_text(before_generate_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                response = await async_generate_content(model, contents)
                await bot.edit_message_text(response.text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
            except Exception:
                traceback.print_exc()
                await bot.edit_message_text(error_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)

    # Start bot
    print("Starting Gemini_Telegram_Bot.")
    await bot.polling(none_stop=True)

if __name__ == '__main__':
    asyncio.run(main())
