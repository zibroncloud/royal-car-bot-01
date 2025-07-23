#!/usr/bin/env python3
# CarValetBOT v6.01 by Zibroncloud - VERSIONE SEMPLICE E FUNZIONANTE
import os,logging,sqlite3,re
from datetime import datetime,date,timedelta
from telegram import Update,InlineKeyboardButton,InlineKeyboardMarkup
from telegram.ext import Application,CommandHandler,MessageHandler,filters,ContextTypes,CallbackQueryHandler

BOT_VERSION="6.04"
BOT_NAME="CarValetBOT"
CANALE_VALET="-1002582736358"

logging.basicConfig(format='%(asctime)s-%(levelname)s-%(message)s',level=logging.INFO)

# Fuso orario italiano (funzionante dalla v29)
def now_italy():
    """Restituisce datetime corrente in fuso orario italiano (UTC+1/+2)"""
    utc_now = datetime.utcnow()
    italy_offset = 2 if utc_now.month >= 3 and utc_now.month <= 10 else 1
    return utc_now + timedelta(hours=italy_offset)

# ===== DATABASE FUNCTIONS =====
def init_db():
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('''CREATE TABLE IF NOT EXISTS auto (
   id INTEGER PRIMARY KEY AUTOINCREMENT,
   targa TEXT NOT NULL,
   cognome TEXT NOT NULL,
   stanza INTEGER NOT NULL,
   numero_chiave INTEGER,
   note TEXT,
   stato TEXT DEFAULT 'richiesta',
   data_arrivo DATE DEFAULT CURRENT_DATE,
   data_park DATE,
   data_uscita DATE,
   foto_count INTEGER DEFAULT 0,
   numero_progressivo INTEGER,
   tempo_stimato TEXT,
   ora_accettazione TIMESTAMP,
   is_ghost INTEGER DEFAULT 0
  )''')
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
  cursor.execute('''CREATE TABLE IF NOT EXISTS prenotazioni (
   id INTEGER PRIMARY KEY AUTOINCREMENT,
   auto_id INTEGER,
   data_partenza DATE NOT NULL,
   ora_partenza TIME NOT NULL,
   completata INTEGER DEFAULT 0,
   data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
   FOREIGN KEY (auto_id) REFERENCES auto (id)
  )''')
  conn.commit()
  conn.close()
  logging.info("Database v29 inizializzato")
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

def get_auto_by_id(auto_id):return db_query('SELECT * FROM auto WHERE id=?',(auto_id,),'one')
def get_prossimo_numero():return(db_query('SELECT MAX(numero_progressivo) FROM auto WHERE date(data_arrivo)=? AND is_ghost=0',(now_italy().date().strftime('%Y-%m-%d'),),'one')[0] or 0)+1
def genera_targa_hotel():count=db_query('SELECT COUNT(*) FROM auto WHERE date(data_arrivo)=? AND targa LIKE "HOTEL%"',(now_italy().date().strftime('%Y-%m-%d'),),'one')[0];return f"HOTEL{count+1:03d}"

# ===== VALIDATION FUNCTIONS =====
def validate_targa(targa):
 targa=targa.upper().strip()
 patterns=[r'^[A-Z]{2}[0-9]{3}[A-Z]{2}$',r'^[A-Z0-9]{4,10}$',r'^[A-Z0-9]{1,4}[-\s][A-Z0-9]{1,4}[-\s][A-Z0-9]{1,4}$']
 return any(re.match(p,targa.replace(' ','-'))for p in patterns)

def validate_cognome(cognome):return bool(re.match(r"^[A-Za-zÀ-ÿ\s']+$",cognome.strip()))
def validate_date_format(date_str):
 try:datetime.strptime(date_str,'%d/%m/%Y');return True
 except:return False
def validate_time_format(time_str):
 try:datetime.strptime(time_str,'%H:%M');return True
 except:return False

# ===== NOTIFICATION FUNCTIONS =====
async def invia_notifica_canale(context:ContextTypes.DEFAULT_TYPE,auto_id,cognome,stanza,numero_progressivo):
 try:
  msg=f"🚗 NUOVA RICHIESTA RITIRO!\n\n👤 Cliente: {cognome}\n🏨 Stanza: {stanza}\n🔢 Numero: #{numero_progressivo}\n📅 {now_italy().strftime('%d/%m/%Y alle %H:%M')}"
  keyboard=[[InlineKeyboardButton("⚙️ Gestisci Richiesta",url=f"https://t.me/{context.bot.username}?start=recupero_{auto_id}_richiesta")]]
  await context.bot.send_message(chat_id=CANALE_VALET,text=msg,reply_markup=InlineKeyboardMarkup(keyboard))
  return True
 except Exception as e:logging.error(f"Errore notifica: {e}");return False

async def invia_notifica_avviato(context:ContextTypes.DEFAULT_TYPE,auto,tempo_stimato,valet_username,tipo_operazione):
 try:
  ghost_text=" 👻" if auto[14] else ""
  numero_text=f"#{auto[11]}" if not auto[14] else "GHOST"
  
  if tipo_operazione == 'rientro':
   titolo = "🔄 RIENTRO AVVIATO!"
  elif tipo_operazione == 'riconsegna':
   titolo = "🚪 RICONSEGNA AVVIATA!"
  else:
   titolo = "🚀 RECUPERO AVVIATO!"
  
  msg=f"{titolo}\n\n{numero_text} | {auto[1]} ({auto[2]}){ghost_text}\n🏨 Stanza: {auto[3]}\n⏰ {tempo_stimato}\n👨‍💼 Valet: @{valet_username}\n\n📅 {now_italy().strftime('%d/%m/%Y alle %H:%M')}"
  await context.bot.send_message(chat_id=CANALE_VALET,text=msg)
  return True
 except Exception as e:logging.error(f"Errore notifica avviato: {e}");return False

async def invia_notifica_riconsegna(context:ContextTypes.DEFAULT_TYPE,auto):
 try:
  ghost_text=" 👻" if auto[14] else ""
  numero_text=f"#{auto[11]}" if not auto[14] else "GHOST"
  msg=f"🚪 RICHIESTA RICONSEGNA!\n\n{numero_text} | {auto[1]} ({auto[2]}){ghost_text}\n🏨 Stanza: {auto[3]}\n\n📅 {now_italy().strftime('%d/%m/%Y alle %H:%M')}"
  keyboard=[[InlineKeyboardButton("⚙️ Gestisci Riconsegna",url=f"https://t.me/{context.bot.username}?start=recupero_{auto[0]}_riconsegna")]]
  await context.bot.send_message(chat_id=CANALE_VALET,text=msg,reply_markup=InlineKeyboardMarkup(keyboard))
  return True
 except Exception as e:logging.error(f"Errore notifica riconsegna: {e}");return False

