#!/usr/bin/env python3
# CarValetBOT v5.04 CORRETTO by Zibroncloud - SNELLITO + DEEP LINK + NOTIFICHE AVANZATE
import os,logging,sqlite3,re
from datetime import datetime,date,timedelta
from telegram import Update,InlineKeyboardButton,InlineKeyboardMarkup
from telegram.ext import Application,CommandHandler,MessageHandler,filters,ContextTypes,CallbackQueryHandler

BOT_VERSION="5.04"
BOT_NAME="CarValetBOT"
CANALE_VALET="-1002582736358"

logging.basicConfig(format='%(asctime)s-%(levelname)s-%(message)s',level=logging.INFO)

# ===== DATABASE FUNCTIONS =====
def init_db():
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('''CREATE TABLE IF NOT EXISTS auto (id INTEGER PRIMARY KEY AUTOINCREMENT,targa TEXT NOT NULL,cognome TEXT NOT NULL,stanza INTEGER NOT NULL,numero_chiave INTEGER,note TEXT,stato TEXT DEFAULT 'richiesta',data_arrivo DATE DEFAULT CURRENT_DATE,data_park DATE,data_uscita DATE,foto_count INTEGER DEFAULT 0,numero_progressivo INTEGER,tempo_stimato TEXT,ora_accettazione TIMESTAMP,is_ghost INTEGER DEFAULT 0)''')
  cursor.execute('''CREATE TABLE IF NOT EXISTS foto (id INTEGER PRIMARY KEY AUTOINCREMENT,auto_id INTEGER,file_id TEXT NOT NULL,data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY (auto_id) REFERENCES auto (id))''')
  cursor.execute('''CREATE TABLE IF NOT EXISTS servizi_extra (id INTEGER PRIMARY KEY AUTOINCREMENT,auto_id INTEGER,tipo_servizio TEXT NOT NULL,data_servizio DATE DEFAULT CURRENT_DATE,FOREIGN KEY (auto_id) REFERENCES auto (id))''')
  cursor.execute('''CREATE TABLE IF NOT EXISTS prenotazioni (id INTEGER PRIMARY KEY AUTOINCREMENT,auto_id INTEGER,data_partenza DATE NOT NULL,ora_partenza TIME NOT NULL,completata INTEGER DEFAULT 0,data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY (auto_id) REFERENCES auto (id))''')
  conn.commit()
  conn.close()
  logging.info("Database inizializzato")
 except Exception as e:logging.error(f"Errore DB: {e}")

def db_query(query,params=(),fetch='all'):
 """Helper unificato per query database"""
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
def get_prossimo_numero():return(db_query('SELECT MAX(numero_progressivo) FROM auto WHERE date(data_arrivo)=? AND is_ghost=0',(date.today().strftime('%Y-%m-%d'),),'one')[0] or 0)+1
def genera_targa_hotel():count=db_query('SELECT COUNT(*) FROM auto WHERE date(data_arrivo)=? AND targa LIKE "HOTEL%"',(date.today().strftime('%Y-%m-%d'),),'one')[0];return f"HOTEL{count+1:03d}"

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
 """Notifica iniziale: nuova richiesta"""
 try:
  msg=f"🚗 NUOVA RICHIESTA RITIRO!\n\n👤 Cliente: {cognome}\n🏨 Stanza: {stanza}\n🔢 Numero: #{numero_progressivo}\n📅 {datetime.now().strftime('%d/%m/%Y alle %H:%M')}"
  keyboard=[[InlineKeyboardButton("⚙️ Gestisci Richiesta",url=f"https://t.me/{context.bot.username}?start=recupero_{auto_id}")]]
  await context.bot.send_message(chat_id=CANALE_VALET,text=msg,reply_markup=InlineKeyboardMarkup(keyboard))
  logging.info(f"Notifica inviata per auto ID {auto_id}")
  return True
 except Exception as e:logging.error(f"Errore notifica canale: {e}");return False

