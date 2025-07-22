#!/usr/bin/env python3
# CarValetBOT v5.05 by Zibroncloud - BASATO SU v29 FUNZIONANTE + DATABASE SEMPLIFICATO
import os,logging,sqlite3,re
from datetime import datetime,date,timedelta
from telegram import Update,InlineKeyboardButton,InlineKeyboardMarkup
from telegram.ext import Application,CommandHandler,MessageHandler,filters,ContextTypes,CallbackQueryHandler

BOT_VERSION="5.05"
BOT_NAME="CarValetBOT"
CANALE_VALET="-1002582736358"

logging.basicConfig(format='%(asctime)s-%(levelname)s-%(message)s',level=logging.INFO)

# Fuso orario italiano (dalla v29 funzionante)
def now_italy():
    """Restituisce datetime corrente in fuso orario italiano (UTC+1/+2)"""
    utc_now = datetime.utcnow()
    italy_offset = 2 if utc_now.month >= 3 and utc_now.month <= 10 else 1
    return utc_now + timedelta(hours=italy_offset)

# ===== DATABASE SEMPLIFICATO =====
def init_db():
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  # DATABASE SEMPLIFICATO - solo essenziale
  cursor.execute('''CREATE TABLE IF NOT EXISTS auto (
   id INTEGER PRIMARY KEY AUTOINCREMENT,
   cognome TEXT NOT NULL,
   targa TEXT NOT NULL, 
   stanza INTEGER NOT NULL,
   stato TEXT DEFAULT 'richiesta',
   data_arrivo DATE DEFAULT CURRENT_DATE,
   data_partenza DATE,
   is_ghost INTEGER DEFAULT 0
  )''')
  # Tabelle foto e servizi mantenute (servono!)
  cursor.execute('''CREATE TABLE IF NOT EXISTS foto (
   id INTEGER PRIMARY KEY AUTOINCREMENT,
   auto_id INTEGER,
   file_id TEXT NOT NULL,
   data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
   FOREIGN KEY (auto_id) REFERENCES auto (id)
  )''')
  cursor.execute('''CREATE TABLE IF NOT EXISTS servizi_extra (
   id INTEGER PRIMARY KEY AUTOINCREMENT,
   auto_id INTEGER,
   tipo_servizio TEXT NOT NULL,
   data_servizio DATE DEFAULT CURRENT_DATE,
   FOREIGN KEY (auto_id) REFERENCES auto (id)
  )''')
  conn.commit()
  conn.close()
  logging.info("Database semplificato inizializzato")
 except Exception as e:logging.error(f"Errore DB: {e}")

def db_query(query,params=(),fetch='all'):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute(query,params)
  if fetch=='one':result=cursor.fetchone()
  elif fetch=='all':result=cursor.fetchall()
  elif fetch=='none':result=cursor.rowcount;conn.commit()
  else:result=cursor.lastrowid;conn.commit()
  conn.close()
  return result
 except Exception as e:logging.error(f"DB Error: {e}");return None if fetch!='none' else 0

def get_auto_by_id(auto_id):
 return db_query('SELECT * FROM auto WHERE id=?',(auto_id,),'one')

def get_prossimo_numero():
 # Semplificato - conto auto di oggi
 oggi=now_italy().date().strftime('%Y-%m-%d')
 count=db_query('SELECT COUNT(*) FROM auto WHERE date(data_arrivo)=? AND is_ghost=0',(oggi,),'one')
 return (count[0] if count else 0) + 1

def genera_targa_hotel():
 oggi=now_italy().date().strftime('%Y-%m-%d')
 count=db_query('SELECT COUNT(*) FROM auto WHERE date(data_arrivo)=? AND targa LIKE "HOTEL%"',(oggi,),'one')
 return f"HOTEL{(count[0] if count else 0)+1:03d}"