async def invia_notifica_rientro(context:ContextTypes.DEFAULT_TYPE,auto):
 try:
  ghost_text=" 👻" if auto[14] else ""
  numero_text=f"#{auto[11]}" if not auto[14] else "GHOST"
  msg=f"🔄 RICHIESTA RIENTRO!\n\n{numero_text} | {auto[1]} ({auto[2]}){ghost_text}\n🏨 Stanza: {auto[3]}\n\n📅 {now_italy().strftime('%d/%m/%Y alle %H:%M')}"
  keyboard=[[InlineKeyboardButton("⚙️ Gestisci Rientro",url=f"https://t.me/{context.bot.username}?start=recupero_{auto[0]}_rientro")]]
  await context.bot.send_message(chat_id=CANALE_VALET,text=msg,reply_markup=InlineKeyboardMarkup(keyboard))
  return True
 except Exception as e:logging.error(f"Errore notifica rientro: {e}");return False
 try:
  ghost_text=" 👻" if auto[14] else ""
  numero_text=f"#{auto[11]}" if not auto[14] else "GHOST"
  msg=f"📅 NUOVA PRENOTAZIONE PARTENZA!\n\n{numero_text} | {auto[1]} ({auto[2]}){ghost_text}\n🏨 Stanza: {auto[3]}\n🕐 Partenza: {data} alle {ora}\n\n📅 {now_italy().strftime('%d/%m/%Y alle %H:%M')}"
  await context.bot.send_message(chat_id=CANALE_VALET,text=msg)
  return True
 except Exception as e:logging.error(f"Errore notifica prenotazione: {e}");return False

# ===== HELPER FUNCTIONS =====
def create_tempo_keyboard(auto_id,tipo_op):
 return InlineKeyboardMarkup([
  [InlineKeyboardButton("⏱️ 15 min ca.",callback_data=f"tempo_{auto_id}_{tipo_op}_15")],
  [InlineKeyboardButton("⏱️ 30 min ca.",callback_data=f"tempo_{auto_id}_{tipo_op}_30")],
  [InlineKeyboardButton("⏱️ 45 min ca.",callback_data=f"tempo_{auto_id}_{tipo_op}_45")],
  [InlineKeyboardButton("🚙🚗🚐 In coda - altri ritiri",callback_data=f"tempo_{auto_id}_{tipo_op}_coda")],
  [InlineKeyboardButton("⚠️ Possibile ritardo",callback_data=f"tempo_{auto_id}_{tipo_op}_ritardo")]
 ])

# ===== MAIN FUNCTIONS =====
init_db()

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
 # Deep link handling
 if context.args and len(context.args)>0:
  arg=context.args[0]
  if arg.startswith('recupero_'):
   try:
    parts=arg.split('_')
    auto_id=int(parts[1])
    tipo=parts[2] if len(parts)>2 else 'richiesta'
    auto=get_auto_by_id(auto_id)
    if auto and auto[6]in['richiesta','riconsegna','rientro']:
     await handle_recupero_specifico(update,context,auto_id,tipo)
     return
   except:pass
 
 msg=f"""🚗 {BOT_NAME} v{BOT_VERSION} - VERSIONE FINALE
By Zibroncloud

🏨 HOTEL:
/ritiro - Cognome + Stanza → AUTOMATICO!
/riconsegna - Richiesta riconsegna temporanea
/rientro - Richiesta rientro in parcheggio
/prenota - Prenotazioni partenza
/mostra_prenotazioni - Visualizza prenotazioni

🚗 VALET:
/recupero - Gestione recuperi
/park - Conferma parcheggio
/completa - Completa dati auto (targa + BOX + foto)
/partito - Uscita definitiva

🔧 UTILITÀ & SERVIZI:
/foto /vedi_foto - Gestione foto
/servizi /servizi_stats - Servizi extra
/modifica - Modifica dati auto
/lista_auto - Statistiche parcheggio
/export - Export database
/situazione - Situazione recuperi

❓ /help /annulla

🆕 v6.01: Notifiche complete + workflow ottimizzato"""
 await update.message.reply_text(msg)

async def help_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 msg=f"""🚗 {BOT_NAME} v{BOT_VERSION} - GUIDA COMPLETA

🏨 HOTEL (WORKFLOW SEMPLIFICATO):
/ritiro → Cognome + Stanza → AUTOMATICO:
  📱 Notifica immediata ai Valet
  🚗 Targa automatica HOTEL001, HOTEL002...
  🔢 Numero progressivo giornaliero

/riconsegna → Richiesta riconsegna temporanea
  📱 Notifica ai Valet per il recupero
  
/prenota → Prenotazioni partenza future
  📱 Notifica ai Valet con data/ora
  
/rientro → Richiesta rientro in parcheggio
  📱 Notifica ai Valet per il recupero
  
/mostra_prenotazioni → Lista prenotazioni attive

🚗 VALET (WORKFLOW AVANZATO):
/recupero → Gestione recuperi con tempistiche:
  ⏱️ 15/30/45 minuti ca.
  🚙 In coda (altri ritiri prima)
  ⚠️ Possibile ritardo
/park → Conferma parcheggio completato
/completa → Workflow completo:
  🚗 Targa reale → 📦 BOX → 📷 Foto
/partito → Uscita definitiva

🔧 FUNZIONI COMPLETE:
/foto /vedi_foto → Gestione foto complete
/servizi /servizi_stats → Servizi extra
/modifica → Modifica tutti i dati auto
/lista_auto → Statistiche giornaliere
/export → Export database CSV
/situazione → Situazione recuperi

📱 WORKFLOW TIPO:
Hotel: /ritiro → Notifica → Valet: /recupero → /park → /completa → /partito

🔔 NOTIFICHE AUTOMATICHE:
✅ Nuove richieste ritiro
✅ Recuperi avviati con tempistiche  
✅ Richieste riconsegna
✅ Prenotazioni partenza"""
 await update.message.reply_text(msg)

# ===== HOTEL COMMANDS =====
async def ritiro_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 context.user_data.clear()
 context.user_data['state']='ritiro_cognome'
 await update.message.reply_text("🚗 RITIRO SEMPLIFICATO v6.01\n\n👤 Inserisci il COGNOME del cliente:")

