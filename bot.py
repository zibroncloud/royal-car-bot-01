#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CarValetBOT v3.0 - Sistema Gestione Auto Hotel
By Claude AI & Zibroncloud
Data: 12 Luglio 2025
"""

import os
import logging
import sqlite3
from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

BOT_VERSION = "3.0"
BOT_NAME = "CarValetBOT"

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

def init_db():
    conn = sqlite3.connect('carvalet.db')
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS auto (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        targa TEXT NOT NULL,
        cognome TEXT NOT NULL,
        stanza INTEGER NOT NULL,
        tipo_auto TEXT,
        numero_chiave INTEGER,
        note TEXT,
        stato TEXT DEFAULT 'richiesta',
        data_arrivo DATE DEFAULT CURRENT_DATE,
        data_park DATE,
        data_uscita DATE,
        giorni_parcheggio INTEGER DEFAULT 0,
        foto_count INTEGER DEFAULT 0
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS foto (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auto_id INTEGER,
        file_id TEXT NOT NULL,
        data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (auto_id) REFERENCES auto (id)
    )''')
    
    conn.commit()
    conn.close()

init_db()

def get_auto_by_id(auto_id):
    conn = sqlite3.connect('carvalet.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM auto WHERE id = ?', (auto_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def update_auto_stato(auto_id, nuovo_stato, giorni=None):
    conn = sqlite3.connect('carvalet.db')
    cursor = conn.cursor()
    
    if nuovo_stato == 'parcheggiata':
        cursor.execute('UPDATE auto SET stato = ?, data_park = CURRENT_DATE WHERE id = ?', 
                      (nuovo_stato, auto_id))
    elif nuovo_stato == 'uscita':
        if giorni:
            cursor.execute('UPDATE auto SET stato = ?, data_uscita = CURRENT_DATE, giorni_parcheggio = ? WHERE id = ?', 
                          (nuovo_stato, giorni, auto_id))
        else:
            cursor.execute('UPDATE auto SET stato = ?, data_uscita = CURRENT_DATE WHERE id = ?', 
                          (nuovo_stato, auto_id))
    else:
        cursor.execute('UPDATE auto SET stato = ? WHERE id = ?', (nuovo_stato, auto_id))
    
    conn.commit()
    conn.close()

def calcola_giorni_parcheggio(data_park):
    if not data_park:
        return 0
    oggi = date.today()
    if isinstance(data_park, str):
        data_park = datetime.strptime(data_park, '%Y-%m-%d').date()
    giorni = (oggi - data_park).days + 1
    return max(1, giorni)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = f"""🚗 *{BOT_NAME} v{BOT_VERSION}*
*By Claude AI & Zibroncloud*

🏨 *COMANDI HOTEL:*
• `/ritiro` - Richiesta ritiro auto
• `/riconsegna` - Lista auto per riconsegna  
• `/partenza` - Riconsegna finale (uscita)

🚗 *COMANDI VALET:*
• `/incorso` - Ritiro in corso
• `/foto` - Carica foto auto
• `/park` - Conferma auto parcheggiata
• `/exit` - Auto in riconsegna
• `/modifica` - Modifica dati auto

📊 *COMANDI STATISTICHE:*
• `/conta_auto` - Conteggio giornaliero
• `/lista_auto` - Auto in parcheggio