# ===== VALIDAZIONE =====
def validate_targa(targa):
 targa=targa.upper().strip()
 patterns=[r'^[A-Z]{2}[0-9]{3}[A-Z]{2}$',r'^[A-Z0-9]{4,10}$']
 return any(re.match(p,targa.replace(' ','-'))for p in patterns)

def validate_cognome(cognome):
 return bool(re.match(r"^[A-Za-zÀ-ÿ\s']+$",cognome.strip()))

# ===== NOTIFICHE (dalla v29 funzionante) =====
async def invia_notifica_canale(context:ContextTypes.DEFAULT_TYPE,auto_id,cognome,stanza,numero):
 try:
  msg=f"🚗 NUOVA RICHIESTA RITIRO!\n\n👤 Cliente: {cognome}\n🏨 Stanza: {stanza}\n🔢 Numero: #{numero}\n📅 {now_italy().strftime('%d/%m/%Y alle %H:%M')}"
  keyboard=[[InlineKeyboardButton("⚙️ Gestisci Richiesta",url=f"https://t.me/{context.bot.username}?start=recupero_{auto_id}")]]
  await context.bot.send_message(chat_id=CANALE_VALET,text=msg,reply_markup=InlineKeyboardMarkup(keyboard))
  return True
 except Exception as e:logging.error(f"Errore notifica: {e}");return False

# ===== COMANDI PRINCIPALI =====
init_db()

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
 # Deep link handling semplificato
 if context.args and len(context.args)>0:
  arg=context.args[0]
  if arg.startswith('recupero_'):
   try:
    auto_id=int(arg.split('_')[1])
    auto=get_auto_by_id(auto_id)
    if auto and auto[4]=='richiesta':  # stato in posizione 4
     await handle_recupero_deep_link(update,context,auto_id)
     return
   except:pass
 
 msg=f"""🚗 {BOT_NAME} v{BOT_VERSION} - SEMPLIFICATO
By Zibroncloud

🏨 HOTEL:
/ritiro - Cognome + Stanza → Automatico!

🚗 VALET:
/recupero - Gestisci recuperi
/park - Auto parcheggiata
/partito - Uscita definitiva

🔧 EXTRA:
/foto - Carica foto
/vedi_foto - Vedi foto auto
/servizi - Servizi extra
/ghostcar - Auto staff
/lista_auto - Statistiche

❓ /help /annulla"""
 await update.message.reply_text(msg)

async def help_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 msg=f"""🚗 {BOT_NAME} v{BOT_VERSION} - GUIDA

🆕 v5.05: Database semplificato, meno errori!

🏨 HOTEL (SUPER VELOCE):
/ritiro → Cognome + Stanza → Automatico:
  📱 Notifica canale Valet
  🚗 Targa HOTEL001, HOTEL002...

🚗 VALET (PRINCIPALI):
/recupero - Lista tutti i recuperi
/park - Conferma parcheggio
/partito - Uscita definitiva

🔧 FUNZIONI EXTRA:
/foto - Carica foto auto
/vedi_foto - Visualizza foto
/servizi - Aggiungi servizi extra
/ghostcar - Registra auto staff
/lista_auto - Statistiche giornaliere

📱 WORKFLOW: Hotel /ritiro → Notifica canale → Valet recupero → /park → /partito"""
 await update.message.reply_text(msg)

# HOTEL COMMANDS
async def ritiro_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 context.user_data.clear()
 context.user_data['state']='ritiro_cognome'
 await update.message.reply_text("🚗 RITIRO HOTEL\n\n👤 Inserisci il COGNOME del cliente:")

# VALET COMMANDS  
async def recupero_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 auto_list=db_query('SELECT id,cognome,targa,stanza FROM auto WHERE stato="richiesta" ORDER BY data_arrivo,id')
 if not auto_list:await update.message.reply_text("📋 Nessun recupero da gestire");return
 keyboard=[]
 for auto in auto_list:
  ghost_text=" 👻" if len(auto)>4 and auto[4] else ""  # check is_ghost se presente
  keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[2]} ({auto[1]}){ghost_text}",callback_data=f"recupero_{auto[0]}")])
 await update.message.reply_text("⚙️ GESTIONE RECUPERI\n\nSeleziona recupero:",reply_markup=InlineKeyboardMarkup(keyboard))