async def prenota_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 auto_list=db_query('SELECT id,targa,cognome,stanza,numero_chiave,stato,is_ghost FROM auto WHERE stato!="uscita" ORDER BY is_ghost,stanza')
 if not auto_list:await update.message.reply_text("📋 Nessuna auto disponibile");return
 keyboard=[]
 emoji_map={'richiesta':'📋','ritiro':'⚙️','parcheggiata':'🅿️','riconsegna':'🚪','stand-by':'⏸️','rientro':'🔄'}
 for auto in auto_list:
  box_text=f" - BOX: {auto[4]}" if auto[4] else ""
  ghost_text=" 👻" if auto[6] else ""
  emoji=emoji_map.get(auto[5],"❓")
  keyboard.append([InlineKeyboardButton(f"{emoji} Stanza {auto[3]} - {auto[1]} ({auto[2]}){ghost_text}{box_text}",callback_data=f"prenota_auto_{auto[0]}")])
 await update.message.reply_text("📅 PRENOTA PARTENZA\n\nSeleziona auto:",reply_markup=InlineKeyboardMarkup(keyboard))

async def mostra_prenotazioni_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 prenotazioni=db_query('SELECT p.id,p.auto_id,a.targa,a.cognome,a.stanza,a.stato,a.is_ghost,p.data_partenza,p.ora_partenza,p.completata FROM prenotazioni p LEFT JOIN auto a ON p.auto_id=a.id WHERE p.completata=0 ORDER BY p.data_partenza,p.ora_partenza')
 if not prenotazioni:await update.message.reply_text("📅 Nessuna prenotazione");return
 oggi,domani=now_italy().date(),now_italy().date()+timedelta(days=1)
 msg="📅 PRENOTAZIONI PARTENZA\n\n"
 for gruppo,etichetta in [(oggi,"🚨 OGGI"),(domani,"📅 DOMANI")]:
  gruppo_pren=[p for p in prenotazioni if datetime.strptime(p[7],'%Y-%m-%d').date()==gruppo]
  if gruppo_pren:
   msg+=f"{etichetta} ({gruppo.strftime('%d/%m/%Y')}):\n"
   for p in gruppo_pren:
    ghost_text=" 👻" if p[6] else ""
    msg+=f"  {p[8]} - {p[2]} ({p[3]}) - Stanza {p[4]}{ghost_text} - {p[5].upper()}\n"
   msg+="\n"
 altri=[p for p in prenotazioni if datetime.strptime(p[7],'%Y-%m-%d').date()>domani]
 if altri:
  msg+="📆 PROSSIMI GIORNI:\n"
  for p in altri:
   ghost_text=" 👻" if p[6] else ""
   data_formattata=datetime.strptime(p[7],'%Y-%m-%d').strftime('%d/%m/%Y')
   msg+=f"  {data_formattata} {p[8]} - {p[2]} ({p[3]}) - Stanza {p[4]}{ghost_text} - {p[5].upper()}\n"
 await update.message.reply_text(msg)

async def riconsegna_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 await generic_auto_selection(update,"riconsegna","🚪 RICONSEGNA TEMPORANEA","stato='parcheggiata'")

