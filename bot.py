import os
import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import asyncio

# Configurazione logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Database setup
def init_db():
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    
    # Tabella utenti
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            active INTEGER DEFAULT 1
        )
    ''')
    
    # Tabella richieste
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            targa TEXT NOT NULL,
            cliente TEXT NOT NULL,
            camera TEXT NOT NULL,
            servizio TEXT NOT NULL,
            stato TEXT DEFAULT 'nuovo',
            tempo_ritiro TEXT,
            tempo_riconsegna TEXT,
            partenza_confermata TIMESTAMP,
            arrivo_confermato TIMESTAMP,
            created_by INTEGER,
            assigned_to INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            note TEXT
        )
    ''')
    
    # Tabella foto
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            file_id TEXT NOT NULL,
            tipo TEXT NOT NULL,
            uploaded_by INTEGER,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (request_id) REFERENCES requests (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Inizializza database
init_db()

# Stati possibili
STATI = ['nuovo', 'assegnato', 'in_corso', 'partito', 'completato', 'in_riconsegna', 'riconsegnato', 'annullato']

# Funzioni database
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
    cursor.execute('''
        INSERT OR REPLACE INTO users (telegram_id, name, role, active) 
        VALUES (?, ?, ?, 1)
    ''', (telegram_id, name, role))
    conn.commit()
    conn.close()

def create_request(targa, cliente, camera, servizio, created_by):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO requests (targa, cliente, camera, servizio, created_by)
        VALUES (?, ?, ?, ?, ?)
    ''', (targa.upper(), cliente, camera, servizio, created_by))
    request_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return request_id

def get_requests(stato=None, search_term=None, assigned_to=None):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    
    query = '''
        SELECT r.id, r.targa, r.cliente, r.camera, r.servizio, r.stato, 
               r.created_at, u1.name as created_by_name, u2.name as assigned_to_name,
               r.tempo_ritiro, r.tempo_riconsegna, r.partenza_confermata, r.arrivo_confermato
        FROM requests r
        LEFT JOIN users u1 ON r.created_by = u1.telegram_id
        LEFT JOIN users u2 ON r.assigned_to = u2.telegram_id
        WHERE 1=1
    '''
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
    
    if new_status == 'partito':
        updates.append('partenza_confermata = CURRENT_TIMESTAMP')
    elif new_status == 'riconsegnato':
        updates.append('arrivo_confermato = CURRENT_TIMESTAMP')
        updates.append('completed_at = CURRENT_TIMESTAMP')
    
    params.append(request_id)
    
    query = f"UPDATE requests SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def add_photo(request_id, file_id, tipo, uploaded_by):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO photos (request_id, file_id, tipo, uploaded_by)
        VALUES (?, ?, ?, ?)
    ''', (request_id, file_id, tipo, uploaded_by))
    conn.commit()
    conn.close()