async def park_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 auto_list=db_query('SELECT id,cognome,targa,stanza FROM auto WHERE stato="ritiro" ORDER BY stanza')
 if not auto_list:await update.message.reply_text("📋 Nessuna auto in ritiro");return
 keyboard=[]
 for auto in auto_list:
  keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[2]} ({auto[1]})",callback_data=f"park_{auto[0]}")])
 await update.message.reply_text("🅿️ CONFERMA PARCHEGGIO\n\nSeleziona auto:",reply_markup=InlineKeyboardMarkup(keyboard))

async def partito_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 auto_list=db_query('SELECT id,cognome,targa,stanza FROM auto WHERE stato IN ("ritiro","parcheggiata") ORDER BY stanza')
 if not auto_list:await update.message.reply_text("📋 Nessuna auto disponibile");return
 keyboard=[]
 for auto in auto_list:
  keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[2]} ({auto[1]})",callback_data=f"partito_{auto[0]}")])
 await update.message.reply_text("🏁 USCITA DEFINITIVA\n\nSeleziona auto:",reply_markup=InlineKeyboardMarkup(keyboard))

async def foto_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 auto_list=db_query('SELECT id,cognome,targa,stanza FROM auto WHERE stato IN ("ritiro","parcheggiata") ORDER BY stanza')
 if not auto_list:await update.message.reply_text("📋 Nessuna auto disponibile");return
 keyboard=[]
 for auto in auto_list:
  keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[2]} ({auto[1]})",callback_data=f"foto_{auto[0]}")])
 await update.message.reply_text("📷 CARICA FOTO\n\nSeleziona auto:",reply_markup=InlineKeyboardMarkup(keyboard))

async def vedi_foto_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 auto_con_foto=db_query('SELECT DISTINCT a.id,a.cognome,a.targa,a.stanza FROM auto a INNER JOIN foto f ON a.id=f.auto_id ORDER BY a.stanza')
 if not auto_con_foto:await update.message.reply_text("📷 Nessuna foto disponibile");return
 keyboard=[]
 for auto in auto_con_foto:
  foto_count=db_query('SELECT COUNT(*) FROM foto WHERE auto_id=?',(auto[0],),'one')[0]
  keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[2]} ({auto[1]}) - 📷 {foto_count}",callback_data=f"mostra_foto_{auto[0]}")])
 await update.message.reply_text("📷 VISUALIZZA FOTO\n\nSeleziona auto:",reply_markup=InlineKeyboardMarkup(keyboard))

async def servizi_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 auto_list=db_query('SELECT id,cognome,targa,stanza FROM auto WHERE stato="parcheggiata" ORDER BY stanza')
 if not auto_list:await update.message.reply_text("📋 Nessuna auto parcheggiata");return
 keyboard=[]
 for auto in auto_list:
  keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[2]} ({auto[1]})",callback_data=f"servizi_{auto[0]}")])
 await update.message.reply_text("🔧 SERVIZI EXTRA\n\nSeleziona auto:",reply_markup=InlineKeyboardMarkup(keyboard))

async def ghostcar_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 context.user_data.clear()
 context.user_data['state']='ghost_targa'
 await update.message.reply_text("👻 GHOST CAR (Staff)\n\nInserisci TARGA:")