# ===== VALET COMMANDS =====
async def recupero_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 auto_list=db_query('SELECT id,targa,cognome,stanza,numero_chiave,numero_progressivo,stato,is_ghost FROM auto WHERE stato IN ("richiesta","riconsegna","rientro") ORDER BY is_ghost,numero_progressivo')
 if not auto_list:await update.message.reply_text("📋 Nessun recupero da gestire");return
 keyboard=[]
 for auto in auto_list:
  box_text=f" - BOX: {auto[4]}" if auto[4] else ""
  ghost_text=" 👻" if auto[7] else ""
  tipo={'richiesta':'📋 RITIRO','riconsegna':'🚪 RICONSEGNA','rientro':'🔄 RIENTRO'}[auto[6]]
  num_text=f"#{auto[5]}" if not auto[7] else "GHOST"
  text=f"{tipo} {num_text} - Stanza {auto[3]} - {auto[1]} ({auto[2]}){ghost_text}{box_text}"
  keyboard.append([InlineKeyboardButton(text,callback_data=f"recupero_{auto[0]}_{auto[6]}")])
 await update.message.reply_text("⚙️ GESTIONE OPERAZIONI",reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_recupero_specifico(update,context,auto_id,tipo_op):
 auto=get_auto_by_id(auto_id)
 if not auto:await update.effective_message.reply_text("❌ Auto non trovata");return
 operazioni={'richiesta':'PRIMO RITIRO','riconsegna':'RICONSEGNA TEMPORANEA','rientro':'RIENTRO IN PARCHEGGIO'}
 ghost_text=" 👻" if auto[14] else ""
 num_text=f"#{auto[11]}" if not auto[14] else "GHOST"
 msg=f"⏰ {operazioni[tipo_op]}\n\n{num_text} | {auto[1]} ({auto[2]}){ghost_text}\n🏨 Stanza: {auto[3]}\n\nSeleziona tempistica:"
 await update.effective_message.reply_text(msg,reply_markup=create_tempo_keyboard(auto_id,tipo_op))

async def rientro_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 await generic_auto_selection(update,"rientro","🔄 RIENTRO IN PARCHEGGIO","stato='stand-by'")

async def park_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 await generic_auto_selection(update,"park","🅿️ CONFERMA PARCHEGGIO","stato='ritiro'")

async def completa_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 auto_list=db_query('SELECT id,targa,cognome,stanza,numero_chiave,stato FROM auto WHERE stato IN ("ritiro","parcheggiata") AND targa LIKE "HOTEL%" ORDER BY stato,targa')
 if not auto_list:await update.message.reply_text("📋 Nessuna auto da completare\n\nComando utile per auto con targa automatica (HOTEL001, HOTEL002...)");return
 keyboard=[]
 emoji_map={'ritiro':'⚙️','parcheggiata':'🅿️'}
 for auto in auto_list:
  box_text=f" - BOX: {auto[4]}" if auto[4] else " - BOX: da inserire"
  stato_emoji=emoji_map.get(auto[5],"❓")
  keyboard.append([InlineKeyboardButton(f"{stato_emoji} {auto[1]} - Stanza {auto[3]} ({auto[2]}){box_text}",callback_data=f"completa_{auto[0]}")])
 await update.message.reply_text("🔧 COMPLETA DATI AUTO\n\nWorkflow: Targa reale → BOX → Foto (opzionale)\n⚙️ = In ritiro | 🅿️ = Parcheggiata\n\nSeleziona auto:",reply_markup=InlineKeyboardMarkup(keyboard))

async def partito_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 await generic_auto_selection(update,"partito","🏁 USCITA DEFINITIVA","stato IN ('ritiro','parcheggiata','stand-by','rientro','riconsegna')")

async def foto_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 await generic_auto_selection(update,"foto","📷 CARICA FOTO","stato IN ('ritiro','parcheggiata')")

async def vedi_foto_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 auto_list=db_query('SELECT DISTINCT a.id,a.targa,a.cognome,a.stanza,a.stato,a.foto_count,a.is_ghost FROM auto a INNER JOIN foto f ON a.id=f.auto_id WHERE a.foto_count>0 ORDER BY a.stanza')
 if not auto_list:await update.message.reply_text("📷 Nessuna foto disponibile");return
 keyboard=[]
 emoji_map={'parcheggiata':"🅿️",'riconsegna':"🚪",'stand-by':"⏸️",'rientro':"🔄",'ritiro':"⚙️",'richiesta':"📋",'uscita':"🏁"}
 for auto in auto_list:
  ghost_text=" 👻" if auto[6] else ""
  emoji=emoji_map.get(auto[4],"❓")
  keyboard.append([InlineKeyboardButton(f"{emoji} Stanza {auto[3]} - {auto[1]} ({auto[2]}){ghost_text} - 📷 {auto[5]} foto",callback_data=f"mostra_foto_{auto[0]}")])
 await update.message.reply_text("📷 VISUALIZZA FOTO AUTO",reply_markup=InlineKeyboardMarkup(keyboard))

async def servizi_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 await generic_auto_selection(update,"servizi_auto","🔧 SERVIZI EXTRA","stato='parcheggiata'")

async def servizi_stats_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 oggi,mese=now_italy().date().strftime('%Y-%m-%d'),now_italy().date().strftime('%Y-%m')
 stats_mese=db_query('SELECT tipo_servizio,COUNT(*) FROM servizi_extra WHERE strftime("%Y-%m",data_servizio)=? GROUP BY tipo_servizio',(mese,))
 stats_oggi=db_query('SELECT tipo_servizio,COUNT(*) FROM servizi_extra WHERE date(data_servizio)=? GROUP BY tipo_servizio',(oggi,))
 servizi_oggi=dict(stats_oggi)if stats_oggi else{}
 servizi_mese=dict(stats_mese)if stats_mese else{}
 msg=f"🔧 STATISTICHE SERVIZI EXTRA\n\n📅 OGGI ({now_italy().strftime('%d/%m/%Y')}):\n"
 msg+=f"  🌙 Ritiri notturni: {servizi_oggi.get('ritiro_notturno',0)}\n"
 msg+=f"  🏠 Garage 10+ giorni: {servizi_oggi.get('garage_10plus',0)}\n"
 msg+=f"  🚿 Autolavaggi: {servizi_oggi.get('autolavaggio',0)}\n\n"
 msg+=f"📊 {now_italy().strftime('%B %Y').upper()}:\n"
 msg+=f"  🌙 Ritiri notturni: {servizi_mese.get('ritiro_notturno',0)}\n"
 msg+=f"  🏠 Garage 10+ giorni: {servizi_mese.get('garage_10plus',0)}\n"
 msg+=f"  🚿 Autolavaggi: {servizi_mese.get('autolavaggio',0)}\n\n"
 totale_oggi=sum(servizi_oggi.values())
 totale_mese=sum(servizi_mese.values())
 msg+=f"📈 TOTALI:\n  🔧 Servizi oggi: {totale_oggi}\n  📅 Servizi mese: {totale_mese}"
 await update.message.reply_text(msg)

async def modifica_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 await generic_auto_selection(update,"modifica","✏️ MODIFICA AUTO","stato!='uscita'")

async def lista_auto_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  oggi=now_italy().date().strftime('%Y-%m-%d')
  auto_parcheggiate=db_query('SELECT stanza,cognome,targa,numero_chiave,foto_count FROM auto WHERE stato="parcheggiata" AND is_ghost=0 ORDER BY stanza') or []
  ghost_cars=db_query('SELECT stanza,cognome,targa,numero_chiave,foto_count FROM auto WHERE stato="parcheggiata" AND is_ghost=1 ORDER BY stanza') or []
  entrate_result=db_query('SELECT COUNT(*) FROM auto WHERE date(data_arrivo)=? AND is_ghost=0',(oggi,),'one')
  entrate_oggi=entrate_result[0] if entrate_result else 0
  uscite_result=db_query('SELECT COUNT(*) FROM auto WHERE date(data_uscita)=? AND stato="uscita" AND is_ghost=0',(oggi,),'one')
  uscite_oggi=uscite_result[0] if uscite_result else 0
  msg=f"📊 STATISTICHE {now_italy().strftime('%d/%m/%Y')}\n\n📈 OGGI: Entrate {entrate_oggi} | Uscite {uscite_oggi}\n\n"
  if auto_parcheggiate:
   msg+=f"🅿️ AUTO IN PARCHEGGIO ({len(auto_parcheggiate)}):\n"
   for auto in auto_parcheggiate:
    stanza,cognome,targa,box,foto_count=auto[0],auto[1],auto[2],auto[3] or '--',auto[4] or 0
    msg+=f"{stanza} | {cognome} | {targa} | BOX:{box}{f' 📷{foto_count}' if foto_count else ''}\n"
  if ghost_cars:
   msg+=f"\n👻 GHOST CARS ({len(ghost_cars)}):\n"
   for auto in ghost_cars:
    stanza,cognome,targa,box,foto_count=auto[0],auto[1],auto[2],auto[3] or '--',auto[4] or 0
    msg+=f"{stanza} | {cognome} | {targa} | BOX:{box}{f' 📷{foto_count}' if foto_count else ''} 👻\n"
  if not auto_parcheggiate and not ghost_cars:
   msg+="🅿️ Nessuna auto in parcheggio"
  await update.message.reply_text(msg)
 except Exception as e:
  logging.error(f"Errore lista_auto: {e}")
  await update.message.reply_text("❌ Errore caricamento statistiche. Riprova tra poco.")

async def export_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 await update.message.reply_text("📊 EXPORT DATABASE\n\n⏳ Generazione CSV...")
 try:
  auto_data=db_query('SELECT * FROM auto ORDER BY is_ghost,data_arrivo DESC')
  servizi_data=db_query('SELECT s.*,a.targa,a.cognome,a.stanza FROM servizi_extra s LEFT JOIN auto a ON s.auto_id=a.id ORDER BY s.data_servizio DESC')
  if not auto_data:auto_data=[]
  if not servizi_data:servizi_data=[]
  csv_content="ID,Targa,Cognome,Stanza,BOX,Note,Stato,DataArrivo,DataPark,DataUscita,NumProgressivo,TempoStimato,OraAccettazione,FotoCount,IsGhost\n"
  for auto in auto_data:
   values=[]
   for v in auto:
    if v is None:values.append("")
    else:
     str_v=str(v).replace('"','""')
     values.append(f'"{str_v}"'if(','in str_v or'"'in str_v)else str_v)
   csv_content+=",".join(values)+"\n"
  csv_content+="\n=== SERVIZI EXTRA ===\nID,AutoID,Targa,Cognome,Stanza,TipoServizio,DataServizio\n"
  for serv in servizi_data:
   values=[str(v or'')for v in serv]
   csv_content+=",".join(values)+"\n"
  filename=f"carvalet_export_{now_italy().strftime('%Y%m%d_%H%M%S')}.csv"
  with open(filename,'w',encoding='utf-8')as f:f.write(csv_content)
  with open(filename,'rb')as f:
   await update.message.reply_document(document=f,filename=filename,caption=f"📊 EXPORT v6.01 - {now_italy().strftime('%d/%m/%Y alle %H:%M')}\n📁 {len(auto_data)} auto totali")
  os.remove(filename)
 except Exception as e:
  logging.error(f"Export error: {e}")
  await update.message.reply_text("❌ Errore durante l'export del database")

async def situazione_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 oggi=now_italy().date().strftime('%Y-%m-%d')
 auto_list=db_query('SELECT id,targa,cognome,stanza,stato,numero_progressivo,tempo_stimato,ora_accettazione,is_ghost FROM auto WHERE date(data_arrivo)=? AND stato IN ("richiesta","ritiro","parcheggiata","riconsegna","stand-by","rientro") ORDER BY numero_progressivo',(oggi,))
 if not auto_list:await update.message.reply_text("📋 Situazione pulita oggi");return
 msg="🔍 SITUAZIONE RECUPERI DI OGGI:\n\n"
 for auto in auto_list:
  ghost_text=" 👻" if auto[8] else ""
  emoji_status={'richiesta':"📋",'ritiro':"⚙️",'parcheggiata':"🅿️",'riconsegna':"🚪",'stand-by':"⏸️",'rientro':"🔄"}
  emoji=emoji_status.get(auto[4],"❓")
  num_text=f"#{auto[5]}" if not auto[8] else "GHOST"
  status_text={'richiesta':'In attesa valet','ritiro':f'Recupero in corso - {auto[6] or "N/A"}'if auto[6] else'Recupero in corso','parcheggiata':'AUTO PARCHEGGIATA ✅','riconsegna':'Riconsegna richiesta','stand-by':'Auto fuori parcheggio','rientro':'Rientro richiesto'}
  msg+=f"{emoji} {num_text} | Stanza {auto[3]} | {auto[1]} ({auto[2]}){ghost_text}\n    {status_text[auto[4]]}\n\n"
 await update.message.reply_text(msg)

# ===== HIDDEN COMMANDS (still functional) =====
async def ghostcar_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 context.user_data.clear()
 context.user_data.update({'state':'ghost_targa','is_ghost':True})
 await update.message.reply_text("👻 GHOST CAR (Staff/Direttore)\n\nInserisci la TARGA del veicolo:")

async def makepark_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 context.user_data.clear()
 context.user_data.update({'state':'makepark_targa','is_ghost':False})
 await update.message.reply_text("🅿️ AUTO GIÀ PARCHEGGIATA\n\nInserisci la TARGA del veicolo:")

# ===== UTILITY FUNCTIONS =====
async def generic_auto_selection(update,action,title,where_clause):
 try:
  auto_list=db_query(f'SELECT id,targa,cognome,stanza,numero_chiave,is_ghost FROM auto WHERE {where_clause} ORDER BY is_ghost,stanza')
  if not auto_list:await update.message.reply_text("📋 Nessuna auto disponibile");return
  keyboard=[]
  for auto in auto_list:
   box_text=f" - BOX: {auto[4]}" if auto[4] else ""
   ghost_text=" 👻" if auto[5] else ""
   keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[1]} ({auto[2]}){ghost_text}{box_text}",callback_data=f"{action}_{auto[0]}")])
  await update.message.reply_text(f"{title}\n\nSeleziona auto:",reply_markup=InlineKeyboardMarkup(keyboard))
 except Exception as e:
  logging.error(f"Errore {action}: {e}")
  await update.message.reply_text(f"❌ Errore caricamento {action}")

