#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CarValetBOT v3.4 - Sistema Gestione Auto Hotel
By Claude AI & Zibroncloud
Data: 12 Luglio 2025
Changelog v3.5: Fix validazione targhe internazionali, menu semplificato
"""

import os
import logging
import sqlite3
import re
from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

BOT_VERSION = "3.5"
BOT_NAME = "CarValetBOT"

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

def init_db():
    try:
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
        logging.info("Database inizializzato correttamente")
    except Exception as e:
        logging.error(f"Errore inizializzazione database: {e}")

init_db()

def validate_targa(targa):
    """Valida formato targa - accetta formati italiani ed europei"""
    targa = targa.upper().strip()
    
    # Formato italiano: XX123XX (2 lettere + 3 numeri + 2 lettere)
    pattern_ita = r'^[A-Z]{2}[0-9]{3}[A-Z]{2}

def validate_cognome(cognome):
    """Valida cognome (solo lettere, spazi, apostrofi)"""
    pattern = r"^[A-Za-zÀ-ÿ\s']+$"
    return bool(re.match(pattern, cognome.strip()))

def get_foto_by_auto_id(auto_id):
    """Recupera tutte le foto di un'auto specifica"""
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        cursor.execute('SELECT file_id, data_upload FROM foto WHERE auto_id = ? ORDER BY data_upload', (auto_id,))
        result = cursor.fetchall()
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Errore lettura foto auto {auto_id}: {e}")
        return []

def get_auto_con_foto():
    """Recupera tutte le auto che hanno almeno una foto"""
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        cursor.execute('''SELECT DISTINCT a.id, a.targa, a.cognome, a.stanza, a.stato, a.foto_count 
                         FROM auto a 
                         INNER JOIN foto f ON a.id = f.auto_id 
                         WHERE a.foto_count > 0 
                         ORDER BY a.stanza''')
        result = cursor.fetchall()
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Errore lettura auto con foto: {e}")
        return []

def get_auto_by_id(auto_id):
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM auto WHERE id = ?', (auto_id,))
        result = cursor.fetchone()
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Errore lettura auto {auto_id}: {e}")
        return None

def update_auto_stato(auto_id, nuovo_stato, giorni=None):
    try:
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
        return True
    except Exception as e:
        logging.error(f"Errore aggiornamento stato auto {auto_id}: {e}")
        return False

