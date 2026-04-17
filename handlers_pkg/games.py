from core import *

SOURCE_LABELS = {
    "main": "Main Balance",
    "referral": "Referral Balance",
    "daily_bonus": "Daily Bonus Balance",
    "gift": "Gift Code Balance",
}

SETTING_META = [
    ("mine_game_enabled", "toggle", "Game ON/OFF"),
    ("mine_global_win_rate", "number", "Global Win Rate %"),
    ("mine_force_win_all", "toggle", "Force Win All"),
    ("mine_force_loss_all", "toggle", "Force Loss All"),
    ("mine_force_win_users", "user_list", "Force Win Users"),
    ("mine_force_loss_users", "user_list", "Force Loss Users"),
    ("mine_base_multiplier", "number", "Base Multiplier"),
    ("mine_progressive_multiplier_rate", "number", "Progressive Rate"),
    ("mine_max_multiplier_cap", "number", "Max Multiplier Cap"),
    ("mine_jackpot_multiplier", "number", "Jackpot Multiplier"),
    ("mine_min_bet", "number", "Min Bet"),
    ("mine_max_bet", "number", "Max Bet"),
    ("mine_grid_size", "int", "Grid Size"),
    ("mine_min_mines", "int", "Min Mines"),
    ("mine_max_mines", "int", "Max Mines"),
    ("mine_daily_play_limit", "int", "Daily Play Limit"),
    ("mine_hourly_play_limit", "int", "Hourly Play Limit"),
    ("mine_cooldown_seconds", "int", "Cooldown Seconds"),
    ("mine_winning_tax_percent", "number", "Winning Tax %"),
    ("mine_gst_on_winnings", "number", "GST On Winnings %"),
    ("mine_max_win_amount_per_session", "number", "Max Win / Session"),
    ("mine_daily_win_cap_per_user", "number", "Daily Win Cap / User"),
    ("mine_house_edge_percent", "number", "House Edge %"),
    ("mine_consecutive_win_limit", "int", "Consecutive Win Limit"),
    ("mine_consecutive_loss_limit", "int", "Consecutive Loss Limit"),
    ("mine_blacklist_users", "user_list", "Blacklist Users"),
    ("mine_sound_effects_enabled", "toggle", "Sound Effects"),
    ("mine_risk_indicator_enabled", "toggle", "Risk Indicator"),
    ("mine_auto_cash_out_enabled", "toggle", "Auto Cash Out"),
    ("mine_force_safe_first_tile", "toggle", "Safe First Tile"),
]
SETTING_META_MAP = {k: {"type": t, "label": lbl} for k, t, lbl in SETTING_META}


def _active_mine_session(user_id):
    return db_execute(
        "SELECT * FROM mine_game_sessions WHERE user_id=? AND status='active' ORDER BY id DESC LIMIT 1",
        (user_id,), fetchone=True
    )


def _build_empty_board(size):
    total = size * size
    return ["hidden"] * total


def _render_session_text(session, user=None, final_message=""):
    user = user or get_user(session["user_id"])
    total_tiles = int(session["grid_size"]) * int(session["grid_size"])
    safe_tiles = total_tiles - int(session["mines_count"])
    payout = round(float(session["bet_amount"]) * float(session["current_multiplier"]), 2)
    source = SOURCE_LABELS.get(session["source_balance"], session["source_balance"])
    risk_line = ""
    if bool(get_setting("mine_risk_indicator_enabled")):
        remaining_hidden = max(0, total_tiles - len(safe_json(session["revealed_json"], [])))
        remaining_mines = max(0, int(session["mines_count"]) - len([x for x in safe_json(session["board_json"], []) if x == "mine"]))
        risk = round((remaining_mines / max(1, remaining_hidden)) * 100, 2)
        risk_line = f"\n{pe('warning')} <b>Risk:</b> {risk}%"
    sound_line = f"\n{pe('speaker')} <b>Sound:</b> {'ON' if bool(get_setting('mine_sound_effects_enabled')) else 'OFF'}"
    return (
        f"{pe('game')} <b>Mine Game</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('money')} <b>Bet:</b> ₹{float(session['bet_amount']):.2f}\n"
        f"{pe('target')} <b>Mines:</b> {int(session['mines_count'])}\n"
        f"{pe('diamond')} <b>Gems Found:</b> {int(session['gems_found'])}/{safe_tiles}\n"
        f"{pe('chart_up')} <b>Multiplier:</b> x{float(session['current_multiplier']):.2f}\n"
        f"{pe('fly_money')} <b>Cash Out Value:</b> ₹{payout:.2f}\n"
        f"{pe('wallet')} <b>Source:</b> {source}"
        f"{risk_line}{sound_line}\n\n"
        f"{final_message or 'Pick a tile. Cash out anytime after a gem.'}"
    )


