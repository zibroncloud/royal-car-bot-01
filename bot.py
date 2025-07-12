#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RoyalCarBot01 - Bot Telegram Car Valet Service
Versione: 2.0.0
Data: 12 Luglio 2025
Autore: Claude AI + zibroncloud
"""

import os
import logging
import sqlite3
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

BOT_VERSION = "2.0.0"
BOT_NAME = "RoyalCarBot01"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def init_db():
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, active INTEGER DEFAULT 1)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT, targa TEXT NOT NULL, cliente TEXT NOT NULL,
        camera TEXT NOT NULL, servizio TEXT NOT NULL, stato TEXT DEFAULT 'nuovo',
        tempo_ritiro TEXT, tempo_riconsegna TEXT, created_by INTEGER, assigned_to INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, completed_at TIMESTAMP, note TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER, file_id TEXT NOT NULL,
        tipo TEXT NOT NULL, uploaded_by INTEGER, uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (request_id) REFERENCES requests (id))''')
    
    conn.commit()
    conn.close()

init_db()

def get_user_role(telegram_id):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT role FROM users WHERE telegram_id = ? AND active = 1', (telegram_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def add_user(telegram_id, name, role):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO users (telegram_id, name, role, active) VALUES (?, ?, ?, 1)', 
                   (telegram_id, name, role))
    conn.commit()
    conn.close()

def create_request(targa, cliente, camera, servizio, created_by):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO requests (targa, cliente, camera, servizio, created_by) VALUES (?, ?, ?, ?, ?)',
                   (targa.upper(), cliente, camera, servizio, created_by))
    request_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return request_id

def get_requests(stato=None, search_term=None, assigned_to=None):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    
    query = '''SELECT r.id, r.targa, r.cliente, r.camera, r.servizio, r.stato, r.created_at,
               u1.name as created_by_name, u2.name as assigned_to_name, r.tempo_ritiro, r.tempo_riconsegna
               FROM requests r LEFT JOIN users u1 ON r.created_by = u1.telegram_id
               LEFT JOIN users u2 ON r.assigned_to = u2.telegram_id WHERE 1=1'''
    params = []
    
    if stato:
        query += ' AND r.stato = ?'
        params.append(stato)
    if assigned_to:
        query += ' AND r.assigned_to = ?'
        params.append(assigned_to)
    if search_term:
        query += ' AND (r.targa LIKE ? OR r.cliente LIKE ?)'
        params.extend([f'%{search_term.upper()}%', f'%{search_term}%'])
    
    query += ' ORDER BY r.created_at DESC'
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return results

def update_request_status(request_id, new_status, assigned_to=None, tempo_ritiro=None, tempo_riconsegna=None):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    
    updates = ['stato = ?']
    params = [new_status]
    
    if assigned_to:
        updates.append('assigned_to = ?')
        params.append(assigned_to)
    if tempo_ritiro:
        updates.append('tempo_ritiro = ?')
        params.append(tempo_ritiro)
    if tempo_riconsegna:
        updates.append('tempo_riconsegna = ?')
        params.append(tempo_riconsegna)
    if new_status == 'riconsegnato':
        updates.append('completed_at = CURRENT_TIMESTAMP')
    
    params.append(request_id)
    query = f"UPDATE requests SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def get_request_by_id(request_id):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    cursor.execute('''SELECT r.*, u1.name as created_by_name, u2.name as assigned_to_name
                      FROM requests r LEFT JOIN users u1 ON r.created_by = u1.telegram_id
                      LEFT JOIN users u2 ON r.assigned_to = u2.telegram_id WHERE r.id = ?''', (request_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def add_photo(request_id, file_id, tipo, uploaded_by):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO photos (request_id, file_id, tipo, uploaded_by) VALUES (?, ?, ?, ?)',
                   (request_id, file_id, tipo, uploaded_by))
    conn.commit()
    conn.close()

def get_main_keyboard(role):
    if role == 'reception':
        keyboard = [
            [KeyboardButton("🆕 Nuova Richiesta")],
            [KeyboardButton("📋 Tutte le Richieste"), KeyboardButton("🔍 Cerca")],
            [KeyboardButton("📊 Dashboard"), KeyboardButton("🚚 Richiedi Riconsegna")],
            [KeyboardButton("❓ Help"), KeyboardButton("❌ Annulla")]
        ]
    else:
        keyboard = [
            [KeyboardButton("📋 Mie Richieste"), KeyboardButton("🆕 Richieste Nuove")],
            [KeyboardButton("📷 Aggiungi Foto"), KeyboardButton("✅ Aggiorna Stato")],
            [KeyboardButton("❓ Help"), KeyboardButton("❌ Annulla")]
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    role = get_user_role(user.id)
    context.user_data.clear()
    
    if not role:
        await update.message.reply_text(
            f"🚗 *{BOT_NAME} v{BOT_VERSION}*\n\n"
            "Per utilizzare questo bot, devi essere registrato.\n\n"
            "📝 *Comandi disponibili:*\n"
            "• `/register <nome> reception` - Registrati come Reception\n"
            "• `/register <nome> valet` - Registrati come Valet\n"
            "• `/help` - Mostra tutti i comandi\n\n"
            "*Esempio:* `/register Mario reception`", parse_mode='Markdown')
        return
    
    welcome_msg = f"🚗 *{BOT_NAME} v{BOT_VERSION}*\n*Benvenuto {user.first_name}!*\n\n"
    if role == 'reception':
        welcome_msg += "Sei connesso come *Reception*\nPuoi creare nuove richieste e gestire tutto il servizio valet."
    else:
        welcome_msg += "Sei connesso come *Valet*\nPuoi vedere le tue richieste e aggiornare lo stato dei servizi."
    
    await update.message.reply_text(welcome_msg, reply_markup=get_main_keyboard(role), parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = get_user_role(update.effective_user.id)
    
    if not role:
        help_text = f"❓ *HELP - {BOT_NAME} v{BOT_VERSION}*\n\n📝 *Registrazione:*\n• `/register <nome> reception`\n• `/register <nome> valet`\n\n🔧 *Comandi:*\n• `/start` - Menu principale\n• `/help` - Questo messaggio\n• `/annulla` - Annulla operazione"
    elif role == 'reception':
        help_text = "❓ *HELP - RECEPTION*\n\n🎯 *Menu:*\n• 🆕 Nuova Richiesta\n• 📋 Tutte le Richieste\n• 🔍 Cerca\n• 📊 Dashboard\n• 🚚 Richiedi Riconsegna\n\n📋 *Stati:* 🆕→👤→⚙️→🚗→✅"
    else:
        help_text = "❓ *HELP - VALET*\n\n🎯 *Menu:*\n• 📋 Mie Richieste\n• 🆕 Richieste Nuove\n• 📷 Aggiungi Foto\n• ✅ Aggiorna Stato\n\n⏰ *Tempi:* 5/10/20 min\n📷 *Foto:* `#123 prima`"
    
    await update.message.reply_text(help_text, parse_mode='Markdown', reply_markup=get_main_keyboard(role) if role else None)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = get_user_role(update.effective_user.id)
    context.user_data.clear()
    
    if role:
        await update.message.reply_text("❌ *Operazione annullata!*", reply_markup=get_main_keyboard(role), parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Operazione annullata.\n\nUsa `/register <nome> <ruolo>` per registrarti.")

async def register_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) != 2:
        await update.message.reply_text("❌ *Formato sbagliato!*\n\n📝 Uso: `/register <nome> <ruolo>`\n🎭 Ruoli: `reception`, `valet`\n💡 Esempio: `/register Mario reception`", parse_mode='Markdown')
        return
    
    name, role = context.args[0], context.args[1].lower()
    
    if role not in ['reception', 'valet']:
        await update.message.reply_text("❌ *Ruolo non valido!* Usa: `reception` o `valet`", parse_mode='Markdown')
        return
    
    add_user(update.effective_user.id, name, role)
    role_name = "Reception" if role == 'reception' else "Valet"
    
    await update.message.reply_text(
        f"✅ *Registrazione completata!*\n\n👤 *Nome:* {name}\n🎭 *Ruolo:* {role_name}\n\nOra puoi utilizzare tutte le funzioni del bot!",
        reply_markup=get_main_keyboard(role), parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    role = get_user_role(user.id)
    text = update.message.text
    
    if not role:
        await update.message.reply_text("⚠️ Non sei registrato!\n\nUsa: `/register <nome> <ruolo>`")
        return
    
    if context.user_data.get('state') == 'creating_request':
        await handle_new_request_data(update, context)
        return
    
    if context.user_data.get('state') == 'searching':
        await handle_search(update, context)
        return
    
    if context.user_data.get('state') == 'requesting_delivery':
        await handle_delivery_request(update, context)
        return
    
    if text == "🆕 Nuova Richiesta" and role == 'reception':
        context.user_data['state'] = 'creating_request'
        context.user_data['request_data'] = {}
        await update.message.reply_text("🚗 *Nuova Richiesta Car Valet*\n\nInserisci la *targa* del veicolo:", parse_mode='Markdown')
    
    elif text == "📋 Tutte le Richieste":
        await show_all_requests(update, context)
    
    elif text == "🔍 Cerca":
        context.user_data['state'] = 'searching'
        await update.message.reply_text("🔍 *Ricerca*\n\nInserisci targa, cognome cliente o numero camera:", parse_mode='Markdown')
    
    elif text == "🚚 Richiedi Riconsegna" and role == 'reception':
        context.user_data['state'] = 'requesting_delivery'
        await update.message.reply_text("🚚 *Richiesta Riconsegna*\n\nInserisci la *targa* del veicolo:", parse_mode='Markdown')
    
    elif text == "📋 Mie Richieste" and role == 'valet':
        await show_valet_requests(update, context)
    
    elif text == "🆕 Richieste Nuove" and role == 'valet':
        await show_new_requests(update, context)
    
    elif text == "📊 Dashboard" and role == 'reception':
        await show_dashboard(update, context)
    
    elif text == "❓ Help":
        await help_command(update, context)
    
    elif text == "❌ Annulla":
        await cancel_command(update, context)
    
    else:
        await update.message.reply_text("❓ *Comando non riconosciuto*\n\nUsa i pulsanti del menu o `/help`", parse_mode='Markdown')

async def handle_new_request_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    request_data = context.user_data.get('request_data', {})
    
    if 'targa' not in request_data:
        request_data['targa'] = text.upper()
        context.user_data['request_data'] = request_data
        await update.message.reply_text("👤 Inserisci il *cognome del cliente*:", parse_mode='Markdown')
    
    elif 'cliente' not in request_data:
        request_data['cliente'] = text
        context.user_data['request_data'] = request_data
        await update.message.reply_text("🏨 Inserisci il *numero della camera*:", parse_mode='Markdown')
    
    elif 'camera' not in request_data:
        request_data['camera'] = text
        context.user_data['request_data'] = request_data
        
        keyboard = [
            [InlineKeyboardButton("🧽 Lavaggio Esterno", callback_data="servizio_lavaggio_esterno")],
            [InlineKeyboardButton("🧼 Lavaggio Completo", callback_data="servizio_lavaggio_completo")],
            [InlineKeyboardButton("🔧 Servizio Meccanico", callback_data="servizio_meccanico")],
            [InlineKeyboardButton("⛽ Rifornimento", callback_data="servizio_rifornimento")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text("🔧 *Tipo di Servizio*\n\nSeleziona il servizio:", 
                                      reply_markup=reply_markup, parse_mode='Markdown')

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_term = update.message.text
    requests = get_requests(search_term=search_term)
    context.user_data['state'] = None
    
    if not requests:
        await update.message.reply_text(f"❌ *Nessuna richiesta trovata*\n\n🔍 Cercato: `{search_term}`", 
                                      parse_mode='Markdown', reply_markup=get_main_keyboard(get_user_role(update.effective_user.id)))
        return
    
    message = f"🔍 *Risultati: {search_term}*\n\n"
    for req in requests:
        status_emoji = {'nuovo': '🆕', 'assegnato': '👤', 'in_corso': '⚙️', 'partito': '🚗', 'completato': '✅', 'riconsegnato': '🏁', 'annullato': '❌'}
        message += f"{status_emoji.get(req[5], '📋')} *#{req[0]}* - {req[1]}\n👤 {req[2]} | 🏨 {req[3]}\n🔧 {req[4]} | 📊 {req[5].upper()}\n"
        if req[8]: message += f"👨‍🔧 {req[8]}\n"
        if req[9]: message += f"⏰ {req[9]}\n"
        message += f"📅 {req[6][:16]}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard(get_user_role(update.effective_user.id)))

async def handle_delivery_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    targa = update.message.text.upper()
    context.user_data['state'] = None
    
    requests = get_requests(search_term=targa)
    completed_requests = [r for r in requests if r[5] in ['completato', 'riconsegnato']]
    
    if not completed_requests:
        await update.message.reply_text(f"❌ *Nessun veicolo trovato*\n\n🚗 Targa: `{targa}`", 
                                      parse_mode='Markdown', reply_markup=get_main_keyboard(get_user_role(update.effective_user.id)))
        return
    
    req = completed_requests[0]
    await notify_valet_for_delivery(context, req)
    
    await update.message.reply_text(f"✅ *Richiesta riconsegna inviata!*\n\n🚗 {req[1]}\n👤 {req[2]}\n🏨 {req[3]}\n👨‍🔧 {req[8]}", 
                                  parse_mode='Markdown', reply_markup=get_main_keyboard(get_user_role(update.effective_user.id)))

async def show_all_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    requests = get_requests()
    
    if not requests:
        await update.message.reply_text("📋 *Nessuna richiesta presente*", parse_mode='Markdown')
        return
    
    message = "📋 *Tutte le Richieste*\n\n"
    for req in requests:
        status_emoji = {'nuovo': '🆕', 'assegnato': '👤', 'in_corso': '⚙️', 'partito': '🚗', 'completato': '✅', 'riconsegnato': '🏁', 'annullato': '❌'}
        message += f"{status_emoji.get(req[5], '📋')} *#{req[0]}* - {req[1]}\n👤 {req[2]} | 🏨 {req[3]}\n🔧 {req[4]} | 📊 {req[5].upper()}\n"
        if req[8]: message += f"👨‍🔧 {req[8]}\n"
        if req[9]: message += f"⏰ {req[9]}\n"
        if req[10]: message += f"🚚 {req[10]}\n"
        message += f"📅 {req[6][:16]}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def show_valet_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    requests = get_requests(assigned_to=user_id)
    active_requests = [r for r in requests if r[5] not in ['riconsegnato', 'annullato']]
    
    if not active_requests:
        await update.message.reply_text("📋 *Nessuna richiesta assegnata*", parse_mode='Markdown')
        return
    
    message = "📋 *Le Tue Richieste*\n\n"
    keyboard = []
    
    for req in active_requests:
        status_emoji = {'assegnato': '👤', 'in_corso': '⚙️', 'partito': '🚗', 'completato': '✅'}
        message += f"{status_emoji.get(req[5], '📋')} *#{req[0]}* - {req[1]}\n👤 {req[2]} | 🏨 {req[3]}\n🔧 {req[4]} | 📊 {req[5].upper()}\n"
        if req[9]: message += f"⏰ {req[9]}\n"
        if req[10]: message += f"🚚 {req[10]}\n"
        message += f"📅 {req[6][:16]}\n\n"
        
        keyboard.append([InlineKeyboardButton(f"⚙️ Gestisci #{req[0]}", callback_data=f"manage_{req[0]}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)

async def show_new_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    requests = get_requests(stato='nuovo')
    
    if not requests:
        await update.message.reply_text("🆕 *Nessuna nuova richiesta*", parse_mode='Markdown')
        return
    
    message = "🆕 *Nuove Richieste*\n\n"
    keyboard = []
    
    for req in requests:
        message += f"🆔 *#{req[0]}* - {req[1]}\n👤 {req[2]} | 🏨 {req[3]}\n🔧 {req[4]}\n📅 {req[6][:16]}\n\n"
        keyboard.append([InlineKeyboardButton(f"🚗 Prendi #{req[0]}", callback_data=f"assign_{req[0]}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)

async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM requests WHERE stato = "nuovo"')
    nuove = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM requests WHERE stato IN ("assegnato", "in_corso", "partito")')
    in_corso = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM requests WHERE stato = "completato"')
    completate = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM requests WHERE DATE(created_at) = DATE("now")')
    oggi = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM requests')
    totali = cursor.fetchone()[0]
    
    conn.close()
    
    message = f"📊 *Dashboard {BOT_NAME} v{BOT_VERSION}*\n\n🆕 Nuove: *{nuove}*\n⚙️ In corso: *{in_corso}*\n✅ Completate: *{completate}*\n📅 Oggi: *{oggi}*\n📈 Totali: *{totali}*\n\n🕐 {datetime.now().strftime('%H:%M')}"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    if data.startswith('servizio_'):
        servizio = data.replace('servizio_', '').replace('_', ' ').title()
        request_data = context.user_data.get('request_data', {})
        request_data['servizio'] = servizio
        
        request_id = create_request(request_data['targa'], request_data['cliente'], 
                                  request_data['camera'], request_data['servizio'], user_id)
        
        context.user_data['state'] = None
        context.user_data['request_data'] = {}
        
        await query.edit_message_text(
            f"✅ *Richiesta #{request_id} creata!*\n\n🚗 {request_data['targa']}\n👤 {request_data['cliente']}\n🏨 {request_data['camera']}\n🔧 {servizio}",
            parse_mode='Markdown')
        
        await notify_valets(context, request_id, request_data)
    
    elif data.startswith('assign_'):
        request_id = int(data.split('_')[1])
        
        keyboard = [
            [InlineKeyboardButton("⏱️ 5 min ca.", callback_data=f"pickup_{request_id}_5")],
            [InlineKeyboardButton("⏱️ 10 min ca.", callback_data=f"pickup_{request_id}_10")],
            [InlineKeyboardButton("⏱️ 20 min ca.", callback_data=f"pickup_{request_id}_20")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(f"⏰ *Tempo ritiro?*\n\nRichiesta #{request_id}", 
                                    reply_markup=reply_markup, parse_mode='Markdown')
    
    elif data.startswith('pickup_'):
        parts = data.split('_')
        request_id = int(parts[1])
        minutes = parts[2]
        
        tempo_text = f"{minutes} min ca."
        update_request_status(request_id, 'assegnato', user_id, tempo_ritiro=tempo_text)
        
        req = get_request_by_id(request_id)
        
        await query.edit_message_text(f"✅ *Richiesta #{request_id} presa in carico!*\n\n⏰ {tempo_text}\n🚗 {req[1]} - {req[2]}", parse_mode='Markdown')
        await notify_reception_assignment(context, request_id, req, tempo_text)
    
    elif data.startswith('manage_'):
        request_id = int(data.split('_')[1])
        req = get_request_by_id(request_id)
        
        if not req:
            await query.edit_message_text("❌ Richiesta non trovata.")
            return
        
        keyboard = []
        
        if req[5] == 'assegnato':
            keyboard.extend([
                [InlineKeyboardButton("🚗 Inizia Servizio", callback_data=f"status_{request_id}_in_corso")],
                [InlineKeyboardButton("🏃‍♂️ Sono Partito", callback_data=f"status_{request_id}_partito")]
            ])
        elif req[5] == 'in_corso':
            keyboard.append([InlineKeyboardButton("✅ Completato", callback_data=f"status_{request_id}_completato")])
        elif req[5] == 'completato':
            keyboard.append([InlineKeyboardButton("🚚 Riconsegna", callback_data=f"request_delivery_{request_id}")])
        
        keyboard.append([InlineKeyboardButton("❌ Annulla", callback_data=f"status_{request_id}_annullato")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        status_emoji = {'assegnato': '👤', 'in_corso': '⚙️', 'partito': '🚗', 'completato': '✅'}
        
        message = f"{status_emoji.get(req[5], '📋')} *Richiesta #{request_id}*\n\n🚗 {req[1]}\n👤 {req[2]}\n🏨 {req[3]}\n🔧 {req[4]}\n📊 {req[5].upper()}"
        if req[9]: message += f"\n⏰ {req[9]}"
        if req[10]: message += f"\n🚚 {req[10]}"
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    elif data.startswith('status_'):
        parts = data.split('_')
        request_id = int(parts[1])
        new_status = parts[2]
        
        update_request_status(request_id, new_status)
        
        status_names = {
            'in_corso': 'In Corso ⚙️',
            'partito': 'Partito 🚗',
            'completato': 'Completato ✅',
            'annullato': 'Annullato ❌'
        }
        
        await query.edit_message_text(f"✅ *Stato aggiornato!*\n\nRichiesta #{request_id}: {status_names[new_status]}\n⏰ {datetime.now().strftime('%H:%M')}")
        
        if new_status == 'partito':
            req = get_request_by_id(request_id)
            await notify_reception_departure(context, request_id, req)
        elif new_status == 'completato':
            await notify_reception_completion(context, request_id)
    
    elif data.startswith('request_delivery_'):
        request_id = int(data.split('_')[2])
        
        keyboard = [
            [InlineKeyboardButton("🚚 10 min", callback_data=f"delivery_{request_id}_10")],
            [InlineKeyboardButton("🚚 20 min", callback_data=f"delivery_{request_id}_20")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text("🚚 *Tempo riconsegna?*", reply_markup=reply_markup, parse_mode='Markdown')
    
    elif data.startswith('delivery_'):
        parts = data.split('_')
        request_id = int(parts[1])
        minutes = parts[2]
        
        tempo_text = f"{minutes} min ca."
        update_request_status(request_id, 'in_riconsegna', tempo_riconsegna=tempo_text)
        
        req = get_request_by_id(request_id)
        
        await query.edit_message_text(f"✅ *Riconsegna programmata!*\n\n🚚 {tempo_text}\n🚗 {req[1]} - {req[2]}", parse_mode='Markdown')
        await notify_reception_delivery_time(context, request_id, req, tempo_text)
    
    elif data.startswith('confirm_delivery_'):
        request_id = int(data.split('_')[2])
        
        update_request_status(request_id, 'riconsegnato')
        
        await query.edit_message_text(f"✅ *Riconsegna confermata!*\n\nRichiesta #{request_id} completata!\n⏰ {datetime.now().strftime('%H:%M')}")

async def notify_valets(context, request_id, request_data):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id FROM users WHERE role = "valet" AND active = 1')
    valets = cursor.fetchall()
    conn.close()
    
    message = f"🆕 *Nuova Richiesta #{request_id}*\n\n🚗 {request_data['targa']}\n👤 {request_data['cliente']}\n🏨 {request_data['camera']}\n🔧 {request_data['servizio']}\n\nUsa '🆕 Richieste Nuove'"
    
    for valet_id, in valets:
        try:
            await context.bot.send_message(chat_id=valet_id, text=message, parse_mode='Markdown')
        except Exception as e:
            logging.error(f"Errore notifica valet {valet_id}: {e}")

async def notify_reception_assignment(context, request_id, req, tempo_text):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id FROM users WHERE role = "reception" AND active = 1')
    reception_users = cursor.fetchall()
    conn.close()
    
    message = f"👤 *Richiesta #{request_id} Assegnata*\n\n🚗 {req[1]}\n👤 {req[2]}\n🏨 {req[3]}\n👨‍🔧 {req[14]}\n⏰ {tempo_text}"
    
    for reception_id, in reception_users:
        try:
            await context.bot.send_message(chat_id=reception_id, text=message, parse_mode='Markdown')
        except Exception as e:
            logging.error(f"Errore notifica reception {reception_id}: {e}")

async def notify_reception_departure(context, request_id, req):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id FROM users WHERE role = "reception" AND active = 1')
    reception_users = cursor.fetchall()
    conn.close()
    
    message = f"🚗 *Valet in Arrivo #{request_id}*\n\n🚗 {req[1]}\n👤 {req[2]}\n🏨 {req[3]}\n👨‍🔧 {req[14]}\n⏰ {datetime.now().strftime('%H:%M')}"
    
    for reception_id, in reception_users:
        try:
            await context.bot.send_message(chat_id=reception_id, text=message, parse_mode='Markdown')
        except Exception as e:
            logging.error(f"Errore notifica reception {reception_id}: {e}")

async def notify_reception_completion(context, request_id):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''SELECT r.targa, r.cliente, r.camera, r.servizio, u.name
                      FROM requests r LEFT JOIN users u ON r.assigned_to = u.telegram_id WHERE r.id = ?''', (request_id,))
    req = cursor.fetchone()
    
    cursor.execute('SELECT telegram_id FROM users WHERE role = "reception" AND active = 1')
    reception_users = cursor.fetchall()
    conn.close()
    
    if not req:
        return
    
    message = f"✅ *Servizio Completato #{request_id}*\n\n🚗 {req[0]}\n👤 {req[1]}\n🏨 {req[2]}\n🔧 {req[3]}\n👨‍🔧 {req[4]}\n⏰ {datetime.now().strftime('%H:%M')}\n\nUsa '🚚 Richiedi Riconsegna'"
    
    for reception_id, in reception_users:
        try:
            await context.bot.send_message(chat_id=reception_id, text=message, parse_mode='Markdown')
        except Exception as e:
            logging.error(f"Errore notifica reception {reception_id}: {e}")

async def notify_valet_for_delivery(context, req):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT assigned_to FROM requests WHERE id = ?', (req[0],))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return
    
    valet_id = result[0]
    
    keyboard = [
        [InlineKeyboardButton("✅ Visualizzato", callback_data=f"delivery_ack_{req[0]}")],
        [InlineKeyboardButton("🚚 10 min", callback_data=f"delivery_{req[0]}_10")],
        [InlineKeyboardButton("🚚 20 min", callback_data=f"delivery_{req[0]}_20")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"🚚 *Richiesta Riconsegna #{req[0]}*\n\n🚗 {req[1]}\n👤 {req[2]}\n🏨 {req[3]}\n\nLa reception richiede la riconsegna!"
    
    try:
        await context.bot.send_message(chat_id=valet_id, text=message, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Errore notifica valet {valet_id}: {e}")

async def notify_reception_delivery_time(context, request_id, req, tempo_text):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id FROM users WHERE role = "reception" AND active = 1')
    reception_users = cursor.fetchall()
    conn.close()
    
    keyboard = [[InlineKeyboardButton("✅ Riconsegnato", callback_data=f"confirm_delivery_{request_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"🚚 *Riconsegna Programmata #{request_id}*\n\n🚗 {req[1]}\n👤 {req[2]}\n🏨 {req[3]}\n👨‍🔧 {req[14]}\n⏰ {tempo_text}\n\nConferma quando avvenuta!"
    
    for reception_id, in reception_users:
        try:
            await context.bot.send_message(chat_id=reception_id, text=message, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e:
            logging.error(f"Errore notifica reception {reception_id}: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    role = get_user_role(user_id)
    
    if not role:
        return
    
    caption = update.message.caption
    if caption and caption.startswith('#'):
        try:
            request_id = int(caption[1:].split()[0])
            file_id = update.message.photo[-1].file_id
            tipo = 'prima' if 'prima' in caption.lower() else 'dopo'
            
            add_photo(request_id, file_id, tipo, user_id)
            
            await update.message.reply_text(f"📷 *Foto aggiunta!*\n\nFoto {tipo} per richiesta #{request_id}\n⏰ {datetime.now().strftime('%H:%M')}", parse_mode='Markdown')
            
        except (ValueError, IndexError):
            await update.message.reply_text("❌ *Formato non valido*\n\nUsa: `#123 prima` o `#123 dopo`", parse_mode='Markdown')
    else:
        await update.message.reply_text("📷 *Come caricare foto*\n\nDidascalia: `#ID_RICHIESTA prima/dopo`\nEsempio: `#123 prima`", parse_mode='Markdown')

def main():
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not TOKEN:
        print("❌ ERRORE: TELEGRAM_BOT_TOKEN non impostato!")
        return
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("annulla", cancel_command))
    application.add_handler(CommandHandler("register", register_user))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    print(f"🤖 {BOT_NAME} v{BOT_VERSION} avviato!")
    print("📋 Funzionalità v2.0.0:")
    print("   ✅ /help e /annulla")
    print("   ✅ Gestione tempi ritiro/riconsegna")
    print("   ✅ Notifiche automatiche")
    print("   ✅ Menu pulsanti sempre visibili")
    print("   ✅ Versioning del bot")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