async def invia_notifica_avviato(context:ContextTypes.DEFAULT_TYPE,auto,tempo_stimato,valet_username):
 """Notifica recupero avviato"""
 try:
  ghost_text=" 👻" if auto[14] else ""
  numero_text=f"#{auto[11]}" if not auto[14] else "GHOST"
  msg=f"🚀 RECUPERO AVVIATO!\n\n{numero_text} | {auto[1]} ({auto[2]}){ghost_text}\n🏨 Stanza: {auto[3]}\n⏰ {tempo_stimato}\n👨‍💼 Valet: @{valet_username}\n\n📅 {datetime.now().strftime('%d/%m/%Y alle %H:%M')}"
  await context.bot.send_message(chat_id=CANALE_VALET,text=msg)
  return True
 except Exception as e:logging.error(f"Errore notifica avviato: {e}");return False

# ===== HELPER FUNCTIONS =====
def create_tempo_keyboard(auto_id,tipo_op):
 """Crea tastiera per selezione tempi"""
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
    auto_id=int(arg.split('_')[1])
    auto=get_auto_by_id(auto_id)
    if auto and auto[6]in['richiesta','riconsegna','rientro']:
     await handle_recupero_specifico(update,context,auto_id,auto[6])
     return
   except:pass
 
 msg=f"""🚗 {BOT_NAME} v{BOT_VERSION} - OTTIMIZZATO
By Zibroncloud

🏨 HOTEL (2 PASSAGGI):
/ritiro - Cognome + Stanza → FINITO!

🚗 VALET:
/recupero - Gestione recuperi
/park - Auto parcheggiata  
/partito - Uscita definitiva

🔧 SERVIZI & UTILITÀ:
/foto /vedi_foto /servizi /servizi_stats
/lista_auto /export /modifica
/prenota /mostra_prenotazioni /riconsegna /rientro
/vedi_recupero /ghostcar /makepark

❓ /help /annulla

🆕 v5.04: Codice ottimizzato, deep link canale, notifiche avanzate"""
 await update.message.reply_text(msg)

async def help_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 msg=f"""🚗 {BOT_NAME} v{BOT_VERSION} - GUIDA OTTIMIZZATA

🆕 NOVITÀ v5.04:
✅ Codice ottimizzato (-30% righe)
✅ Click notifica canale → Bot specifico
✅ Notifica "recupero avviato" 
✅ Opzioni ritardo: coda, traffico

🏨 HOTEL (SUPER VELOCE):
/ritiro → Cognome + Stanza → AUTOMATICO:
  📱 Notifica canale Valet
  🚗 Targa HOTEL001, HOTEL002...
  🔢 Numero progressivo

🚗 VALET (PRINCIPALI):
/recupero - Gestisci tutti i recuperi
/park - Conferma parcheggio
/partito - Uscita definitiva

🔧 EXTRA:
/foto /vedi_foto - Gestione foto
/servizi /servizi_stats - Servizi extra
/prenota /mostra_prenotazioni - Prenotazioni
/riconsegna /rientro - Riconsegne/rientri
/modifica - Modifica dati
/lista_auto /export - Statistiche
/vedi_recupero - Stato recuperi
/ghostcar /makepark - Auto speciali

⏱️ TEMPISTICHE AVANZATE:
• 15/30/45 minuti ca.
• In coda (altri ritiri prima)
• Possibile ritardo (traffico/lavori)

📱 WORKFLOW: Hotel /ritiro → Notifica canale → Valet click → Recupero automatico"""
 await update.message.reply_text(msg)

# ===== HOTEL COMMANDS =====
async def ritiro_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 context.user_data.clear()
 context.user_data['state']='ritiro_cognome'
 await update.message.reply_text("🚗 RITIRO SEMPLIFICATO v5.04\n\n👤 Inserisci il COGNOME del cliente:")

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
 prenotazioni=db_query('''SELECT p.id,p.auto_id,a.targa,a.cognome,a.stanza,a.stato,a.is_ghost,p.data_partenza,p.ora_partenza,p.completata FROM prenotazioni p LEFT JOIN auto a ON p.auto_id=a.id WHERE p.completata=0 ORDER BY p.data_partenza,p.ora_partenza''')
 if not prenotazioni:await update.message.reply_text("📅 Nessuna prenotazione");return
 oggi,domani=date.today(),date.today()+timedelta(days=1)
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