def _render_board_markup(session, game_over=False):
    board = safe_json(session["board_json"], [])
    revealed = set(safe_json(session["revealed_json"], []))
    size = int(session["grid_size"])
    markup = types.InlineKeyboardMarkup(row_width=size)
    rows = []
    for r in range(size):
        row = []
        for c in range(size):
            idx = r * size + c
            if idx in revealed or game_over:
                state = board[idx] if idx < len(board) else "hidden"
                if state == "gem":
                    label = "💎"
                elif state == "mine":
                    label = "💣"
                else:
                    label = "⬜"
                row.append(types.InlineKeyboardButton(label, callback_data="mine_noop"))
            else:
                row.append(types.InlineKeyboardButton("❔", callback_data=f"mine_pick|{session['id']}|{idx}"))
        rows.append(row)
    for row in rows:
        markup.row(*row)
    if not game_over:
        markup.row(
            types.InlineKeyboardButton("💰 Cash Out", callback_data=f"mine_cashout|{session['id']}"),
            types.InlineKeyboardButton("🛑 End", callback_data=f"mine_end|{session['id']}"),
        )
    else:
        markup.row(types.InlineKeyboardButton("🔁 Play Again", callback_data="mine_play_again"))
    url = get_public_mine_url()
    if url:
        markup.row(types.InlineKeyboardButton("🌐 Mine UI", url=url))
    return markup


