def send_copyable_code(call, delete_message, *, chat_id, text, code, remove_keyboard=False):
    markup = {"inline_keyboard": [[{
        "text": "📋 Kodni nusxalash / Копировать код",
        "copy_text": {"text": code},
    }]]}
    # Protected content prevents clients from copying the code. Keep these
    # private OTP messages copyable; their expiry and one-use checks still apply.
    if remove_keyboard:
        # Telegram accepts only one reply markup per send. Clear the contact
        # keyboard with a silent temporary message and remove it before the OTP.
        clearing = call("sendMessage", chat_id=chat_id,
                        text="Kod tayyorlanmoqda… / Готовим код…", disable_notification=True,
                        reply_markup={"remove_keyboard": True})
        delete_message(chat_id, clearing["message_id"])
    return call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=markup)