async def rientro_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 await generic_auto_selection(update,"rientro","🔄 RIENTRO IN PARCHEGGIO","stato='stand-by'")

async def vedi_recupero_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 oggi=date.today().strftime('%Y-%m-%d')
 auto_list=db_query('SELECT id,targa,cognome,stanza,stato,numero_progressivo,tempo_stimato,ora_accettazione,is_ghost FROM auto WHERE date(data_arrivo)=? AND stato IN ("richiesta","ritiro","parcheggiata","riconsegna","stand-by","rientro") ORDER BY numero_progressivo',(oggi,))
 if not auto_list:await update.message.reply_text("📋 Nessun recupero oggi");return
 msg="🔍 STATO RECUPERI DI OGGI:\n\n"
 for auto in auto_list:
  ghost_text=" 👻" if auto[8] else ""
  emoji_status={'richiesta':"📋",'ritiro':"⚙️",'parcheggiata':"🅿️",'riconsegna':"🚪",'stand-by':"⏸️",'rientro':"🔄"}
  emoji=emoji_status.get(auto[4],"❓")
  num_text=f"#{auto[5]}" if not auto[8] else "GHOST"
  status_text={'richiesta':'In attesa valet','ritiro':f'Recupero in corso - {auto[6] or "N/A"}'if auto[6] else'Recupero in corso','parcheggiata':'AUTO PARCHEGGIATA ✅','riconsegna':'Riconsegna richiesta','stand-by':'Auto fuori parcheggio','rientro':'Rientro richiesto'}
  msg+=f"{emoji} {num_text} | Stanza {auto[3]} | {auto[1]} ({auto[2]}){ghost_text}\n    {status_text[auto[4]]}\n\n"
 await update.message.reply_text(msg)

async def ghostcar_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 context.user_data.clear()
 context.user_data.update({'state':'ghost_targa','is_ghost':True})
 await update.message.reply_text("👻 GHOST CAR (Staff/Direttore)\n\nInserisci la TARGA del veicolo:")