💡 *TIPI AUTO:* Compatta, SUV, Elettrica, VAN, Gancio traino, LUXURY
🔑 *NUMERI:* Stanze e chiavi da 0 a 999"""

    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def ritiro_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = 'ritiro_targa'
    await update.message.reply_text("🚗 *RITIRO AUTO*\n\nInserisci la *TARGA* del veicolo:", parse_mode='Markdown')

async def riconsegna_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('carvalet.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, targa, cognome, stanza, numero_chiave FROM auto WHERE stato = "parcheggiata" ORDER BY stanza')
    auto_list = cursor.fetchall()
    conn.close()
    
    if not auto_list:
        await update.message.reply_text("📋 *Nessuna auto in parcheggio*", parse_mode='Markdown')
        return
    
    keyboard = []
    for auto in auto_list:
        chiave_text = f" - Chiave: {auto[4]}" if auto[4] else ""
        keyboard.append([InlineKeyboardButton(
            f"Stanza {auto[3]} - {auto[1]} ({auto[2]}){chiave_text}", 
            callback_data=f"riconsegna_{auto[0]}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🚚 *RICONSEGNA AUTO*\n\nSeleziona l'auto:", 
                                   reply_markup=reply_markup, parse_mode='Markdown')

async def partenza_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('carvalet.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, targa, cognome, stanza, numero_chiave FROM auto WHERE stato = "riconsegna" ORDER BY stanza')
    auto_list = cursor.fetchall()
    conn.close()
    
    if not auto_list:
        await update.message.reply_text("📋 *Nessuna auto in riconsegna*", parse_mode='Markdown')
        return
    
    keyboard = []
    for auto in auto_list:
        chiave_text = f" - Chiave: {auto[4]}" if auto[4] else ""
        keyboard.append([InlineKeyboardButton(
            f"Stanza {auto[3]} - {auto[1]} ({auto[2]}){chiave_text}", 
            callback_data=f"partenza_{auto[0]}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🏁 *PARTENZA DEFINITIVA*\n\nSeleziona l'auto:", 
                                   reply_markup=reply_markup, parse_mode='Markdown')

async def incorso_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('carvalet.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, targa, cognome, stanza, numero_chiave FROM auto WHERE stato = "richiesta" ORDER BY stanza')
    auto_list = cursor.fetchall()
    conn.close()
    
    if not auto_list:
        await update.message.reply_text("📋 *Nessuna richiesta di ritiro*", parse_mode='Markdown')
        return
    
    keyboard = []
    for auto in auto_list:
        chiave_text = f" - Chiave: {auto[4]}" if auto[4] else ""
        keyboard.append([InlineKeyboardButton(
            f"Stanza {auto[3]} - {auto[1]} ({auto[2]}){chiave_text}", 
            callback_data=f"incorso_{auto[0]}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⚙️ *RITIRO IN CORSO*\n\nSeleziona l'auto da ritirare:", 
                                   reply_markup=reply_markup, parse_mode='Markdown')

async def foto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('carvalet.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, targa, cognome, stanza FROM auto WHERE stato IN ("ritiro", "parcheggiata") ORDER BY stanza')
    auto_list = cursor.fetchall()
    conn.close()
    
    if not auto_list:
        await update.message.reply_text("📋 *Nessuna auto disponibile per foto*", parse_mode='Markdown')
        return
    
    keyboard = []
    for auto in auto_list:
        keyboard.append([InlineKeyboardButton(
            f"Stanza {auto[3]} - {auto[1]} ({auto[2]})", 
            callback_data=f"foto_{auto[0]}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📷 *CARICA FOTO*\n\nSeleziona l'auto:", 
                                   reply_markup=reply_markup, parse_mode='Markdown')

async def park_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('carvalet.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, targa, cognome, stanza FROM auto WHERE stato = "ritiro" ORDER BY stanza')
    auto_list = cursor.fetchall()
    conn.close()
    
    if not auto_list:
        await update.message.reply_text("📋 *Nessuna auto in ritiro*", parse_mode='Markdown')
        return
    
    keyboard = []
    for auto in auto_list:
        keyboard.append([InlineKeyboardButton(
            f"Stanza {auto[3]} - {auto[1]} ({auto[2]})", 
            callback_data=f"park_{auto[0]}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🅿️ *CONFERMA PARCHEGGIO*\n\nSeleziona l'auto parcheggiata:", 
                                   reply_markup=reply_markup, parse_mode='Markdown')

async def exit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('carvalet.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, targa, cognome, stanza FROM auto WHERE stato = "parcheggiata" ORDER BY stanza')
    auto_list = cursor.fetchall()
    conn.close()
    
    if not auto_list:
        await update.message.reply_text("📋 *Nessuna auto in parcheggio*", parse_mode='Markdown')
        return
    
    keyboard = []
    for auto in auto_list:
        keyboard.append([InlineKeyboardButton(
            f"Stanza {auto[3]} - {auto[1]} ({auto[2]})", 
            callback_data=f"exit_{auto[0]}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🚪 *AUTO IN RICONSEGNA*\n\nSeleziona l'auto:", 
                                   reply_markup=reply_markup, parse_mode='Markdown')

async def modifica_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('carvalet.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, targa, cognome, stanza FROM auto WHERE stato != "uscita" ORDER BY stanza')
    auto_list = cursor.fetchall()
    conn.close()
    
    if not auto_list:
        await update.message.reply_text("📋 *Nessuna auto da modificare*", parse_mode='Markdown')
        return
    
    keyboard = []
    for auto in auto_list:
        keyboard.append([InlineKeyboardButton(
            f"Stanza {auto[3]} - {auto[1]} ({auto[2]})", 
            callback_data=f"modifica_{auto[0]}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("✏️ *MODIFICA AUTO*\n\nSeleziona l'auto da modificare:", 
                                   reply_markup=reply_markup, parse_mode='Markdown')

async def conta_auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('carvalet.db')
    cursor = conn.cursor()
    
    oggi = date.today().strftime('%Y-%m-%d')
    
    cursor.execute('SELECT COUNT(*) FROM auto WHERE data_uscita = ?', (oggi,))
    uscite_oggi = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM auto WHERE data_arrivo = ?', (oggi,))
    entrate_oggi = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM auto WHERE stato = "parcheggiata"')
    in_parcheggio = cursor.fetchone()[0]
    
    conn.close()
    
    oggi_formattato = datetime.now().strftime('%d %B %Y')
    
    messaggio = f"""📊 *STATISTICHE {oggi_formattato}*