async def annulla_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 if context.user_data.get('state'):
  context.user_data.clear()
  await update.message.reply_text("❌ Operazione annullata")
 else:
  await update.message.reply_text("ℹ️ Nessuna operazione in corso")

async def handle_modifica(update,context,state,text):
 try:
  field,auto_id=state.split('_')[1],int(state.split('_')[2])
  auto=get_auto_by_id(auto_id)
  if not auto:await update.message.reply_text("❌ Auto non trovata");return
  
  if field=='targa':
   if not validate_targa(text):await update.message.reply_text("❌ Targa non valida!");return
   value=text.upper()
  elif field=='cognome':
   if not validate_cognome(text):await update.message.reply_text("❌ Cognome non valido!");return
   value=text.strip()
  elif field=='stanza':
   try:value=int(text);assert 0<=value<=999
   except:await update.message.reply_text("❌ Stanza 0-999!");return
  elif field in['box','note']:
   if text.lower()=='rimuovi':
    value=None
   elif field=='box' and text.isdigit() and 0<=int(text)<=999:
    value=int(text)
   elif field=='note':
    value=text.strip()
   else:
    value=None
   
   if field=='box' and text.lower()!='rimuovi' and (not text.isdigit() or not 0<=int(text)<=999):
    await update.message.reply_text("❌ BOX 0-999 o rimuovi!");return
  
  field_db={'box':'numero_chiave'}.get(field,field)
  if db_query(f'UPDATE auto SET {field_db}=? WHERE id=?',(value,auto_id),'none'):
   result_text={'box':f"BOX {'rimosso'if value is None else f'impostato a {value}'}",
               'note':f"Note {'rimosse'if value is None else'aggiornate'}"}.get(field,f"{field.title()} aggiornato")
   await update.message.reply_text(f"✅ {result_text}\n🚗 {auto[1]} - Stanza {auto[3]}")
  context.user_data.clear()
 except Exception as e:
  logging.error(f"Errore handle_modifica: {e}")
  await update.message.reply_text("❌ Errore durante la modifica")
  context.user_data.clear()