async def makepark_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 context.user_data.clear()
 context.user_data.update({'state':'makepark_targa','is_ghost':False})
 await update.message.reply_text("🅿️ AUTO GIÀ PARCHEGGIATA\n\nInserisci la TARGA del veicolo:")

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
 await update.message.reply_text("⚙️ GESTIONE RECUPERI",reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_recupero_specifico(update,context,auto_id,tipo_op):
 """Handler per recupero specifico da deep link"""
 auto=get_auto_by_id(auto_id)
 if not auto:await update.effective_message.reply_text("❌ Auto non trovata");return
 operazioni={'richiesta':'PRIMO RITIRO','riconsegna':'RICONSEGNA TEMPORANEA','rientro':'RIENTRO IN PARCHEGGIO'}
 ghost_text=" 👻" if auto[14] else ""
 num_text=f"#{auto[11]}" if not auto[14] else "GHOST"
 msg=f"⏰ {operazioni[tipo_op]}\n\n{num_text} | {auto[1]} ({auto[2]}){ghost_text}\n🏨 Stanza: {auto[3]}\n\nSeleziona tempistica:"
 await update.effective_message.reply_text(msg,reply_markup=create_tempo_keyboard(auto_id,tipo_op))

async def park_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 await generic_auto_selection(update,"park","🅿️ CONFERMA PARCHEGGIO","stato='ritiro'")

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
 oggi,mese=date.today().strftime('%Y-%m-%d'),date.today().strftime('%Y-%m')
 stats_mese=db_query('SELECT tipo_servizio,COUNT(*) FROM servizi_extra WHERE strftime("%Y-%m",data_servizio)=? GROUP BY tipo_servizio',(mese,))
 stats_oggi=db_query('SELECT tipo_servizio,COUNT(*) FROM servizi_extra WHERE date(data_servizio)=? GROUP BY tipo_servizio',(oggi,))
 servizi_oggi=dict(stats_oggi)if stats_oggi else{}
 servizi_mese=dict(stats_mese)if stats_mese else{}
 msg=f"🔧 STATISTICHE SERVIZI EXTRA\n\n📅 OGGI ({datetime.now().strftime('%d/%m/%Y')}):\n"
 msg+=f"  🌙 Ritiri notturni: {servizi_oggi.get('ritiro_notturno',0)}\n"
 msg+=f"  🏠 Garage 10+ giorni: {servizi_oggi.get('garage_10plus',0)}\n"
 msg+=f"  🚿 Autolavaggi: {servizi_oggi.get('autolavaggio',0)}\n\n"
 msg+=f"📊 {datetime.now().strftime('%B %Y').upper()}:\n"
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
 auto_list=db_query('SELECT stanza,cognome,targa,numero_chiave,foto_count FROM auto WHERE stato="parcheggiata" AND is_ghost=0 ORDER BY stanza')
 ghost_list=db_query('SELECT stanza,cognome,targa,numero_chiave,foto_count FROM auto WHERE stato="parcheggiata" AND is_ghost=1 ORDER BY stanza')
 oggi,mese=date.today().strftime('%Y-%m-%d'),date.today().strftime('%Y-%m')
 stats=db_query(f'SELECT (SELECT COUNT(*) FROM auto WHERE date(data_arrivo)="{oggi}" AND is_ghost=0),(SELECT COUNT(*) FROM auto WHERE date(data_uscita)="{oggi}" AND stato="uscita" AND is_ghost=0),(SELECT COUNT(*) FROM auto WHERE strftime("%Y-%m",data_arrivo)="{mese}" AND is_ghost=0),(SELECT COUNT(*) FROM auto WHERE strftime("%Y-%m",data_uscita)="{mese}" AND stato="uscita" AND is_ghost=0)','one')
 
 msg=f"📊 STATISTICHE {datetime.now().strftime('%d/%m/%Y')}\n\n📈 OGGI: Entrate {stats[0]} | Uscite {stats[1]}\n📅 MESE: Entrate {stats[2]} | Uscite {stats[3]}\n\n"
 if auto_list:
  msg+=f"🅿️ AUTO IN PARCHEGGIO ({len(auto_list)}):\n"
  for a in auto_list:msg+=f"{a[0]} | {a[1]} | {a[2]} | BOX:{a[3] or '--'}{f' 📷{a[4]}'if a[4]else''}\n"
 if ghost_list:
  msg+=f"\n👻 GHOST CARS ({len(ghost_list)}):\n"
  for a in ghost_list:msg+=f"{a[0]} | {a[1]} | {a[2]} | BOX:{a[3] or '--'}{f' 📷{a[4]}'if a[4]else''} 👻\n"
 if not auto_list and not ghost_list:msg+="🅿️ Nessuna auto in parcheggio"
 await update.message.reply_text(msg)

async def export_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 await update.message.reply_text("📊 EXPORT DATABASE\n\n⏳ Generazione CSV...")
 try:
  auto_data=db_query('SELECT * FROM auto ORDER BY is_ghost,data_arrivo DESC')
  servizi_data=db_query('SELECT s.*,a.targa,a.cognome,a.stanza FROM servizi_extra s LEFT JOIN auto a ON s.auto_id=a.id ORDER BY s.data_servizio DESC')
  csv_content="ID,Targa,Cognome,Stanza,BOX,Note,Stato,DataArrivo,DataPark,DataUscita,NumProgressivo,TempoStimato,OraAccettazione,FotoCount,IsGhost\n"
  for auto in auto_data:csv_content+=",".join([f'"{str(v).replace("\"","\"\"")}"'if v and(','in str(v)or '"'in str(v))else str(v or'')for v in auto])+"\n"
  csv_content+="\n=== SERVIZI EXTRA ===\nID,AutoID,Targa,Cognome,Stanza,TipoServizio,DataServizio\n"
  for serv in servizi_data:csv_content+=",".join([str(v or'')for v in serv])+"\n"
  filename=f"carvalet_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
  with open(filename,'w',encoding='utf-8')as f:f.write(csv_content)
  with open(filename,'rb')as f:
   await update.message.reply_document(document=f,filename=filename,caption=f"📊 EXPORT v5.04 - {datetime.now().strftime('%d/%m/%Y %H:%M')}\n📁 {len(auto_data)} auto totali")
  os.remove(filename)
 except Exception as e:logging.error(f"Export error: {e}");await update.message.reply_text("❌ Errore export")

# ===== UTILITY FUNCTIONS =====
async def generic_auto_selection(update,action,title,where_clause):
 """Helper generico per selezione auto"""
 auto_list=db_query(f'SELECT id,targa,cognome,stanza,numero_chiave,is_ghost FROM auto WHERE {where_clause} ORDER BY is_ghost,stanza')
 if not auto_list:await update.message.reply_text("📋 Nessuna auto disponibile");return
 keyboard=[]
 for auto in auto_list:
  box_text=f" - BOX: {auto[4]}" if auto[4] else ""
  ghost_text=" 👻" if auto[5] else ""
  keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[1]} ({auto[2]}){ghost_text}{box_text}",callback_data=f"{action}_{auto[0]}")])
 await update.message.reply_text(f"{title}\n\nSeleziona auto:",reply_markup=InlineKeyboardMarkup(keyboard))