def get_request_by_id(request_id):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.*, u1.name as created_by_name, u2.name as assigned_to_name
        FROM requests r
        LEFT JOIN users u1 ON r.created_by = u1.telegram_id
        LEFT JOIN users u2 ON r.assigned_to = u2.telegram_id
        WHERE r.id = ?
    ''', (request_id,))
    result = cursor.fetchone()
    conn.close()
    return result

# Keyboards
def get_main_keyboard(role):
    if role == 'reception':
        keyboard = [
            [KeyboardButton("🆕 Nuova Richiesta")],
            [KeyboardButton("📋 Tutte le Richieste"), KeyboardButton("🔍 Cerca")],
            [KeyboardButton("📊 Dashboard"), KeyboardButton("🚚 Richiedi Riconsegna")],
            [KeyboardButton("❓ Help"), KeyboardButton("❌ Annulla")]
        ]
    else:  # valet
        keyboard = [
            [KeyboardButton("📋 Mie Richieste"), KeyboardButton("🆕 Richieste Nuove")],
            [KeyboardButton("📷 Aggiungi Foto"), KeyboardButton("✅ Aggiorna Stato")],
            [KeyboardButton("❓ Help"), KeyboardButton("❌ Annulla")]
        ]
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    role = get_user_role(user.id)
    
    # Reset stato conversazione
    context.user_data.clear()
    
    if not role:
        await update.message.reply_text(
            "🚗 *Benvenuto in RoyalCarBot01!*\n\n"
            "Per utilizzare questo bot, devi essere registrato.\n\n"
            "📝 *Comandi disponibili:*\n"
            "• `/register <nome> reception` - Registrati come Reception\n"
            "• `/register <nome> valet` - Registrati come Valet\n"
            "• `/help` - Mostra tutti i comandi\n\n"
            "*Esempio:* `/register Mario reception`",
            parse_mode='Markdown'
        )
        return
    
    welcome_msg = f"🚗 *Benvenuto {user.first_name}!*\n\n"
    if role == 'reception':
        welcome_msg += "Sei connesso come *Reception*\n"
        welcome_msg += "Puoi creare nuove richieste e gestire tutto il servizio valet."
    else:
        welcome_msg += "Sei connesso come *Valet*\n"
        welcome_msg += "Puoi vedere le tue richieste e aggiornare lo stato dei servizi."
    
    await update.message.reply_text(
        welcome_msg,
        reply_markup=get_main_keyboard(role),
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = get_user_role(update.effective_user.id)
    
    if not role:
        help_text = """
❓ *HELP - RoyalCarBot01*

📝 *Registrazione:*
• `/register <nome> reception` - Registrati come Reception
• `/register <nome> valet` - Registrati come Valet

*Esempio:* `/register Mario reception`

🔧 *Comandi Generali:*
• `/start` - Avvia il bot e mostra menu
• `/help` - Mostra questo messaggio
• `/annulla` - Annulla operazione in corso

Per accedere alle funzioni complete, devi prima registrarti!
"""
    elif role == 'reception':
        help_text = """
❓ *HELP - RECEPTION*

🎯 *Menu Principale:*
• 🆕 *Nuova Richiesta* - Crea richiesta car valet
• 📋 *Tutte le Richieste* - Visualizza tutte le richieste
• 🔍 *Cerca* - Cerca per targa o cognome
• 📊 *Dashboard* - Statistiche e riepilogo
• 🚚 *Richiedi Riconsegna* - Richiedi riconsegna auto

📝 *Flusso Nuova Richiesta:*
1. Inserisci targa veicolo
2. Inserisci cognome cliente  
3. Inserisci numero camera
4. Scegli tipo servizio

🔧 *Comandi:*
• `/start` - Menu principale
• `/help` - Mostra questo aiuto
• `/annulla` - Annulla operazione
• `/register <nome> <ruolo>` - Registra utente

📋 *Stati Richieste:*
🆕 Nuovo → 👤 Assegnato → ⚙️ In Corso → 🚗 Partito → ✅ Completato
"""
    else:  # valet
        help_text = """
❓ *HELP - VALET*

🎯 *Menu Principale:*
• 📋 *Mie Richieste* - Richieste assegnate a te
• 🆕 *Richieste Nuove* - Nuove richieste disponibili  
• 📷 *Aggiungi Foto* - Carica foto servizio
• ✅ *Aggiorna Stato* - Cambia stato richiesta

⏰ *Gestione Tempi:*
Quando prendi una richiesta, scegli:
• Ritiro in 5 min ca.
• Ritiro in 10 min ca.  
• Ritiro in 20 min ca.

📷 *Caricamento Foto:*
Carica foto con didascalia: `#123 prima` o `#123 dopo`

🔧 *Comandi:*
• `/start` - Menu principale
• `/help` - Mostra questo aiuto
• `/annulla` - Annulla operazione

📋 *Stati che puoi gestire:*
👤 Assegnato → ⚙️ In Corso → 🚗 Partito → ✅ Completato
"""
    
    await update.message.reply_text(
        help_text, 
        parse_mode='Markdown',
        reply_markup=get_main_keyboard(role) if role else None
    )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = get_user_role(update.effective_user.id)
    
    # Reset stato conversazione
    context.user_data.clear()
    
    if role:
        await update.message.reply_text(
            "❌ *Operazione annullata!*\n\nTorna al menu principale.",
            reply_markup=get_main_keyboard(role),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "❌ Operazione annullata.\n\nUsa `/register <nome> <ruolo>` per registrarti."
        )

async def register_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) != 2:
        await update.message.reply_text(
            "❌ *Formato sbagliato!*\n\n"
            "📝 *Uso corretto:*\n"
            "`/register <nome> <ruolo>`\n\n"
            "🎭 *Ruoli disponibili:*\n"
            "• `reception` - Reception hotel\n"
            "• `valet` - Car valet staff\n\n"
            "💡 *Esempi:*\n"
            "• `/register Mario reception`\n"
            "• `/register Luca valet`",
            parse_mode='Markdown'
        )
        return
    
    name = context.args[0]
    role = context.args[1].lower()
    
    if role not in ['reception', 'valet']:
        await update.message.reply_text(
            "❌ *Ruolo non valido!*\n\n"
            "🎭 *Ruoli disponibili:*\n"
            "• `reception`\n" 
            "• `valet`\n\n"
            "💡 *Esempio:* `/register Mario reception`",
            parse_mode='Markdown'
        )
        return
    
    add_user(update.effective_user.id, name, role)
    
    role_name = "Reception" if role == 'reception' else "Valet"
    await update.message.reply_text(
        f"✅ *Registrazione completata!*\n\n"
        f"👤 *Nome:* {name}\n"
        f"🎭 *Ruolo:* {role_name}\n\n"
        f"Ora puoi utilizzare tutte le funzioni del bot!",
        reply_markup=get_main_keyboard(role),
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    role = get_user_role(user.id)
    text = update.message.text
    
    if not role:
        await update.message.reply_text(
            "⚠️ Non sei registrato!\n\n"
            "Usa: `/register <nome> <ruolo>`\n"
            "Oppure `/help` per maggiori informazioni."
        )
        return
    
    # Gestione stati conversazione
    if context.user_data.get('state') == 'creating_request':
        await handle_new_request_data(update, context)
        return
    
    if context.user_data.get('state') == 'searching':
        await handle_search(update, context)
        return
    
    if context.user_data.get('state') == 'requesting_delivery':
        await handle_delivery_request(update, context)
        return
    
    # Menu principale
    if text == "🆕 Nuova Richiesta" and role == 'reception':
        context.user_data['state'] = 'creating_request'
        context.user_data['request_data'] = {}
        await update.message.reply_text(
            "🚗 *Nuova Richiesta Car Valet*\n\n"
            "Inserisci la *targa* del veicolo:\n\n"
            "💡 *Suggerimento:* Usa formato ABC123 o AB123CD",
            parse_mode='Markdown'
        )
    
    elif text == "📋 Tutte le Richieste":
        await show_all_requests(update, context)
    
    elif text == "🔍 Cerca":
        context.user_data['state'] = 'searching'
        await update.message.reply_text(
            "🔍 *Ricerca Richieste*\n\n"
            "Inserisci:\n"
            "• Targa del veicolo\n"
            "• Cognome del cliente\n"
            "• Numero camera",
            parse_mode='Markdown'
        )
    
    elif text == "🚚 Richiedi Riconsegna" and role == 'reception':
        context.user_data['state'] = 'requesting_delivery'
        await update.message.reply_text(
            "🚚 *Richiesta Riconsegna*\n\n"
            "Inserisci la *targa* del veicolo da riconsegnare:",
            parse_mode='Markdown'
        )
    
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
        await update.message.reply_text(
            "❓ *Comando non riconosciuto*\n\n"
            "Usa i pulsanti del menu o `/help` per vedere tutti i comandi disponibili.",
            parse_mode='Markdown'
        )

async def handle_new_request_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    request_data = context.user_data.get('request_data', {})
    
    if 'targa' not in request_data:
        request_data['targa'] = text.upper()
        context.user_data['request_data'] = request_data
        await update.message.reply_text(
            "👤 *Dati Cliente*\n\n"
            "Inserisci il *cognome del cliente*:",
            parse_mode='Markdown'
        )
    
    elif 'cliente' not in request_data:
        request_data['cliente'] = text
        context.user_data['request_data'] = request_data
        await update.message.reply_text(
            "🏨 *Dettagli Soggiorno*\n\n"
            "Inserisci il *numero della camera*:",
            parse_mode='Markdown'
        )
    
    elif 'camera' not in request_data:
        request_data['camera'] = text
        context.user_data['request_data'] = request_data
        
        # Keyboard per tipo servizio
        keyboard = [
            [InlineKeyboardButton("🧽 Lavaggio Esterno", callback_data="servizio_lavaggio_esterno")],
            [InlineKeyboardButton("🧼 Lavaggio Completo", callback_data="servizio_lavaggio_completo")],
            [InlineKeyboardButton("🔧 Servizio Meccanico", callback_data="servizio_meccanico")],
            [InlineKeyboardButton("⛽ Rifornimento", callback_data="servizio_rifornimento")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔧 *Tipo di Servizio*\n\n"
            "Seleziona il servizio richiesto:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_term = update.message.text
    requests = get_requests(search_term=search_term)
    
    context.user_data['state'] = None
    
    if not requests:
        await update.message.reply_text(
            f"❌ *Nessuna richiesta trovata*\n\n"
            f"🔍 Termine cercato: `{search_term}`\n\n"
            f"💡 Prova con:\n"
            f"• Targa completa o parziale\n"
            f"• Cognome cliente\n"
            f"• Numero camera",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard(get_user_role(update.effective_user.id))
        )
        return
    
    message = f"🔍 *Risultati ricerca: {search_term}*\n\n"
    for req in requests:
        status_emoji = {
            'nuovo': '🆕', 'assegnato': '👤', 'in_corso': '⚙️', 
            'partito': '🚗', 'completato': '✅', 'riconsegnato': '🏁', 'annullato': '❌'
        }
        
        message += f"{status_emoji.get(req[5], '📋')} *#{req[0]}* - {req[1]}\n"
        message += f"👤 {req[2]} | 🏨 Camera {req[3]}\n"
        message += f"🔧 {req[4]} | 📊 {req[5].upper()}\n"
        if req[8]:  # assigned_to_name
            message += f"👨‍🔧 Valet: {req[8]}\n"
        if req[9]:  # tempo_ritiro
            message += f"⏰ Ritiro: {req[9]}\n"
        message += f"📅 {req[6][:16]}\n\n"
    
    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=get_main_keyboard(get_user_role(update.effective_user.id))
    )

async def handle_delivery_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    targa = update.message.text.upper()
    context.user_data['state'] = None
    
    # Trova richiesta per targa
    requests = get_requests(search_term=targa)
    completed_requests = [r for r in requests if r[5] in ['completato', 'riconsegnato']]
    
    if not completed_requests:
        await update.message.reply_text(
            f"❌ *Nessun veicolo trovato*\n\n"
            f"🚗 Targa: `{targa}`\n\n"
            f"Verifica che:\n"
            f"• La targa sia corretta\n"
            f"• Il servizio sia completato",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard(get_user_role(update.effective_user.id))
        )
        return
    
    # Prendi la richiesta più recente completata
    req = completed_requests[0]
    
    if not req[8]:  # assigned_to_name
        await update.message.reply_text(
            f"❌ *Errore*\n\n"
            f"Nessun valet assegnato per il veicolo `{targa}`",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard(get_user_role(update.effective_user.id))
        )
        return
    
    # Invia notifica al valet per riconsegna
    await notify_valet_for_delivery(context, req)
    
    await update.message.reply_text(
        f"✅ *Richiesta riconsegna inviata!*\n\n"
        f"🚗 Targa: `{req[1]}`\n"
        f"👤 Cliente: {req[2]}\n"
        f"🏨 Camera: {req[3]}\n"
        f"👨‍🔧 Valet: {req[8]}\n\n"
        f"Il valet riceverà la notifica per la riconsegna.",
        parse_mode='Markdown',
        reply_markup=get_main_keyboard(get_user_role(update.effective_user.id))
    )

async def show_all_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    requests = get_requests()
    
    if not requests:
        await update.message.reply_text(
            "📋 *Nessuna richiesta presente*\n\n"
            "Usa '🆕 Nuova Richiesta' per creare la prima richiesta!",
            parse_mode='Markdown'
        )
        return
    
    message = "📋 *Tutte le Richieste*\n\n"
    for req in requests:
        status_emoji = {
            'nuovo': '🆕', 'assegnato': '👤', 'in_corso': '⚙️', 
            'partito': '🚗', 'completato': '✅', 'riconsegnato': '🏁', 'annullato': '❌'
        }
        
        message += f"{status_emoji.get(req[5], '📋')} *#{req[0]}* - {req[1]}\n"
        message += f"👤 {req[2]} | 🏨 {req[3]}\n"
        message += f"🔧 {req[4]} | 📊 {req[5].upper()}\n"
        if req[8]:  # assigned_to_name
            message += f"👨‍🔧 {req[8]}\n"
        if req[9]:  # tempo_ritiro
            message += f"⏰ Ritiro: {req[9]}\n"
        if req[10]:  # tempo_riconsegna
            message += f"🚚 Riconsegna: {req[10]}\n"
        message += f"📅 {req[6][:16]}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def show_valet_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    requests = get_requests(assigned_to=user_id)
    active_requests = [r for r in requests if r[5] not in ['riconsegnato', 'annullato']]
    
    if not active_requests:
        await update.message.reply_text(
            "📋 *Nessuna richiesta assegnata*\n\n"
            "Usa '🆕 Richieste Nuove' per vedere le richieste disponibili!",
            parse_mode='Markdown'
        )
        return
    
    message = "📋 *Le Tue Richieste*\n\n"
    keyboard = []
    
    for req in active_requests:
        status_emoji = {
            'assegnato': '👤', 'in_corso': '⚙️', 'partito': '🚗', 'completato': '✅'
        }
        
        message += f"{status_emoji.get(req[5], '📋')} *#{req[0]}* - {req[1]}\n"
        message += f"👤 {req[2]} | 🏨 {req[3]}\n"
        message += f"🔧 {req[4]} | 📊 {req[5].upper()}\n"
        if req[9]:  # tempo_ritiro
            message += f"⏰ Ritiro: {req[9]}\n"
        if req[10]:  # tempo_riconsegna  
            message += f"🚚 Riconsegna: {req[10]}\n"
        message += f"📅 {req[6][:16]}\n\n"
        
        keyboard.append([InlineKeyboardButton(
            f"🚗 Prendi #{req[0]}", 
            callback_data=f"assign_{req[0]}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message, 
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    
    # Statistiche
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
    
    message = f"📊 *Dashboard RoyalCarBot01*\n\n"
    message += f"🆕 Richieste nuove: *{nuove}*\n"
    message += f"⚙️ In lavorazione: *{in_corso}*\n"
    message += f"✅ Completate: *{completate}*\n"
    message += f"📅 Richieste oggi: *{oggi}*\n"
    message += f"📈 Totale richieste: *{totali}*\n\n"
    message += f"🕐 Ultimo aggiornamento: {datetime.now().strftime('%H:%M')}"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    role = get_user_role(user_id)
    
    # Gestione selezione servizio
    if data.startswith('servizio_'):
        servizio = data.replace('servizio_', '').replace('_', ' ').title()
        request_data = context.user_data.get('request_data', {})
        request_data['servizio'] = servizio
        
        # Crea la richiesta
        request_id = create_request(
            request_data['targa'],
            request_data['cliente'],
            request_data['camera'],
            request_data['servizio'],
            user_id
        )
        
        # Reset stato
        context.user_data['state'] = None
        context.user_data['request_data'] = {}
        
        await query.edit_message_text(
            f"✅ *Richiesta #{request_id} creata!*\n\n"
            f"🚗 Targa: `{request_data['targa']}`\n"
            f"👤 Cliente: {request_data['cliente']}\n"
            f"🏨 Camera: {request_data['camera']}\n"
            f"🔧 Servizio: {servizio}\n\n"
            f"La richiesta è stata inviata al team valet! 🚀",
            parse_mode='Markdown'
        )
        
        # Notifica ai valet
        await notify_valets(context, request_id, request_data)
    
    # Gestione presa in carico con scelta tempi
    elif data.startswith('assign_'):
        request_id = int(data.split('_')[1])
        
        keyboard = [
            [InlineKeyboardButton("⏱️ Ritiro in 5 min ca.", callback_data=f"pickup_{request_id}_5")],
            [InlineKeyboardButton("⏱️ Ritiro in 10 min ca.", callback_data=f"pickup_{request_id}_10")],
            [InlineKeyboardButton("⏱️ Ritiro in 20 min ca.", callback_data=f"pickup_{request_id}_20")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"⏰ *Tempo stimato per il ritiro?*\n\n"
            f"Richiesta #{request_id}\n"
            f"Seleziona il tempo stimato per raggiungere l'hotel:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    # Gestione conferma ritiro con tempo
    elif data.startswith('pickup_'):
        parts = data.split('_')
        request_id = int(parts[1])
        minutes = parts[2]
        
        tempo_text = f"{minutes} min ca."
        update_request_status(request_id, 'assegnato', user_id, tempo_ritiro=tempo_text)
        
        req = get_request_by_id(request_id)
        
        await query.edit_message_text(
            f"✅ *Richiesta #{request_id} presa in carico!*\n\n"
            f"⏰ Tempo stimato ritiro: *{tempo_text}*\n\n"
            f"🚗 {req[1]} - {req[2]}\n"
            f"🏨 Camera {req[3]}\n"
            f"🔧 {req[4]}\n\n"
            f"Ora puoi aggiornare lo stato quando parti dall'hotel.",
            parse_mode='Markdown'
        )
        
        # Notifica reception
        await notify_reception_assignment(context, request_id, req, tempo_text)
    
    # Gestione richieste valet
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
            keyboard.append([InlineKeyboardButton("✅ Servizio Completato", callback_data=f"status_{request_id}_completato")])
        elif req[5] == 'completato':
            keyboard.append([InlineKeyboardButton("🚚 Richiedi Riconsegna", callback_data=f"request_delivery_{request_id}")])
        
        keyboard.append([InlineKeyboardButton("❌ Annulla Richiesta", callback_data=f"status_{request_id}_annullato")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        status_emoji = {
            'assegnato': '👤', 'in_corso': '⚙️', 'partito': '🚗', 'completato': '✅'
        }
        
        message = f"{status_emoji.get(req[5], '📋')} *Richiesta #{request_id}*\n\n"
        message += f"🚗 Targa: `{req[1]}`\n"
        message += f"👤 Cliente: {req[2]}\n"
        message += f"🏨 Camera: {req[3]}\n"
        message += f"🔧 Servizio: {req[4]}\n"
        message += f"📊 Stato: {req[5].upper()}\n"
        if req[9]:  # tempo_ritiro
            message += f"⏰ Ritiro: {req[9]}\n"
        if req[10]:  # tempo_riconsegna
            message += f"🚚 Riconsegna: {req[10]}\n"
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    # Gestione cambio stato
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
        
        await query.edit_message_text(
            f"✅ *Stato aggiornato!*\n\n"
            f"Richiesta #{request_id}: {status_names[new_status]}\n\n"
            f"⏰ Aggiornato alle {datetime.now().strftime('%H:%M')}"
        )
        
        # Notifiche specifiche
        if new_status == 'partito':
            req = get_request_by_id(request_id)
            await notify_reception_departure(context, request_id, req)
        elif new_status == 'completato':
            await notify_reception_completion(context, request_id)
    
    # Richiesta riconsegna dal valet
    elif data.startswith('request_delivery_'):
        request_id = int(data.split('_')[2])
        
        keyboard = [
            [InlineKeyboardButton("🚚 Riconsegna in 10 min", callback_data=f"delivery_{request_id}_10")],
            [InlineKeyboardButton("🚚 Riconsegna in 20 min", callback_data=f"delivery_{request_id}_20")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🚚 *Richiesta Riconsegna*\n\n"
            f"Quanto tempo ti serve per la riconsegna?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    # Gestione riconsegna dal valet
    elif data.startswith('delivery_'):
        parts = data.split('_')
        request_id = int(parts[1])
        minutes = parts[2]
        
        tempo_text = f"{minutes} min ca."
        update_request_status(request_id, 'in_riconsegna', tempo_riconsegna=tempo_text)
        
        req = get_request_by_id(request_id)
        
        await query.edit_message_text(
            f"✅ *Riconsegna programmata!*\n\n"
            f"🚚 Tempo stimato: *{tempo_text}*\n"
            f"🚗 {req[1]} - {req[2]}\n"
            f"🏨 Camera {req[3]}\n\n"
            f"La reception è stata avvisata.",
            parse_mode='Markdown'
        )
        
        # Notifica reception
        await notify_reception_delivery_time(context, request_id, req, tempo_text)
    
    # Conferma riconsegna da reception
    elif data.startswith('confirm_delivery_'):
        request_id = int(data.split('_')[2])
        
        update_request_status(request_id, 'riconsegnato')
        
        await query.edit_message_text(
            f"✅ *Riconsegna confermata!*\n\n"
            f"Richiesta #{request_id} completata con successo!\n"
            f"⏰ Completata alle {datetime.now().strftime('%H:%M')}"
        )

async def notify_valets(context, request_id, request_data):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id, name FROM users WHERE role = "valet" AND active = 1')
    valets = cursor.fetchall()
    conn.close()
    
    message = f"🆕 *Nuova Richiesta #{request_id}*\n\n"
    message += f"🚗 Targa: `{request_data['targa']}`\n"
    message += f"👤 Cliente: {request_data['cliente']}\n"
    message += f"🏨 Camera: {request_data['camera']}\n"
    message += f"🔧 Servizio: {request_data['servizio']}\n\n"
    message += "Usa il menu '🆕 Richieste Nuove' per prendere in carico!"
    
    for valet_id, valet_name in valets:
        try:
            await context.bot.send_message(
                chat_id=valet_id,
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logging.error(f"Errore invio notifica a valet {valet_id}: {e}")

async def notify_reception_assignment(context, request_id, req, tempo_text):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id FROM users WHERE role = "reception" AND active = 1')
    reception_users = cursor.fetchall()
    conn.close()
    
    message = f"👤 *Richiesta #{request_id} Assegnata*\n\n"
    message += f"🚗 Targa: `{req[1]}`\n"
    message += f"👤 Cliente: {req[2]}\n"
    message += f"🏨 Camera: {req[3]}\n"
    message += f"👨‍🔧 Valet: {req[14]}\n"  # assigned_to_name
    message += f"⏰ Tempo ritiro: {tempo_text}\n\n"
    message += "Il valet raggiungerà l'hotel nel tempo indicato."
    
    for reception_id, in reception_users:
        try:
            await context.bot.send_message(
                chat_id=reception_id,
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logging.error(f"Errore invio notifica a reception {reception_id}: {e}")

async def notify_reception_departure(context, request_id, req):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id FROM users WHERE role = "reception" AND active = 1')
    reception_users = cursor.fetchall()
    conn.close()
    
    message = f"🚗 *Valet in Arrivo #{request_id}*\n\n"
    message += f"🚗 Targa: `{req[1]}`\n"
    message += f"👤 Cliente: {req[2]}\n"
    message += f"🏨 Camera: {req[3]}\n"
    message += f"👨‍🔧 Valet: {req[14]}\n"  # assigned_to_name
    message += f"⏰ Partito alle: {datetime.now().strftime('%H:%M')}\n\n"
    message += "Il valet è in arrivo per il ritiro del veicolo!"
    
    for reception_id, in reception_users:
        try:
            await context.bot.send_message(
                chat_id=reception_id,
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logging.error(f"Errore invio notifica a reception {reception_id}: {e}")

async def notify_reception_completion(context, request_id):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT r.targa, r.cliente, r.camera, r.servizio, u.name
        FROM requests r
        LEFT JOIN users u ON r.assigned_to = u.telegram_id
        WHERE r.id = ?
    ''', (request_id,))
    req = cursor.fetchone()
    
    cursor.execute('SELECT telegram_id FROM users WHERE role = "reception" AND active = 1')
    reception_users = cursor.fetchall()
    conn.close()
    
    if not req:
        return
    
    message = f"✅ *Servizio Completato #{request_id}*\n\n"
    message += f"🚗 Targa: `{req[0]}`\n"
    message += f"👤 Cliente: {req[1]}\n"
    message += f"🏨 Camera: {req[2]}\n"
    message += f"🔧 Servizio: {req[3]}\n"
    message += f"👨‍🔧 Valet: {req[4]}\n"
    message += f"⏰ Completato alle: {datetime.now().strftime('%H:%M')}\n\n"
    message += "Il veicolo è pronto! Usa '🚚 Richiedi Riconsegna' quando necessario."
    
    for reception_id, in reception_users:
        try:
            await context.bot.send_message(
                chat_id=reception_id,
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logging.error(f"Errore invio notifica a reception {reception_id}: {e}")

async def notify_valet_for_delivery(context, req):
    valet_id = None
    
    # Trova l'ID del valet dalla richiesta
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT assigned_to FROM requests WHERE id = ?', (req[0],))
    result = cursor.fetchone()
    if result:
        valet_id = result[0]
    conn.close()
    
    if not valet_id:
        return
    
    keyboard = [
        [InlineKeyboardButton("✅ Messaggio Visualizzato", callback_data=f"delivery_ack_{req[0]}")],
        [InlineKeyboardButton("🚚 Riconsegna in 10 min", callback_data=f"delivery_{req[0]}_10")],
        [InlineKeyboardButton("🚚 Riconsegna in 20 min", callback_data=f"delivery_{req[0]}_20")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"🚚 *Richiesta Riconsegna #{req[0]}*\n\n"
    message += f"🚗 Targa: `{req[1]}`\n"
    message += f"👤 Cliente: {req[2]}\n"
    message += f"🏨 Camera: {req[3]}\n\n"
    message += "La reception richiede la riconsegna del veicolo.\n"
    message += "Conferma la visualizzazione e indica i tempi!"
    
    try:
        await context.bot.send_message(
            chat_id=valet_id,
            text=message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logging.error(f"Errore invio notifica riconsegna a valet {valet_id}: {e}")

async def notify_reception_delivery_time(context, request_id, req, tempo_text):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id FROM users WHERE role = "reception" AND active = 1')
    reception_users = cursor.fetchall()
    conn.close()
    
    keyboard = [[InlineKeyboardButton("✅ Riconsegna Avvenuta", callback_data=f"confirm_delivery_{request_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"🚚 *Riconsegna Programmata #{request_id}*\n\n"
    message += f"🚗 Targa: `{req[1]}`\n"
    message += f"👤 Cliente: {req[2]}\n"
    message += f"🏨 Camera: {req[3]}\n"
    message += f"👨‍🔧 Valet: {req[14]}\n"  # assigned_to_name
    message += f"⏰ Tempo stimato: {tempo_text}\n\n"
    message += "Il valet arriverà per la riconsegna nel tempo indicato.\n"
    message += "Clicca il pulsante quando la riconsegna è avvenuta!"
    
    for reception_id, in reception_users:
        try:
            await context.bot.send_message(
                chat_id=reception_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except Exception as e:
            logging.error(f"Errore invio notifica a reception {reception_id}: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    role = get_user_role(user_id)
    
    if not role:
        return
    
    # Gestisci foto con caption che indica l'ID richiesta
    caption = update.message.caption
    if caption and caption.startswith('#'):
        try:
            request_id = int(caption[1:].split()[0])
            file_id = update.message.photo[-1].file_id
            
            # Determina tipo foto
            tipo = 'prima' if 'prima' in caption.lower() else 'dopo'
            
            add_photo(request_id, file_id, tipo, user_id)
            
            await update.message.reply_text(
                f"📷 *Foto aggiunta!*\n\n"
                f"Foto {tipo} per richiesta #{request_id}\n"
                f"⏰ Caricata alle {datetime.now().strftime('%H:%M')}",
                parse_mode='Markdown'
            )
            
        except (ValueError, IndexError):
            await update.message.reply_text(
                "❌ *Formato didascalia non valido*\n\n"
                "📝 *Formato corretto:*\n"
                "`#ID_RICHIESTA prima` o `#ID_RICHIESTA dopo`\n\n"
                "💡 *Esempi:*\n"
                "• `#123 prima`\n"
                "• `#123 dopo`",
                parse_mode='Markdown'
            )
    else:
        await update.message.reply_text(
            "📷 *Come caricare le foto*\n\n"
            "Per associare la foto ad una richiesta,\n"
            "aggiungi come didascalia:\n\n"
            "`#ID_RICHIESTA prima` o `#ID_RICHIESTA dopo`\n\n"
            "💡 *Esempio:* `#123 prima`",
            parse_mode='Markdown'
        )

def main():
    # Token del bot (da impostare nelle variabili d'ambiente)
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not TOKEN:
        print("❌ ERRORE: TELEGRAM_BOT_TOKEN non impostato!")
        return
    
    # Crea applicazione
    application = Application.builder().token(TOKEN).build()
    
    # Aggiungi handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("annulla", cancel_command))
    application.add_handler(CommandHandler("register", register_user))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Avvia bot
    print("🤖 RoyalCarBot01 avviato!")
    print("📋 Nuove funzionalità:")
    print("   ✅ Comando /help completo")
    print("   ✅ Comando /annulla")
    print("   ✅ Gestione tempi ritiro/riconsegna")
    print("   ✅ Notifiche automatiche con orari")
    print("   ✅ Menu pulsanti sempre visibili")
    print("   ✅ Messaggi di conferma migliorati")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()dButton(
            f"⚙️ Gestisci #{req[0]}", 
            callback_data=f"manage_{req[0]}"
        )))
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    await update.message.reply_text(
        message, 
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_new_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    requests = get_requests(stato='nuovo')
    
    if not requests:
        await update.message.reply_text(
            "🆕 *Nessuna nuova richiesta*\n\n"
            "Al momento non ci sono richieste disponibili.",
            parse_mode='Markdown'
        )
        return
    
    message = "🆕 *Nuove Richieste Disponibili*\n\n"
    keyboard = []
    
    for req in requests:
        message += f"🆔 *#{req[0]}* - {req[1]}\n"
        message += f"👤 {req[2]} | 🏨 {req[3]}\n"
        message += f"🔧 {req[4]}\n"
        message += f"📅 {req[6][:16]}\n\n"
        
        keyboard.append([InlineKeyboar