# ===== MESSAGE HANDLER =====
async def handle_message(update:Update,context:ContextTypes.DEFAULT_TYPE):
 state=context.user_data.get('state')
 text=update.message.text.strip()
 
 if state=='ritiro_cognome':
  if not validate_cognome(text):await update.message.reply_text("❌ Cognome non valido!");return
  context.user_data['cognome']=text.strip()
  context.user_data['state']='ritiro_stanza'
  await update.message.reply_text("🏨 Numero STANZA (0-999):")
 
 elif state=='ritiro_stanza':
  try:
   stanza=int(text)
   if not 0<=stanza<=999:await update.message.reply_text("❌ Stanza 0-999!");return
   targa,cognome,numero=genera_targa_hotel(),context.user_data['cognome'],get_prossimo_numero()
   auto_id=db_query('INSERT INTO auto (targa,cognome,stanza,numero_chiave,note,numero_progressivo,is_ghost) VALUES (?,?,?,?,?,?,?)',
                    (targa,cognome,stanza,None,'Richiesta hotel semplificata',numero,0),'lastid')
   if auto_id:
    await update.message.reply_text(f"✅ RICHIESTA CREATA!\n\n🆔 ID: {auto_id}\n🚗 {targa}\n👤 {cognome}\n🏨 Stanza {stanza}\n🔢 #{numero}\n\n📅 {now_italy().strftime('%d/%m/%Y alle %H:%M')}\n📱 Notifica inviata ai Valet!")
    await invia_notifica_canale(context,auto_id,cognome,stanza,numero)
   context.user_data.clear()
  except:await update.message.reply_text("❌ Numero stanza non valido!")
 
 elif state.startswith('completa_targa_'):
  auto_id=int(state.split('_')[2])
  if not validate_targa(text):await update.message.reply_text("❌ Targa non valida! Inserisci targa reale:");return
  if db_query('UPDATE auto SET targa=? WHERE id=?',(text.upper(),auto_id),'none'):
   await update.message.reply_text(f"✅ Targa aggiornata: {text.upper()}\n\n📦 Ora inserisci il numero BOX (0-999) o 'skip':")
   context.user_data['state']=f'completa_box_{auto_id}'
  else:await update.message.reply_text("❌ Errore aggiornamento targa");context.user_data.clear()
 
 elif state.startswith('completa_box_'):
  auto_id=int(state.split('_')[2])
  if text.lower()=='skip':
   box_value=None
   await update.message.reply_text("📦 BOX non assegnato\n\n📷 Vuoi caricare foto? Invia foto o scrivi 'skip' per terminare:")
  else:
   try:
    box_value=int(text)
    if not 0<=box_value<=999:await update.message.reply_text("❌ BOX 0-999 o 'skip'!");return
    await update.message.reply_text(f"✅ BOX assegnato: {box_value}\n\n📷 Vuoi caricare foto? Invia foto o scrivi 'skip' per terminare:")
   except:await update.message.reply_text("❌ BOX numero valido o 'skip'!");return
  
  if db_query('UPDATE auto SET numero_chiave=? WHERE id=?',(box_value,auto_id),'none'):
   context.user_data['state']=f'completa_foto_{auto_id}'
   context.user_data['foto_auto_id']=auto_id
  else:await update.message.reply_text("❌ Errore aggiornamento BOX");context.user_data.clear()
 
 elif state.startswith('completa_foto_'):
  if text.lower() in ['fine','skip']:
   auto_id=int(state.split('_')[2])
   auto=get_auto_by_id(auto_id)
   if auto:
    foto_count=auto[10] if auto[10] else 0
    await update.message.reply_text(f"✅ AUTO COMPLETATA!\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n📦 BOX: {auto[4] or 'Non assegnato'}\n📷 Foto: {foto_count} caricate\n\n🎯 Dati completati con successo!")
   context.user_data.clear()
  else:
   await update.message.reply_text("📷 Invia foto dell'auto o scrivi 'fine'/'skip' per terminare")

 elif state=='ghost_targa':
  if not validate_targa(text):await update.message.reply_text("❌ Targa non valida!");return
  context.user_data['targa']=text.upper()
  context.user_data['state']='ghost_cognome'
  await update.message.reply_text("👤 COGNOME del cliente:")
 
 elif state=='ghost_cognome':
  if not validate_cognome(text):await update.message.reply_text("❌ Cognome non valido!");return
  context.user_data['cognome']=text.strip()
  context.user_data['state']='ghost_stanza'
  await update.message.reply_text("🏨 Numero STANZA (0-999):")
 
 elif state=='ghost_stanza':
  try:
   stanza=int(text)
   if not 0<=stanza<=999:await update.message.reply_text("❌ Stanza 0-999!");return
   targa,cognome=context.user_data['targa'],context.user_data['cognome']
   auto_id=db_query('INSERT INTO auto (targa,cognome,stanza,numero_chiave,note,numero_progressivo,is_ghost) VALUES (?,?,?,?,?,?,?)',
                   (targa,cognome,stanza,None,'Ghost car staff',0,1),'lastid')
   await update.message.reply_text(f"👻 GHOST CAR REGISTRATA!\n\n🚗 {targa}\n👤 {cognome}\n🏨 Stanza {stanza}\n\n📅 {now_italy().strftime('%d/%m/%Y alle %H:%M')}")
   context.user_data.clear()
  except:await update.message.reply_text("❌ Numero stanza non valido!")
 
 elif state=='makepark_targa':
  if not validate_targa(text):await update.message.reply_text("❌ Targa non valida!");return
  context.user_data['targa']=text.upper()
  context.user_data['state']='makepark_cognome'
  await update.message.reply_text("👤 COGNOME del cliente:")
 
 elif state=='makepark_cognome':
  if not validate_cognome(text):await update.message.reply_text("❌ Cognome non valido!");return
  context.user_data['cognome']=text.strip()
  context.user_data['state']='makepark_stanza'
  await update.message.reply_text("🏨 Numero STANZA (0-999):")
 
 elif state=='makepark_stanza':
  try:
   stanza=int(text)
   if not 0<=stanza<=999:await update.message.reply_text("❌ Stanza 0-999!");return
   targa,cognome=context.user_data['targa'],context.user_data['cognome']
   auto_id=db_query('INSERT INTO auto (targa,cognome,stanza,numero_chiave,note,stato,data_arrivo,data_park,is_ghost) VALUES (?,?,?,?,?,?,CURRENT_DATE,CURRENT_DATE,?)',
                   (targa,cognome,stanza,None,'Auto già parcheggiata','parcheggiata',0),'lastid')
   await update.message.reply_text(f"🅿️ AUTO PARCHEGGIATA REGISTRATA!\n\n🚗 {targa}\n👤 {cognome}\n🏨 Stanza {stanza}\n\n📅 {now_italy().strftime('%d/%m/%Y alle %H:%M')}")
   context.user_data.clear()
  except:await update.message.reply_text("❌ Numero stanza non valido!")
 
 elif state.startswith('mod_'):
  await handle_modifica(update,context,state,text)

 elif state=='prenota_data':
  if not validate_date_format(text):await update.message.reply_text("❌ Formato data gg/mm/aaaa!");return
  context.user_data['data']=text;context.user_data['state']='prenota_ora'
  await update.message.reply_text("🕐 ORA partenza (hh:mm):")
 
 elif state=='prenota_ora':
  if not validate_time_format(text):await update.message.reply_text("❌ Formato ora hh:mm!");return
  try:
   auto_id,data=context.user_data['auto_id'],context.user_data['data']
   data_sql=datetime.strptime(data,'%d/%m/%Y').strftime('%Y-%m-%d')
   if db_query('INSERT INTO prenotazioni (auto_id,data_partenza,ora_partenza) VALUES (?,?,?)',(auto_id,data_sql,text),'none'):
    auto=get_auto_by_id(auto_id)
    if auto:
     await invia_notifica_prenotazione(context,auto,data,text)
     await update.message.reply_text(f"📅 PRENOTAZIONE SALVATA!\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}\n📅 {data} alle {text}\n\n✅ {now_italy().strftime('%d/%m/%Y alle %H:%M')}\n📱 Notifica inviata ai Valet!")
   context.user_data.clear()
  except Exception as e:
   await update.message.reply_text("❌ Errore salvataggio prenotazione")
   context.user_data.clear()

 elif state=='upload_foto':
  if text.lower()=='fine':
   auto_id=context.user_data.get('foto_auto_id')
   if auto_id:
    auto=get_auto_by_id(auto_id)
    if auto:await update.message.reply_text(f"📷 Upload completato! {auto[1]} - Stanza {auto[3]}")
   context.user_data.clear()
  else:
   await update.message.reply_text("📷 Invia foto o scrivi 'fine'")