def _determine_safe_target(user_id, mines_count, grid_size):
    total_tiles = grid_size * grid_size
    safe_tiles = max(1, total_tiles - mines_count)
    outcome_mode = get_mine_outcome_mode(user_id)
    if outcome_mode == "force_win":
        return safe_tiles, outcome_mode
    if outcome_mode == "force_loss":
        return 0, outcome_mode
    win_rate = max(0.0, min(100.0, safe_float(get_setting("mine_global_win_rate"), 45)))
    roll = random.uniform(0, 100)
    if roll <= win_rate:
        target = random.randint(1, max(1, min(safe_tiles, 5 + mines_count // 2)))
    else:
        target = random.randint(0, min(2, safe_tiles))
    return target, outcome_mode


def _create_session(user_id, chat_id, bet_amount, mines_count, source_balance):
    grid_size = safe_int(get_setting("mine_grid_size"), 5)
    board = _build_empty_board(grid_size)
    safe_target, outcome_mode = _determine_safe_target(user_id, mines_count, grid_size)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session_id = db_lastrowid(
        "INSERT INTO mine_game_sessions (user_id, chat_id, source_balance, bet_amount, mines_count, grid_size, board_json, revealed_json, gems_found, safe_target, current_multiplier, payout_amount, status, outcome_mode, first_pick_safe, created_at, updated_at, client_seed, server_seed) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            user_id, chat_id, source_balance, bet_amount, mines_count, grid_size,
            json.dumps(board), json.dumps([]), 0, safe_target, 1.0, 0.0, "active", outcome_mode,
            1 if bool(get_setting("mine_force_safe_first_tile")) else 0,
            now, now, generate_code(8), generate_code(16)
        )
    )
    return db_execute("SELECT * FROM mine_game_sessions WHERE id=?", (session_id,), fetchone=True)


def _finalize_session(session, result, gross_payout=0.0, tax_amount=0.0, gst_amount=0.0, finished_note=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    net_payout = round(max(0.0, gross_payout - tax_amount - gst_amount), 2)
    board = safe_json(session["board_json"], [])
    for i, value in enumerate(board):
        if value == "hidden":
            board[i] = "gem"
    if result == "loss":
        hidden_indices = [i for i, value in enumerate(board) if value == "gem" and i not in safe_json(session["revealed_json"], [])]
        mines_needed = max(0, int(session["mines_count"]) - len([x for x in board if x == "mine"]))
        random.shuffle(hidden_indices)
        for idx in hidden_indices[:mines_needed]:
            board[idx] = "mine"
    db_execute(
        "UPDATE mine_game_sessions SET board_json=?, payout_amount=?, status=?, finished_at=?, updated_at=? WHERE id=?",
        (json.dumps(board), gross_payout, result, now, now, session["id"])
    )
    db_execute(
        "INSERT INTO mine_game_history (session_id, user_id, source_balance, bet_amount, mines_count, grid_size, gems_found, multiplier, gross_payout, tax_amount, gst_amount, net_payout, result, status, board_json, revealed_json, created_at, finished_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            session["id"], session["user_id"], session["source_balance"], session["bet_amount"], session["mines_count"],
            session["grid_size"], session["gems_found"], session["current_multiplier"], gross_payout, tax_amount, gst_amount,
            net_payout, result, result, json.dumps(board), session["revealed_json"], session["created_at"], now
        )
    )
    return db_execute("SELECT * FROM mine_game_sessions WHERE id=?", (session["id"],), fetchone=True), net_payout


def _show_games_home(chat_id, user_id):
    user = get_user(user_id)
    if not user:
        safe_send(chat_id, "Please send /start first.")
        return
    wallets = get_wallet_breakdown(user)
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("💣 Mine Game", callback_data="mine_open"))
    url = get_public_mine_url()
    if url:
        markup.add(types.InlineKeyboardButton("🌐 Open Mine UI", url=url))
    text = (
        f"{pe('game')} <b>Games</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('money')} <b>Total Balance:</b> ₹{float(user['balance']):.2f}\n"
        f"{pe('people')} <b>Referral Balance:</b> ₹{wallets['referral']:.2f}\n"
        f"{pe('party')} <b>Daily Bonus Balance:</b> ₹{wallets['daily_bonus']:.2f}\n"
        f"{pe('gift')} <b>Gift Balance:</b> ₹{wallets['gift']:.2f}\n\n"
        f"{pe('diamond')} Play Mine Game using your real wallet balances."
    )
    safe_send(chat_id, text, reply_markup=markup)


def games_menu_user(message):
    _show_games_home(message.chat.id, message.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "mine_open")
def mine_open(call):
    if is_admin(call.from_user.id) and call.message.reply_markup is None:
        pass
    safe_answer(call)
    ok, reason = can_user_play_mine(call.from_user.id)
    if not ok:
        safe_send(call.message.chat.id, f"{pe('warning')} {reason}")
        return
    min_mines = safe_int(get_setting("mine_min_mines"), 1)
    max_mines = safe_int(get_setting("mine_max_mines"), max(1, safe_int(get_setting("mine_grid_size"), 5) ** 2 - 1))
    set_state(call.from_user.id, "mine_enter_mines")
    safe_send(
        call.message.chat.id,
        f"{pe('target')} <b>Mine Game Setup</b>\n\nEnter number of mines between <b>{min_mines}</b> and <b>{max_mines}</b>."
    )


@bot.callback_query_handler(func=lambda call: call.data == "mine_play_again")
def mine_play_again(call):
    safe_answer(call)
    ok, reason = can_user_play_mine(call.from_user.id)
    if not ok:
        safe_send(call.message.chat.id, f"{pe('warning')} {reason}")
        return
    set_state(call.from_user.id, "mine_enter_mines")
    safe_send(call.message.chat.id, f"{pe('target')} Enter mine count to start a new round.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("mine_source|"))
def mine_source_pick(call):
    if not check_force_join(call.from_user.id):
        send_join_message(call.message.chat.id)
        return
    _, source = call.data.split("|", 1)
    data = get_state_data(call.from_user.id)
    bet = safe_float(data.get("bet_amount"), 0)
    mines = safe_int(data.get("mines_count"), 0)
    if bet <= 0 or mines <= 0:
        safe_answer(call, "Session setup expired.", True)
        clear_state(call.from_user.id)
        return
    avail = get_available_game_balance(call.from_user.id, source)
    if avail < bet:
        safe_answer(call, f"Not enough {SOURCE_LABELS.get(source, source)}.", True)
        return
    ok, reason = debit_game_balance(call.from_user.id, bet, source)
    if not ok:
        safe_answer(call, reason, True)
        return
    session = _create_session(call.from_user.id, call.message.chat.id, bet, mines, source)
    clear_state(call.from_user.id)
    safe_answer(call, "Mine Game started!")
    safe_send(call.message.chat.id, _render_session_text(session), reply_markup=_render_board_markup(session))


@bot.callback_query_handler(func=lambda call: call.data.startswith("mine_pick|"))
def mine_pick(call):
    if not check_force_join(call.from_user.id):
        send_join_message(call.message.chat.id)
        return
    safe_answer(call)
    _, session_id, idx = call.data.split("|")
    session = db_execute("SELECT * FROM mine_game_sessions WHERE id=? AND user_id=?", (int(session_id), call.from_user.id), fetchone=True)
    if not session or session["status"] != "active":
        safe_send(call.message.chat.id, f"{pe('warning')} This game session is no longer active.")
        return
    idx = safe_int(idx)
    revealed = safe_json(session["revealed_json"], [])
    if idx in revealed:
        return
    board = safe_json(session["board_json"], [])
    gems_found = safe_int(session["gems_found"])
    safe_target = safe_int(session["safe_target"])
    total_tiles = safe_int(session["grid_size"]) ** 2
    safe_tiles = total_tiles - safe_int(session["mines_count"])
    force_first = bool(session["first_pick_safe"]) and gems_found == 0 and bool(get_setting("mine_force_safe_first_tile"))
    should_be_gem = force_first or gems_found < safe_target
    if safe_int(session["mines_count"]) >= total_tiles:
        should_be_gem = False
    board[idx] = "gem" if should_be_gem else "mine"
    revealed.append(idx)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if should_be_gem:
        gems_found += 1
        multiplier = get_mine_multiplier(gems_found, session["mines_count"], session["grid_size"])
        payout = round(float(session["bet_amount"]) * multiplier, 2)
        db_execute(
            "UPDATE mine_game_sessions SET board_json=?, revealed_json=?, gems_found=?, current_multiplier=?, payout_amount=?, updated_at=? WHERE id=?",
            (json.dumps(board), json.dumps(revealed), gems_found, multiplier, payout, now, session["id"])
        )
        session = db_execute("SELECT * FROM mine_game_sessions WHERE id=?", (session["id"],), fetchone=True)
        auto_cash = bool(get_setting("mine_auto_cash_out_enabled")) and gems_found >= max(1, min(3, safe_target if safe_target > 0 else 3))
        if gems_found >= safe_tiles:
            auto_cash = True
        if auto_cash:
            _cashout_session(call, session, auto_trigger=True)
            return
        safe_edit(call.message.chat.id, call.message.message_id, _render_session_text(session, final_message="💎 Safe tile! Keep going or cash out."), reply_markup=_render_board_markup(session))
        return
    db_execute(
        "UPDATE mine_game_sessions SET board_json=?, revealed_json=?, updated_at=? WHERE id=?",
        (json.dumps(board), json.dumps(revealed), now, session["id"])
    )
    session = db_execute("SELECT * FROM mine_game_sessions WHERE id=?", (session["id"],), fetchone=True)
    finished, _ = _finalize_session(session, "loss", 0.0, 0.0, 0.0)
    safe_edit(call.message.chat.id, call.message.message_id, _render_session_text(finished, final_message="💣 Boom! You hit a mine and lost this round."), reply_markup=_render_board_markup(finished, game_over=True))


def _cashout_session(call, session, auto_trigger=False):
    payout = round(float(session["bet_amount"]) * float(session["current_multiplier"]), 2)
    max_win = safe_float(get_setting("mine_max_win_amount_per_session"), 0)
    if max_win > 0:
        payout = min(payout, max_win)
    today = datetime.now().strftime("%Y-%m-%d")
    daily_cap = safe_float(get_setting("mine_daily_win_cap_per_user"), 0)
    if daily_cap > 0:
        row = db_execute(
            "SELECT SUM(net_payout) AS s FROM mine_game_history WHERE user_id=? AND substr(created_at,1,10)=? AND result='cashout'",
            (session["user_id"], today), fetchone=True
        )
        already = safe_float(row["s"] if row else 0)
        payout = min(payout, max(0.0, daily_cap - already))
    gross_profit = max(0.0, payout - float(session["bet_amount"]))
    tax_amount = round(gross_profit * safe_float(get_setting("mine_winning_tax_percent"), 0) / 100.0, 2)
    gst_amount = round(gross_profit * safe_float(get_setting("mine_gst_on_winnings"), 0) / 100.0, 2)
    finished, net_payout = _finalize_session(session, "cashout", payout, tax_amount, gst_amount)
    credit_game_winnings(session["user_id"], net_payout, gross_profit)
    note = "🤖 Auto cash out triggered." if auto_trigger else "💰 Cashed out successfully."
    safe_edit(
        call.message.chat.id,
        call.message.message_id,
        _render_session_text(
            finished,
            final_message=f"{note}\nGross: ₹{payout:.2f} | Tax: ₹{tax_amount:.2f} | GST: ₹{gst_amount:.2f} | Net: ₹{net_payout:.2f}"
        ),
        reply_markup=_render_board_markup(finished, game_over=True)
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("mine_cashout|"))
def mine_cashout(call):
    safe_answer(call)
    _, session_id = call.data.split("|")
    session = db_execute("SELECT * FROM mine_game_sessions WHERE id=? AND user_id=?", (int(session_id), call.from_user.id), fetchone=True)
    if not session or session["status"] != "active":
        safe_send(call.message.chat.id, f"{pe('warning')} Session not active.")
        return
    if safe_int(session["gems_found"]) <= 0:
        safe_answer(call, "Reveal at least one gem first.", True)
        return
    _cashout_session(call, session)


@bot.callback_query_handler(func=lambda call: call.data.startswith("mine_end|"))
def mine_end(call):
    safe_answer(call)
    _, session_id = call.data.split("|")
    session = db_execute("SELECT * FROM mine_game_sessions WHERE id=? AND user_id=?", (int(session_id), call.from_user.id), fetchone=True)
    if not session or session["status"] != "active":
        return
    finished, _ = _finalize_session(session, "loss", 0.0, 0.0, 0.0)
    safe_edit(call.message.chat.id, call.message.message_id, _render_session_text(finished, final_message="🛑 Game ended. Bet forfeited."), reply_markup=_render_board_markup(finished, game_over=True))


@bot.callback_query_handler(func=lambda call: call.data == "mine_noop")
def mine_noop(call):
    safe_answer(call)


# ---------------- Admin controls ----------------

def _mine_admin_value(key):
    val = get_setting(key)
    if isinstance(val, list):
        return ", ".join(str(x) for x in val[:20]) or "—"
    if isinstance(val, bool):
        return "ON" if val else "OFF"
    return str(val)


def show_mine_admin_panel(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for key, _, label in SETTING_META[:12]:
        markup.add(types.InlineKeyboardButton(label[:28], callback_data=f"mineadm_set|{key}"))
    markup.add(
        types.InlineKeyboardButton("More Settings", callback_data="mineadm_more"),
        types.InlineKeyboardButton("Stats", callback_data="mineadm_stats"),
    )
    markup.add(
        types.InlineKeyboardButton("History", callback_data="mineadm_history"),
        types.InlineKeyboardButton("Active Sessions", callback_data="mineadm_active"),
    )
    summary = (
        f"{pe('game')} <b>Mine Game Control</b>\n\n"
        f"Enabled: <b>{_mine_admin_value('mine_game_enabled')}</b>\n"
        f"Win Rate: <b>{_mine_admin_value('mine_global_win_rate')}%</b>\n"
        f"Bet Range: <b>₹{get_setting('mine_min_bet')} - ₹{get_setting('mine_max_bet')}</b>\n"
        f"Grid: <b>{get_setting('mine_grid_size')}x{get_setting('mine_grid_size')}</b>\n"
        f"Mines: <b>{get_setting('mine_min_mines')} - {get_setting('mine_max_mines')}</b>\n"
        f"Safe First Tile: <b>{_mine_admin_value('mine_force_safe_first_tile')}</b>\n"
        f"Auto Cash Out: <b>{_mine_admin_value('mine_auto_cash_out_enabled')}</b>"
    )
    safe_send(chat_id, summary, reply_markup=markup)


def mine_admin_entry(message):
    show_mine_admin_panel(message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == "mineadm_more")
def mineadm_more(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    markup = types.InlineKeyboardMarkup(row_width=2)
    for key, _, label in SETTING_META[12:]:
        markup.add(types.InlineKeyboardButton(label[:28], callback_data=f"mineadm_set|{key}"))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="mineadm_home"))
    safe_send(call.message.chat.id, f"{pe('gear')} <b>More Mine Settings</b>", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "mineadm_home")
def mineadm_home(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    show_mine_admin_panel(call.message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("mineadm_set|"))
def mineadm_set(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    _, key = call.data.split("|", 1)
    meta = SETTING_META_MAP.get(key)
    if not meta:
        return
    if meta["type"] == "toggle":
        set_setting(key, not bool(get_setting(key)))
        safe_send(call.message.chat.id, f"{pe('check')} {meta['label']} set to {_mine_admin_value(key)}")
        return
    prompt = f"{pe('pencil')} <b>{meta['label']}</b>\nCurrent: <code>{h(_mine_admin_value(key))}</code>\n\nSend new value."
    if meta["type"] == "user_list":
        prompt += "\nFormat: <code>12345,67890</code> or <code>empty</code>"
    set_state(call.from_user.id, f"mine_admin_setting|{key}")
    safe_send(call.message.chat.id, prompt)


@bot.callback_query_handler(func=lambda call: call.data == "mineadm_stats")
def mineadm_stats(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    row = db_execute(
        "SELECT COUNT(*) AS plays, SUM(bet_amount) AS wagered, SUM(net_payout) AS paid, SUM(CASE WHEN result='cashout' THEN 1 ELSE 0 END) AS wins, SUM(CASE WHEN result='loss' THEN 1 ELSE 0 END) AS losses FROM mine_game_history",
        fetchone=True
    )
    active = db_execute("SELECT COUNT(*) AS c FROM mine_game_sessions WHERE status='active'", fetchone=True)
    today = datetime.now().strftime("%Y-%m-%d")
    today_row = db_execute(
        "SELECT COUNT(*) AS plays, SUM(bet_amount) AS wagered, SUM(net_payout) AS paid FROM mine_game_history WHERE substr(created_at,1,10)=?",
        (today,), fetchone=True
    )
    plays = safe_int(row["plays"] if row else 0)
    wagered = safe_float(row["wagered"] if row else 0)
    paid = safe_float(row["paid"] if row else 0)
    safe_send(
        call.message.chat.id,
        f"{pe('chart')} <b>Mine Game Analytics</b>\n\n"
        f"Total Plays: <b>{plays}</b>\n"
        f"Wins: <b>{safe_int(row['wins'] if row else 0)}</b> | Losses: <b>{safe_int(row['losses'] if row else 0)}</b>\n"
        f"Wagered: <b>₹{wagered:.2f}</b>\n"
        f"Paid Out: <b>₹{paid:.2f}</b>\n"
        f"House Profit: <b>₹{(wagered - paid):.2f}</b>\n"
        f"Active Sessions: <b>{safe_int(active['c'] if active else 0)}</b>\n\n"
        f"Today → Plays: <b>{safe_int(today_row['plays'] if today_row else 0)}</b>, Wagered: <b>₹{safe_float(today_row['wagered'] if today_row else 0):.2f}</b>, Paid: <b>₹{safe_float(today_row['paid'] if today_row else 0):.2f}</b>"
    )


@bot.callback_query_handler(func=lambda call: call.data == "mineadm_history")
def mineadm_history(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    rows = db_execute(
        "SELECT * FROM mine_game_history ORDER BY id DESC LIMIT 20",
        fetch=True
    ) or []
    if not rows:
        safe_send(call.message.chat.id, f"{pe('info')} No Mine Game history yet.")
        return
    text = f"{pe('list')} <b>Mine Game History</b>\n\n"
    for row in rows:
        text += (
            f"#{row['id']} | User <code>{row['user_id']}</code> | {row['result']}\n"
            f"Bet ₹{float(row['bet_amount']):.2f} | Mult x{float(row['multiplier']):.2f} | Net ₹{float(row['net_payout']):.2f}\n"
            f"Gems {int(row['gems_found'])} | Mines {int(row['mines_count'])} | {row['created_at'][:16]}\n\n"
        )
    safe_send(call.message.chat.id, text[:4000])


@bot.callback_query_handler(func=lambda call: call.data == "mineadm_active")
def mineadm_active(call):
    if not is_admin(call.from_user.id):
        return
    safe_answer(call)
    rows = db_execute(
        "SELECT * FROM mine_game_sessions WHERE status='active' ORDER BY id DESC LIMIT 20",
        fetch=True
    ) or []
    if not rows:
        safe_send(call.message.chat.id, f"{pe('info')} No active Mine Game sessions.")
        return
    text = f"{pe('active')} <b>Active Mine Sessions</b>\n\n"
    for row in rows:
        text += (
            f"Session #{row['id']} | User <code>{row['user_id']}</code>\n"
            f"Bet ₹{float(row['bet_amount']):.2f} | Gems {int(row['gems_found'])} | x{float(row['current_multiplier']):.2f}\n"
            f"Mode: {row['outcome_mode']} | {row['created_at'][:16]}\n\n"
        )
    safe_send(call.message.chat.id, text[:4000])
