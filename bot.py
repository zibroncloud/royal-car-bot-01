import os
import logging
import sqlite3
from datetime import datetime
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
STATI = ['nuovo', 'assegnato', 'in_corso', 'completato', 'annullato']

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

def get_requests(stato=None, search_term=None):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    
    query = '''
        SELECT r.id, r.targa, r.cliente, r.camera, r.servizio, r.stato, 
               r.created_at, u1.name as created_by_name, u2.name as assigned_to_name
        FROM requests r
        LEFT JOIN users u1 ON r.created_by = u1.telegram_id
        LEFT JOIN users u2 ON r.assigned_to = u2.telegram_id
        WHERE 1=1
    '''
    params = []
    
    if stato:
        query += ' AND r.stato = ?'
        params.append(stato)
    
    if search_term:
        query += ' AND (r.targa LIKE ? OR r.cliente LIKE ?)'
        params.extend([f'%{search_term.upper()}%', f'%{search_term}%'])
    
    query += ' ORDER BY r.created_at DESC'
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return results

def update_request_status(request_id, new_status, assigned_to=None):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    
    if assigned_to:
        cursor.execute('''
            UPDATE requests SET stato = ?, assigned_to = ? WHERE id = ?
        ''', (new_status, assigned_to, request_id))
    else:
        cursor.execute('''
            UPDATE requests SET stato = ? WHERE id = ?
        ''', (new_status, request_id))
    
    if new_status == 'completato':
        cursor.execute('''
            UPDATE requests SET completed_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (request_id,))
    
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

# Keyboards
def get_main_keyboard(role):
    if role == 'reception':
        keyboard = [
            [KeyboardButton("🆕 Nuova Richiesta")],
            [KeyboardButton("📋 Tutte le Richieste"), KeyboardButton("🔍 Cerca")],
            [KeyboardButton("📊 Dashboard"), KeyboardButton("⚙️ Gestione Utenti")]
        ]
    else:  # valet
        keyboard = [
            [KeyboardButton("📋 Mie Richieste"), KeyboardButton("🆕 Richieste Nuove")],
            [KeyboardButton("📷 Aggiungi Foto"), KeyboardButton("✅ Completa Servizio")]
        ]
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    role = get_user_role(user.id)
    
    if not role:
        await update.message.reply_text(
            "🚗 *Benvenuto in RoyalCarBot01!*\n\n"
            "Per utilizzare questo bot, devi essere registrato dal personale dell'hotel.\n"
            "Contatta la reception per l'accesso.",
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

async def register_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) != 2:
        await update.message.reply_text(
            "Uso: /register <nome> <ruolo>\n"
            "Ruoli disponibili: reception, valet"
        )
        return
    
    name = context.args[0]
    role = context.args[1].lower()
    
    if role not in ['reception', 'valet']:
        await update.message.reply_text("Ruolo non valido. Usa 'reception' o 'valet'")
        return
    
    add_user(update.effective_user.id, name, role)
    await update.message.reply_text(
        f"✅ Utente {name} registrato come {role}!",
        reply_markup=get_main_keyboard(role)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    role = get_user_role(user.id)
    text = update.message.text
    
    if not role:
        await update.message.reply_text("Non sei autorizzato. Contatta la reception.")
        return
    
    # Gestione stati conversazione
    if context.user_data.get('state') == 'creating_request':
        await handle_new_request_data(update, context)
        return
    
    if context.user_data.get('state') == 'searching':
        await handle_search(update, context)
        return
    
    # Menu principale
    if text == "🆕 Nuova Richiesta" and role == 'reception':
        context.user_data['state'] = 'creating_request'
        context.user_data['request_data'] = {}
        await update.message.reply_text(
            "🚗 *Nuova Richiesta Car Valet*\n\n"
            "Inserisci la *targa* del veicolo:",
            parse_mode='Markdown'
        )
    
    elif text == "📋 Tutte le Richieste":
        await show_all_requests(update, context)
    
    elif text == "🔍 Cerca":
        context.user_data['state'] = 'searching'
        await update.message.reply_text("🔍 Inserisci targa o cognome cliente da cercare:")
    
    elif text == "📋 Mie Richieste" and role == 'valet':
        await show_valet_requests(update, context)
    
    elif text == "🆕 Richieste Nuove" and role == 'valet':
        await show_new_requests(update, context)
    
    elif text == "📊 Dashboard" and role == 'reception':
        await show_dashboard(update, context)

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
        
        # Keyboard per tipo servizio
        keyboard = [
            [InlineKeyboardButton(" Lavaggio Esterno", callback_data="servizio_lavaggio_esterno")],
            [InlineKeyboardButton(" Lavaggio Completo", callback_data="servizio_lavaggio_completo")],
            [InlineKeyboardButton("🔧 Servizio Meccanico", callback_data="servizio_meccanico")],
            [InlineKeyboardButton("⛽ Rifornimento", callback_data="servizio_rifornimento")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔧 Seleziona il tipo di servizio:",
            reply_markup=reply_markup
        )

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_term = update.message.text
    requests = get_requests(search_term=search_term)
    
    context.user_data['state'] = None
    
    if not requests:
        await update.message.reply_text(
            f"❌ Nessuna richiesta trovata per: {search_term}",
            reply_markup=get_main_keyboard(get_user_role(update.effective_user.id))
        )
        return
    
    message = f"🔍 *Risultati ricerca: {search_term}*\n\n"
    for req in requests:
        message += f"🆔 #{req[0]} - {req[1]} ({req[2]})\n"
        message += f"🏨 Camera: {req[3]} | 🔧 {req[4]}\n"
        message += f"📊 Stato: {req[5].upper()}\n"
        message += f"📅 {req[6][:16]}\n\n"
    
    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=get_main_keyboard(get_user_role(update.effective_user.id))
    )

async def show_all_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    requests = get_requests()
    
    if not requests:
        await update.message.reply_text("📋 Nessuna richiesta presente.")
        return
    
    message = "📋 *Tutte le Richieste*\n\n"
    for req in requests:
        status_emoji = {
            'nuovo': '🆕', 'assegnato': '👤', 'in_corso': '⚙️', 
            'completato': '✅', 'annullato': '❌'
        }
        
        message += f"{status_emoji.get(req[5], '📋')} *#{req[0]}* - {req[1]}\n"
        message += f"👤 {req[2]} | 🏨 {req[3]}\n"
        message += f"🔧 {req[4]} | 📊 {req[5].upper()}\n"
        if req[8]:  # assigned_to_name
            message += f"👨‍🔧 Assegnato a: {req[8]}\n"
        message += f"📅 {req[6][:16]}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def show_valet_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, targa, cliente, camera, servizio, stato, created_at
        FROM requests 
        WHERE assigned_to = ? AND stato != 'completato'
        ORDER BY created_at DESC
    ''', (user_id,))
    
    requests = cursor.fetchall()
    conn.close()
    
    if not requests:
        await update.message.reply_text("📋 Non hai richieste assegnate al momento.")
        return
    
    message = "📋 *Le Tue Richieste*\n\n"
    for req in requests:
        message += f"🆔 #{req[0]} - {req[1]}\n"
        message += f"👤 {req[2]} | 🏨 {req[3]}\n"
        message += f"🔧 {req[4]} | 📊 {req[5].upper()}\n"
        message += f"📅 {req[6][:16]}\n\n"
    
    # Keyboard per azioni rapide
    keyboard = []
    for req in requests:
        keyboard.append([InlineKeyboardButton(
            f"Aggiorna #{req[0]}", 
            callback_data=f"update_{req[0]}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    await update.message.reply_text(
        message, 
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_new_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    requests = get_requests(stato='nuovo')
    
    if not requests:
        await update.message.reply_text("🆕 Nessuna nuova richiesta al momento.")
        return
    
    message = "🆕 *Nuove Richieste Disponibili*\n\n"
    keyboard = []
    
    for req in requests:
        message += f"🆔 #{req[0]} - {req[1]}\n"
        message += f"👤 {req[2]} | 🏨 {req[3]}\n"
        message += f"🔧 {req[4]}\n"
        message += f"📅 {req[6][:16]}\n\n"
        
        keyboard.append([InlineKeyboardButton(
            f"Prendi in carico #{req[0]}", 
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
    
    cursor.execute('SELECT COUNT(*) FROM requests WHERE stato = "in_corso"')
    in_corso = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM requests WHERE stato = "completato" AND DATE(completed_at) = DATE("now")')
    completate_oggi = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM requests')
    totali = cursor.fetchone()[0]
    
    conn.close()
    
    message = f"📊 *Dashboard RoyalCarBot01*\n\n"
    message += f"🆕 Nuove richieste: {nuove}\n"
    message += f"⚙️ In corso: {in_corso}\n"
    message += f"✅ Completate oggi: {completate_oggi}\n"
    message += f"📈 Totale richieste: {totali}\n\n"
    message += f"🕐 Ultimo aggiornamento: {datetime.now().strftime('%H:%M')}"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
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
            f"🚗 Targa: {request_data['targa']}\n"
            f"👤 Cliente: {request_data['cliente']}\n"
            f"🏨 Camera: {request_data['camera']}\n"
            f"🔧 Servizio: {servizio}\n\n"
            f"La richiesta è stata inviata al team valet.",
            parse_mode='Markdown'
        )
        
        # Notifica ai valet
        await notify_valets(context, request_id, request_data)
    
    # Gestione presa in carico
    elif data.startswith('assign_'):
        request_id = int(data.split('_')[1])
        update_request_status(request_id, 'assegnato', user_id)
        
        await query.edit_message_text(
            f"✅ Richiesta #{request_id} presa in carico!\n"
            f"Puoi ora aggiornare lo stato tramite il menu principale."
        )
    
    # Gestione aggiornamento stato
    elif data.startswith('update_'):
        request_id = int(data.split('_')[1])
        
        keyboard = [
            [InlineKeyboardButton("⚙️ Inizia Lavoro", callback_data=f"status_{request_id}_in_corso")],
            [InlineKeyboardButton("✅ Completa", callback_data=f"status_{request_id}_completato")],
            [InlineKeyboardButton("❌ Annulla", callback_data=f"status_{request_id}_annullato")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"Aggiorna stato richiesta #{request_id}:",
            reply_markup=reply_markup
        )
    
    # Gestione cambio stato
    elif data.startswith('status_'):
        parts = data.split('_')
        request_id = int(parts[1])
        new_status = parts[2]
        
        update_request_status(request_id, new_status)
        
        status_names = {
            'in_corso': 'In Corso ⚙️',
            'completato': 'Completato ✅',
            'annullato': 'Annullato ❌'
        }
        
        await query.edit_message_text(
            f"✅ Richiesta #{request_id} aggiornata a: {status_names[new_status]}"
        )
        
        # Notifica reception se completato
        if new_status == 'completato':
            await notify_reception_completion(context, request_id)

async def notify_valets(context, request_id, request_data):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id FROM users WHERE role = "valet" AND active = 1')
    valets = cursor.fetchall()
    conn.close()
    
    message = f"🆕 *Nuova Richiesta #{request_id}*\n\n"
    message += f"🚗 Targa: {request_data['targa']}\n"
    message += f"👤 Cliente: {request_data['cliente']}\n"
    message += f"🏨 Camera: {request_data['camera']}\n"
    message += f"🔧 Servizio: {request_data['servizio']}\n\n"
    message += "Usa /start per vedere e prendere in carico la richiesta."
    
    for valet in valets:
        try:
            await context.bot.send_message(
                chat_id=valet[0],
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logging.error(f"Errore invio notifica a valet {valet[0]}: {e}")

async def notify_reception_completion(context, request_id):
    conn = sqlite3.connect('royal_car_bot.db')
    cursor = conn.cursor()
    
    # Ottieni dettagli richiesta
    cursor.execute('''
        SELECT targa, cliente, camera, servizio 
        FROM requests WHERE id = ?
    ''', (request_id,))
    req = cursor.fetchone()
    
    # Ottieni reception users
    cursor.execute('SELECT telegram_id FROM users WHERE role = "reception" AND active = 1')
    reception_users = cursor.fetchall()
    conn.close()
    
    if not req:
        return
    
    message = f"✅ *Servizio Completato #{request_id}*\n\n"
    message += f"🚗 Targa: {req[0]}\n"
    message += f"👤 Cliente: {req[1]}\n"
    message += f"🏨 Camera: {req[2]}\n"
    message += f"🔧 Servizio: {req[3]}\n\n"
    message += "Il veicolo è pronto per la riconsegna."
    
    for reception in reception_users:
        try:
            await context.bot.send_message(
                chat_id=reception[0],
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logging.error(f"Errore invio notifica a reception {reception[0]}: {e}")

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
                f"📷 Foto {tipo} aggiunta alla richiesta #{request_id}!"
            )
            
        except (ValueError, IndexError):
            await update.message.reply_text(
                "❌ Formato caption non valido.\n"
                "Usa: #ID_RICHIESTA prima/dopo\n"
                "Esempio: #123 prima"
            )
    else:
        await update.message.reply_text(
            "📷 Per associare la foto ad una richiesta, aggiungi come didascalia:\n"
            "#ID_RICHIESTA prima/dopo\n\n"
            "Esempio: #123 prima"
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
    application.add_handler(CommandHandler("register", register_user))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Avvia bot
    print("🤖 RoyalCarBot01 avviato!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()