# ===== PHOTO HANDLER =====
async def handle_photo(update:Update,context:ContextTypes.DEFAULT_TYPE):
 state=context.user_data.get('state')
 if state=='upload_foto' or state.startswith('completa_foto_'):
  auto_id=context.user_data.get('foto_auto_id')
  if auto_id:
   file_id=update.message.photo[-1].file_id
   db_query('INSERT INTO foto (auto_id,file_id) VALUES (?,?)',(auto_id,file_id),'none')
   db_query('UPDATE auto SET foto_count=foto_count+1 WHERE id=?',(auto_id,),'none')
   count=db_query('SELECT foto_count FROM auto WHERE id=?',(auto_id,),'one')[0]
   
   if state.startswith('completa_foto_'):
    await update.message.reply_text(f"📷 Foto #{count} salvata!\n\nInvia altre foto o scrivi 'fine'/'skip' per completare l'auto")
   else:
    await update.message.reply_text(f"📷 Foto #{count} salvata! Altre foto o 'fine'")
 else:
  await update.message.reply_text("📷 Per caricare foto, usa /foto o /completa")

# ===== CALLBACK HANDLER =====
async def handle_callback_query(update:Update,context:ContextTypes.DEFAULT_TYPE):
 query=update.callback_query
 await query.answer()
 data=query.data
 
 if data.startswith('recupero_'):
  parts=data.split('_')
  auto_id,tipo=int(parts[1]),parts[2]
  operazioni={'richiesta':'PRIMO RITIRO','riconsegna':'RICONSEGNA TEMPORANEA','rientro':'RIENTRO IN PARCHEGGIO'}
  await query.edit_message_text(f"⏰ {operazioni[tipo]}:",reply_markup=create_tempo_keyboard(auto_id,tipo))
 
 elif data.startswith('tempo_'):
  parts=data.split('_')
  auto_id,tipo,tempo=int(parts[1]),parts[2],parts[3]
  auto=get_auto_by_id(auto_id)
  
  tempo_map={'15':'15 min ca.','30':'30 min ca.','45':'45 min ca.','coda':'In coda - altri ritiri prima','ritardo':'Possibile ritardo - traffico/lavori'}
  tempo_display=tempo_map[tempo]
  
  if tipo=='richiesta':nuovo_stato,desc='ritiro','PRIMO RITIRO AVVIATO'
  elif tipo=='riconsegna':nuovo_stato,desc='stand-by','RICONSEGNA CONFERMATA'
  elif tipo=='rientro':nuovo_stato,desc='ritiro','RIENTRO AVVIATO'
  
  db_query('UPDATE auto SET stato=?,tempo_stimato=?,ora_accettazione=CURRENT_TIMESTAMP WHERE id=?',(nuovo_stato,tempo_display,auto_id),'none')
  
  valet_username=update.effective_user.username or"Valet"
  await invia_notifica_avviato(context,auto,tempo_display,valet_username,tipo)
  
  ghost_text=" 👻" if auto[14] else ""
  num_text=f"#{auto[11]}" if not auto[14] else "GHOST"
  await query.edit_message_text(f"✅ {desc}!\n\n{num_text} | {auto[1]} ({auto[2]}){ghost_text}\n🏨 Stanza: {auto[3]}\n⏰ {tempo_display}\n\n📅 {now_italy().strftime('%d/%m/%Y alle %H:%M')}")

 elif data.startswith('park_'):
  auto_id=int(data.split('_')[1])
  db_query('UPDATE auto SET stato=?,data_park=CURRENT_DATE WHERE id=?',('parcheggiata',auto_id),'none')
  auto=get_auto_by_id(auto_id)
  num_text=f"#{auto[11]}" if not auto[14] else "GHOST"
  await query.edit_message_text(f"🅿️ AUTO PARCHEGGIATA!\n\n{num_text} | {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}\n\n📅 {now_italy().strftime('%d/%m/%Y alle %H:%M')}")

 elif data.startswith('completa_'):
  auto_id=int(data.split('_')[1])
  auto=get_auto_by_id(auto_id)
  context.user_data['state']=f'completa_targa_{auto_id}'
  await query.edit_message_text(f"🔧 COMPLETA AUTO - Passo 1/3\n\n🚗 Targa attuale: {auto[1]}\n👤 Cliente: {auto[2]} - Stanza {auto[3]}\n\n🚗 Inserisci la TARGA REALE dell'auto:")

 elif data.startswith('partito_'):
  auto_id=int(data.split('_')[1])
  auto=get_auto_by_id(auto_id)
  keyboard=InlineKeyboardMarkup([[InlineKeyboardButton("✅ CONFERMA",callback_data=f"conferma_partito_{auto_id}")],[InlineKeyboardButton("❌ ANNULLA",callback_data="annulla_op")]])
  await query.edit_message_text(f"🏁 CONFERMA USCITA\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}",reply_markup=keyboard)
 
 elif data.startswith('conferma_partito_'):
  auto_id=int(data.split('_')[2])
  auto=get_auto_by_id(auto_id)
  db_query('UPDATE auto SET stato=?,data_uscita=CURRENT_DATE WHERE id=?',('uscita',auto_id),'none')
  await query.edit_message_text(f"🏁 AUTO PARTITA!\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}\n\n📅 {now_italy().strftime('%d/%m/%Y alle %H:%M')}")

 elif data.startswith('foto_'):
  auto_id=int(data.split('_')[1])
  context.user_data['state']='upload_foto'
  context.user_data['foto_auto_id']=auto_id
  auto=get_auto_by_id(auto_id)
  await query.edit_message_text(f"📷 CARICA FOTO\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}\n\nInvia foto o scrivi 'fine'")
 
 elif data.startswith('mostra_foto_'):
  auto_id=int(data.split('_')[2])
  auto=get_auto_by_id(auto_id)
  foto_list=db_query('SELECT file_id,data_upload FROM foto WHERE auto_id=? ORDER BY data_upload',(auto_id,))
  await query.edit_message_text(f"📷 FOTO AUTO\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}\n📷 Totale: {len(foto_list)} foto")
  for i,(file_id,data_upload) in enumerate(foto_list[:5]):
   try:await update.effective_chat.send_photo(photo=file_id)
   except:pass
 
 elif data.startswith('servizi_auto_'):
  auto_id=int(data.split('_')[2])
  auto=get_auto_by_id(auto_id)
  keyboard=InlineKeyboardMarkup([
   [InlineKeyboardButton("🌙 Ritiro Notturno",callback_data=f"servizio_{auto_id}_ritiro_notturno")],
   [InlineKeyboardButton("🏠 Garage 10+ giorni",callback_data=f"servizio_{auto_id}_garage_10plus")],
   [InlineKeyboardButton("🚿 Autolavaggio",callback_data=f"servizio_{auto_id}_autolavaggio")]
  ])
  await query.edit_message_text(f"🔧 SERVIZI EXTRA\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}\n\nSeleziona servizio:",reply_markup=keyboard)
 
 elif data.startswith('servizio_'):
  parts=data.split('_')
  auto_id,tipo_servizio=int(parts[1]),'_'.join(parts[2:])
  auto=get_auto_by_id(auto_id)
  db_query('INSERT INTO servizi_extra (auto_id,tipo_servizio) VALUES (?,?)',(auto_id,tipo_servizio),'none')
  servizio_names={'ritiro_notturno':'🌙 Ritiro Notturno','garage_10plus':'🏠 Garage 10+ giorni','autolavaggio':'🚿 Autolavaggio'}
  servizio_nome=servizio_names.get(tipo_servizio,'🔧 Servizio Extra')
  await query.edit_message_text(f"✅ SERVIZIO REGISTRATO!\n\n{servizio_nome}\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}\n\n📅 {now_italy().strftime('%d/%m/%Y alle %H:%M')}")
 
 elif data.startswith('prenota_auto_'):
  auto_id=int(data.split('_')[2])
  context.user_data.update({'auto_id':auto_id,'state':'prenota_data'})
  auto=get_auto_by_id(auto_id)
  await query.edit_message_text(f"📅 PRENOTA PARTENZA\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}\n\nData partenza (gg/mm/aaaa):")

 elif data.startswith('riconsegna_'):
  auto_id=int(data.split('_')[1])
  db_query('UPDATE auto SET stato=? WHERE id=?',('riconsegna',auto_id),'none')
  auto=get_auto_by_id(auto_id)
  await invia_notifica_riconsegna(context,auto)
  await query.edit_message_text(f"🚪 RICONSEGNA RICHIESTA!\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}\n\n📅 {now_italy().strftime('%d/%m/%Y alle %H:%M')}\n📱 Notifica inviata ai Valet!")
 
 elif data.startswith('rientro_'):
  auto_id=int(data.split('_')[1])
  db_query('UPDATE auto SET stato=? WHERE id=?',('rientro',auto_id),'none')
  auto=get_auto_by_id(auto_id)
  await invia_notifica_rientro(context,auto)
  await query.edit_message_text(f"🔄 RIENTRO RICHIESTO!\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}\n\n📅 {now_italy().strftime('%d/%m/%Y alle %H:%M')}\n📱 Notifica inviata ai Valet!")

 elif data.startswith('modifica_'):
  auto_id=int(data.split('_')[1])
  auto=get_auto_by_id(auto_id)
  keyboard=InlineKeyboardMarkup([
   [InlineKeyboardButton("🚗 Modifica Targa",callback_data=f"mod_targa_{auto_id}")],
   [InlineKeyboardButton("👤 Modifica Cognome",callback_data=f"mod_cognome_{auto_id}")],
   [InlineKeyboardButton("🏨 Modifica Stanza",callback_data=f"mod_stanza_{auto_id}")],
   [InlineKeyboardButton("📦 Modifica BOX",callback_data=f"mod_box_{auto_id}")],
   [InlineKeyboardButton("📝 Modifica Note",callback_data=f"mod_note_{auto_id}")]
  ])
  box_text=f"BOX: {auto[4]}" if auto[4] else "BOX: Non assegnato"
  note_text=f"Note: {auto[5]}" if auto[5] else "Note: Nessuna"
  await query.edit_message_text(f"✏️ MODIFICA AUTO\n\n🚗 {auto[1]} - {auto[2]}\n🏨 Stanza: {auto[3]}\n📦 {box_text}\n📝 {note_text}\n\nCosa modificare?",reply_markup=keyboard)
 
 elif data.startswith('mod_'):
  field,auto_id=data.split('_')[1],int(data.split('_')[2])
  auto=get_auto_by_id(auto_id)
  context.user_data['state']=f'mod_{field}_{auto_id}'
  prompts={'targa':'🚗 Nuova TARGA:','cognome':'👤 Nuovo COGNOME:','stanza':'🏨 Nuova STANZA (0-999):','box':'📦 Nuovo BOX (0-999) o rimuovi:','note':'📝 Nuove NOTE o rimuovi:'}
  await query.edit_message_text(f"✏️ MODIFICA {field.upper()}\n\n{auto[1]} - Stanza {auto[3]}\n\n{prompts[field]}")

 elif data=='annulla_op':
  await query.edit_message_text("❌ Operazione annullata")