🚗 Auto uscite oggi: *{uscite_oggi}*
🚗 Auto entrate oggi: *{entrate_oggi}*  
🅿️ Auto in parcheggio: *{in_parcheggio}*"""

    await update.message.reply_text(messaggio, parse_mode='Markdown')

async def lista_auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('carvalet.db')
    cursor = conn.cursor()
    cursor.execute('SELECT stanza, cognome, targa, numero_chiave, data_park FROM auto WHERE stato = "parcheggiata" ORDER BY stanza')
    auto_list = cursor.fetchall()
    conn.close()
    
    if not auto_list:
        await update.message.reply_text("🅿️ *Nessuna auto in parcheggio*", parse_mode='Markdown')
        return
    
    messaggio = "🅿️ *AUTO IN PARCHEGGIO:*\n\n"
    
    for auto in auto_list:
        stanza, cognome, targa, chiave, data_park = auto
        giorni = calcola_giorni_parcheggio(data_park) if data_park else 0
        
        chiave_text = f"Chiave: {chiave}" if chiave else "Chiave: --"
        sconto_text = " ✨ SCONTO" if giorni >= 10 else ""
        
        messaggio += f"{stanza} | {cognome} | {targa} | {chiave_text}{sconto_text}\n"
        if giorni >= 10:
            messaggio += f"     ({giorni} giorni)\n"
    
    await update.message.reply_text(messaggio, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    text = update.message.text
    
    if state == 'ritiro_targa':
        context.user_data['targa'] = text.upper()
        context.user_data['state'] = 'ritiro_cognome'
        await update.message.reply_text("👤 Inserisci il *COGNOME* del cliente:", parse_mode='Markdown')
    
    elif state == 'ritiro_cognome':
        context.user_data['cognome'] = text
        context.user_data['state'] = 'ritiro_stanza'
        await update.message.reply_text("🏨 Inserisci il numero *STANZA* (0-999):", parse_mode='Markdown')
    
    elif state == 'ritiro_stanza':
        try:
            stanza = int(text)
            if 0 <= stanza <= 999:
                context.user_data['stanza'] = stanza
                
                keyboard = [
                    [InlineKeyboardButton("🚗 Compatta", callback_data="tipo_compatta")],
                    [InlineKeyboardButton("🚙 SUV", callback_data="tipo_suv")],
                    [InlineKeyboardButton("🔋 Elettrica", callback_data="tipo_elettrica")],
                    [InlineKeyboardButton("🚐 VAN (fino 9 posti)", callback_data="tipo_van")],
                    [InlineKeyboardButton("🚚 Gancio traino/carrello", callback_data="tipo_gancio")],
                    [InlineKeyboardButton("💎 LUXURY", callback_data="tipo_luxury")],
                    [InlineKeyboardButton("⏭️ Salta", callback_data="tipo_skip")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text("🚗 *TIPO AUTO* (opzionale):", 
                                               reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Numero stanza non valido! Inserisci un numero da 0 a 999:")
        except ValueError:
            await update.message.reply_text("❌ Inserisci un numero valido per la stanza:")
    
    elif state == 'ritiro_chiave':
        try:
            chiave = int(text)
            if 0 <= chiave <= 999:
                context.user_data['numero_chiave'] = chiave
                context.user_data['state'] = 'ritiro_note'
                await update.message.reply_text("📝 Inserisci eventuali *NOTE* (o scrivi 'skip' per saltare):", parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Numero chiave non valido! Inserisci un numero da 0 a 999:")
        except ValueError:
            await update.message.reply_text("❌ Inserisci un numero valido per la chiave:")
    
    elif state == 'ritiro_note':
        note = text if text.lower() != 'skip' else None
        
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO auto (targa, cognome, stanza, tipo_auto, numero_chiave, note) 
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (context.user_data['targa'], context.user_data['cognome'], context.user_data['stanza'],
                       context.user_data.get('tipo_auto'), context.user_data.get('numero_chiave'), note))
        auto_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        context.user_data.clear()
        
        await update.message.reply_text(f"✅ *RICHIESTA CREATA!*\n\n🆔 ID: {auto_id}\n🚗 {context.user_data.get('targa', 'N/A')}\n👤 {context.user_data.get('cognome', 'N/A')}\n🏨 Stanza: {context.user_data.get('stanza', 'N/A')}", parse_mode='Markdown')
    
    elif state == 'upload_foto':
        await update.message.reply_text("📷 Invia le foto dell'auto (una o più foto). Scrivi 'fine' quando hai finito.")
    
    else:
        await update.message.reply_text("❓ Comando non riconosciuto. Usa /start per vedere tutti i comandi.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') == 'upload_foto':
        auto_id = context.user_data.get('foto_auto_id')
        if auto_id:
            file_id = update.message.photo[-1].file_id
            
            conn = sqlite3.connect('carvalet.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO foto (auto_id, file_id) VALUES (?, ?)', (auto_id, file_id))
            cursor.execute('UPDATE auto SET foto_count = foto_count + 1 WHERE id = ?', (auto_id,))
            conn.commit()
            conn.close()
            
            await update.message.reply_text("📷 Foto salvata! Invia altre foto o scrivi 'fine' per terminare.")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith('tipo_'):
        tipo = data.replace('tipo_', '')
        if tipo == 'skip':
            context.user_data['tipo_auto'] = None
        else:
            tipo_map = {
                'compatta': 'Compatta',
                'suv': 'SUV', 
                'elettrica': 'Elettrica',
                'van': 'VAN',
                'gancio': 'Gancio traino',
                'luxury': 'LUXURY'
            }
            context.user_data['tipo_auto'] = tipo_map.get(tipo)
        
        context.user_data['state'] = 'ritiro_chiave'
        await query.edit_message_text("🔑 Inserisci il *NUMERO CHIAVE* (0-999) o scrivi 'skip' per saltare:", parse_mode='Markdown')
    
    elif data.startswith('incorso_'):
        auto_id = int(data.split('_')[1])
        
        keyboard = [
            [InlineKeyboardButton("⏱️ 15 min ca.", callback_data=f"tempo_{auto_id}_15")],
            [InlineKeyboardButton("⏱️ 30 min ca.", callback_data=f"tempo_{auto_id}_30")],
            [InlineKeyboardButton("⏱️ 45 min ca.", callback_data=f"tempo_{auto_id}_45")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text("⏰ *TEMPO STIMATO RITIRO:*", reply_markup=reply_markup, parse_mode='Markdown')
    
    elif data.startswith('tempo_'):
        parts = data.split('_')
        auto_id = int(parts[1])
        minuti = parts[2]
        
        update_auto_stato(auto_id, 'ritiro')
        
        auto = get_auto_by_id(auto_id)
        await query.edit_message_text(f"✅ *RITIRO AVVIATO!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n⏰ Tempo stimato: {minuti} minuti", parse_mode='Markdown')
    
    elif data.startswith('park_'):
        auto_id = int(data.split('_')[1])
        update_auto_stato(auto_id, 'parcheggiata')
        
        auto = get_auto_by_id(auto_id)
        await query.edit_message_text(f"🅿️ *AUTO PARCHEGGIATA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n📅 Inizio conteggio giorni", parse_mode='Markdown')
    
    elif data.startswith('exit_'):
        auto_id = int(data.split('_')[1])
        update_auto_stato(auto_id, 'riconsegna')
        
        auto = get_auto_by_id(auto_id)
        await query.edit_message_text(f"🚪 *AUTO IN RICONSEGNA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}", parse_mode='Markdown')
    
    elif data.startswith('riconsegna_'):
        auto_id = int(data.split('_')[1])
        auto = get_auto_by_id(auto_id)
        
        if auto[9]:  # data_park
            giorni = calcola_giorni_parcheggio(auto[9])
            update_auto_stato(auto_id, 'riconsegna', giorni)
            
            sconto_text = " ✨ CON SCONTO" if giorni >= 10 else ""
            await query.edit_message_text(f"🚚 *RICONSEGNA RICHIESTA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n📅 Parcheggiata {giorni} giorni{sconto_text}", parse_mode='Markdown')
    
    elif data.startswith('partenza_'):
        auto_id = int(data.split('_')[1])
        auto = get_auto_by_id(auto_id)
        
        if auto[9]:  # data_park
            giorni = calcola_giorni_parcheggio(auto[9])
            update_auto_stato(auto_id, 'uscita', giorni)
        else:
            update_auto_stato(auto_id, 'uscita')
        
        await query.edit_message_text(f"🏁 *PARTENZA CONFERMATA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n✅ Auto uscita definitivamente", parse_mode='Markdown')
    
    elif data.startswith('foto_'):
        auto_id = int(data.split('_')[1])
        context.user_data['state'] = 'upload_foto'
        context.user_data['foto_auto_id'] = auto_id
        
        auto = get_auto_by_id(auto_id)
        await query.edit_message_text(f"📷 *CARICA FOTO*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n\nInvia le foto dell'auto (una o più). Scrivi 'fine' quando terminato.", parse_mode='Markdown')

def main():
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ritiro", ritiro_command))
    application.add_handler(CommandHandler("riconsegna", riconsegna_command))
    application.add_handler(CommandHandler("partenza", partenza_command))
    application.add_handler(CommandHandler("incorso", incorso_command))
    application.add_handler(CommandHandler("foto", foto_command))
    application.add_handler(CommandHandler("park", park_command))
    application.add_handler(CommandHandler("exit", exit_command))
    application.add_handler(CommandHandler("modifica", modifica_command))
    application.add_handler(CommandHandler("conta_auto", conta_auto_command))
    application.add_handler(CommandHandler("lista_auto", lista_auto_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    print(f"🚗 {BOT_NAME} v{BOT_VERSION} avviato!")
    print("✅ Sistema gestione auto hotel attivo")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