def update_auto_field(auto_id, field, value):
    """Aggiorna un campo specifico dell'auto"""
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        
        query = f'UPDATE auto SET {field} = ? WHERE id = ?'
        cursor.execute(query, (value, auto_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Errore aggiornamento campo {field} per auto {auto_id}: {e}")
        return False

def calcola_giorni_parcheggio(data_park):
    if not data_park:
        return 0
    try:
        oggi = date.today()
        if isinstance(data_park, str):
            data_park = datetime.strptime(data_park, '%Y-%m-%d').date()
        giorni = (oggi - data_park).days + 1
        return max(1, giorni)
    except Exception as e:
        logging.error(f"Errore calcolo giorni: {e}")
        return 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = f"""🚗 *{BOT_NAME} v{BOT_VERSION}*
*By Claude AI & Zibroncloud*

🏨 *COMANDI HOTEL:*
/ritiro - Richiesta ritiro auto
/riconsegna - Lista auto per riconsegna  
/partenza - Riconsegna finale (uscita)

🚗 *COMANDI VALET:*
/incorso - Ritiro in corso
/foto - Carica foto auto
/vedi_foto - Visualizza foto auto
/park - Conferma auto parcheggiata
/exit - Auto in riconsegna
/modifica - Modifica dati auto

📊 *COMANDI STATISTICHE:*
/conta_auto - Conteggio giornaliero
/lista_auto - Auto in parcheggio

❓ *COMANDI AIUTO:*
/help - Mostra questa guida
/annulla - Annulla operazione in corso

💡 *TIPI AUTO:* Compatta, SUV, Elettrica, VAN, Gancio traino, LUXURY
🔑 *NUMERI:* Stanze e chiavi da 0 a 999
🌍 *TARGHE:* Italiane ed europee accettate"""

    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help - Mostra la guida completa"""
    help_msg = f"""🚗 *{BOT_NAME} v{BOT_VERSION} - GUIDA COMPLETA*

🏨 *COMANDI HOTEL:*
/ritiro - Crea nuova richiesta ritiro auto
/riconsegna - Seleziona auto da riconsegnare
/partenza - Conferma partenza definitiva

🚗 *COMANDI VALET:*
/incorso - Inizia ritiro auto richiesta
/foto - Carica foto dell'auto
/vedi_foto - Visualizza foto per auto/cliente
/park - Conferma auto parcheggiata
/exit - Metti auto in riconsegna
/modifica - Modifica dati auto esistente

📊 *COMANDI STATISTICHE:*
/conta_auto - Statistiche giornaliere
/lista_auto - Elenco auto parcheggiate

❓ *COMANDI AIUTO:*
/start - Messaggio di benvenuto
/help - Questa guida
/annulla - Annulla operazione in corso

📋 *WORKFLOW TIPICO:*
1️⃣ Hotel: /ritiro (inserisci targa, cognome, stanza)
2️⃣ Valet: /incorso (seleziona auto e tempo)
3️⃣ Valet: /park (conferma parcheggio)
4️⃣ Hotel: /riconsegna (richiesta riconsegna)
5️⃣ Hotel: /partenza (conferma uscita)

🎯 *STATI AUTO:*
*richiesta* - Appena creata
*ritiro* - Valet sta ritirando
*parcheggiata* - In parcheggio
*riconsegna* - In attesa riconsegna
*uscita* - Partita definitivamente

💡 *TIPI AUTO:* Compatta, SUV, Elettrica, VAN, Gancio traino, LUXURY
🔑 *RANGE NUMERI:* Stanze e chiavi da 0 a 999
🌍 *TARGHE ACCETTATE:* Italiane (XX123XX), Europee, con trattini
✨ *SCONTO AUTOMATICO:* Dopo 10+ giorni di parcheggio"""

    await update.message.reply_text(help_msg, parse_mode='Markdown')

async def annulla_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /annulla - Annulla operazione in corso"""
    current_state = context.user_data.get('state')
    
    if current_state:
        if current_state.startswith('ritiro_'):
            operazione = "registrazione auto"
        elif current_state == 'upload_foto':
            operazione = "caricamento foto"
        elif current_state.startswith('mod_'):
            operazione = "modifica auto"
        else:
            operazione = "operazione"
        
        context.user_data.clear()
        await update.message.reply_text(f"❌ *{operazione.title()} annullata*\n\nPuoi iniziare una nuova operazione quando vuoi.", parse_mode='Markdown')
    else:
        await update.message.reply_text("ℹ️ *Nessuna operazione in corso*\n\nUsa `/help` per vedere tutti i comandi disponibili.", parse_mode='Markdown')

async def vedi_foto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /vedi_foto - Mostra foto per auto specifica"""
    try:
        auto_con_foto = get_auto_con_foto()
        
        if not auto_con_foto:
            await update.message.reply_text("📷 *Nessuna foto disponibile*\n\nNon ci sono auto con foto caricate.", parse_mode='Markdown')
            return
        
        stati_order = ['parcheggiata', 'riconsegna', 'ritiro', 'richiesta', 'uscita']
        auto_per_stato = {}
        
        for auto in auto_con_foto:
            stato = auto[4]
            if stato not in auto_per_stato:
                auto_per_stato[stato] = []
            auto_per_stato[stato].append(auto)
        
        keyboard = []
        
        for stato in stati_order:
            if stato in auto_per_stato:
                if stato == 'parcheggiata':
                    emoji_stato = "🅿️"
                elif stato == 'riconsegna':
                    emoji_stato = "🚪"
                elif stato == 'ritiro':
                    emoji_stato = "⚙️"
                elif stato == 'richiesta':
                    emoji_stato = "📋"
                else:
                    emoji_stato = "🏁"
                
                for auto in auto_per_stato[stato]:
                    id_auto, targa, cognome, stanza, _, foto_count = auto
                    keyboard.append([InlineKeyboardButton(
                        f"{emoji_stato} Stanza {stanza} - {targa} ({cognome}) - 📷 {foto_count} foto", 
                        callback_data=f"mostra_foto_{id_auto}"
                    )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📷 *VISUALIZZA FOTO AUTO*\n\nSeleziona l'auto per vedere le sue foto:", 
                                       reply_markup=reply_markup, parse_mode='Markdown')
    
    except Exception as e:
        logging.error(f"Errore comando vedi_foto: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto con foto")

async def ritiro_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['state'] = 'ritiro_targa'
    await update.message.reply_text("🚗 *RITIRO AUTO*\n\nInserisci la *TARGA* del veicolo:", parse_mode='Markdown')

async def riconsegna_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando riconsegna: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def partenza_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando partenza: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def incorso_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando incorso: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def foto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando foto: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def park_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando park: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def exit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando exit: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def modifica_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, targa, cognome, stanza, tipo_auto, numero_chiave FROM auto WHERE stato != "uscita" ORDER BY stanza')
        auto_list = cursor.fetchall()
        conn.close()
        
        if not auto_list:
            await update.message.reply_text("📋 *Nessuna auto da modificare*", parse_mode='Markdown')
            return
        
        keyboard = []
        for auto in auto_list:
            tipo_text = f" ({auto[4]})" if auto[4] else ""
            chiave_text = f" - Chiave: {auto[5]}" if auto[5] else ""
            keyboard.append([InlineKeyboardButton(
                f"Stanza {auto[3]} - {auto[1]} ({auto[2]}){tipo_text}{chiave_text}", 
                callback_data=f"modifica_{auto[0]}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("✏️ *MODIFICA AUTO*\n\nSeleziona l'auto da modificare:", 
                                       reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Errore comando modifica: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def conta_auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando conta_auto: {e}")
        await update.message.reply_text("❌ Errore durante il conteggio delle auto")

async def lista_auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
            
            try:
                conn_foto = sqlite3.connect('carvalet.db')
                cursor_foto = conn_foto.cursor()
                cursor_foto.execute('SELECT foto_count FROM auto WHERE targa = ? AND cognome = ? AND stanza = ?', (targa, cognome, stanza))
                foto_result = cursor_foto.fetchone()
                foto_count = foto_result[0] if foto_result and foto_result[0] > 0 else 0
                conn_foto.close()
            except:
                foto_count = 0
            
            chiave_text = f"Chiave: {chiave}" if chiave else "Chiave: --"
            sconto_text = " ✨ SCONTO" if giorni >= 10 else ""
            foto_text = f" 📷 {foto_count}" if foto_count > 0 else ""
            
            messaggio += f"{stanza} | {cognome} | {targa} | {chiave_text}{sconto_text}{foto_text}\n"
            if giorni >= 10:
                messaggio += f"     ({giorni} giorni)\n"
        
        await update.message.reply_text(messaggio, parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Errore comando lista_auto: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento della lista")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        state = context.user_data.get('state')
        text = update.message.text.strip()
        
        if text.lower() in ['/annulla', '/help', '/start']:
            if text.lower() == '/annulla':
                await annulla_command(update, context)
                return
            elif text.lower() == '/help':
                await help_command(update, context)
                return
            elif text.lower() == '/start':
                await start(update, context)
                return
        
        if state == 'ritiro_targa':
            targa = text.upper()
            if not validate_targa(targa):
                await update.message.reply_text("❌ *Formato targa non valido!*\n\nInserisci una targa valida:\n• Italiana: XX123XX\n• Europea: ABC123, 123ABC\n• Con trattini: XX-123-XX", parse_mode='Markdown')
                return
            
            context.user_data['targa'] = targa
            context.user_data['state'] = 'ritiro_cognome'
            await update.message.reply_text("👤 Inserisci il *COGNOME* del cliente:", parse_mode='Markdown')
        
        elif state == 'ritiro_cognome':
            if not validate_cognome(text):
                await update.message.reply_text("❌ *Cognome non valido!*\n\nUsa solo lettere, spazi e apostrofi:", parse_mode='Markdown')
                return
            
            context.user_data['cognome'] = text.strip()
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
            if text.lower() == 'skip':
                context.user_data['numero_chiave'] = None
                context.user_data['state'] = 'ritiro_note'
                await update.message.reply_text("📝 Inserisci eventuali *NOTE* (o scrivi 'skip' per saltare):", parse_mode='Markdown')
            else:
                try:
                    chiave = int(text)
                    if 0 <= chiave <= 999:
                        context.user_data['numero_chiave'] = chiave
                        context.user_data['state'] = 'ritiro_note'
                        await update.message.reply_text("📝 Inserisci eventuali *NOTE* (o scrivi 'skip' per saltare):", parse_mode='Markdown')
                    else:
                        await update.message.reply_text("❌ Numero chiave non valido! Inserisci un numero da 0 a 999 o 'skip':")
                except ValueError:
                    await update.message.reply_text("❌ Inserisci un numero valido per la chiave o 'skip':")
        
        elif state == 'ritiro_note':
            note = text if text.lower() != 'skip' else None
            
            targa = context.user_data['targa']
            cognome = context.user_data['cognome'] 
            stanza = context.user_data['stanza']
            tipo_auto = context.user_data.get('tipo_auto')
            numero_chiave = context.user_data.get('numero_chiave')
            
            try:
                conn = sqlite3.connect('carvalet.db')
                cursor = conn.cursor()
                cursor.execute('''INSERT INTO auto (targa, cognome, stanza, tipo_auto, numero_chiave, note) 
                                 VALUES (?, ?, ?, ?, ?, ?)''',
                              (targa, cognome, stanza, tipo_auto, numero_chiave, note))
                auto_id = cursor.lastrowid
                conn.commit()
                conn.close()
                
                context.user_data.clear()
                
                recap_msg = f"✅ *RICHIESTA CREATA!*\n\n🆔 ID: {auto_id}\n🚗 Targa: {targa}\n👤 Cliente: {cognome}\n🏨 Stanza: {stanza}"
                
                if tipo_auto:
                    recap_msg += f"\n🚗 Tipo: {tipo_auto}"
                if numero_chiave is not None:
                    recap_msg += f"\n🔑 Chiave: {numero_chiave}"
                if note:
                    recap_msg += f"\n📝 Note: {note}"
                
                recap_msg += f"\n\n📅 Richiesta del {datetime.now().strftime('%d/%m/%Y alle %H:%M')}"
                
                await update.message.reply_text(recap_msg, parse_mode='Markdown')
                
            except Exception as e:
                logging.error(f"Errore salvataggio richiesta: {e}")
                await update.message.reply_text("❌ Errore durante il salvataggio della richiesta")
                context.user_data.clear()
        
        elif state == 'upload_foto':
            if text.lower() == 'fine':
                auto_id = context.user_data.get('foto_auto_id')
                context.user_data.clear()
                
                if auto_id:
                    auto = get_auto_by_id(auto_id)
                    if auto:
                        await update.message.reply_text(f"📷 *Upload foto completato!*\n\n🚗 {auto[1]} - Stanza {auto[3]}", parse_mode='Markdown')
            else:
                await update.message.reply_text("📷 Invia le foto dell'auto (una o più foto). Scrivi 'fine' quando hai finito.")
        
        elif state.startswith('mod_'):
            parts = state.split('_')
            field = parts[1]
            auto_id = int(parts[2])
            
            if field == 'chiave':
                if text.lower() == 'rimuovi':
                    value = None
                else:
                    try:
                        value = int(text)
                        if not (0 <= value <= 999):
                            await update.message.reply_text("❌ Numero chiave non valido! Inserisci un numero da 0 a 999 o 'rimuovi':")
                            return
                    except ValueError:
                        await update.message.reply_text("❌ Inserisci un numero valido per la chiave o 'rimuovi':")
                        return
                
                if update_auto_field(auto_id, 'numero_chiave', value):
                    auto = get_auto_by_id(auto_id)
                    text_result = f"rimossa" if value is None else f"impostata a {value}"
                    await update.message.reply_text(f"✅ *Chiave {text_result}*\n\n🚗 {auto[1]} - Stanza {auto[3]}", parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ Errore durante l'aggiornamento")
                
                context.user_data.clear()
            
            elif field == 'note':
                if text.lower() == 'rimuovi':
                    value = None
                else:
                    value = text.strip()
                
                if update_auto_field(auto_id, 'note', value):
                    auto = get_auto_by_id(auto_id)
                    text_result = "rimosse" if value is None else "aggiornate"
                    await update.message.reply_text(f"✅ *Note {text_result}*\n\n🚗 {auto[1]} - Stanza {auto[3]}", parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ Errore durante l'aggiornamento")
                
                context.user_data.clear()
        
        else:
            await update.message.reply_text("❓ *Comando non riconosciuto*\n\nUsa `/help` per vedere tutti i comandi disponibili.", parse_mode='Markdown')
    
    except Exception as e:
        logging.error(f"Errore handle_message: {e}")
        await update.message.reply_text("❌ Si è verificato un errore durante l'elaborazione del messaggio")
        context.user_data.clear()

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('state') == 'upload_foto':
            auto_id = context.user_data.get('foto_auto_id')
            if auto_id:
                file_id = update.message.photo[-1].file_id
                
                conn = sqlite3.connect('carvalet.db')
                cursor = conn.cursor()
                cursor.execute('INSERT INTO foto (auto_id, file_id) VALUES (?, ?)', (auto_id, file_id))
                cursor.execute('UPDATE auto SET foto_count = foto_count + 1 WHERE id = ?', (auto_id,))
                conn.commit()
                
                cursor.execute('SELECT foto_count FROM auto WHERE id = ?', (auto_id,))
                foto_count = cursor.fetchone()[0]
                conn.close()
                
                await update.message.reply_text(f"📷 Foto #{foto_count} salvata! Invia altre foto o scrivi 'fine' per terminare.")
        else:
            await update.message.reply_text("📷 Per caricare foto, usa prima il comando /foto e seleziona un'auto")
    except Exception as e:
        logging.error(f"Errore handle_photo: {e}")
        await update.message.reply_text("❌ Errore durante il salvataggio della foto")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
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
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
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
            
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if update_auto_stato(auto_id, 'ritiro'):
                await query.edit_message_text(f"✅ *RITIRO AVVIATO!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n⏰ Tempo stimato: {minuti} minuti\n\n📅 {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
            else:
                await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('park_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if update_auto_stato(auto_id, 'parcheggiata'):
                await query.edit_message_text(f"🅿️ *AUTO PARCHEGGIATA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n📅 Inizio conteggio giorni\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
            else:
                await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('exit_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            giorni = calcola_giorni_parcheggio(auto[9]) if auto[9] else 0
            
            if update_auto_stato(auto_id, 'riconsegna'):
                sconto_text = " ✨ CON SCONTO" if giorni >= 10 else ""
                await query.edit_message_text(f"🚪 *AUTO IN RICONSEGNA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n📅 Parcheggiata {giorni} giorni{sconto_text}\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
            else:
                await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('riconsegna_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if auto[9]:
                giorni = calcola_giorni_parcheggio(auto[9])
                if update_auto_stato(auto_id, 'riconsegna', giorni):
                    sconto_text = " ✨ CON SCONTO" if giorni >= 10 else ""
                    await query.edit_message_text(f"🚚 *RICONSEGNA RICHIESTA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n📅 Parcheggiata {giorni} giorni{sconto_text}\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
                else:
                    await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('partenza_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if auto[9]:
                giorni = calcola_giorni_parcheggio(auto[9])
                if update_auto_stato(auto_id, 'uscita', giorni):
                    sconto_text = f" ({giorni} giorni" + (" - SCONTO ✨)" if giorni >= 10 else ")")
                    await query.edit_message_text(f"🏁 *PARTENZA CONFERMATA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}{sconto_text}\n✅ Auto uscita definitivamente\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
                else:
                    await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
            else:
                if update_auto_stato(auto_id, 'uscita'):
                    await query.edit_message_text(f"🏁 *PARTENZA CONFERMATA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n✅ Auto uscita definitivamente\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
                else:
                    await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('foto_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            context.user_data['state'] = 'upload_foto'
            context.user_data['foto_auto_id'] = auto_id
            
            await query.edit_message_text(f"📷 *CARICA FOTO*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n\nInvia le foto dell'auto (una o più). Scrivi 'fine' quando terminato.", parse_mode='Markdown')
        
        elif data.startswith('modifica_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            keyboard = [
                [InlineKeyboardButton("🚗 Modifica Tipo Auto", callback_data=f"mod_tipo_{auto_id}")],
                [InlineKeyboardButton("🔑 Modifica Chiave", callback_data=f"mod_chiave_{auto_id}")],
                [InlineKeyboardButton("📝 Modifica Note", callback_data=f"mod_note_{auto_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            tipo_text = f"\n🚗 Tipo: {auto[4]}" if auto[4] else "\n🚗 Tipo: Non specificato"
            chiave_text = f"\n🔑 Chiave: {auto[5]}" if auto[5] else "\n🔑 Chiave: Non assegnata"
            note_text = f"\n📝 Note: {auto[6]}" if auto[6] else "\n📝 Note: Nessuna"
            
            await query.edit_message_text(f"✏️ *MODIFICA AUTO*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}{tipo_text}{chiave_text}{note_text}\n\nCosa vuoi modificare?", 
                                        reply_markup=reply_markup, parse_mode='Markdown')
        
        elif data.startswith('mostra_foto_'):
            auto_id = int(data.split('_')[2])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            foto_list = get_foto_by_auto_id(auto_id)
            if not foto_list:
                await query.edit_message_text(f"📷 *Nessuna foto trovata*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}", parse_mode='Markdown')
                return
            
            await query.edit_message_text(f"📷 *FOTO AUTO*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n📊 Stato: {auto[7]}\n📷 Totale foto: {len(foto_list)}", parse_mode='Markdown')
            
            max_foto_per_invio = 10
            for i, foto in enumerate(foto_list):
                if i >= max_foto_per_invio:
                    await update.effective_chat.send_message(f"📷 Mostrate prime {max_foto_per_invio} foto di {len(foto_list)} totali.\nUsa di nuovo il comando per vedere le altre.")
                    break
                
                file_id, data_upload = foto
                try:
                    data_formattata = datetime.strptime(data_upload, '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
                    caption = f"📷 Foto #{i+1} - {data_formattata}"
                    
                    await update.effective_chat.send_photo(
                        photo=file_id,
                        caption=caption
                    )
                except Exception as e:
                    logging.error(f"Errore invio foto {file_id}: {e}")
                    await update.effective_chat.send_message(f"❌ Errore caricamento foto #{i+1}")
        
        elif data.startswith('mod_tipo_'):
            auto_id = int(data.split('_')[2])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            keyboard = [
                [InlineKeyboardButton("🚗 Compatta", callback_data=f"set_tipo_{auto_id}_compatta")],
                [InlineKeyboardButton("🚙 SUV", callback_data=f"set_tipo_{auto_id}_suv")],
                [InlineKeyboardButton("🔋 Elettrica", callback_data=f"set_tipo_{auto_id}_elettrica")],
                [InlineKeyboardButton("🚐 VAN", callback_data=f"set_tipo_{auto_id}_van")],
                [InlineKeyboardButton("🚚 Gancio traino", callback_data=f"set_tipo_{auto_id}_gancio")],
                [InlineKeyboardButton("💎 LUXURY", callback_data=f"set_tipo_{auto_id}_luxury")],
                [InlineKeyboardButton("❌ Rimuovi", callback_data=f"set_tipo_{auto_id}_rimuovi")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(f"🚗 *MODIFICA TIPO AUTO*\n\n{auto[1]} - Stanza {auto[3]}\nTipo attuale: {auto[4] or 'Non specificato'}\n\nSeleziona nuovo tipo:", 
                                        reply_markup=reply_markup, parse_mode='Markdown')
        
        elif data.startswith('set_tipo_'):
            parts = data.split('_')
            auto_id = int(parts[2])
            tipo = parts[3]
            
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if tipo == 'rimuovi':
                value = None
                text_result = "rimosso"
            else:
                tipo_map = {
                    'compatta': 'Compatta',
                    'suv': 'SUV',
                    'elettrica': 'Elettrica',
                    'van': 'VAN',
                    'gancio': 'Gancio traino',
                    'luxury': 'LUXURY'
                }
                value = tipo_map.get(tipo)
                text_result = f"impostato a {value}"
            
            if update_auto_field(auto_id, 'tipo_auto', value):
                await query.edit_message_text(f"✅ *Tipo auto {text_result}*\n\n🚗 {auto[1]} - Stanza {auto[3]}", parse_mode='Markdown')
            else:
                await query.edit_message_text("❌ Errore durante l'aggiornamento")
        
        elif data.startswith('mod_chiave_'):
            auto_id = int(data.split('_')[2])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            context.user_data['state'] = f'mod_chiave_{auto_id}'
            await query.edit_message_text(f"🔑 *MODIFICA CHIAVE*\n\n{auto[1]} - Stanza {auto[3]}\nChiave attuale: {auto[5] or 'Non assegnata'}\n\nInserisci nuovo numero chiave (0-999) o scrivi 'rimuovi':", parse_mode='Markdown')
        
        elif data.startswith('mod_note_'):
            auto_id = int(data.split('_')[2])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            context.user_data['state'] = f'mod_note_{auto_id}'
            await query.edit_message_text(f"📝 *MODIFICA NOTE*\n\n{auto[1]} - Stanza {auto[3]}\nNote attuali: {auto[6] or 'Nessuna'}\n\nInserisci nuove note o scrivi 'rimuovi':", parse_mode='Markdown')
    
    except Exception as e:
        logging.error(f"Errore handle_callback_query: {e}")
        await query.edit_message_text("❌ Errore durante l'elaborazione della richiesta")

def main():
    try:
        TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        if not TOKEN:
            logging.error("TELEGRAM_BOT_TOKEN non trovato nelle variabili d'ambiente")
            return
        
        application = Application.builder().token(TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("annulla", annulla_command))
        application.add_handler(CommandHandler("vedi_foto", vedi_foto_command))
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
        
        logging.info(f"🚗 {BOT_NAME} v{BOT_VERSION} avviato!")
        logging.info("✅ Sistema gestione auto hotel attivo")
        logging.info("🔧 v3.5: Fix validazione targhe internazionali, menu semplificato")
        
        print(f"🚗 {BOT_NAME} v{BOT_VERSION} avviato!")
        print("✅ Sistema gestione auto hotel attivo")
        print("🔧 v3.5: Fix validazione targhe internazionali, menu semplificato")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    
    except Exception as e:
        logging.error(f"Errore durante l'avvio del bot: {e}")
        print(f"❌ Errore durante l'avvio: {e}")

if __name__ == '__main__':
    main()
    
    # Formato europeo generico: lettere e numeri (min 4, max 10 caratteri)
    pattern_eu = r'^[A-Z0-9]{4,10}

def validate_cognome(cognome):
    """Valida cognome (solo lettere, spazi, apostrofi)"""
    pattern = r"^[A-Za-zÀ-ÿ\s']+$"
    return bool(re.match(pattern, cognome.strip()))

def get_foto_by_auto_id(auto_id):
    """Recupera tutte le foto di un'auto specifica"""
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        cursor.execute('SELECT file_id, data_upload FROM foto WHERE auto_id = ? ORDER BY data_upload', (auto_id,))
        result = cursor.fetchall()
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Errore lettura foto auto {auto_id}: {e}")
        return []

def get_auto_con_foto():
    """Recupera tutte le auto che hanno almeno una foto"""
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        cursor.execute('''SELECT DISTINCT a.id, a.targa, a.cognome, a.stanza, a.stato, a.foto_count 
                         FROM auto a 
                         INNER JOIN foto f ON a.id = f.auto_id 
                         WHERE a.foto_count > 0 
                         ORDER BY a.stanza''')
        result = cursor.fetchall()
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Errore lettura auto con foto: {e}")
        return []

def get_auto_by_id(auto_id):
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM auto WHERE id = ?', (auto_id,))
        result = cursor.fetchone()
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Errore lettura auto {auto_id}: {e}")
        return None

def update_auto_stato(auto_id, nuovo_stato, giorni=None):
    try:
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
        return True
    except Exception as e:
        logging.error(f"Errore aggiornamento stato auto {auto_id}: {e}")
        return False

def update_auto_field(auto_id, field, value):
    """Aggiorna un campo specifico dell'auto"""
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        
        query = f'UPDATE auto SET {field} = ? WHERE id = ?'
        cursor.execute(query, (value, auto_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Errore aggiornamento campo {field} per auto {auto_id}: {e}")
        return False

def calcola_giorni_parcheggio(data_park):
    if not data_park:
        return 0
    try:
        oggi = date.today()
        if isinstance(data_park, str):
            data_park = datetime.strptime(data_park, '%Y-%m-%d').date()
        giorni = (oggi - data_park).days + 1
        return max(1, giorni)
    except Exception as e:
        logging.error(f"Errore calcolo giorni: {e}")
        return 0

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
• `/vedi_foto` - Visualizza foto auto
• `/park` - Conferma auto parcheggiata
• `/exit` - Auto in riconsegna
• `/modifica` - Modifica dati auto

📊 *COMANDI STATISTICHE:*
• `/conta_auto` - Conteggio giornaliero
• `/lista_auto` - Auto in parcheggio

❓ *COMANDI AIUTO:*
• `/help` - Mostra questa guida
• `/annulla` - Annulla operazione in corso

💡 *TIPI AUTO:* Compatta, SUV, Elettrica, VAN, Gancio traino, LUXURY
🔑 *NUMERI:* Stanze e chiavi da 0 a 999"""

    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help - Mostra la guida completa"""
    help_msg = f"""🚗 *{BOT_NAME} v{BOT_VERSION} - GUIDA COMPLETA*

🏨 *COMANDI HOTEL:*
• `/ritiro` - Crea nuova richiesta ritiro auto
• `/riconsegna` - Seleziona auto da riconsegnare
• `/partenza` - Conferma partenza definitiva

🚗 *COMANDI VALET:*
• `/incorso` - Inizia ritiro auto richiesta
• `/foto` - Carica foto dell'auto
• `/vedi_foto` - Visualizza foto per auto/cliente
• `/park` - Conferma auto parcheggiata
• `/exit` - Metti auto in riconsegna
• `/modifica` - Modifica dati auto esistente

📊 *COMANDI STATISTICHE:*
• `/conta_auto` - Statistiche giornaliere
• `/lista_auto` - Elenco auto parcheggiate

❓ *COMANDI AIUTO:*
• `/start` - Messaggio di benvenuto
• `/help` - Questa guida
• `/annulla` - Annulla operazione in corso

📋 *WORKFLOW TIPICO:*
1️⃣ Hotel: `/ritiro` (inserisci targa, cognome, stanza)
2️⃣ Valet: `/incorso` (seleziona auto e tempo)
3️⃣ Valet: `/park` (conferma parcheggio)
4️⃣ Hotel: `/riconsegna` (richiesta riconsegna)
5️⃣ Hotel: `/partenza` (conferma uscita)

🎯 *STATI AUTO:*
• *richiesta* - Appena creata
• *ritiro* - Valet sta ritirando
• *parcheggiata* - In parcheggio
• *riconsegna* - In attesa riconsegna
• *uscita* - Partita definitivamente

💡 *TIPI AUTO:* Compatta, SUV, Elettrica, VAN, Gancio traino, LUXURY
🔑 *RANGE NUMERI:* Stanze e chiavi da 0 a 999
✨ *SCONTO AUTOMATICO:* Dopo 10+ giorni di parcheggio"""

    await update.message.reply_text(help_msg, parse_mode='Markdown')

async def annulla_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /annulla - Annulla operazione in corso"""
    current_state = context.user_data.get('state')
    
    if current_state:
        if current_state.startswith('ritiro_'):
            operazione = "registrazione auto"
        elif current_state == 'upload_foto':
            operazione = "caricamento foto"
        elif current_state.startswith('mod_'):
            operazione = "modifica auto"
        else:
            operazione = "operazione"
        
        context.user_data.clear()
        await update.message.reply_text(f"❌ *{operazione.title()} annullata*\n\nPuoi iniziare una nuova operazione quando vuoi.", parse_mode='Markdown')
    else:
        await update.message.reply_text("ℹ️ *Nessuna operazione in corso*\n\nUsa `/help` per vedere tutti i comandi disponibili.", parse_mode='Markdown')

async def vedi_foto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /vedi_foto - Mostra foto per auto specifica"""
    try:
        auto_con_foto = get_auto_con_foto()
        
        if not auto_con_foto:
            await update.message.reply_text("📷 *Nessuna foto disponibile*\n\nNon ci sono auto con foto caricate.", parse_mode='Markdown')
            return
        
        stati_order = ['parcheggiata', 'riconsegna', 'ritiro', 'richiesta', 'uscita']
        auto_per_stato = {}
        
        for auto in auto_con_foto:
            stato = auto[4]
            if stato not in auto_per_stato:
                auto_per_stato[stato] = []
            auto_per_stato[stato].append(auto)
        
        keyboard = []
        
        for stato in stati_order:
            if stato in auto_per_stato:
                if stato == 'parcheggiata':
                    emoji_stato = "🅿️"
                elif stato == 'riconsegna':
                    emoji_stato = "🚪"
                elif stato == 'ritiro':
                    emoji_stato = "⚙️"
                elif stato == 'richiesta':
                    emoji_stato = "📋"
                else:
                    emoji_stato = "🏁"
                
                for auto in auto_per_stato[stato]:
                    id_auto, targa, cognome, stanza, _, foto_count = auto
                    keyboard.append([InlineKeyboardButton(
                        f"{emoji_stato} Stanza {stanza} - {targa} ({cognome}) - 📷 {foto_count} foto", 
                        callback_data=f"mostra_foto_{id_auto}"
                    )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📷 *VISUALIZZA FOTO AUTO*\n\nSeleziona l'auto per vedere le sue foto:", 
                                       reply_markup=reply_markup, parse_mode='Markdown')
    
    except Exception as e:
        logging.error(f"Errore comando vedi_foto: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto con foto")

async def ritiro_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['state'] = 'ritiro_targa'
    await update.message.reply_text("🚗 *RITIRO AUTO*\n\nInserisci la *TARGA* del veicolo (formato: XX123XX):", parse_mode='Markdown')

async def riconsegna_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando riconsegna: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def partenza_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando partenza: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def incorso_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando incorso: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def foto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando foto: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def park_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando park: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def exit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando exit: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def modifica_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, targa, cognome, stanza, tipo_auto, numero_chiave FROM auto WHERE stato != "uscita" ORDER BY stanza')
        auto_list = cursor.fetchall()
        conn.close()
        
        if not auto_list:
            await update.message.reply_text("📋 *Nessuna auto da modificare*", parse_mode='Markdown')
            return
        
        keyboard = []
        for auto in auto_list:
            tipo_text = f" ({auto[4]})" if auto[4] else ""
            chiave_text = f" - Chiave: {auto[5]}" if auto[5] else ""
            keyboard.append([InlineKeyboardButton(
                f"Stanza {auto[3]} - {auto[1]} ({auto[2]}){tipo_text}{chiave_text}", 
                callback_data=f"modifica_{auto[0]}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("✏️ *MODIFICA AUTO*\n\nSeleziona l'auto da modificare:", 
                                       reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Errore comando modifica: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def conta_auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando conta_auto: {e}")
        await update.message.reply_text("❌ Errore durante il conteggio delle auto")

async def lista_auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
            
            try:
                conn_foto = sqlite3.connect('carvalet.db')
                cursor_foto = conn_foto.cursor()
                cursor_foto.execute('SELECT foto_count FROM auto WHERE targa = ? AND cognome = ? AND stanza = ?', (targa, cognome, stanza))
                foto_result = cursor_foto.fetchone()
                foto_count = foto_result[0] if foto_result and foto_result[0] > 0 else 0
                conn_foto.close()
            except:
                foto_count = 0
            
            chiave_text = f"Chiave: {chiave}" if chiave else "Chiave: --"
            sconto_text = " ✨ SCONTO" if giorni >= 10 else ""
            foto_text = f" 📷 {foto_count}" if foto_count > 0 else ""
            
            messaggio += f"{stanza} | {cognome} | {targa} | {chiave_text}{sconto_text}{foto_text}\n"
            if giorni >= 10:
                messaggio += f"     ({giorni} giorni)\n"
        
        await update.message.reply_text(messaggio, parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Errore comando lista_auto: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento della lista")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        state = context.user_data.get('state')
        text = update.message.text.strip()
        
        if text.lower() in ['/annulla', '/help', '/start']:
            if text.lower() == '/annulla':
                await annulla_command(update, context)
                return
            elif text.lower() == '/help':
                await help_command(update, context)
                return
            elif text.lower() == '/start':
                await start(update, context)
                return
        
        if state == 'ritiro_targa':
            targa = text.upper()
            if not validate_targa(targa):
                await update.message.reply_text("❌ *Formato targa non valido!*\n\nInserisci una targa nel formato: *XX123XX*\n(2 lettere + 3 numeri + 2 lettere)", parse_mode='Markdown')
                return
            
            context.user_data['targa'] = targa
            context.user_data['state'] = 'ritiro_cognome'
            await update.message.reply_text("👤 Inserisci il *COGNOME* del cliente:", parse_mode='Markdown')
        
        elif state == 'ritiro_cognome':
            if not validate_cognome(text):
                await update.message.reply_text("❌ *Cognome non valido!*\n\nUsa solo lettere, spazi e apostrofi:", parse_mode='Markdown')
                return
            
            context.user_data['cognome'] = text.strip()
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
            if text.lower() == 'skip':
                context.user_data['numero_chiave'] = None
                context.user_data['state'] = 'ritiro_note'
                await update.message.reply_text("📝 Inserisci eventuali *NOTE* (o scrivi 'skip' per saltare):", parse_mode='Markdown')
            else:
                try:
                    chiave = int(text)
                    if 0 <= chiave <= 999:
                        context.user_data['numero_chiave'] = chiave
                        context.user_data['state'] = 'ritiro_note'
                        await update.message.reply_text("📝 Inserisci eventuali *NOTE* (o scrivi 'skip' per saltare):", parse_mode='Markdown')
                    else:
                        await update.message.reply_text("❌ Numero chiave non valido! Inserisci un numero da 0 a 999 o 'skip':")
                except ValueError:
                    await update.message.reply_text("❌ Inserisci un numero valido per la chiave o 'skip':")
        
        elif state == 'ritiro_note':
            note = text if text.lower() != 'skip' else None
            
            targa = context.user_data['targa']
            cognome = context.user_data['cognome'] 
            stanza = context.user_data['stanza']
            tipo_auto = context.user_data.get('tipo_auto')
            numero_chiave = context.user_data.get('numero_chiave')
            
            try:
                conn = sqlite3.connect('carvalet.db')
                cursor = conn.cursor()
                cursor.execute('''INSERT INTO auto (targa, cognome, stanza, tipo_auto, numero_chiave, note) 
                                 VALUES (?, ?, ?, ?, ?, ?)''',
                              (targa, cognome, stanza, tipo_auto, numero_chiave, note))
                auto_id = cursor.lastrowid
                conn.commit()
                conn.close()
                
                context.user_data.clear()
                
                recap_msg = f"✅ *RICHIESTA CREATA!*\n\n🆔 ID: {auto_id}\n🚗 Targa: {targa}\n👤 Cliente: {cognome}\n🏨 Stanza: {stanza}"
                
                if tipo_auto:
                    recap_msg += f"\n🚗 Tipo: {tipo_auto}"
                if numero_chiave is not None:
                    recap_msg += f"\n🔑 Chiave: {numero_chiave}"
                if note:
                    recap_msg += f"\n📝 Note: {note}"
                
                recap_msg += f"\n\n📅 Richiesta del {datetime.now().strftime('%d/%m/%Y alle %H:%M')}"
                
                await update.message.reply_text(recap_msg, parse_mode='Markdown')
                
            except Exception as e:
                logging.error(f"Errore salvataggio richiesta: {e}")
                await update.message.reply_text("❌ Errore durante il salvataggio della richiesta")
                context.user_data.clear()
        
        elif state == 'upload_foto':
            if text.lower() == 'fine':
                auto_id = context.user_data.get('foto_auto_id')
                context.user_data.clear()
                
                if auto_id:
                    auto = get_auto_by_id(auto_id)
                    if auto:
                        await update.message.reply_text(f"📷 *Upload foto completato!*\n\n🚗 {auto[1]} - Stanza {auto[3]}", parse_mode='Markdown')
            else:
                await update.message.reply_text("📷 Invia le foto dell'auto (una o più foto). Scrivi 'fine' quando hai finito.")
        
        elif state.startswith('mod_'):
            parts = state.split('_')
            field = parts[1]
            auto_id = int(parts[2])
            
            if field == 'chiave':
                if text.lower() == 'rimuovi':
                    value = None
                else:
                    try:
                        value = int(text)
                        if not (0 <= value <= 999):
                            await update.message.reply_text("❌ Numero chiave non valido! Inserisci un numero da 0 a 999 o 'rimuovi':")
                            return
                    except ValueError:
                        await update.message.reply_text("❌ Inserisci un numero valido per la chiave o 'rimuovi':")
                        return
                
                if update_auto_field(auto_id, 'numero_chiave', value):
                    auto = get_auto_by_id(auto_id)
                    text_result = f"rimossa" if value is None else f"impostata a {value}"
                    await update.message.reply_text(f"✅ *Chiave {text_result}*\n\n🚗 {auto[1]} - Stanza {auto[3]}", parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ Errore durante l'aggiornamento")
                
                context.user_data.clear()
            
            elif field == 'note':
                if text.lower() == 'rimuovi':
                    value = None
                else:
                    value = text.strip()
                
                if update_auto_field(auto_id, 'note', value):
                    auto = get_auto_by_id(auto_id)
                    text_result = "rimosse" if value is None else "aggiornate"
                    await update.message.reply_text(f"✅ *Note {text_result}*\n\n🚗 {auto[1]} - Stanza {auto[3]}", parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ Errore durante l'aggiornamento")
                
                context.user_data.clear()
        
        else:
            await update.message.reply_text("❓ *Comando non riconosciuto*\n\nUsa `/help` per vedere tutti i comandi disponibili.", parse_mode='Markdown')
    
    except Exception as e:
        logging.error(f"Errore handle_message: {e}")
        await update.message.reply_text("❌ Si è verificato un errore durante l'elaborazione del messaggio")
        context.user_data.clear()

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('state') == 'upload_foto':
            auto_id = context.user_data.get('foto_auto_id')
            if auto_id:
                file_id = update.message.photo[-1].file_id
                
                conn = sqlite3.connect('carvalet.db')
                cursor = conn.cursor()
                cursor.execute('INSERT INTO foto (auto_id, file_id) VALUES (?, ?)', (auto_id, file_id))
                cursor.execute('UPDATE auto SET foto_count = foto_count + 1 WHERE id = ?', (auto_id,))
                conn.commit()
                
                cursor.execute('SELECT foto_count FROM auto WHERE id = ?', (auto_id,))
                foto_count = cursor.fetchone()[0]
                conn.close()
                
                await update.message.reply_text(f"📷 Foto #{foto_count} salvata! Invia altre foto o scrivi 'fine' per terminare.")
        else:
            await update.message.reply_text("📷 Per caricare foto, usa prima il comando /foto e seleziona un'auto")
    except Exception as e:
        logging.error(f"Errore handle_photo: {e}")
        await update.message.reply_text("❌ Errore durante il salvataggio della foto")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
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
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
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
            
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if update_auto_stato(auto_id, 'ritiro'):
                await query.edit_message_text(f"✅ *RITIRO AVVIATO!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n⏰ Tempo stimato: {minuti} minuti\n\n📅 {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
            else:
                await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('park_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if update_auto_stato(auto_id, 'parcheggiata'):
                await query.edit_message_text(f"🅿️ *AUTO PARCHEGGIATA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n📅 Inizio conteggio giorni\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
            else:
                await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('exit_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            giorni = calcola_giorni_parcheggio(auto[9]) if auto[9] else 0
            
            if update_auto_stato(auto_id, 'riconsegna'):
                sconto_text = " ✨ CON SCONTO" if giorni >= 10 else ""
                await query.edit_message_text(f"🚪 *AUTO IN RICONSEGNA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n📅 Parcheggiata {giorni} giorni{sconto_text}\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
            else:
                await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('riconsegna_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if auto[9]:
                giorni = calcola_giorni_parcheggio(auto[9])
                if update_auto_stato(auto_id, 'riconsegna', giorni):
                    sconto_text = " ✨ CON SCONTO" if giorni >= 10 else ""
                    await query.edit_message_text(f"🚚 *RICONSEGNA RICHIESTA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n📅 Parcheggiata {giorni} giorni{sconto_text}\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
                else:
                    await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('partenza_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if auto[9]:
                giorni = calcola_giorni_parcheggio(auto[9])
                if update_auto_stato(auto_id, 'uscita', giorni):
                    sconto_text = f" ({giorni} giorni" + (" - SCONTO ✨)" if giorni >= 10 else ")")
                    await query.edit_message_text(f"🏁 *PARTENZA CONFERMATA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}{sconto_text}\n✅ Auto uscita definitivamente\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
                else:
                    await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
            else:
                if update_auto_stato(auto_id, 'uscita'):
                    await query.edit_message_text(f"🏁 *PARTENZA CONFERMATA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n✅ Auto uscita definitivamente\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
                else:
                    await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('foto_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            context.user_data['state'] = 'upload_foto'
            context.user_data['foto_auto_id'] = auto_id
            
            await query.edit_message_text(f"📷 *CARICA FOTO*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n\nInvia le foto dell'auto (una o più). Scrivi 'fine' quando terminato.", parse_mode='Markdown')
        
        elif data.startswith('modifica_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            keyboard = [
                [InlineKeyboardButton("🚗 Modifica Tipo Auto", callback_data=f"mod_tipo_{auto_id}")],
                [InlineKeyboardButton("🔑 Modifica Chiave", callback_data=f"mod_chiave_{auto_id}")],
                [InlineKeyboardButton("📝 Modifica Note", callback_data=f"mod_note_{auto_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            tipo_text = f"\n🚗 Tipo: {auto[4]}" if auto[4] else "\n🚗 Tipo: Non specificato"
            chiave_text = f"\n🔑 Chiave: {auto[5]}" if auto[5] else "\n🔑 Chiave: Non assegnata"
            note_text = f"\n📝 Note: {auto[6]}" if auto[6] else "\n📝 Note: Nessuna"
            
            await query.edit_message_text(f"✏️ *MODIFICA AUTO*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}{tipo_text}{chiave_text}{note_text}\n\nCosa vuoi modificare?", 
                                        reply_markup=reply_markup, parse_mode='Markdown')
        
        elif data.startswith('mostra_foto_'):
            auto_id = int(data.split('_')[2])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            foto_list = get_foto_by_auto_id(auto_id)
            if not foto_list:
                await query.edit_message_text(f"📷 *Nessuna foto trovata*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}", parse_mode='Markdown')
                return
            
            await query.edit_message_text(f"📷 *FOTO AUTO*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n📊 Stato: {auto[7]}\n📷 Totale foto: {len(foto_list)}", parse_mode='Markdown')
            
            max_foto_per_invio = 10
            for i, foto in enumerate(foto_list):
                if i >= max_foto_per_invio:
                    await update.effective_chat.send_message(f"📷 Mostrate prime {max_foto_per_invio} foto di {len(foto_list)} totali.\nUsa di nuovo il comando per vedere le altre.")
                    break
                
                file_id, data_upload = foto
                try:
                    data_formattata = datetime.strptime(data_upload, '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
                    caption = f"📷 Foto #{i+1} - {data_formattata}"
                    
                    await update.effective_chat.send_photo(
                        photo=file_id,
                        caption=caption
                    )
                except Exception as e:
                    logging.error(f"Errore invio foto {file_id}: {e}")
                    await update.effective_chat.send_message(f"❌ Errore caricamento foto #{i+1}")
        
        elif data.startswith('mod_tipo_'):
            auto_id = int(data.split('_')[2])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            keyboard = [
                [InlineKeyboardButton("🚗 Compatta", callback_data=f"set_tipo_{auto_id}_compatta")],
                [InlineKeyboardButton("🚙 SUV", callback_data=f"set_tipo_{auto_id}_suv")],
                [InlineKeyboardButton("🔋 Elettrica", callback_data=f"set_tipo_{auto_id}_elettrica")],
                [InlineKeyboardButton("🚐 VAN", callback_data=f"set_tipo_{auto_id}_van")],
                [InlineKeyboardButton("🚚 Gancio traino", callback_data=f"set_tipo_{auto_id}_gancio")],
                [InlineKeyboardButton("💎 LUXURY", callback_data=f"set_tipo_{auto_id}_luxury")],
                [InlineKeyboardButton("❌ Rimuovi", callback_data=f"set_tipo_{auto_id}_rimuovi")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(f"🚗 *MODIFICA TIPO AUTO*\n\n{auto[1]} - Stanza {auto[3]}\nTipo attuale: {auto[4] or 'Non specificato'}\n\nSeleziona nuovo tipo:", 
                                        reply_markup=reply_markup, parse_mode='Markdown')
        
        elif data.startswith('set_tipo_'):
            parts = data.split('_')
            auto_id = int(parts[2])
            tipo = parts[3]
            
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if tipo == 'rimuovi':
                value = None
                text_result = "rimosso"
            else:
                tipo_map = {
                    'compatta': 'Compatta',
                    'suv': 'SUV',
                    'elettrica': 'Elettrica',
                    'van': 'VAN',
                    'gancio': 'Gancio traino',
                    'luxury': 'LUXURY'
                }
                value = tipo_map.get(tipo)
                text_result = f"impostato a {value}"
            
            if update_auto_field(auto_id, 'tipo_auto', value):
                await query.edit_message_text(f"✅ *Tipo auto {text_result}*\n\n🚗 {auto[1]} - Stanza {auto[3]}", parse_mode='Markdown')
            else:
                await query.edit_message_text("❌ Errore durante l'aggiornamento")
        
        elif data.startswith('mod_chiave_'):
            auto_id = int(data.split('_')[2])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            context.user_data['state'] = f'mod_chiave_{auto_id}'
            await query.edit_message_text(f"🔑 *MODIFICA CHIAVE*\n\n{auto[1]} - Stanza {auto[3]}\nChiave attuale: {auto[5] or 'Non assegnata'}\n\nInserisci nuovo numero chiave (0-999) o scrivi 'rimuovi':", parse_mode='Markdown')
        
        elif data.startswith('mod_note_'):
            auto_id = int(data.split('_')[2])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            context.user_data['state'] = f'mod_note_{auto_id}'
            await query.edit_message_text(f"📝 *MODIFICA NOTE*\n\n{auto[1]} - Stanza {auto[3]}\nNote attuali: {auto[6] or 'Nessuna'}\n\nInserisci nuove note o scrivi 'rimuovi':", parse_mode='Markdown')
    
    except Exception as e:
        logging.error(f"Errore handle_callback_query: {e}")
        await query.edit_message_text("❌ Errore durante l'elaborazione della richiesta")

def main():
    try:
        TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        if not TOKEN:
            logging.error("TELEGRAM_BOT_TOKEN non trovato nelle variabili d'ambiente")
            return
        
        application = Application.builder().token(TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("annulla", annulla_command))
        application.add_handler(CommandHandler("vedi_foto", vedi_foto_command))
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
        
        logging.info(f"🚗 {BOT_NAME} v{BOT_VERSION} avviato!")
        logging.info("✅ Sistema gestione auto hotel attivo")
        logging.info("🔧 v3.4: Aggiunto comando /vedi_foto con selezione auto, indicatori foto")
        
        print(f"🚗 {BOT_NAME} v{BOT_VERSION} avviato!")
        print("✅ Sistema gestione auto hotel attivo")
        print("🔧 v3.4: Aggiunto comando /vedi_foto con selezione auto, indicatori foto")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    
    except Exception as e:
        logging.error(f"Errore durante l'avvio del bot: {e}")
        print(f"❌ Errore durante l'avvio: {e}")

if __name__ == '__main__':
    main()
    
    # Formato con trattini/spazi: XX-123-XX o XX 123 XX
    pattern_separatori = r'^[A-Z0-9]{1,4}[-\s][A-Z0-9]{1,4}[-\s][A-Z0-9]{1,4}

def validate_cognome(cognome):
    """Valida cognome (solo lettere, spazi, apostrofi)"""
    pattern = r"^[A-Za-zÀ-ÿ\s']+$"
    return bool(re.match(pattern, cognome.strip()))

def get_foto_by_auto_id(auto_id):
    """Recupera tutte le foto di un'auto specifica"""
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        cursor.execute('SELECT file_id, data_upload FROM foto WHERE auto_id = ? ORDER BY data_upload', (auto_id,))
        result = cursor.fetchall()
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Errore lettura foto auto {auto_id}: {e}")
        return []

def get_auto_con_foto():
    """Recupera tutte le auto che hanno almeno una foto"""
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        cursor.execute('''SELECT DISTINCT a.id, a.targa, a.cognome, a.stanza, a.stato, a.foto_count 
                         FROM auto a 
                         INNER JOIN foto f ON a.id = f.auto_id 
                         WHERE a.foto_count > 0 
                         ORDER BY a.stanza''')
        result = cursor.fetchall()
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Errore lettura auto con foto: {e}")
        return []

def get_auto_by_id(auto_id):
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM auto WHERE id = ?', (auto_id,))
        result = cursor.fetchone()
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Errore lettura auto {auto_id}: {e}")
        return None

def update_auto_stato(auto_id, nuovo_stato, giorni=None):
    try:
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
        return True
    except Exception as e:
        logging.error(f"Errore aggiornamento stato auto {auto_id}: {e}")
        return False

def update_auto_field(auto_id, field, value):
    """Aggiorna un campo specifico dell'auto"""
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        
        query = f'UPDATE auto SET {field} = ? WHERE id = ?'
        cursor.execute(query, (value, auto_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Errore aggiornamento campo {field} per auto {auto_id}: {e}")
        return False

def calcola_giorni_parcheggio(data_park):
    if not data_park:
        return 0
    try:
        oggi = date.today()
        if isinstance(data_park, str):
            data_park = datetime.strptime(data_park, '%Y-%m-%d').date()
        giorni = (oggi - data_park).days + 1
        return max(1, giorni)
    except Exception as e:
        logging.error(f"Errore calcolo giorni: {e}")
        return 0

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
• `/vedi_foto` - Visualizza foto auto
• `/park` - Conferma auto parcheggiata
• `/exit` - Auto in riconsegna
• `/modifica` - Modifica dati auto

📊 *COMANDI STATISTICHE:*
• `/conta_auto` - Conteggio giornaliero
• `/lista_auto` - Auto in parcheggio

❓ *COMANDI AIUTO:*
• `/help` - Mostra questa guida
• `/annulla` - Annulla operazione in corso

💡 *TIPI AUTO:* Compatta, SUV, Elettrica, VAN, Gancio traino, LUXURY
🔑 *NUMERI:* Stanze e chiavi da 0 a 999"""

    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help - Mostra la guida completa"""
    help_msg = f"""🚗 *{BOT_NAME} v{BOT_VERSION} - GUIDA COMPLETA*

🏨 *COMANDI HOTEL:*
• `/ritiro` - Crea nuova richiesta ritiro auto
• `/riconsegna` - Seleziona auto da riconsegnare
• `/partenza` - Conferma partenza definitiva

🚗 *COMANDI VALET:*
• `/incorso` - Inizia ritiro auto richiesta
• `/foto` - Carica foto dell'auto
• `/vedi_foto` - Visualizza foto per auto/cliente
• `/park` - Conferma auto parcheggiata
• `/exit` - Metti auto in riconsegna
• `/modifica` - Modifica dati auto esistente

📊 *COMANDI STATISTICHE:*
• `/conta_auto` - Statistiche giornaliere
• `/lista_auto` - Elenco auto parcheggiate

❓ *COMANDI AIUTO:*
• `/start` - Messaggio di benvenuto
• `/help` - Questa guida
• `/annulla` - Annulla operazione in corso

📋 *WORKFLOW TIPICO:*
1️⃣ Hotel: `/ritiro` (inserisci targa, cognome, stanza)
2️⃣ Valet: `/incorso` (seleziona auto e tempo)
3️⃣ Valet: `/park` (conferma parcheggio)
4️⃣ Hotel: `/riconsegna` (richiesta riconsegna)
5️⃣ Hotel: `/partenza` (conferma uscita)

🎯 *STATI AUTO:*
• *richiesta* - Appena creata
• *ritiro* - Valet sta ritirando
• *parcheggiata* - In parcheggio
• *riconsegna* - In attesa riconsegna
• *uscita* - Partita definitivamente

💡 *TIPI AUTO:* Compatta, SUV, Elettrica, VAN, Gancio traino, LUXURY
🔑 *RANGE NUMERI:* Stanze e chiavi da 0 a 999
✨ *SCONTO AUTOMATICO:* Dopo 10+ giorni di parcheggio"""

    await update.message.reply_text(help_msg, parse_mode='Markdown')

async def annulla_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /annulla - Annulla operazione in corso"""
    current_state = context.user_data.get('state')
    
    if current_state:
        if current_state.startswith('ritiro_'):
            operazione = "registrazione auto"
        elif current_state == 'upload_foto':
            operazione = "caricamento foto"
        elif current_state.startswith('mod_'):
            operazione = "modifica auto"
        else:
            operazione = "operazione"
        
        context.user_data.clear()
        await update.message.reply_text(f"❌ *{operazione.title()} annullata*\n\nPuoi iniziare una nuova operazione quando vuoi.", parse_mode='Markdown')
    else:
        await update.message.reply_text("ℹ️ *Nessuna operazione in corso*\n\nUsa `/help` per vedere tutti i comandi disponibili.", parse_mode='Markdown')

async def vedi_foto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /vedi_foto - Mostra foto per auto specifica"""
    try:
        auto_con_foto = get_auto_con_foto()
        
        if not auto_con_foto:
            await update.message.reply_text("📷 *Nessuna foto disponibile*\n\nNon ci sono auto con foto caricate.", parse_mode='Markdown')
            return
        
        stati_order = ['parcheggiata', 'riconsegna', 'ritiro', 'richiesta', 'uscita']
        auto_per_stato = {}
        
        for auto in auto_con_foto:
            stato = auto[4]
            if stato not in auto_per_stato:
                auto_per_stato[stato] = []
            auto_per_stato[stato].append(auto)
        
        keyboard = []
        
        for stato in stati_order:
            if stato in auto_per_stato:
                if stato == 'parcheggiata':
                    emoji_stato = "🅿️"
                elif stato == 'riconsegna':
                    emoji_stato = "🚪"
                elif stato == 'ritiro':
                    emoji_stato = "⚙️"
                elif stato == 'richiesta':
                    emoji_stato = "📋"
                else:
                    emoji_stato = "🏁"
                
                for auto in auto_per_stato[stato]:
                    id_auto, targa, cognome, stanza, _, foto_count = auto
                    keyboard.append([InlineKeyboardButton(
                        f"{emoji_stato} Stanza {stanza} - {targa} ({cognome}) - 📷 {foto_count} foto", 
                        callback_data=f"mostra_foto_{id_auto}"
                    )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📷 *VISUALIZZA FOTO AUTO*\n\nSeleziona l'auto per vedere le sue foto:", 
                                       reply_markup=reply_markup, parse_mode='Markdown')
    
    except Exception as e:
        logging.error(f"Errore comando vedi_foto: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto con foto")

async def ritiro_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['state'] = 'ritiro_targa'
    await update.message.reply_text("🚗 *RITIRO AUTO*\n\nInserisci la *TARGA* del veicolo (formato: XX123XX):", parse_mode='Markdown')

async def riconsegna_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando riconsegna: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def partenza_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando partenza: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def incorso_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando incorso: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def foto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando foto: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def park_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando park: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def exit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando exit: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def modifica_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, targa, cognome, stanza, tipo_auto, numero_chiave FROM auto WHERE stato != "uscita" ORDER BY stanza')
        auto_list = cursor.fetchall()
        conn.close()
        
        if not auto_list:
            await update.message.reply_text("📋 *Nessuna auto da modificare*", parse_mode='Markdown')
            return
        
        keyboard = []
        for auto in auto_list:
            tipo_text = f" ({auto[4]})" if auto[4] else ""
            chiave_text = f" - Chiave: {auto[5]}" if auto[5] else ""
            keyboard.append([InlineKeyboardButton(
                f"Stanza {auto[3]} - {auto[1]} ({auto[2]}){tipo_text}{chiave_text}", 
                callback_data=f"modifica_{auto[0]}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("✏️ *MODIFICA AUTO*\n\nSeleziona l'auto da modificare:", 
                                       reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Errore comando modifica: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def conta_auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando conta_auto: {e}")
        await update.message.reply_text("❌ Errore durante il conteggio delle auto")

async def lista_auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
            
            try:
                conn_foto = sqlite3.connect('carvalet.db')
                cursor_foto = conn_foto.cursor()
                cursor_foto.execute('SELECT foto_count FROM auto WHERE targa = ? AND cognome = ? AND stanza = ?', (targa, cognome, stanza))
                foto_result = cursor_foto.fetchone()
                foto_count = foto_result[0] if foto_result and foto_result[0] > 0 else 0
                conn_foto.close()
            except:
                foto_count = 0
            
            chiave_text = f"Chiave: {chiave}" if chiave else "Chiave: --"
            sconto_text = " ✨ SCONTO" if giorni >= 10 else ""
            foto_text = f" 📷 {foto_count}" if foto_count > 0 else ""
            
            messaggio += f"{stanza} | {cognome} | {targa} | {chiave_text}{sconto_text}{foto_text}\n"
            if giorni >= 10:
                messaggio += f"     ({giorni} giorni)\n"
        
        await update.message.reply_text(messaggio, parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Errore comando lista_auto: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento della lista")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        state = context.user_data.get('state')
        text = update.message.text.strip()
        
        if text.lower() in ['/annulla', '/help', '/start']:
            if text.lower() == '/annulla':
                await annulla_command(update, context)
                return
            elif text.lower() == '/help':
                await help_command(update, context)
                return
            elif text.lower() == '/start':
                await start(update, context)
                return
        
        if state == 'ritiro_targa':
            targa = text.upper()
            if not validate_targa(targa):
                await update.message.reply_text("❌ *Formato targa non valido!*\n\nInserisci una targa nel formato: *XX123XX*\n(2 lettere + 3 numeri + 2 lettere)", parse_mode='Markdown')
                return
            
            context.user_data['targa'] = targa
            context.user_data['state'] = 'ritiro_cognome'
            await update.message.reply_text("👤 Inserisci il *COGNOME* del cliente:", parse_mode='Markdown')
        
        elif state == 'ritiro_cognome':
            if not validate_cognome(text):
                await update.message.reply_text("❌ *Cognome non valido!*\n\nUsa solo lettere, spazi e apostrofi:", parse_mode='Markdown')
                return
            
            context.user_data['cognome'] = text.strip()
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
            if text.lower() == 'skip':
                context.user_data['numero_chiave'] = None
                context.user_data['state'] = 'ritiro_note'
                await update.message.reply_text("📝 Inserisci eventuali *NOTE* (o scrivi 'skip' per saltare):", parse_mode='Markdown')
            else:
                try:
                    chiave = int(text)
                    if 0 <= chiave <= 999:
                        context.user_data['numero_chiave'] = chiave
                        context.user_data['state'] = 'ritiro_note'
                        await update.message.reply_text("📝 Inserisci eventuali *NOTE* (o scrivi 'skip' per saltare):", parse_mode='Markdown')
                    else:
                        await update.message.reply_text("❌ Numero chiave non valido! Inserisci un numero da 0 a 999 o 'skip':")
                except ValueError:
                    await update.message.reply_text("❌ Inserisci un numero valido per la chiave o 'skip':")
        
        elif state == 'ritiro_note':
            note = text if text.lower() != 'skip' else None
            
            targa = context.user_data['targa']
            cognome = context.user_data['cognome'] 
            stanza = context.user_data['stanza']
            tipo_auto = context.user_data.get('tipo_auto')
            numero_chiave = context.user_data.get('numero_chiave')
            
            try:
                conn = sqlite3.connect('carvalet.db')
                cursor = conn.cursor()
                cursor.execute('''INSERT INTO auto (targa, cognome, stanza, tipo_auto, numero_chiave, note) 
                                 VALUES (?, ?, ?, ?, ?, ?)''',
                              (targa, cognome, stanza, tipo_auto, numero_chiave, note))
                auto_id = cursor.lastrowid
                conn.commit()
                conn.close()
                
                context.user_data.clear()
                
                recap_msg = f"✅ *RICHIESTA CREATA!*\n\n🆔 ID: {auto_id}\n🚗 Targa: {targa}\n👤 Cliente: {cognome}\n🏨 Stanza: {stanza}"
                
                if tipo_auto:
                    recap_msg += f"\n🚗 Tipo: {tipo_auto}"
                if numero_chiave is not None:
                    recap_msg += f"\n🔑 Chiave: {numero_chiave}"
                if note:
                    recap_msg += f"\n📝 Note: {note}"
                
                recap_msg += f"\n\n📅 Richiesta del {datetime.now().strftime('%d/%m/%Y alle %H:%M')}"
                
                await update.message.reply_text(recap_msg, parse_mode='Markdown')
                
            except Exception as e:
                logging.error(f"Errore salvataggio richiesta: {e}")
                await update.message.reply_text("❌ Errore durante il salvataggio della richiesta")
                context.user_data.clear()
        
        elif state == 'upload_foto':
            if text.lower() == 'fine':
                auto_id = context.user_data.get('foto_auto_id')
                context.user_data.clear()
                
                if auto_id:
                    auto = get_auto_by_id(auto_id)
                    if auto:
                        await update.message.reply_text(f"📷 *Upload foto completato!*\n\n🚗 {auto[1]} - Stanza {auto[3]}", parse_mode='Markdown')
            else:
                await update.message.reply_text("📷 Invia le foto dell'auto (una o più foto). Scrivi 'fine' quando hai finito.")
        
        elif state.startswith('mod_'):
            parts = state.split('_')
            field = parts[1]
            auto_id = int(parts[2])
            
            if field == 'chiave':
                if text.lower() == 'rimuovi':
                    value = None
                else:
                    try:
                        value = int(text)
                        if not (0 <= value <= 999):
                            await update.message.reply_text("❌ Numero chiave non valido! Inserisci un numero da 0 a 999 o 'rimuovi':")
                            return
                    except ValueError:
                        await update.message.reply_text("❌ Inserisci un numero valido per la chiave o 'rimuovi':")
                        return
                
                if update_auto_field(auto_id, 'numero_chiave', value):
                    auto = get_auto_by_id(auto_id)
                    text_result = f"rimossa" if value is None else f"impostata a {value}"
                    await update.message.reply_text(f"✅ *Chiave {text_result}*\n\n🚗 {auto[1]} - Stanza {auto[3]}", parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ Errore durante l'aggiornamento")
                
                context.user_data.clear()
            
            elif field == 'note':
                if text.lower() == 'rimuovi':
                    value = None
                else:
                    value = text.strip()
                
                if update_auto_field(auto_id, 'note', value):
                    auto = get_auto_by_id(auto_id)
                    text_result = "rimosse" if value is None else "aggiornate"
                    await update.message.reply_text(f"✅ *Note {text_result}*\n\n🚗 {auto[1]} - Stanza {auto[3]}", parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ Errore durante l'aggiornamento")
                
                context.user_data.clear()
        
        else:
            await update.message.reply_text("❓ *Comando non riconosciuto*\n\nUsa `/help` per vedere tutti i comandi disponibili.", parse_mode='Markdown')
    
    except Exception as e:
        logging.error(f"Errore handle_message: {e}")
        await update.message.reply_text("❌ Si è verificato un errore durante l'elaborazione del messaggio")
        context.user_data.clear()

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('state') == 'upload_foto':
            auto_id = context.user_data.get('foto_auto_id')
            if auto_id:
                file_id = update.message.photo[-1].file_id
                
                conn = sqlite3.connect('carvalet.db')
                cursor = conn.cursor()
                cursor.execute('INSERT INTO foto (auto_id, file_id) VALUES (?, ?)', (auto_id, file_id))
                cursor.execute('UPDATE auto SET foto_count = foto_count + 1 WHERE id = ?', (auto_id,))
                conn.commit()
                
                cursor.execute('SELECT foto_count FROM auto WHERE id = ?', (auto_id,))
                foto_count = cursor.fetchone()[0]
                conn.close()
                
                await update.message.reply_text(f"📷 Foto #{foto_count} salvata! Invia altre foto o scrivi 'fine' per terminare.")
        else:
            await update.message.reply_text("📷 Per caricare foto, usa prima il comando /foto e seleziona un'auto")
    except Exception as e:
        logging.error(f"Errore handle_photo: {e}")
        await update.message.reply_text("❌ Errore durante il salvataggio della foto")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
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
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
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
            
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if update_auto_stato(auto_id, 'ritiro'):
                await query.edit_message_text(f"✅ *RITIRO AVVIATO!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n⏰ Tempo stimato: {minuti} minuti\n\n📅 {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
            else:
                await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('park_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if update_auto_stato(auto_id, 'parcheggiata'):
                await query.edit_message_text(f"🅿️ *AUTO PARCHEGGIATA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n📅 Inizio conteggio giorni\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
            else:
                await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('exit_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            giorni = calcola_giorni_parcheggio(auto[9]) if auto[9] else 0
            
            if update_auto_stato(auto_id, 'riconsegna'):
                sconto_text = " ✨ CON SCONTO" if giorni >= 10 else ""
                await query.edit_message_text(f"🚪 *AUTO IN RICONSEGNA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n📅 Parcheggiata {giorni} giorni{sconto_text}\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
            else:
                await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('riconsegna_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if auto[9]:
                giorni = calcola_giorni_parcheggio(auto[9])
                if update_auto_stato(auto_id, 'riconsegna', giorni):
                    sconto_text = " ✨ CON SCONTO" if giorni >= 10 else ""
                    await query.edit_message_text(f"🚚 *RICONSEGNA RICHIESTA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n📅 Parcheggiata {giorni} giorni{sconto_text}\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
                else:
                    await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('partenza_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if auto[9]:
                giorni = calcola_giorni_parcheggio(auto[9])
                if update_auto_stato(auto_id, 'uscita', giorni):
                    sconto_text = f" ({giorni} giorni" + (" - SCONTO ✨)" if giorni >= 10 else ")")
                    await query.edit_message_text(f"🏁 *PARTENZA CONFERMATA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}{sconto_text}\n✅ Auto uscita definitivamente\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
                else:
                    await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
            else:
                if update_auto_stato(auto_id, 'uscita'):
                    await query.edit_message_text(f"🏁 *PARTENZA CONFERMATA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n✅ Auto uscita definitivamente\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
                else:
                    await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('foto_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            context.user_data['state'] = 'upload_foto'
            context.user_data['foto_auto_id'] = auto_id
            
            await query.edit_message_text(f"📷 *CARICA FOTO*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n\nInvia le foto dell'auto (una o più). Scrivi 'fine' quando terminato.", parse_mode='Markdown')
        
        elif data.startswith('modifica_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            keyboard = [
                [InlineKeyboardButton("🚗 Modifica Tipo Auto", callback_data=f"mod_tipo_{auto_id}")],
                [InlineKeyboardButton("🔑 Modifica Chiave", callback_data=f"mod_chiave_{auto_id}")],
                [InlineKeyboardButton("📝 Modifica Note", callback_data=f"mod_note_{auto_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            tipo_text = f"\n🚗 Tipo: {auto[4]}" if auto[4] else "\n🚗 Tipo: Non specificato"
            chiave_text = f"\n🔑 Chiave: {auto[5]}" if auto[5] else "\n🔑 Chiave: Non assegnata"
            note_text = f"\n📝 Note: {auto[6]}" if auto[6] else "\n📝 Note: Nessuna"
            
            await query.edit_message_text(f"✏️ *MODIFICA AUTO*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}{tipo_text}{chiave_text}{note_text}\n\nCosa vuoi modificare?", 
                                        reply_markup=reply_markup, parse_mode='Markdown')
        
        elif data.startswith('mostra_foto_'):
            auto_id = int(data.split('_')[2])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            foto_list = get_foto_by_auto_id(auto_id)
            if not foto_list:
                await query.edit_message_text(f"📷 *Nessuna foto trovata*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}", parse_mode='Markdown')
                return
            
            await query.edit_message_text(f"📷 *FOTO AUTO*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n📊 Stato: {auto[7]}\n📷 Totale foto: {len(foto_list)}", parse_mode='Markdown')
            
            max_foto_per_invio = 10
            for i, foto in enumerate(foto_list):
                if i >= max_foto_per_invio:
                    await update.effective_chat.send_message(f"📷 Mostrate prime {max_foto_per_invio} foto di {len(foto_list)} totali.\nUsa di nuovo il comando per vedere le altre.")
                    break
                
                file_id, data_upload = foto
                try:
                    data_formattata = datetime.strptime(data_upload, '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
                    caption = f"📷 Foto #{i+1} - {data_formattata}"
                    
                    await update.effective_chat.send_photo(
                        photo=file_id,
                        caption=caption
                    )
                except Exception as e:
                    logging.error(f"Errore invio foto {file_id}: {e}")
                    await update.effective_chat.send_message(f"❌ Errore caricamento foto #{i+1}")
        
        elif data.startswith('mod_tipo_'):
            auto_id = int(data.split('_')[2])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            keyboard = [
                [InlineKeyboardButton("🚗 Compatta", callback_data=f"set_tipo_{auto_id}_compatta")],
                [InlineKeyboardButton("🚙 SUV", callback_data=f"set_tipo_{auto_id}_suv")],
                [InlineKeyboardButton("🔋 Elettrica", callback_data=f"set_tipo_{auto_id}_elettrica")],
                [InlineKeyboardButton("🚐 VAN", callback_data=f"set_tipo_{auto_id}_van")],
                [InlineKeyboardButton("🚚 Gancio traino", callback_data=f"set_tipo_{auto_id}_gancio")],
                [InlineKeyboardButton("💎 LUXURY", callback_data=f"set_tipo_{auto_id}_luxury")],
                [InlineKeyboardButton("❌ Rimuovi", callback_data=f"set_tipo_{auto_id}_rimuovi")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(f"🚗 *MODIFICA TIPO AUTO*\n\n{auto[1]} - Stanza {auto[3]}\nTipo attuale: {auto[4] or 'Non specificato'}\n\nSeleziona nuovo tipo:", 
                                        reply_markup=reply_markup, parse_mode='Markdown')
        
        elif data.startswith('set_tipo_'):
            parts = data.split('_')
            auto_id = int(parts[2])
            tipo = parts[3]
            
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if tipo == 'rimuovi':
                value = None
                text_result = "rimosso"
            else:
                tipo_map = {
                    'compatta': 'Compatta',
                    'suv': 'SUV',
                    'elettrica': 'Elettrica',
                    'van': 'VAN',
                    'gancio': 'Gancio traino',
                    'luxury': 'LUXURY'
                }
                value = tipo_map.get(tipo)
                text_result = f"impostato a {value}"
            
            if update_auto_field(auto_id, 'tipo_auto', value):
                await query.edit_message_text(f"✅ *Tipo auto {text_result}*\n\n🚗 {auto[1]} - Stanza {auto[3]}", parse_mode='Markdown')
            else:
                await query.edit_message_text("❌ Errore durante l'aggiornamento")
        
        elif data.startswith('mod_chiave_'):
            auto_id = int(data.split('_')[2])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            context.user_data['state'] = f'mod_chiave_{auto_id}'
            await query.edit_message_text(f"🔑 *MODIFICA CHIAVE*\n\n{auto[1]} - Stanza {auto[3]}\nChiave attuale: {auto[5] or 'Non assegnata'}\n\nInserisci nuovo numero chiave (0-999) o scrivi 'rimuovi':", parse_mode='Markdown')
        
        elif data.startswith('mod_note_'):
            auto_id = int(data.split('_')[2])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            context.user_data['state'] = f'mod_note_{auto_id}'
            await query.edit_message_text(f"📝 *MODIFICA NOTE*\n\n{auto[1]} - Stanza {auto[3]}\nNote attuali: {auto[6] or 'Nessuna'}\n\nInserisci nuove note o scrivi 'rimuovi':", parse_mode='Markdown')
    
    except Exception as e:
        logging.error(f"Errore handle_callback_query: {e}")
        await query.edit_message_text("❌ Errore durante l'elaborazione della richiesta")

def main():
    try:
        TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        if not TOKEN:
            logging.error("TELEGRAM_BOT_TOKEN non trovato nelle variabili d'ambiente")
            return
        
        application = Application.builder().token(TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("annulla", annulla_command))
        application.add_handler(CommandHandler("vedi_foto", vedi_foto_command))
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
        
        logging.info(f"🚗 {BOT_NAME} v{BOT_VERSION} avviato!")
        logging.info("✅ Sistema gestione auto hotel attivo")
        logging.info("🔧 v3.4: Aggiunto comando /vedi_foto con selezione auto, indicatori foto")
        
        print(f"🚗 {BOT_NAME} v{BOT_VERSION} avviato!")
        print("✅ Sistema gestione auto hotel attivo")
        print("🔧 v3.4: Aggiunto comando /vedi_foto con selezione auto, indicatori foto")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    
    except Exception as e:
        logging.error(f"Errore durante l'avvio del bot: {e}")
        print(f"❌ Errore durante l'avvio: {e}")

if __name__ == '__main__':
    main()
    
    return (bool(re.match(pattern_ita, targa)) or 
            bool(re.match(pattern_eu, targa)) or 
            bool(re.match(pattern_separatori, targa.replace(' ', '-'))))

def validate_cognome(cognome):
    """Valida cognome (solo lettere, spazi, apostrofi)"""
    pattern = r"^[A-Za-zÀ-ÿ\s']+$"
    return bool(re.match(pattern, cognome.strip()))

def get_foto_by_auto_id(auto_id):
    """Recupera tutte le foto di un'auto specifica"""
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        cursor.execute('SELECT file_id, data_upload FROM foto WHERE auto_id = ? ORDER BY data_upload', (auto_id,))
        result = cursor.fetchall()
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Errore lettura foto auto {auto_id}: {e}")
        return []

def get_auto_con_foto():
    """Recupera tutte le auto che hanno almeno una foto"""
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        cursor.execute('''SELECT DISTINCT a.id, a.targa, a.cognome, a.stanza, a.stato, a.foto_count 
                         FROM auto a 
                         INNER JOIN foto f ON a.id = f.auto_id 
                         WHERE a.foto_count > 0 
                         ORDER BY a.stanza''')
        result = cursor.fetchall()
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Errore lettura auto con foto: {e}")
        return []

def get_auto_by_id(auto_id):
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM auto WHERE id = ?', (auto_id,))
        result = cursor.fetchone()
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Errore lettura auto {auto_id}: {e}")
        return None

def update_auto_stato(auto_id, nuovo_stato, giorni=None):
    try:
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
        return True
    except Exception as e:
        logging.error(f"Errore aggiornamento stato auto {auto_id}: {e}")
        return False

def update_auto_field(auto_id, field, value):
    """Aggiorna un campo specifico dell'auto"""
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        
        query = f'UPDATE auto SET {field} = ? WHERE id = ?'
        cursor.execute(query, (value, auto_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Errore aggiornamento campo {field} per auto {auto_id}: {e}")
        return False

def calcola_giorni_parcheggio(data_park):
    if not data_park:
        return 0
    try:
        oggi = date.today()
        if isinstance(data_park, str):
            data_park = datetime.strptime(data_park, '%Y-%m-%d').date()
        giorni = (oggi - data_park).days + 1
        return max(1, giorni)
    except Exception as e:
        logging.error(f"Errore calcolo giorni: {e}")
        return 0

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
• `/vedi_foto` - Visualizza foto auto
• `/park` - Conferma auto parcheggiata
• `/exit` - Auto in riconsegna
• `/modifica` - Modifica dati auto

📊 *COMANDI STATISTICHE:*
• `/conta_auto` - Conteggio giornaliero
• `/lista_auto` - Auto in parcheggio

❓ *COMANDI AIUTO:*
• `/help` - Mostra questa guida
• `/annulla` - Annulla operazione in corso

💡 *TIPI AUTO:* Compatta, SUV, Elettrica, VAN, Gancio traino, LUXURY
🔑 *NUMERI:* Stanze e chiavi da 0 a 999"""

    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help - Mostra la guida completa"""
    help_msg = f"""🚗 *{BOT_NAME} v{BOT_VERSION} - GUIDA COMPLETA*

🏨 *COMANDI HOTEL:*
• `/ritiro` - Crea nuova richiesta ritiro auto
• `/riconsegna` - Seleziona auto da riconsegnare
• `/partenza` - Conferma partenza definitiva

🚗 *COMANDI VALET:*
• `/incorso` - Inizia ritiro auto richiesta
• `/foto` - Carica foto dell'auto
• `/vedi_foto` - Visualizza foto per auto/cliente
• `/park` - Conferma auto parcheggiata
• `/exit` - Metti auto in riconsegna
• `/modifica` - Modifica dati auto esistente

📊 *COMANDI STATISTICHE:*
• `/conta_auto` - Statistiche giornaliere
• `/lista_auto` - Elenco auto parcheggiate

❓ *COMANDI AIUTO:*
• `/start` - Messaggio di benvenuto
• `/help` - Questa guida
• `/annulla` - Annulla operazione in corso

📋 *WORKFLOW TIPICO:*
1️⃣ Hotel: `/ritiro` (inserisci targa, cognome, stanza)
2️⃣ Valet: `/incorso` (seleziona auto e tempo)
3️⃣ Valet: `/park` (conferma parcheggio)
4️⃣ Hotel: `/riconsegna` (richiesta riconsegna)
5️⃣ Hotel: `/partenza` (conferma uscita)

🎯 *STATI AUTO:*
• *richiesta* - Appena creata
• *ritiro* - Valet sta ritirando
• *parcheggiata* - In parcheggio
• *riconsegna* - In attesa riconsegna
• *uscita* - Partita definitivamente

💡 *TIPI AUTO:* Compatta, SUV, Elettrica, VAN, Gancio traino, LUXURY
🔑 *RANGE NUMERI:* Stanze e chiavi da 0 a 999
✨ *SCONTO AUTOMATICO:* Dopo 10+ giorni di parcheggio"""

    await update.message.reply_text(help_msg, parse_mode='Markdown')

async def annulla_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /annulla - Annulla operazione in corso"""
    current_state = context.user_data.get('state')
    
    if current_state:
        if current_state.startswith('ritiro_'):
            operazione = "registrazione auto"
        elif current_state == 'upload_foto':
            operazione = "caricamento foto"
        elif current_state.startswith('mod_'):
            operazione = "modifica auto"
        else:
            operazione = "operazione"
        
        context.user_data.clear()
        await update.message.reply_text(f"❌ *{operazione.title()} annullata*\n\nPuoi iniziare una nuova operazione quando vuoi.", parse_mode='Markdown')
    else:
        await update.message.reply_text("ℹ️ *Nessuna operazione in corso*\n\nUsa `/help` per vedere tutti i comandi disponibili.", parse_mode='Markdown')

async def vedi_foto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /vedi_foto - Mostra foto per auto specifica"""
    try:
        auto_con_foto = get_auto_con_foto()
        
        if not auto_con_foto:
            await update.message.reply_text("📷 *Nessuna foto disponibile*\n\nNon ci sono auto con foto caricate.", parse_mode='Markdown')
            return
        
        stati_order = ['parcheggiata', 'riconsegna', 'ritiro', 'richiesta', 'uscita']
        auto_per_stato = {}
        
        for auto in auto_con_foto:
            stato = auto[4]
            if stato not in auto_per_stato:
                auto_per_stato[stato] = []
            auto_per_stato[stato].append(auto)
        
        keyboard = []
        
        for stato in stati_order:
            if stato in auto_per_stato:
                if stato == 'parcheggiata':
                    emoji_stato = "🅿️"
                elif stato == 'riconsegna':
                    emoji_stato = "🚪"
                elif stato == 'ritiro':
                    emoji_stato = "⚙️"
                elif stato == 'richiesta':
                    emoji_stato = "📋"
                else:
                    emoji_stato = "🏁"
                
                for auto in auto_per_stato[stato]:
                    id_auto, targa, cognome, stanza, _, foto_count = auto
                    keyboard.append([InlineKeyboardButton(
                        f"{emoji_stato} Stanza {stanza} - {targa} ({cognome}) - 📷 {foto_count} foto", 
                        callback_data=f"mostra_foto_{id_auto}"
                    )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📷 *VISUALIZZA FOTO AUTO*\n\nSeleziona l'auto per vedere le sue foto:", 
                                       reply_markup=reply_markup, parse_mode='Markdown')
    
    except Exception as e:
        logging.error(f"Errore comando vedi_foto: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto con foto")

async def ritiro_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['state'] = 'ritiro_targa'
    await update.message.reply_text("🚗 *RITIRO AUTO*\n\nInserisci la *TARGA* del veicolo (formato: XX123XX):", parse_mode='Markdown')

async def riconsegna_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando riconsegna: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def partenza_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando partenza: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def incorso_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando incorso: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def foto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando foto: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def park_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando park: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def exit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando exit: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def modifica_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = sqlite3.connect('carvalet.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, targa, cognome, stanza, tipo_auto, numero_chiave FROM auto WHERE stato != "uscita" ORDER BY stanza')
        auto_list = cursor.fetchall()
        conn.close()
        
        if not auto_list:
            await update.message.reply_text("📋 *Nessuna auto da modificare*", parse_mode='Markdown')
            return
        
        keyboard = []
        for auto in auto_list:
            tipo_text = f" ({auto[4]})" if auto[4] else ""
            chiave_text = f" - Chiave: {auto[5]}" if auto[5] else ""
            keyboard.append([InlineKeyboardButton(
                f"Stanza {auto[3]} - {auto[1]} ({auto[2]}){tipo_text}{chiave_text}", 
                callback_data=f"modifica_{auto[0]}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("✏️ *MODIFICA AUTO*\n\nSeleziona l'auto da modificare:", 
                                       reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Errore comando modifica: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def conta_auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
    except Exception as e:
        logging.error(f"Errore comando conta_auto: {e}")
        await update.message.reply_text("❌ Errore durante il conteggio delle auto")

async def lista_auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
            
            try:
                conn_foto = sqlite3.connect('carvalet.db')
                cursor_foto = conn_foto.cursor()
                cursor_foto.execute('SELECT foto_count FROM auto WHERE targa = ? AND cognome = ? AND stanza = ?', (targa, cognome, stanza))
                foto_result = cursor_foto.fetchone()
                foto_count = foto_result[0] if foto_result and foto_result[0] > 0 else 0
                conn_foto.close()
            except:
                foto_count = 0
            
            chiave_text = f"Chiave: {chiave}" if chiave else "Chiave: --"
            sconto_text = " ✨ SCONTO" if giorni >= 10 else ""
            foto_text = f" 📷 {foto_count}" if foto_count > 0 else ""
            
            messaggio += f"{stanza} | {cognome} | {targa} | {chiave_text}{sconto_text}{foto_text}\n"
            if giorni >= 10:
                messaggio += f"     ({giorni} giorni)\n"
        
        await update.message.reply_text(messaggio, parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Errore comando lista_auto: {e}")
        await update.message.reply_text("❌ Errore durante il caricamento della lista")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        state = context.user_data.get('state')
        text = update.message.text.strip()
        
        if text.lower() in ['/annulla', '/help', '/start']:
            if text.lower() == '/annulla':
                await annulla_command(update, context)
                return
            elif text.lower() == '/help':
                await help_command(update, context)
                return
            elif text.lower() == '/start':
                await start(update, context)
                return
        
        if state == 'ritiro_targa':
            targa = text.upper()
            if not validate_targa(targa):
                await update.message.reply_text("❌ *Formato targa non valido!*\n\nInserisci una targa nel formato: *XX123XX*\n(2 lettere + 3 numeri + 2 lettere)", parse_mode='Markdown')
                return
            
            context.user_data['targa'] = targa
            context.user_data['state'] = 'ritiro_cognome'
            await update.message.reply_text("👤 Inserisci il *COGNOME* del cliente:", parse_mode='Markdown')
        
        elif state == 'ritiro_cognome':
            if not validate_cognome(text):
                await update.message.reply_text("❌ *Cognome non valido!*\n\nUsa solo lettere, spazi e apostrofi:", parse_mode='Markdown')
                return
            
            context.user_data['cognome'] = text.strip()
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
            if text.lower() == 'skip':
                context.user_data['numero_chiave'] = None
                context.user_data['state'] = 'ritiro_note'
                await update.message.reply_text("📝 Inserisci eventuali *NOTE* (o scrivi 'skip' per saltare):", parse_mode='Markdown')
            else:
                try:
                    chiave = int(text)
                    if 0 <= chiave <= 999:
                        context.user_data['numero_chiave'] = chiave
                        context.user_data['state'] = 'ritiro_note'
                        await update.message.reply_text("📝 Inserisci eventuali *NOTE* (o scrivi 'skip' per saltare):", parse_mode='Markdown')
                    else:
                        await update.message.reply_text("❌ Numero chiave non valido! Inserisci un numero da 0 a 999 o 'skip':")
                except ValueError:
                    await update.message.reply_text("❌ Inserisci un numero valido per la chiave o 'skip':")
        
        elif state == 'ritiro_note':
            note = text if text.lower() != 'skip' else None
            
            targa = context.user_data['targa']
            cognome = context.user_data['cognome'] 
            stanza = context.user_data['stanza']
            tipo_auto = context.user_data.get('tipo_auto')
            numero_chiave = context.user_data.get('numero_chiave')
            
            try:
                conn = sqlite3.connect('carvalet.db')
                cursor = conn.cursor()
                cursor.execute('''INSERT INTO auto (targa, cognome, stanza, tipo_auto, numero_chiave, note) 
                                 VALUES (?, ?, ?, ?, ?, ?)''',
                              (targa, cognome, stanza, tipo_auto, numero_chiave, note))
                auto_id = cursor.lastrowid
                conn.commit()
                conn.close()
                
                context.user_data.clear()
                
                recap_msg = f"✅ *RICHIESTA CREATA!*\n\n🆔 ID: {auto_id}\n🚗 Targa: {targa}\n👤 Cliente: {cognome}\n🏨 Stanza: {stanza}"
                
                if tipo_auto:
                    recap_msg += f"\n🚗 Tipo: {tipo_auto}"
                if numero_chiave is not None:
                    recap_msg += f"\n🔑 Chiave: {numero_chiave}"
                if note:
                    recap_msg += f"\n📝 Note: {note}"
                
                recap_msg += f"\n\n📅 Richiesta del {datetime.now().strftime('%d/%m/%Y alle %H:%M')}"
                
                await update.message.reply_text(recap_msg, parse_mode='Markdown')
                
            except Exception as e:
                logging.error(f"Errore salvataggio richiesta: {e}")
                await update.message.reply_text("❌ Errore durante il salvataggio della richiesta")
                context.user_data.clear()
        
        elif state == 'upload_foto':
            if text.lower() == 'fine':
                auto_id = context.user_data.get('foto_auto_id')
                context.user_data.clear()
                
                if auto_id:
                    auto = get_auto_by_id(auto_id)
                    if auto:
                        await update.message.reply_text(f"📷 *Upload foto completato!*\n\n🚗 {auto[1]} - Stanza {auto[3]}", parse_mode='Markdown')
            else:
                await update.message.reply_text("📷 Invia le foto dell'auto (una o più foto). Scrivi 'fine' quando hai finito.")
        
        elif state.startswith('mod_'):
            parts = state.split('_')
            field = parts[1]
            auto_id = int(parts[2])
            
            if field == 'chiave':
                if text.lower() == 'rimuovi':
                    value = None
                else:
                    try:
                        value = int(text)
                        if not (0 <= value <= 999):
                            await update.message.reply_text("❌ Numero chiave non valido! Inserisci un numero da 0 a 999 o 'rimuovi':")
                            return
                    except ValueError:
                        await update.message.reply_text("❌ Inserisci un numero valido per la chiave o 'rimuovi':")
                        return
                
                if update_auto_field(auto_id, 'numero_chiave', value):
                    auto = get_auto_by_id(auto_id)
                    text_result = f"rimossa" if value is None else f"impostata a {value}"
                    await update.message.reply_text(f"✅ *Chiave {text_result}*\n\n🚗 {auto[1]} - Stanza {auto[3]}", parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ Errore durante l'aggiornamento")
                
                context.user_data.clear()
            
            elif field == 'note':
                if text.lower() == 'rimuovi':
                    value = None
                else:
                    value = text.strip()
                
                if update_auto_field(auto_id, 'note', value):
                    auto = get_auto_by_id(auto_id)
                    text_result = "rimosse" if value is None else "aggiornate"
                    await update.message.reply_text(f"✅ *Note {text_result}*\n\n🚗 {auto[1]} - Stanza {auto[3]}", parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ Errore durante l'aggiornamento")
                
                context.user_data.clear()
        
        else:
            await update.message.reply_text("❓ *Comando non riconosciuto*\n\nUsa `/help` per vedere tutti i comandi disponibili.", parse_mode='Markdown')
    
    except Exception as e:
        logging.error(f"Errore handle_message: {e}")
        await update.message.reply_text("❌ Si è verificato un errore durante l'elaborazione del messaggio")
        context.user_data.clear()

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.user_data.get('state') == 'upload_foto':
            auto_id = context.user_data.get('foto_auto_id')
            if auto_id:
                file_id = update.message.photo[-1].file_id
                
                conn = sqlite3.connect('carvalet.db')
                cursor = conn.cursor()
                cursor.execute('INSERT INTO foto (auto_id, file_id) VALUES (?, ?)', (auto_id, file_id))
                cursor.execute('UPDATE auto SET foto_count = foto_count + 1 WHERE id = ?', (auto_id,))
                conn.commit()
                
                cursor.execute('SELECT foto_count FROM auto WHERE id = ?', (auto_id,))
                foto_count = cursor.fetchone()[0]
                conn.close()
                
                await update.message.reply_text(f"📷 Foto #{foto_count} salvata! Invia altre foto o scrivi 'fine' per terminare.")
        else:
            await update.message.reply_text("📷 Per caricare foto, usa prima il comando /foto e seleziona un'auto")
    except Exception as e:
        logging.error(f"Errore handle_photo: {e}")
        await update.message.reply_text("❌ Errore durante il salvataggio della foto")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
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
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
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
            
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if update_auto_stato(auto_id, 'ritiro'):
                await query.edit_message_text(f"✅ *RITIRO AVVIATO!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n⏰ Tempo stimato: {minuti} minuti\n\n📅 {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
            else:
                await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('park_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if update_auto_stato(auto_id, 'parcheggiata'):
                await query.edit_message_text(f"🅿️ *AUTO PARCHEGGIATA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n📅 Inizio conteggio giorni\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
            else:
                await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('exit_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            giorni = calcola_giorni_parcheggio(auto[9]) if auto[9] else 0
            
            if update_auto_stato(auto_id, 'riconsegna'):
                sconto_text = " ✨ CON SCONTO" if giorni >= 10 else ""
                await query.edit_message_text(f"🚪 *AUTO IN RICONSEGNA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n📅 Parcheggiata {giorni} giorni{sconto_text}\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
            else:
                await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('riconsegna_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if auto[9]:
                giorni = calcola_giorni_parcheggio(auto[9])
                if update_auto_stato(auto_id, 'riconsegna', giorni):
                    sconto_text = " ✨ CON SCONTO" if giorni >= 10 else ""
                    await query.edit_message_text(f"🚚 *RICONSEGNA RICHIESTA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n📅 Parcheggiata {giorni} giorni{sconto_text}\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
                else:
                    await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('partenza_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if auto[9]:
                giorni = calcola_giorni_parcheggio(auto[9])
                if update_auto_stato(auto_id, 'uscita', giorni):
                    sconto_text = f" ({giorni} giorni" + (" - SCONTO ✨)" if giorni >= 10 else ")")
                    await query.edit_message_text(f"🏁 *PARTENZA CONFERMATA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}{sconto_text}\n✅ Auto uscita definitivamente\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
                else:
                    await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
            else:
                if update_auto_stato(auto_id, 'uscita'):
                    await query.edit_message_text(f"🏁 *PARTENZA CONFERMATA!*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n✅ Auto uscita definitivamente\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}", parse_mode='Markdown')
                else:
                    await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
        
        elif data.startswith('foto_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            context.user_data['state'] = 'upload_foto'
            context.user_data['foto_auto_id'] = auto_id
            
            await query.edit_message_text(f"📷 *CARICA FOTO*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n\nInvia le foto dell'auto (una o più). Scrivi 'fine' quando terminato.", parse_mode='Markdown')
        
        elif data.startswith('modifica_'):
            auto_id = int(data.split('_')[1])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            keyboard = [
                [InlineKeyboardButton("🚗 Modifica Tipo Auto", callback_data=f"mod_tipo_{auto_id}")],
                [InlineKeyboardButton("🔑 Modifica Chiave", callback_data=f"mod_chiave_{auto_id}")],
                [InlineKeyboardButton("📝 Modifica Note", callback_data=f"mod_note_{auto_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            tipo_text = f"\n🚗 Tipo: {auto[4]}" if auto[4] else "\n🚗 Tipo: Non specificato"
            chiave_text = f"\n🔑 Chiave: {auto[5]}" if auto[5] else "\n🔑 Chiave: Non assegnata"
            note_text = f"\n📝 Note: {auto[6]}" if auto[6] else "\n📝 Note: Nessuna"
            
            await query.edit_message_text(f"✏️ *MODIFICA AUTO*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}{tipo_text}{chiave_text}{note_text}\n\nCosa vuoi modificare?", 
                                        reply_markup=reply_markup, parse_mode='Markdown')
        
        elif data.startswith('mostra_foto_'):
            auto_id = int(data.split('_')[2])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            foto_list = get_foto_by_auto_id(auto_id)
            if not foto_list:
                await query.edit_message_text(f"📷 *Nessuna foto trovata*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}", parse_mode='Markdown')
                return
            
            await query.edit_message_text(f"📷 *FOTO AUTO*\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n📊 Stato: {auto[7]}\n📷 Totale foto: {len(foto_list)}", parse_mode='Markdown')
            
            max_foto_per_invio = 10
            for i, foto in enumerate(foto_list):
                if i >= max_foto_per_invio:
                    await update.effective_chat.send_message(f"📷 Mostrate prime {max_foto_per_invio} foto di {len(foto_list)} totali.\nUsa di nuovo il comando per vedere le altre.")
                    break
                
                file_id, data_upload = foto
                try:
                    data_formattata = datetime.strptime(data_upload, '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
                    caption = f"📷 Foto #{i+1} - {data_formattata}"
                    
                    await update.effective_chat.send_photo(
                        photo=file_id,
                        caption=caption
                    )
                except Exception as e:
                    logging.error(f"Errore invio foto {file_id}: {e}")
                    await update.effective_chat.send_message(f"❌ Errore caricamento foto #{i+1}")
        
        elif data.startswith('mod_tipo_'):
            auto_id = int(data.split('_')[2])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            keyboard = [
                [InlineKeyboardButton("🚗 Compatta", callback_data=f"set_tipo_{auto_id}_compatta")],
                [InlineKeyboardButton("🚙 SUV", callback_data=f"set_tipo_{auto_id}_suv")],
                [InlineKeyboardButton("🔋 Elettrica", callback_data=f"set_tipo_{auto_id}_elettrica")],
                [InlineKeyboardButton("🚐 VAN", callback_data=f"set_tipo_{auto_id}_van")],
                [InlineKeyboardButton("🚚 Gancio traino", callback_data=f"set_tipo_{auto_id}_gancio")],
                [InlineKeyboardButton("💎 LUXURY", callback_data=f"set_tipo_{auto_id}_luxury")],
                [InlineKeyboardButton("❌ Rimuovi", callback_data=f"set_tipo_{auto_id}_rimuovi")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(f"🚗 *MODIFICA TIPO AUTO*\n\n{auto[1]} - Stanza {auto[3]}\nTipo attuale: {auto[4] or 'Non specificato'}\n\nSeleziona nuovo tipo:", 
                                        reply_markup=reply_markup, parse_mode='Markdown')
        
        elif data.startswith('set_tipo_'):
            parts = data.split('_')
            auto_id = int(parts[2])
            tipo = parts[3]
            
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            if tipo == 'rimuovi':
                value = None
                text_result = "rimosso"
            else:
                tipo_map = {
                    'compatta': 'Compatta',
                    'suv': 'SUV',
                    'elettrica': 'Elettrica',
                    'van': 'VAN',
                    'gancio': 'Gancio traino',
                    'luxury': 'LUXURY'
                }
                value = tipo_map.get(tipo)
                text_result = f"impostato a {value}"
            
            if update_auto_field(auto_id, 'tipo_auto', value):
                await query.edit_message_text(f"✅ *Tipo auto {text_result}*\n\n🚗 {auto[1]} - Stanza {auto[3]}", parse_mode='Markdown')
            else:
                await query.edit_message_text("❌ Errore durante l'aggiornamento")
        
        elif data.startswith('mod_chiave_'):
            auto_id = int(data.split('_')[2])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            context.user_data['state'] = f'mod_chiave_{auto_id}'
            await query.edit_message_text(f"🔑 *MODIFICA CHIAVE*\n\n{auto[1]} - Stanza {auto[3]}\nChiave attuale: {auto[5] or 'Non assegnata'}\n\nInserisci nuovo numero chiave (0-999) o scrivi 'rimuovi':", parse_mode='Markdown')
        
        elif data.startswith('mod_note_'):
            auto_id = int(data.split('_')[2])
            auto = get_auto_by_id(auto_id)
            if not auto:
                await query.edit_message_text("❌ Auto non trovata")
                return
            
            context.user_data['state'] = f'mod_note_{auto_id}'
            await query.edit_message_text(f"📝 *MODIFICA NOTE*\n\n{auto[1]} - Stanza {auto[3]}\nNote attuali: {auto[6] or 'Nessuna'}\n\nInserisci nuove note o scrivi 'rimuovi':", parse_mode='Markdown')
    
    except Exception as e:
        logging.error(f"Errore handle_callback_query: {e}")
        await query.edit_message_text("❌ Errore durante l'elaborazione della richiesta")

def main():
    try:
        TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        if not TOKEN:
            logging.error("TELEGRAM_BOT_TOKEN non trovato nelle variabili d'ambiente")
            return
        
        application = Application.builder().token(TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("annulla", annulla_command))
        application.add_handler(CommandHandler("vedi_foto", vedi_foto_command))
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
        
        logging.info(f"🚗 {BOT_NAME} v{BOT_VERSION} avviato!")
        logging.info("✅ Sistema gestione auto hotel attivo")
        logging.info("🔧 v3.4: Aggiunto comando /vedi_foto con selezione auto, indicatori foto")
        
        print(f"🚗 {BOT_NAME} v{BOT_VERSION} avviato!")
        print("✅ Sistema gestione auto hotel attivo")
        print("🔧 v3.4: Aggiunto comando /vedi_foto con selezione auto, indicatori foto")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    
    except Exception as e:
        logging.error(f"Errore durante l'avvio del bot: {e}")
        print(f"❌ Errore durante l'avvio: {e}")

if __name__ == '__main__':
    main()