def main():
 TOKEN=os.getenv('TELEGRAM_BOT_TOKEN')
 if not TOKEN:logging.error("TOKEN mancante");return
 
 app=Application.builder().token(TOKEN).build()
 
 commands=[
  ("start",start),("help",help_command),("annulla",annulla_command),
  ("ritiro",ritiro_command),("prenota",prenota_command),("mostra_prenotazioni",mostra_prenotazioni_command),
  ("riconsegna",riconsegna_command),("rientro",rientro_command),("situazione",situazione_command),
  ("ghostcar",ghostcar_command),("makepark",makepark_command),
  ("recupero",recupero_command),("park",park_command),("completa",completa_command),("partito",partito_command),
  ("foto",foto_command),("vedi_foto",vedi_foto_command),("servizi",servizi_command),("servizi_stats",servizi_stats_command),
  ("modifica",modifica_command),("lista_auto",lista_auto_command),("export",export_command)
 ]
 
 for cmd,func in commands:app.add_handler(CommandHandler(cmd,func))
 app.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,handle_message))
 app.add_handler(MessageHandler(filters.PHOTO,handle_photo))
 app.add_handler(CallbackQueryHandler(handle_callback_query))
 
 logging.info(f"🚗 {BOT_NAME} v{BOT_VERSION} avviato!")
 app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=='__main__':main()