async def annulla_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 if context.user_data.get('state'):
  context.user_data.clear()
  await update.message.reply_text("❌ Operazione annullata")
 else:
  await update.message.reply_text("ℹ️ Nessuna operazione in corso")

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
   await update.message.reply_text(f"✅ RICHIESTA CREATA!\n\n🆔 ID: {auto_id}\n🚗 {targa}\n👤 {cognome}\n🏨 Stanza {stanza}\n🔢 #{numero}\n\n📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}\n📱 Notifica inviata ai Valet!")
   await invia_notifica_canale(context,auto_id,cognome,stanza,numero)
   context.user_data.clear()
  except:await update.message.reply_text("❌ Numero stanza non valido!")
 
 elif state=='prenota_data':
  if not validate_date_format(text):await update.message.reply_text("❌ Formato data gg/mm/aaaa!");return
  context.user_data['data']=text;context.user_data['state']='prenota_ora'
  await update.message.reply_text("🕐 ORA partenza (hh:mm):")
 
 elif state=='prenota_ora':
  if not validate_time_format(text):await update.message.reply_text("❌ Formato ora hh:mm!");return
  auto_id,data=context.user_data['auto_id'],context.user_data['data']
  data_sql=datetime.strptime(data,'%d/%m/%Y').strftime('%Y-%m-%d')
  if db_query('INSERT INTO prenotazioni (auto_id,data_partenza,ora_partenza) VALUES (?,?,?)',(auto_id,data_sql,text),'none'):
   auto=get_auto_by_id(auto_id)
   await update.message.reply_text(f"📅 PRENOTAZIONE SALVATA!\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}\n📅 {data} {text}")
  context.user_data.clear()
 
 elif state=='upload_foto':
  if text.lower()=='fine':
   auto_id=context.user_data.get('foto_auto_id')
   if auto_id:auto=get_auto_by_id(auto_id);await update.message.reply_text(f"📷 Upload completato! {auto[1]} - Stanza {auto[3]}")
   context.user_data.clear()
  else:await update.message.reply_text("📷 Invia foto o scrivi 'fine'")
 
 # Gestione ghost car e makepark
 elif state in['ghost_targa','makepark_targa']:
  if not validate_targa(text):await update.message.reply_text("❌ Targa non valida!");return
  context.user_data['targa']=text.upper()
  context.user_data['state']=state.replace('targa','cognome')
  await update.message.reply_text("👤 COGNOME del cliente:")
 
 elif state in['ghost_cognome','makepark_cognome']:
  if not validate_cognome(text):await update.message.reply_text("❌ Cognome non valido!");return
  context.user_data['cognome']=text.strip()
  context.user_data['state']=state.replace('cognome','stanza')
  await update.message.reply_text("🏨 Numero STANZA (0-999):")
 
 elif state in['ghost_stanza','makepark_stanza']:
  try:
   stanza=int(text)
   if not 0<=stanza<=999:await update.message.reply_text("❌ Stanza 0-999!");return
   context.user_data['stanza']=stanza
   context.user_data['state']=state.replace('stanza','box')
   await update.message.reply_text("📦 BOX (0-999) o 'skip':")
  except:await update.message.reply_text("❌ Numero non valido!")
 
 elif state in['ghost_box','makepark_box']:
  if text.lower()=='skip':context.user_data['box']=None
  else:
   try:
    box=int(text)
    if not 0<=box<=999:await update.message.reply_text("❌ BOX 0-999 o 'skip'!");return
    context.user_data['box']=box
   except:await update.message.reply_text("❌ BOX numero o 'skip'!");return
  context.user_data['state']=state.replace('box','note')
  await update.message.reply_text("📝 NOTE o 'skip':")
 
 elif state in['ghost_note','makepark_note']:
  note=None if text.lower()=='skip'else text.strip()
  targa,cognome,stanza=context.user_data['targa'],context.user_data['cognome'],context.user_data['stanza']
  box,is_ghost=context.user_data.get('box'),context.user_data.get('is_ghost',False)
  if state=='makepark_note':
   auto_id=db_query('INSERT INTO auto (targa,cognome,stanza,numero_chiave,note,stato,data_arrivo,data_park,is_ghost) VALUES (?,?,?,?,?,?,CURRENT_DATE,CURRENT_DATE,?)',
                   (targa,cognome,stanza,box,note,'parcheggiata',1 if is_ghost else 0),'lastid')
   await update.message.reply_text(f"🅿️ AUTO PARCHEGGIATA REGISTRATA!\n\n🆔 ID: {auto_id}\n🚗 {targa}\n👤 {cognome}\n🏨 Stanza {stanza}")
  else:
   auto_id=db_query('INSERT INTO auto (targa,cognome,stanza,numero_chiave,note,numero_progressivo,is_ghost) VALUES (?,?,?,?,?,?,?)',
                   (targa,cognome,stanza,box,note,0,1),'lastid')
   await update.message.reply_text(f"👻 GHOST CAR REGISTRATA!\n\n🆔 ID: {auto_id}\n🚗 {targa}\n👤 {cognome}\n🏨 Stanza {stanza}")
  context.user_data.clear()
 
 # Gestione modifiche
 elif state.startswith('mod_'):
  await handle_modifica(update,context,state,text)