async def lista_auto_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 oggi=now_italy().date().strftime('%Y-%m-%d')
 auto_parcheggiate=db_query('SELECT stanza,cognome,targa FROM auto WHERE stato="parcheggiata" AND is_ghost=0 ORDER BY stanza')
 ghost_cars=db_query('SELECT stanza,cognome,targa FROM auto WHERE stato="parcheggiata" AND is_ghost=1 ORDER BY stanza')
 entrate_oggi=db_query('SELECT COUNT(*) FROM auto WHERE date(data_arrivo)=? AND is_ghost=0',(oggi,),'one')[0]
 uscite_oggi=db_query('SELECT COUNT(*) FROM auto WHERE date(data_partenza)=? AND is_ghost=0',(oggi,),'one')[0] if db_query('SELECT COUNT(*) FROM auto WHERE date(data_partenza)=?',(oggi,),'one')[0]>0 else 0
 
 msg=f"📊 STATISTICHE {now_italy().strftime('%d/%m/%Y')}\n\n📈 OGGI: Entrate {entrate_oggi} | Uscite {uscite_oggi}\n\n"
 
 if auto_parcheggiate:
  msg+=f"🅿️ AUTO IN PARCHEGGIO ({len(auto_parcheggiate)}):\n"
  for auto in auto_parcheggiate:msg+=f"{auto[0]} | {auto[1]} | {auto[2]}\n"
 
 if ghost_cars:
  msg+=f"\n👻 GHOST CARS ({len(ghost_cars)}):\n" 
  for auto in ghost_cars:msg+=f"{auto[0]} | {auto[1]} | {auto[2]} 👻\n"
 
 if not auto_parcheggiate and not ghost_cars:msg+="🅿️ Nessuna auto in parcheggio"
 
 await update.message.reply_text(msg)

async def annulla_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 context.user_data.clear()
 await update.message.reply_text("❌ Operazione annullata")

# ===== DEEP LINK HANDLER =====
async def handle_recupero_deep_link(update,context,auto_id):
 auto=get_auto_by_id(auto_id)
 if not auto:await update.effective_message.reply_text("❌ Auto non trovata");return
 keyboard=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ AVVIA RECUPERO",callback_data=f"avvia_recupero_{auto_id}")]])
 ghost_text=" 👻" if auto[7] else ""
 await update.effective_message.reply_text(f"🚗 RECUPERO AUTO\n\nStanza {auto[3]} - {auto[2]} ({auto[1]}){ghost_text}\n\nConferma avvio recupero:",reply_markup=keyboard)

# ===== MESSAGE HANDLER =====
async def handle_message(update:Update,context:ContextTypes.DEFAULT_TYPE):
 state=context.user_data.get('state')
 text=update.message.text.strip()
 
 if state=='ritiro_cognome':
  if not validate_cognome(text):await update.message.reply_text("❌ Cognome non valido");return
  context.user_data['cognome']=text.strip()
  context.user_data['state']='ritiro_stanza'
  await update.message.reply_text("🏨 Numero STANZA:")
 
 elif state=='ritiro_stanza':
  try:
   stanza=int(text)
   if not 0<=stanza<=9999:await update.message.reply_text("❌ Stanza non valida");return
   cognome,targa,numero=context.user_data['cognome'],genera_targa_hotel(),get_prossimo_numero()
   auto_id=db_query('INSERT INTO auto (cognome,targa,stanza) VALUES (?,?,?)',(cognome,targa,stanza),'lastid')
   if auto_id:
    await update.message.reply_text(f"✅ RICHIESTA CREATA!\n\n🚗 {targa}\n👤 {cognome}\n🏨 Stanza {stanza}\n🔢 #{numero}\n\n📅 {now_italy().strftime('%d/%m/%Y %H:%M')}")
    await invia_notifica_canale(context,auto_id,cognome,stanza,numero)
   context.user_data.clear()
  except:await update.message.reply_text("❌ Numero stanza non valido")
 
 elif state=='ghost_targa':
  if not validate_targa(text):await update.message.reply_text("❌ Targa non valida");return
  context.user_data['targa']=text.upper()
  context.user_data['state']='ghost_cognome'
  await update.message.reply_text("👤 COGNOME:")
 
 elif state=='ghost_cognome':
  if not validate_cognome(text):await update.message.reply_text("❌ Cognome non valido");return
  context.user_data['cognome']=text.strip()
  context.user_data['state']='ghost_stanza'
  await update.message.reply_text("🏨 STANZA:")
 
 elif state=='ghost_stanza':
  try:
   stanza=int(text)
   targa,cognome=context.user_data['targa'],context.user_data['cognome']
   auto_id=db_query('INSERT INTO auto (cognome,targa,stanza,is_ghost) VALUES (?,?,?,1)',(cognome,targa,stanza),'lastid')
   await update.message.reply_text(f"👻 GHOST CAR REGISTRATA!\n\n🚗 {targa}\n👤 {cognome}\n🏨 Stanza {stanza}")
   context.user_data.clear()
  except:await update.message.reply_text("❌ Stanza non valida")
 
 elif state=='upload_foto':
  if text.lower()=='fine':
   context.user_data.clear()
   await update.message.reply_text("📷 Upload completato!")
  else:
   await update.message.reply_text("📷 Invia foto o scrivi 'fine'")