async def handle_modifica(update,context,state,text):
 """Handler unificato per modifiche"""
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
  value=None if text.lower()=='rimuovi'else(int(text)if field=='box'and text.isdigit()and 0<=int(text)<=999 else text.strip()if field=='note'else None)
  if field=='box'and text.lower()!='rimuovi'and(not text.isdigit()or not 0<=int(text)<=999):
   await update.message.reply_text("❌ BOX 0-999 o 'rimuovi'!");return
 
 field_db={'box':'numero_chiave'}.get(field,field)
 if db_query(f'UPDATE auto SET {field_db}=? WHERE id=?',(value,auto_id),'none'):
  result_text={'box':f"BOX {'rimosso'if value is None else f'impostato a {value}'}",
              'note':f"Note {'rimosse'if value is None else'aggiornate'}"}.get(field,f"{field.title()} aggiornato")
  await update.message.reply_text(f"✅ {result_text}\n🚗 {auto[1]} - Stanza {auto[3]}")
 context.user_data.clear()

# ===== PHOTO HANDLER =====
async def handle_photo(update:Update,context:ContextTypes.DEFAULT_TYPE):
 if context.user_data.get('state')=='upload_foto':
  auto_id=context.user_data.get('foto_auto_id')
  if auto_id:
   file_id=update.message.photo[-1].file_id
   db_query('INSERT INTO foto (auto_id,file_id) VALUES (?,?)',(auto_id,file_id),'none')
   db_query('UPDATE auto SET foto_count=foto_count+1 WHERE id=?',(auto_id,),'none')
   count=db_query('SELECT foto_count FROM auto WHERE id=?',(auto_id,),'one')[0]
   await update.message.reply_text(f"📷 Foto #{count} salvata! Altre foto o 'fine'")