# ===== PHOTO HANDLER =====
async def handle_photo(update:Update,context:ContextTypes.DEFAULT_TYPE):
 if context.user_data.get('state')=='upload_foto':
  auto_id=context.user_data.get('foto_auto_id')
  if auto_id:
   file_id=update.message.photo[-1].file_id
   db_query('INSERT INTO foto (auto_id,file_id) VALUES (?,?)',(auto_id,file_id),'none')
   count=db_query('SELECT COUNT(*) FROM foto WHERE auto_id=?',(auto_id,),'one')[0]
   await update.message.reply_text(f"📷 Foto #{count} salvata! Altre foto o 'fine'")

# ===== CALLBACK HANDLER =====
async def handle_callback_query(update:Update,context:ContextTypes.DEFAULT_TYPE):
 query=update.callback_query
 await query.answer()
 data=query.data
 
 if data.startswith('recupero_'):
  auto_id=int(data.split('_')[1])
  db_query('UPDATE auto SET stato="ritiro" WHERE id=?',(auto_id,),'none')
  auto=get_auto_by_id(auto_id)
  await query.edit_message_text(f"⚙️ RECUPERO AVVIATO!\n\n🚗 {auto[2]} - Stanza {auto[3]}\n👤 {auto[1]}")
 
 elif data.startswith('avvia_recupero_'):
  auto_id=int(data.split('_')[2])
  db_query('UPDATE auto SET stato="ritiro" WHERE id=?',(auto_id,),'none')
  auto=get_auto_by_id(auto_id)
  await query.edit_message_text(f"⚙️ RECUPERO AVVIATO!\n\n🚗 {auto[2]} - Stanza {auto[3]}\n👤 {auto[1]}")
 
 elif data.startswith('park_'):
  auto_id=int(data.split('_')[1])
  db_query('UPDATE auto SET stato="parcheggiata" WHERE id=?',(auto_id,),'none')
  auto=get_auto_by_id(auto_id)
  await query.edit_message_text(f"🅿️ AUTO PARCHEGGIATA!\n\n🚗 {auto[2]} - Stanza {auto[3]}\n👤 {auto[1]}")
 
 elif data.startswith('partito_'):
  auto_id=int(data.split('_')[1])
  auto=get_auto_by_id(auto_id)
  keyboard=InlineKeyboardMarkup([[InlineKeyboardButton("✅ CONFERMA",callback_data=f"conferma_partito_{auto_id}")],[InlineKeyboardButton("❌ ANNULLA",callback_data="annulla_op")]])
  await query.edit_message_text(f"🏁 CONFERMA USCITA\n\n🚗 {auto[2]} - Stanza {auto[3]}\n👤 {auto[1]}",reply_markup=keyboard)
 
 elif data.startswith('conferma_partito_'):
  auto_id=int(data.split('_')[2])
  db_query('UPDATE auto SET stato="uscita",data_partenza=CURRENT_DATE WHERE id=?',(auto_id,),'none')
  auto=get_auto_by_id(auto_id)
  await query.edit_message_text(f"🏁 AUTO PARTITA!\n\n🚗 {auto[2]} - Stanza {auto[3]}\n👤 {auto[1]}")
 
 elif data.startswith('foto_'):
  auto_id=int(data.split('_')[1])
  context.user_data['state']='upload_foto'
  context.user_data['foto_auto_id']=auto_id
  auto=get_auto_by_id(auto_id)
  await query.edit_message_text(f"📷 CARICA FOTO\n\n🚗 {auto[2]} - Stanza {auto[3]}\n👤 {auto[1]}\n\nInvia foto o scrivi 'fine'")
 
 elif data.startswith('mostra_foto_'):
  auto_id=int(data.split('_')[2])
  auto=get_auto_by_id(auto_id)
  foto_list=db_query('SELECT file_id FROM foto WHERE auto_id=? ORDER BY data_upload',(auto_id,))
  await query.edit_message_text(f"📷 FOTO AUTO\n\n🚗 {auto[2]} - Stanza {auto[3]}\n👤 {auto[1]}\n📷 Totale: {len(foto_list)} foto")
  for foto in foto_list[:5]:  # Max 5 foto
   try:await update.effective_chat.send_photo(photo=foto[0])
   except:pass
 
 elif data.startswith('servizi_'):
  auto_id=int(data.split('_')[1])
  auto=get_auto_by_id(auto_id)
  keyboard=InlineKeyboardMarkup([
   [InlineKeyboardButton("🌙 Ritiro Notturno",callback_data=f"add_servizio_{auto_id}_ritiro_notturno")],
   [InlineKeyboardButton("🚿 Autolavaggio",callback_data=f"add_servizio_{auto_id}_autolavaggio")]
  ])
  await query.edit_message_text(f"🔧 SERVIZI EXTRA\n\n🚗 {auto[2]} - Stanza {auto[3]}\n👤 {auto[1]}\n\nSeleziona servizio:",reply_markup=keyboard)
 
 elif data.startswith('add_servizio_'):
  parts=data.split('_')
  auto_id,servizio=int(parts[2]),'_'.join(parts[3:])
  auto=get_auto_by_id(auto_id)
  db_query('INSERT INTO servizi_extra (auto_id,tipo_servizio) VALUES (?,?)',(auto_id,servizio),'none')
  servizio_nome={'ritiro_notturno':'🌙 Ritiro Notturno','autolavaggio':'🚿 Autolavaggio'}.get(servizio,'🔧 Servizio')
  await query.edit_message_text(f"✅ SERVIZIO AGGIUNTO!\n\n{servizio_nome}\n🚗 {auto[2]} - Stanza {auto[3]}\n👤 {auto[1]}")
 
 elif data=='annulla_op':
  await query.edit_message_text("❌ Operazione annullata")

def main():
 TOKEN=os.getenv('TELEGRAM_BOT_TOKEN')
 if not TOKEN:logging.error("TOKEN mancante");return
 
 app=Application.builder().token(TOKEN).build()
 
 commands=[
  ("start",start),("help",help_command),("ritiro",ritiro_command),("recupero",recupero_command),
  ("park",park_command),("partito",partito_command),("foto",foto_command),("vedi_foto",vedi_foto_command),
  ("servizi",servizi_command),("ghostcar",ghostcar_command),("lista_auto",lista_auto_command),("annulla",annulla_command)
 ]
 
 for cmd,func in commands:app.add_handler(CommandHandler(cmd,func))
 app.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,handle_message))
 app.add_handler(MessageHandler(filters.PHOTO,handle_photo))
 app.add_handler(CallbackQueryHandler(handle_callback_query))
 
 logging.info(f"🚗 {BOT_NAME} v{BOT_VERSION} avviato - DATABASE SEMPLIFICATO!")
 app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=='__main__':main()