# ===== CALLBACK HANDLER =====
async def handle_callback_query(update:Update,context:ContextTypes.DEFAULT_TYPE):
 query=update.callback_query
 await query.answer()
 data=query.data
 
 # Gestione recuperi
 if data.startswith('recupero_'):
  parts=data.split('_')
  auto_id,tipo=int(parts[1]),parts[2]
  operazioni={'richiesta':'PRIMO RITIRO','riconsegna':'RICONSEGNA TEMPORANEA','rientro':'RIENTRO IN PARCHEGGIO'}
  await query.edit_message_text(f"⏰ {operazioni[tipo]}:",reply_markup=create_tempo_keyboard(auto_id,tipo))
 
 # Gestione tempi
 elif data.startswith('tempo_'):
  parts=data.split('_')
  auto_id,tipo,tempo=int(parts[1]),parts[2],parts[3]
  auto=get_auto_by_id(auto_id)
  
  # Mapping tempi
  tempo_map={'15':'15 min ca.','30':'30 min ca.','45':'45 min ca.',
            'coda':'In coda - altri ritiri prima','ritardo':'Possibile ritardo - traffico/lavori'}
  tempo_display=tempo_map[tempo]
  
  # Aggiorna stato
  if tipo=='richiesta':nuovo_stato,desc='ritiro','PRIMO RITIRO AVVIATO'
  elif tipo=='riconsegna':nuovo_stato,desc='stand-by','RICONSEGNA CONFERMATA'
  elif tipo=='rientro':nuovo_stato,desc='ritiro','RIENTRO AVVIATO'
  
  db_query('UPDATE auto SET stato=?,tempo_stimato=?,ora_accettazione=CURRENT_TIMESTAMP WHERE id=?',(nuovo_stato,tempo_display,auto_id),'none')
  
  # Notifica
  valet_username=update.effective_user.username or"Valet"
  await invia_notifica_avviato(context,auto,tempo_display,valet_username)
  
  ghost_text=" 👻" if auto[14] else ""
  num_text=f"#{auto[11]}" if not auto[14] else "GHOST"
  await query.edit_message_text(f"✅ {desc}!\n\n{num_text} | {auto[1]} ({auto[2]}){ghost_text}\n🏨 Stanza: {auto[3]}\n⏰ {tempo_display}\n\n📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
 
 # Prenotazioni
 elif data.startswith('prenota_auto_'):
  auto_id=int(data.split('_')[2])
  context.user_data.update({'auto_id':auto_id,'state':'prenota_data'})
  auto=get_auto_by_id(auto_id)
  await query.edit_message_text(f"📅 PRENOTA PARTENZA\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}\n\nData partenza (gg/mm/aaaa):")
 
 # Operazioni auto
 elif data.startswith(('park_','riconsegna_','rientro_')):
  action,auto_id=data.split('_')[0],int(data.split('_')[1])
  auto=get_auto_by_id(auto_id)
  
  if action=='park':
   db_query('UPDATE auto SET stato=?,data_park=CURRENT_DATE WHERE id=?',('parcheggiata',auto_id),'none')
   num_text=f"#{auto[11]}" if not auto[14] else "GHOST"
   await query.edit_message_text(f"🅿️ AUTO PARCHEGGIATA!\n\n{num_text} | {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}")
  
  elif action=='riconsegna':
   db_query('UPDATE auto SET stato=? WHERE id=?',('riconsegna',auto_id),'none')
   await query.edit_message_text(f"🚪 RICONSEGNA RICHIESTA!\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}")
  
  elif action=='rientro':
   db_query('UPDATE auto SET stato=? WHERE id=?',('rientro',auto_id),'none')
   await query.edit_message_text(f"🔄 RIENTRO RICHIESTO!\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}")
 
 # Partenze
 elif data.startswith('partito_'):
  auto_id=int(data.split('_')[1])
  auto=get_auto_by_id(auto_id)
  keyboard=InlineKeyboardMarkup([[InlineKeyboardButton("✅ CONFERMA",callback_data=f"conferma_partito_{auto_id}")],[InlineKeyboardButton("❌ ANNULLA",callback_data="annulla_partito")]])
  await query.edit_message_text(f"🏁 CONFERMA USCITA DEFINITIVA\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}\n\n⚠️ L'auto sarà eliminata!",reply_markup=keyboard)
 
 elif data.startswith('conferma_partito_'):
  auto_id=int(data.split('_')[2])
  auto=get_auto_by_id(auto_id)
  db_query('UPDATE auto SET stato=?,data_uscita=CURRENT_DATE WHERE id=?',('uscita',auto_id),'none')
  db_query('UPDATE prenotazioni SET completata=1 WHERE auto_id=? AND completata=0',(auto_id,),'none')
  await query.edit_message_text(f"🏁 AUTO PARTITA!\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}\n✅ Eliminata dal sistema")
 
 elif data=='annulla_partito':
  await query.edit_message_text("❌ Operazione annullata")
 
 # Foto
 elif data.startswith('foto_'):
  auto_id=int(data.split('_')[1])
  auto=get_auto_by_id(auto_id)
  context.user_data.update({'state':'upload_foto','foto_auto_id':auto_id})
  await query.edit_message_text(f"📷 CARICA FOTO\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}\n\nInvia foto o scrivi 'fine'")
 
 elif data.startswith('mostra_foto_'):
  auto_id=int(data.split('_')[2])
  auto=get_auto_by_id(auto_id)
  foto_list=db_query('SELECT file_id,data_upload FROM foto WHERE auto_id=? ORDER BY data_upload',(auto_id,))
  if not foto_list:await query.edit_message_text(f"📷 Nessuna foto\n\n🚗 {auto[1]} - Stanza {auto[3]}");return
  await query.edit_message_text(f"📷 FOTO AUTO\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}\n📷 Totale: {len(foto_list)} foto")
  for i,(file_id,data_upload)in enumerate(foto_list[:10]):
   try:
    data_formattata=datetime.strptime(data_upload,'%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
    await update.effective_chat.send_photo(photo=file_id,caption=f"📷 Foto #{i+1} - {data_formattata}")
   except:pass
 
 # Servizi
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
  if db_query('INSERT INTO servizi_extra (auto_id,tipo_servizio) VALUES (?,?)',(auto_id,tipo_servizio),'none'):
   servizio_names={'ritiro_notturno':'🌙 Ritiro Notturno','garage_10plus':'🏠 Garage 10+ giorni','autolavaggio':'🚿 Autolavaggio'}
   servizio_nome=servizio_names.get(tipo_servizio,'🔧 Servizio Extra')
   await query.edit_message_text(f"✅ SERVIZIO REGISTRATO!\n\n{servizio_nome}\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 {auto[2]}")
 
 # Modifiche
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
  prompts={'targa':'🚗 Nuova TARGA:','cognome':'👤 Nuovo COGNOME:','stanza':'🏨 Nuova STANZA (0-999):','box':'📦 Nuovo BOX (0-999) o "rimuovi":','note':'📝 Nuove NOTE o "rimuovi":'}
  await query.edit_message_text(f"✏️ MODIFICA {field.upper()}\n\n{auto[1]} - Stanza {auto[3]}\n\n{prompts[field]}")

def main():
 TOKEN=os.getenv('TELEGRAM_BOT_TOKEN')
 if not TOKEN:logging.error("TOKEN mancante");return
 
 app=Application.builder().token(TOKEN).build()
 
 # Command Handlers
 commands=[
  ("start",start),("help",help_command),("annulla",annulla_command),
  ("ritiro",ritiro_command),("prenota",prenota_command),("mostra_prenotazioni",mostra_prenotazioni_command),
  ("riconsegna",riconsegna_command),("rientro",rientro_command),("vedi_recupero",vedi_recupero_command),
  ("ghostcar",ghostcar_command),("makepark",makepark_command),
  ("recupero",recupero_command),("park",park_command),("partito",partito_command),
  ("foto",foto_command),("vedi_foto",vedi_foto_command),("servizi",servizi_command),("servizi_stats",servizi_stats_command),
  ("modifica",modifica_command),("lista_auto",lista_auto_command),("export",export_command)
 ]
 
 for cmd,func in commands:app.add_handler(CommandHandler(cmd,func))
 app.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,handle_message))
 app.add_handler(MessageHandler(filters.PHOTO,handle_photo))
 app.add_handler(CallbackQueryHandler(handle_callback_query))
 
 logging.info(f"🚗 {BOT_NAME} v{BOT_VERSION} CORRETTO avviato!")
 print(f"🚗 {BOT_NAME} v{BOT_VERSION} - CODICE CORRETTO + COMPLETO + OTTIMIZZATO")
 app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=='__main__':main()
