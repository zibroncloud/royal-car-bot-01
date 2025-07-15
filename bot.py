#!/usr/bin/env python3
# CarValetBOT v5.02 COMPLETA by Zibroncloud
import os,logging,sqlite3,re
from datetime import datetime,date,timedelta
from telegram import Update,InlineKeyboardButton,InlineKeyboardMarkup
from telegram.ext import Application,CommandHandler,MessageHandler,filters,ContextTypes,CallbackQueryHandler

BOT_VERSION="5.02"
BOT_NAME="CarValetBOT"
logging.basicConfig(format='%(asctime)s-%(levelname)s-%(message)s',level=logging.INFO)

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

def get_prossimo_numero():
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  oggi=date.today().strftime('%Y-%m-%d')
  cursor.execute('SELECT MAX(numero_progressivo) FROM auto WHERE date(data_arrivo)=? AND is_ghost=0',(oggi,))
  result=cursor.fetchone()
  conn.close()
  return (result[0] or 0)+1
 except:return 1

def aggiungi_servizio_extra(auto_id,tipo_servizio):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('INSERT INTO servizi_extra (auto_id,tipo_servizio) VALUES (?,?)',(auto_id,tipo_servizio))
  conn.commit()
  conn.close()
  return True
 except:return False

def aggiungi_prenotazione(auto_id,data_partenza,ora_partenza):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('INSERT INTO prenotazioni (auto_id,data_partenza,ora_partenza) VALUES (?,?,?)',(auto_id,data_partenza,ora_partenza))
  conn.commit()
  conn.close()
  return True
 except:return False

def get_prenotazioni():
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('''SELECT p.id,p.auto_id,a.targa,a.cognome,a.stanza,a.stato,a.is_ghost,p.data_partenza,p.ora_partenza,p.completata FROM prenotazioni p LEFT JOIN auto a ON p.auto_id=a.id WHERE p.completata=0 ORDER BY p.data_partenza,p.ora_partenza''')
  result=cursor.fetchall()
  conn.close()
  return result
 except:return[]

def completa_prenotazione(auto_id):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('UPDATE prenotazioni SET completata=1 WHERE auto_id=? AND completata=0',(auto_id,))
  conn.commit()
  conn.close()
  return True
 except:return False

def get_servizi_stats():
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  mese_corrente=date.today().strftime('%Y-%m')
  cursor.execute('SELECT tipo_servizio,COUNT(*) FROM servizi_extra WHERE strftime("%Y-%m",data_servizio)=? GROUP BY tipo_servizio',(mese_corrente,))
  stats_mese=cursor.fetchall()
  oggi=date.today().strftime('%Y-%m-%d')
  cursor.execute('SELECT tipo_servizio,COUNT(*) FROM servizi_extra WHERE date(data_servizio)=? GROUP BY tipo_servizio',(oggi,))
  stats_oggi=cursor.fetchall()
  conn.close()
  return stats_mese,stats_oggi
 except:return [],[]

def validate_date_format(date_str):
 try:
  datetime.strptime(date_str,'%d/%m/%Y')
  return True
 except:return False

def validate_time_format(time_str):
 try:
  datetime.strptime(time_str,'%H:%M')
  return True
 except:return False

init_db()

def validate_targa(targa):
 targa=targa.upper().strip()
 p1=r'^[A-Z]{2}[0-9]{3}[A-Z]{2}$'
 p2=r'^[A-Z0-9]{4,10}$'
 p3=r'^[A-Z0-9]{1,4}[-\s][A-Z0-9]{1,4}[-\s][A-Z0-9]{1,4}$'
 return bool(re.match(p1,targa))or bool(re.match(p2,targa))or bool(re.match(p3,targa.replace(' ','-')))

def validate_cognome(cognome):return bool(re.match(r"^[A-Za-zÀ-ÿ\s']+$",cognome.strip()))

def validate_date(date_str):
 try:
  datetime.strptime(date_str,'%d/%m/%Y')
  return True
 except:return False

def get_foto_by_auto_id(auto_id):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT file_id,data_upload FROM foto WHERE auto_id=? ORDER BY data_upload',(auto_id,))
  result=cursor.fetchall()
  conn.close()
  return result
 except:return[]

def get_auto_con_foto():
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('''SELECT DISTINCT a.id,a.targa,a.cognome,a.stanza,a.stato,a.foto_count,a.is_ghost FROM auto a INNER JOIN foto f ON a.id=f.auto_id WHERE a.foto_count>0 ORDER BY a.stanza''')
  result=cursor.fetchall()
  conn.close()
  return result
 except:return[]

def get_auto_by_id(auto_id):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT * FROM auto WHERE id=?',(auto_id,))
  result=cursor.fetchone()
  conn.close()
  return result
 except:return None

def update_auto_stato(auto_id,nuovo_stato):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  if nuovo_stato=='parcheggiata':cursor.execute('UPDATE auto SET stato=?,data_park=CURRENT_DATE WHERE id=?',(nuovo_stato,auto_id))
  elif nuovo_stato=='uscita':cursor.execute('UPDATE auto SET stato=?,data_uscita=CURRENT_DATE WHERE id=?',(nuovo_stato,auto_id))
  else:cursor.execute('UPDATE auto SET stato=? WHERE id=?',(nuovo_stato,auto_id))
  conn.commit()
  conn.close()
  return True
 except:return False

def update_auto_field(auto_id,field,value):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute(f'UPDATE auto SET {field}=? WHERE id=?',(value,auto_id))
  conn.commit()
  conn.close()
  return True
 except:return False

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
 msg=f"""🚗 {BOT_NAME} v{BOT_VERSION}
By Zibroncloud

🏨 COMANDI HOTEL:
/ritiro - Richiesta ritiro auto
/prenota - Prenota partenza auto (data/ora)
/vedi_recupero - Stato recuperi in corso
/riconsegna - Lista auto per riconsegna temporanea
/rientro - Richiesta rientro auto in stand-by

🚗 COMANDI VALET:
/recupero - Gestione recuperi (ritiri/riconsegne/rientri)
/mostra_prenotazioni - Visualizza partenze programmate
/foto - Carica foto auto
/vedi_foto - Visualizza foto auto
/park - Conferma auto parcheggiata
/partito - Auto uscita definitiva (da qualunque stato)
/modifica - Modifica TUTTI i dati auto

🔧 SERVIZI EXTRA:
/servizi - Registra servizi aggiuntivi (ritiro notturno, garage 10+, autolavaggio)
/servizi_stats - Statistiche mensili servizi extra

📊 COMANDI UTILITÀ:
/lista_auto - Auto in parcheggio + statistiche
/export - Esporta database in CSV per Excel

❓ COMANDI AIUTO:
/help - Mostra questa guida
/annulla - Annulla operazione in corso

🔑 NUMERI: Stanze e chiavi da 0 a 999
🌍 TARGHE: Italiane ed europee accettate"""
 await update.message.reply_text(msg)

async def help_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 msg=f"""🚗 {BOT_NAME} v{BOT_VERSION} - GUIDA COMPLETA

🏨 COMANDI HOTEL:
/ritiro - Crea nuova richiesta ritiro auto
/prenota - Prenota partenza auto con data/ora specifica
/vedi_recupero - Vedi tutti i recuperi con tempi stimati
/riconsegna - Richiesta riconsegna temporanea
/rientro - Richiesta rientro auto in stand-by

🚗 COMANDI VALET:
/recupero - Gestione completa recuperi (priorità automatica)
/mostra_prenotazioni - Visualizza tutte le partenze programmate
/foto - Carica foto dell'auto
/vedi_foto - Visualizza foto per auto/cliente
/park - Conferma auto parcheggiata
/partito - Uscita definitiva auto (da qualunque stato)
/modifica - Modifica targa, cognome, stanza, chiave, note

🔧 SERVIZI EXTRA:
/servizi - Registra servizi aggiuntivi per auto parcheggiate:
  🌙 Ritiro notturno
  🏠 Garage 10+ giorni  
  🚿 Autolavaggio
/servizi_stats - Statistiche mensili servizi (separate dal normale flusso)

📊 COMANDI UTILITÀ:
/lista_auto - Auto in parcheggio + statistiche
/export - Esporta database completo in CSV per Excel

❓ COMANDI AIUTO:
/start - Messaggio di benvenuto
/help - Questa guida
/annulla - Annulla operazione in corso

📋 WORKFLOW COMPLETO:
🔄 CICLO 1 - ARRIVO:
1️⃣ Hotel: /ritiro → 2️⃣ Valet: /recupero → 3️⃣ Valet: /park

🔄 CICLO 2 - RICONSEGNA TEMPORANEA:
4️⃣ Hotel: /riconsegna → 5️⃣ Valet: /recupero → Auto in stand-by

🔄 CICLO 3 - RIENTRO:
6️⃣ Hotel: /rientro → 7️⃣ Valet: /recupero → 8️⃣ Valet: /park

🔧 SERVIZI AGGIUNTIVI:
9️⃣ Valet: /servizi → Seleziona auto parcheggiata → Servizio completato

📅 PRENOTAZIONI PARTENZA (v5.02):
🔟 Hotel: /prenota → Seleziona auto → Data/Ora → Prenotazione salvata
1️⃣1️⃣ Valet: /mostra_prenotazioni → Vede tutte le partenze programmate
1️⃣2️⃣ Valet: /partito → Uscita definitiva + prenotazione completata

🏁 USCITA DEFINITIVA:
1️⃣3️⃣ Valet: /partito (da qualunque stato) → Auto eliminata

🎯 STATI AUTO:
📋 richiesta - Primo ritiro richiesto
⚙️ ritiro - Valet sta recuperando/riportando
🅿️ parcheggiata - In parcheggio
🚪 riconsegna - Riconsegna temporanea richiesta
⏸️ stand-by - Auto fuori (cliente l'ha presa)
🔄 rientro - Rientro richiesto
🏁 uscita - Partita definitivamente

🔢 NUMERAZIONE: Auto numerate giornalmente per priorità
🔧 SERVIZI EXTRA: Statistiche separate per servizi aggiuntivi
📅 PRENOTAZIONI: Sistema di prenotazione partenze programmata
🔑 RANGE NUMERI: Stanze e chiavi da 0 a 999
🌍 TARGHE ACCETTATE: Italiane (XX123XX), Europee, con trattini"""
 await update.message.reply_text(msg)

async def prenota_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT id,targa,cognome,stanza,numero_chiave,stato,is_ghost FROM auto WHERE stato!="uscita" ORDER BY is_ghost,stanza')
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("📋 Nessuna auto disponibile per prenotazione")
   return
  keyboard=[]
  emoji_map={'richiesta':'📋','ritiro':'⚙️','parcheggiata':'🅿️','riconsegna':'🚪','stand-by':'⏸️','rientro':'🔄'}
  for auto in auto_list:
   chiave_text=f" - Chiave: {auto[4]}" if auto[4] else ""
   ghost_text=" 👻" if auto[6] else ""
   emoji=emoji_map.get(auto[5],"❓")
   keyboard.append([InlineKeyboardButton(f"{emoji} Stanza {auto[3]} - {auto[1]} ({auto[2]}){ghost_text}{chiave_text}",callback_data=f"prenota_auto_{auto[0]}")])
  reply_markup=InlineKeyboardMarkup(keyboard)
  await update.message.reply_text("📅 PRENOTA PARTENZA AUTO\n\nSeleziona l'auto per prenotare la partenza:",reply_markup=reply_markup)
 except Exception as e:
  logging.error(f"Errore prenota: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def mostra_prenotazioni_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  prenotazioni=get_prenotazioni()
  if not prenotazioni:
   await update.message.reply_text("📅 Nessuna prenotazione di partenza in corso")
   return
  oggi=date.today()
  domani=oggi+timedelta(days=1)
  prenotazioni_oggi=[]
  prenotazioni_domani=[]
  prenotazioni_future=[]
  for pren in prenotazioni:
   data_partenza=datetime.strptime(pren[7],'%Y-%m-%d').date()
   if data_partenza==oggi:
    prenotazioni_oggi.append(pren)
   elif data_partenza==domani:
    prenotazioni_domani.append(pren)
   else:
    prenotazioni_future.append(pren)
  msg="📅 PRENOTAZIONI PARTENZA\n\n"
  if prenotazioni_oggi:
   msg+=f"🚨 OGGI ({oggi.strftime('%d/%m/%Y')}):\n"
   for pren in prenotazioni_oggi:
    _,_,targa,cognome,stanza,stato,is_ghost,_,ora_partenza,_=pren
    ghost_text=" 👻" if is_ghost else ""
    emoji_map={'richiesta':'📋','ritiro':'⚙️','parcheggiata':'🅿️','riconsegna':'🚪','stand-by':'⏸️','rientro':'🔄'}
    emoji=emoji_map.get(stato,"❓")
    msg+=f"  {ora_partenza} - {targa} ({cognome}) - Stanza {stanza}{ghost_text} - {emoji} {stato.upper()}\n"
   msg+="\n"
  if prenotazioni_domani:
   msg+=f"📅 DOMANI ({domani.strftime('%d/%m/%Y')}):\n"
   for pren in prenotazioni_domani:
    _,_,targa,cognome,stanza,stato,is_ghost,_,ora_partenza,_=pren
    ghost_text=" 👻" if is_ghost else ""
    emoji_map={'richiesta':'📋','ritiro':'⚙️','parcheggiata':'🅿️','riconsegna':'🚪','stand-by':'⏸️','rientro':'🔄'}
    emoji=emoji_map.get(stato,"❓")
    msg+=f"  {ora_partenza} - {targa} ({cognome}) - Stanza {stanza}{ghost_text} - {emoji} {stato.upper()}\n"
   msg+="\n"
  if prenotazioni_future:
   msg+=f"📆 PROSSIMI GIORNI:\n"
   for pren in prenotazioni_future:
    _,_,targa,cognome,stanza,stato,is_ghost,data_partenza,ora_partenza,_=pren
    ghost_text=" 👻" if is_ghost else ""
    emoji_map={'richiesta':'📋','ritiro':'⚙️','parcheggiata':'🅿️','riconsegna':'🚪','stand-by':'⏸️','rientro':'🔄'}
    emoji=emoji_map.get(stato,"❓")
    data_formattata=datetime.strptime(data_partenza,'%Y-%m-%d').strftime('%d/%m/%Y')
    msg+=f"  {data_formattata} {ora_partenza} - {targa} ({cognome}) - Stanza {stanza}{ghost_text} - {emoji} {stato.upper()}\n"
  await update.message.reply_text(msg)
 except Exception as e:
  logging.error(f"Errore mostra_prenotazioni: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle prenotazioni")

async def servizi_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT id,targa,cognome,stanza,numero_chiave,is_ghost FROM auto WHERE stato="parcheggiata" ORDER BY is_ghost,stanza')
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("📋 Nessuna auto in parcheggio per servizi")
   return
  keyboard=[]
  for auto in auto_list:
   chiave_text=f" - Chiave: {auto[4]}" if auto[4] else ""
   ghost_text=" 👻" if auto[5] else ""
   keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[1]} ({auto[2]}){ghost_text}{chiave_text}",callback_data=f"servizi_auto_{auto[0]}")])
  reply_markup=InlineKeyboardMarkup(keyboard)
  await update.message.reply_text("🔧 SERVIZI EXTRA\n\nSeleziona l'auto per registrare un servizio:",reply_markup=reply_markup)
 except Exception as e:
  logging.error(f"Errore servizi: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def servizi_stats_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  stats_mese,stats_oggi=get_servizi_stats()
  oggi_formattato=datetime.now().strftime('%d/%m/%Y')
  mese_formattato=datetime.now().strftime('%B %Y')
  msg=f"🔧 STATISTICHE SERVIZI EXTRA\n\n"
  msg+=f"📅 OGGI ({oggi_formattato}):\n"
  servizi_oggi={'ritiro_notturno':0,'garage_10plus':0,'autolavaggio':0}
  for tipo,count in stats_oggi:
   servizi_oggi[tipo]=count
  msg+=f"  🌙 Ritiri notturni: {servizi_oggi['ritiro_notturno']}\n"
  msg+=f"  🏠 Garage 10+ giorni: {servizi_oggi['garage_10plus']}\n"
  msg+=f"  🚿 Autolavaggi: {servizi_oggi['autolavaggio']}\n\n"
  msg+=f"📊 {mese_formattato.upper()}:\n"
  servizi_mese={'ritiro_notturno':0,'garage_10plus':0,'autolavaggio':0}
  for tipo,count in stats_mese:
   servizi_mese[tipo]=count
  msg+=f"  🌙 Ritiri notturni: {servizi_mese['ritiro_notturno']}\n"
  msg+=f"  🏠 Garage 10+ giorni: {servizi_mese['garage_10plus']}\n"
  msg+=f"  🚿 Autolavaggi: {servizi_mese['autolavaggio']}\n\n"
  totale_oggi=sum(servizi_oggi.values())
  totale_mese=sum(servizi_mese.values())
  msg+=f"📈 TOTALI:\n"
  msg+=f"  🔧 Servizi oggi: {totale_oggi}\n"
  msg+=f"  📅 Servizi mese: {totale_mese}"
  await update.message.reply_text(msg)
 except Exception as e:
  logging.error(f"Errore servizi_stats: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle statistiche")

async def annulla_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 state=context.user_data.get('state')
 if state:
  if state.startswith('ritiro_'):op="registrazione auto"
  elif state.startswith('ghost_'):op="registrazione ghost car"
  elif state.startswith('makepark_'):op="registrazione auto parcheggiata"
  elif state=='upload_foto':op="caricamento foto"
  elif state.startswith('mod_'):op="modifica auto"
  elif state.startswith('prenota_'):op="prenotazione partenza"
  else:op="operazione"
  context.user_data.clear()
  await update.message.reply_text(f"❌ {op.title()} annullata\n\nPuoi iniziare una nuova operazione quando vuoi.")
 else:await update.message.reply_text("ℹ️ Nessuna operazione in corso\n\nUsa /help per vedere tutti i comandi disponibili.")

async def vedi_foto_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  auto_con_foto=get_auto_con_foto()
  if not auto_con_foto:
   await update.message.reply_text("📷 Nessuna foto disponibile\n\nNon ci sono auto con foto caricate.")
   return
  stati=['parcheggiata','riconsegna','stand-by','rientro','ritiro','richiesta','uscita']
  auto_per_stato={}
  for auto in auto_con_foto:
   stato=auto[4]
   if stato not in auto_per_stato:auto_per_stato[stato]=[]
   auto_per_stato[stato].append(auto)
  keyboard=[]
  emoji_map={'parcheggiata':"🅿️",'riconsegna':"🚪",'stand-by':"⏸️",'rientro':"🔄",'ritiro':"⚙️",'richiesta':"📋",'uscita':"🏁"}
  for stato in stati:
   if stato in auto_per_stato:
    emoji=emoji_map.get(stato,"❓")
    for auto in auto_per_stato[stato]:
     id_auto,targa,cognome,stanza,_,foto_count,is_ghost=auto
     ghost_text=" 👻" if is_ghost else ""
     keyboard.append([InlineKeyboardButton(f"{emoji} Stanza {stanza} - {targa} ({cognome}){ghost_text} - 📷 {foto_count} foto",callback_data=f"mostra_foto_{id_auto}")])
  reply_markup=InlineKeyboardMarkup(keyboard)
  await update.message.reply_text("📷 VISUALIZZA FOTO AUTO\n\nSeleziona l'auto per vedere le sue foto:",reply_markup=reply_markup)
 except Exception as e:
  logging.error(f"Errore vedi_foto: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle auto con foto")

async def vedi_recupero_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  oggi=date.today().strftime('%Y-%m-%d')
  cursor.execute('SELECT id,targa,cognome,stanza,stato,numero_progressivo,tempo_stimato,ora_accettazione,is_ghost FROM auto WHERE date(data_arrivo)=? AND stato IN ("richiesta","ritiro","parcheggiata","riconsegna","stand-by","rientro") ORDER BY numero_progressivo',(oggi,))
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("📋 Nessun recupero in corso oggi")
   return
  msg="🔍 STATO RECUPERI DI OGGI:\n\n"
  for auto in auto_list:
   id_auto,targa,cognome,stanza,stato,numero,tempo_stimato,ora_accettazione,is_ghost=auto
   ghost_text=" 👻" if is_ghost else ""
   if stato=='richiesta':
    emoji="📋"
    status_text="In attesa valet (primo ritiro)"
   elif stato=='ritiro':
    emoji="⚙️"
    if tempo_stimato and ora_accettazione:
     try:
      ora_acc=datetime.strptime(ora_accettazione,'%Y-%m-%d %H:%M:%S')
      status_text=f"Recupero in corso - {tempo_stimato} min (dalle {ora_acc.strftime('%H:%M')})"
     except:status_text=f"Recupero in corso - {tempo_stimato} min"
    else:status_text="Recupero in corso"
   elif stato=='parcheggiata':
    emoji="🅿️"
    status_text="AUTO PARCHEGGIATA ✅"
   elif stato=='riconsegna':
    emoji="🚪"
    status_text="Riconsegna richiesta (da confermare)"
   elif stato=='stand-by':
    emoji="⏸️"
    status_text="Auto fuori parcheggio (cliente l'ha presa)"
   elif stato=='rientro':
    emoji="🔄"
    status_text="Rientro richiesto (da confermare)"
   if is_ghost:
    msg+=f"{emoji} GHOST - Stanza {stanza} | {targa} ({cognome}){ghost_text}\n    {status_text}\n\n"
   else:
    msg+=f"{emoji} #{numero} | Stanza {stanza} | {targa} ({cognome}){ghost_text}\n    {status_text}\n\n"
  await update.message.reply_text(msg)
 except Exception as e:
  logging.error(f"Errore vedi_recupero: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento dei recuperi")

async def ritiro_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 context.user_data.clear()
 context.user_data['state']='ritiro_targa'
 context.user_data['is_ghost']=False
 await update.message.reply_text("🚗 RITIRO AUTO\n\nInserisci la TARGA del veicolo:")

async def ghostcar_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 context.user_data.clear()
 context.user_data['state']='ghost_targa'
 context.user_data['is_ghost']=True
 await update.message.reply_text("👻 GHOST CAR (Auto Staff/Direttore)\n\nInserisci la TARGA del veicolo:")

async def makepark_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 context.user_data.clear()
 context.user_data['state']='makepark_targa'
 context.user_data['is_ghost']=False
 await update.message.reply_text("🅿️ REGISTRA AUTO GIÀ PARCHEGGIATA\n\nInserisci la TARGA del veicolo:")

async def riconsegna_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT id,targa,cognome,stanza,numero_chiave,is_ghost FROM auto WHERE stato="parcheggiata" ORDER BY is_ghost,stanza')
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("📋 Nessuna auto in parcheggio")
   return
  keyboard=[]
  for auto in auto_list:
   chiave_text=f" - Chiave: {auto[4]}" if auto[4] else ""
   ghost_text=" 👻" if auto[5] else ""
   keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[1]} ({auto[2]}){ghost_text}{chiave_text}",callback_data=f"riconsegna_{auto[0]}")])
  reply_markup=InlineKeyboardMarkup(keyboard)
  await update.message.reply_text("🚪 RICONSEGNA TEMPORANEA\n\nSeleziona l'auto (tornerà in stand-by):",reply_markup=reply_markup)
 except Exception as e:
  logging.error(f"Errore riconsegna: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def rientro_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT id,targa,cognome,stanza,numero_chiave,is_ghost FROM auto WHERE stato="stand-by" ORDER BY is_ghost,stanza')
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("📋 Nessuna auto in stand-by")
   return
  keyboard=[]
  for auto in auto_list:
   chiave_text=f" - Chiave: {auto[4]}" if auto[4] else ""
   ghost_text=" 👻" if auto[5] else ""
   keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[1]} ({auto[2]}){ghost_text}{chiave_text}",callback_data=f"rientro_{auto[0]}")])
  reply_markup=InlineKeyboardMarkup(keyboard)
  await update.message.reply_text("🔄 RIENTRO IN PARCHEGGIO\n\nSeleziona l'auto da far rientrare:",reply_markup=reply_markup)
 except Exception as e:
  logging.error(f"Errore rientro: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def partito_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT id,targa,cognome,stanza,stato,is_ghost FROM auto WHERE stato IN ("ritiro","parcheggiata","stand-by","rientro","riconsegna") ORDER BY is_ghost,stanza')
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("📋 Nessuna auto disponibile per uscita definitiva")
   return
  keyboard=[]
  emoji_map={'ritiro':"⚙️",'parcheggiata':"🅿️",'stand-by':"⏸️",'rientro':"🔄",'riconsegna':"🚪"}
  for auto in auto_list:
   emoji=emoji_map.get(auto[4],"❓")
   ghost_text=" 👻" if auto[5] else ""
   keyboard.append([InlineKeyboardButton(f"{emoji} Stanza {auto[3]} - {auto[1]} ({auto[2]}){ghost_text} - {auto[4]}",callback_data=f"partito_{auto[0]}")])
  reply_markup=InlineKeyboardMarkup(keyboard)
  await update.message.reply_text("🏁 USCITA DEFINITIVA AUTO\n\nSeleziona l'auto da far partire definitivamente:",reply_markup=reply_markup)
 except Exception as e:
  logging.error(f"Errore partito: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def recupero_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT id,targa,cognome,stanza,numero_chiave,numero_progressivo,stato,is_ghost FROM auto WHERE stato IN ("richiesta","riconsegna","rientro") ORDER BY is_ghost,numero_progressivo')
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("📋 Nessun recupero da gestire")
   return
  keyboard=[]
  for auto in auto_list:
   chiave_text=f" - Chiave: {auto[4]}" if auto[4] else ""
   ghost_text=" 👻" if auto[7] else ""
   if auto[6]=='richiesta':tipo_emoji="📋 RITIRO"
   elif auto[6]=='riconsegna':tipo_emoji="🚪 RICONSEGNA"
   elif auto[6]=='rientro':tipo_emoji="🔄 RIENTRO"
   if auto[7]:
    keyboard.append([InlineKeyboardButton(f"{tipo_emoji} GHOST - Stanza {auto[3]} - {auto[1]} ({auto[2]}){ghost_text}{chiave_text}",callback_data=f"recupero_{auto[0]}_{auto[6]}")])
   else:
    keyboard.append([InlineKeyboardButton(f"{tipo_emoji} #{auto[5]} - Stanza {auto[3]} - {auto[1]} ({auto[2]}){ghost_text}{chiave_text}",callback_data=f"recupero_{auto[0]}_{auto[6]}")])
  reply_markup=InlineKeyboardMarkup(keyboard)
  await update.message.reply_text("⚙️ GESTIONE RECUPERI (Ordine cronologico)\n\nSeleziona l'operazione da gestire:",reply_markup=reply_markup)
 except Exception as e:
  logging.error(f"Errore recupero: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle operazioni")

async def foto_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT id,targa,cognome,stanza,is_ghost FROM auto WHERE stato IN ("ritiro","parcheggiata") ORDER BY is_ghost,stanza')
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("📋 Nessuna auto disponibile per foto")
   return
  keyboard=[]
  for auto in auto_list:
   ghost_text=" 👻" if auto[4] else ""
   keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[1]} ({auto[2]}){ghost_text}",callback_data=f"foto_{auto[0]}")])
  reply_markup=InlineKeyboardMarkup(keyboard)
  await update.message.reply_text("📷 CARICA FOTO\n\nSeleziona l'auto:",reply_markup=reply_markup)
 except Exception as e:
  logging.error(f"Errore foto: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def park_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT id,targa,cognome,stanza,is_ghost FROM auto WHERE stato="ritiro" ORDER BY is_ghost,stanza')
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("📋 Nessuna auto in ritiro")
   return
  keyboard=[]
  for auto in auto_list:
   ghost_text=" 👻" if auto[4] else ""
   keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[1]} ({auto[2]}){ghost_text}",callback_data=f"park_{auto[0]}")])
  reply_markup=InlineKeyboardMarkup(keyboard)
  await update.message.reply_text("🅿️ CONFERMA PARCHEGGIO\n\nSeleziona l'auto parcheggiata:",reply_markup=reply_markup)
 except Exception as e:
  logging.error(f"Errore park: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def modifica_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT id,targa,cognome,stanza,numero_chiave,note,is_ghost FROM auto WHERE stato!="uscita" ORDER BY is_ghost,stanza')
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("📋 Nessuna auto da modificare")
   return
  keyboard=[]
  for auto in auto_list:
   chiave_text=f" - Chiave: {auto[4]}" if auto[4] else ""
   ghost_text=" 👻" if auto[6] else ""
   keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[1]} ({auto[2]}){ghost_text}{chiave_text}",callback_data=f"modifica_{auto[0]}")])
  reply_markup=InlineKeyboardMarkup(keyboard)
  await update.message.reply_text("✏️ MODIFICA AUTO\n\nSeleziona l'auto da modificare:",reply_markup=reply_markup)
 except Exception as e:
  logging.error(f"Errore modifica: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def lista_auto_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT stanza,cognome,targa,numero_chiave,foto_count FROM auto WHERE stato="parcheggiata" AND is_ghost=0 ORDER BY stanza')
  auto_list=cursor.fetchall()
  cursor.execute('SELECT stanza,cognome,targa,numero_chiave,foto_count FROM auto WHERE stato="parcheggiata" AND is_ghost=1 ORDER BY stanza')
  ghost_list=cursor.fetchall()
  oggi=date.today().strftime('%Y-%m-%d')
  cursor.execute('SELECT COUNT(*) FROM auto WHERE date(data_arrivo)=? AND is_ghost=0',(oggi,))
  entrate_oggi=cursor.fetchone()[0]
  cursor.execute('SELECT COUNT(*) FROM auto WHERE date(data_uscita)=? AND stato="uscita" AND is_ghost=0',(oggi,))
  uscite_oggi=cursor.fetchone()[0]
  mese_corrente=date.today().strftime('%Y-%m')
  cursor.execute('SELECT COUNT(*) FROM auto WHERE strftime("%Y-%m",data_arrivo)=? AND is_ghost=0',(mese_corrente,))
  entrate_mese=cursor.fetchone()[0]
  cursor.execute('SELECT COUNT(*) FROM auto WHERE strftime("%Y-%m",data_uscita)=? AND stato="uscita" AND is_ghost=0',(mese_corrente,))
  uscite_mese=cursor.fetchone()[0]
  cursor.execute('SELECT COUNT(*) FROM auto WHERE date(data_arrivo)=? AND is_ghost=1',(oggi,))
  ghost_oggi=cursor.fetchone()[0]
  cursor.execute('SELECT COUNT(*) FROM auto WHERE strftime("%Y-%m",data_arrivo)=? AND is_ghost=1',(mese_corrente,))
  ghost_mese=cursor.fetchone()[0]
  conn.close()
  oggi_formattato=datetime.now().strftime('%d/%m/%Y')
  mese_formattato=datetime.now().strftime('%B %Y')
  msg=f"📊 STATISTICHE {oggi_formattato}:\n\n"
  msg+=f"📈 OGGI (Auto Normali):\n"
  msg+=f"  🚗 Entrate: {entrate_oggi}\n"
  msg+=f"  🏁 Uscite: {uscite_oggi}\n\n"
  msg+=f"📅 {mese_formattato.upper()} (Auto Normali):\n"
  msg+=f"  🚗 Entrate: {entrate_mese}\n"
  msg+=f"  🏁 Uscite: {uscite_mese}\n\n"
  if ghost_oggi>0 or ghost_mese>0:
   msg+=f"👻 GHOST CARS:\n"
   msg+=f"  🚗 Oggi: {ghost_oggi}\n"
   msg+=f"  📅 Mese: {ghost_mese}\n\n"
  if not auto_list and not ghost_list:
   msg+="🅿️ Nessuna auto in parcheggio"
  else:
   if auto_list:
    msg+=f"🅿️ AUTO NORMALI IN PARCHEGGIO ({len(auto_list)}):\n\n"
    for auto in auto_list:
     stanza,cognome,targa,chiave,foto_count=auto
     chiave_text=f"Chiave: {chiave}" if chiave else "Chiave: --"
     foto_text=f" 📷 {foto_count}" if foto_count>0 else ""
     msg+=f"{stanza} | {cognome} | {targa} | {chiave_text}{foto_text}\n"
   if ghost_list:
    msg+=f"\n👻 GHOST CARS IN PARCHEGGIO ({len(ghost_list)}):\n\n"
    for auto in ghost_list:
     stanza,cognome,targa,chiave,foto_count=auto
     chiave_text=f"Chiave: {chiave}" if chiave else "Chiave: --"
     foto_text=f" 📷 {foto_count}" if foto_count>0 else ""
     msg+=f"{stanza} | {cognome} | {targa} | {chiave_text}{foto_text} 👻\n"
  await update.message.reply_text(msg)
 except Exception as e:
  logging.error(f"Errore lista_auto: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento della lista")

async def export_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  await update.message.reply_text("📊 EXPORT DATABASE\n\n⏳ Generazione file CSV in corso...")
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('''SELECT id,targa,cognome,stanza,numero_chiave,note,stato,data_arrivo,data_park,data_uscita,numero_progressivo,tempo_stimato,ora_accettazione,foto_count,is_ghost FROM auto ORDER BY is_ghost,data_arrivo DESC''')
  auto_data=cursor.fetchall()
  cursor.execute('''SELECT s.id,s.auto_id,a.targa,a.cognome,a.stanza,s.tipo_servizio,s.data_servizio FROM servizi_extra s LEFT JOIN auto a ON s.auto_id=a.id ORDER BY s.data_servizio DESC''')
  servizi_data=cursor.fetchall()
  cursor.execute('''SELECT p.id,p.auto_id,a.targa,a.cognome,a.stanza,p.data_partenza,p.ora_partenza,p.completata,p.data_creazione FROM prenotazioni p LEFT JOIN auto a ON p.auto_id=a.id ORDER BY p.data_partenza,p.ora_partenza''')
  prenotazioni_data=cursor.fetchall()
  cursor.execute('SELECT COUNT(*) FROM foto')
  total_foto=cursor.fetchone()[0]
  conn.close()
  csv_content="=== TABELLA AUTO ===\n"
  csv_content+="ID,Targa,Cognome,Stanza,Numero_Chiave,Note,Stato,Data_Arrivo,Data_Park,Data_Uscita,Numero_Progressivo,Tempo_Stimato,Ora_Accettazione,Foto_Count,Is_Ghost\n"
  for auto in auto_data:
   values=[]
   for value in auto:
    if value is None:
     values.append("")
    else:
     str_value=str(value).replace('"','""')
     if ',' in str_value or '"' in str_value:
      values.append(f'"{str_value}"')
     else:
      values.append(str_value)
   csv_content+=",".join(values)+"\n"
  csv_content+="\n=== TABELLA SERVIZI EXTRA ===\n"
  csv_content+="ID,Auto_ID,Targa,Cognome,Stanza,Tipo_Servizio,Data_Servizio\n"
  for servizio in servizi_data:
   values=[]
   for value in servizio:
    if value is None:
     values.append("")
    else:
     str_value=str(value).replace('"','""')
     if ',' in str_value or '"' in str_value:
      values.append(f'"{str_value}"')
     else:
      values.append(str_value)
   csv_content+=",".join(values)+"\n"
  csv_content+="\n=== TABELLA PRENOTAZIONI ===\n"
  csv_content+="ID,Auto_ID,Targa,Cognome,Stanza,Data_Partenza,Ora_Partenza,Completata,Data_Creazione\n"
  for prenotazione in prenotazioni_data:
   values=[]
   for value in prenotazione:
    if value is None:
     values.append("")
    else:
     str_value=str(value).replace('"','""')
     if ',' in str_value or '"' in str_value:
      values.append(f'"{str_value}"')
     else:
      values.append(str_value)
   csv_content+=",".join(values)+"\n"
  oggi=date.today().strftime('%Y-%m-%d')
  mese_corrente=date.today().strftime('%Y-%m')
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT COUNT(*) FROM auto WHERE date(data_arrivo)=? AND is_ghost=0',(oggi,))
  entrate_oggi=cursor.fetchone()[0]
  cursor.execute('SELECT COUNT(*) FROM auto WHERE date(data_uscita)=? AND stato="uscita" AND is_ghost=0',(oggi,))
  uscite_oggi=cursor.fetchone()[0]
  cursor.execute('SELECT COUNT(*) FROM auto WHERE strftime("%Y-%m",data_arrivo)=? AND is_ghost=0',(mese_corrente,))
  entrate_mese=cursor.fetchone()[0]
  cursor.execute('SELECT COUNT(*) FROM auto WHERE strftime("%Y-%m",data_uscita)=? AND stato="uscita" AND is_ghost=0',(mese_corrente,))
  uscite_mese=cursor.fetchone()[0]
  cursor.execute('SELECT COUNT(*) FROM auto WHERE stato="parcheggiata" AND is_ghost=0')
  in_parcheggio=cursor.fetchone()[0]
  cursor.execute('SELECT COUNT(*) FROM auto WHERE is_ghost=1')
  ghost_total=cursor.fetchone()[0]
  cursor.execute('SELECT COUNT(*) FROM auto WHERE stato="parcheggiata" AND is_ghost=1')
  ghost_parcheggio=cursor.fetchone()[0]
  cursor.execute('SELECT COUNT(*) FROM servizi_extra')
  total_servizi=cursor.fetchone()[0]
  cursor.execute('SELECT COUNT(*) FROM servizi_extra WHERE strftime("%Y-%m",data_servizio)=?',(mese_corrente,))
  servizi_mese=cursor.fetchone()[0]
  cursor.execute('SELECT COUNT(*) FROM prenotazioni')
  total_prenotazioni=cursor.fetchone()[0]
  cursor.execute('SELECT COUNT(*) FROM prenotazioni WHERE completata=0')
  prenotazioni_attive=cursor.fetchone()[0]
  conn.close()
  csv_content+=f"\n\n=== STATISTICHE EXPORT v5.02 ===\n"
  csv_content+=f"Data Export,{datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
  csv_content+=f"Totale Auto Database,{len(auto_data)}\n"
  csv_content+=f"Totale Foto Database,{total_foto}\n"
  csv_content+=f"Totale Servizi Extra,{total_servizi}\n"
  csv_content+=f"Totale Prenotazioni,{total_prenotazioni}\n"
  csv_content+=f"Prenotazioni Attive,{prenotazioni_attive}\n"
  csv_content+=f"Auto Normali Entrate Oggi,{entrate_oggi}\n"
  csv_content+=f"Auto Normali Uscite Oggi,{uscite_oggi}\n"
  csv_content+=f"Auto Normali Entrate Mese,{entrate_mese}\n"
  csv_content+=f"Auto Normali Uscite Mese,{uscite_mese}\n"
  csv_content+=f"Auto Normali In Parcheggio,{in_parcheggio}\n"
  csv_content+=f"Ghost Cars Totali,{ghost_total}\n"
  csv_content+=f"Ghost Cars In Parcheggio,{ghost_parcheggio}\n"
  csv_content+=f"Servizi Extra Mese Corrente,{servizi_mese}\n"
  filename=f"carvalet_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
  with open(filename,'w',encoding='utf-8') as f:
   f.write(csv_content)
  with open(filename,'rb') as f:
   await update.message.reply_document(
    document=f,
    filename=filename,
    caption=f"📊 EXPORT DATABASE COMPLETO v5.02\n\n📅 {datetime.now().strftime('%d/%m/%Y alle %H:%M')}\n📁 {len(auto_data)} auto totali ({len(auto_data)-ghost_total} normali + {ghost_total} ghost)\n📷 {total_foto} foto totali\n🔧 {total_servizi} servizi extra totali\n📅 {total_prenotazioni} prenotazioni totali ({prenotazioni_attive} attive)\n\n💡 Apri con Excel/Calc"
   )
  os.remove(filename)
 except Exception as e:
  logging.error(f"Errore export: {e}")
  await update.message.reply_text("❌ Errore durante l'export del database")

async def handle_message(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  state=context.user_data.get('state')
  text=update.message.text.strip()
  if text.lower() in ['/annulla','/help','/start']:
   if text.lower()=='/annulla':await annulla_command(update,context);return
   elif text.lower()=='/help':await help_command(update,context);return
   elif text.lower()=='/start':await start(update,context);return
  if state=='prenota_data':
   if not validate_date_format(text):
    await update.message.reply_text("❌ Formato data non valido!\n\nInserisci la data nel formato gg/mm/aaaa\nEsempio: 15/07/2025")
    return
   context.user_data['data_partenza']=text
   context.user_data['state']='prenota_ora'
   await update.message.reply_text("🕐 Inserisci l'ORA di partenza (formato hh:mm):\n\nEsempio: 07:00 o 09:30")
  elif state=='prenota_ora':
   if not validate_time_format(text):
    await update.message.reply_text("❌ Formato ora non valido!\n\nInserisci l'ora nel formato hh:mm\nEsempio: 07:00 o 09:30")
    return
   auto_id=context.user_data['auto_id']
   data_partenza=context.user_data['data_partenza']
   ora_partenza=text
   data_sql=datetime.strptime(data_partenza,'%d/%m/%Y').strftime('%Y-%m-%d')
   if aggiungi_prenotazione(auto_id,data_sql,ora_partenza):
    auto=get_auto_by_id(auto_id)
    ghost_text=" 👻" if auto[14] else ""
    await update.message.reply_text(f"📅 PRENOTAZIONE SALVATA!\n\n🚗 {auto[1]} - Stanza {auto[3]}{ghost_text}\n👤 Cliente: {auto[2]}\n📅 Data partenza: {data_partenza}\n🕐 Ora partenza: {ora_partenza}\n\n✅ Prenotazione registrata il {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
   else:
    await update.message.reply_text("❌ Errore durante il salvataggio della prenotazione")
   context.user_data.clear()
  elif state in ['ritiro_targa','ghost_targa','makepark_targa']:
   targa=text.upper()
   if not validate_targa(targa):
    await update.message.reply_text("❌ Formato targa non valido!\n\nInserisci una targa valida:\n• Italiana: XX123XX\n• Europea: ABC123, 123ABC\n• Con trattini: XX-123-XX")
    return
   context.user_data['targa']=targa
   if state=='makepark_targa':
    context.user_data['state']='makepark_cognome'
   elif state=='ghost_targa':
    context.user_data['state']='ghost_cognome'
   else:
    context.user_data['state']='ritiro_cognome'
   await update.message.reply_text("👤 Inserisci il COGNOME del cliente:")
  elif state in ['ritiro_cognome','ghost_cognome','makepark_cognome']:
   if not validate_cognome(text):
    await update.message.reply_text("❌ Cognome non valido!\n\nUsa solo lettere, spazi e apostrofi:")
    return
   context.user_data['cognome']=text.strip()
   if state=='makepark_cognome':
    context.user_data['state']='makepark_stanza'
   elif state=='ghost_cognome':
    context.user_data['state']='ghost_stanza'
   else:
    context.user_data['state']='ritiro_stanza'
   await update.message.reply_text("🏨 Inserisci il numero STANZA (0-999):")
  elif state in ['ritiro_stanza','ghost_stanza','makepark_stanza']:
   try:
    stanza=int(text)
    if 0<=stanza<=999:
     context.user_data['stanza']=stanza
     if state=='makepark_stanza':
      context.user_data['state']='makepark_data'
      await update.message.reply_text("📅 Inserisci la DATA DI ENTRATA (formato gg/mm/aaaa):\n\nEsempio: 01/07/2025")
     elif state=='ghost_stanza':
      context.user_data['state']='ghost_chiave'
      await update.message.reply_text("🔑 Inserisci il NUMERO CHIAVE (0-999) o scrivi 'skip' per saltare:")
     else:
      context.user_data['state']='ritiro_chiave'
      await update.message.reply_text("🔑 Inserisci il NUMERO CHIAVE (0-999) o scrivi 'skip' per saltare:")
    else:await update.message.reply_text("❌ Numero stanza non valido! Inserisci un numero da 0 a 999:")
   except ValueError:await update.message.reply_text("❌ Inserisci un numero valido per la stanza:")
  elif state=='makepark_data':
   if not validate_date(text):
    await update.message.reply_text("❌ Formato data non valido!\n\nInserisci la data nel formato gg/mm/aaaa\nEsempio: 15/07/2025")
    return
   context.user_data['data_custom']=text
   context.user_data['state']='makepark_chiave'
   await update.message.reply_text("🔑 Inserisci il NUMERO CHIAVE (0-999) o scrivi 'skip' per saltare:")
  elif state in ['ritiro_chiave','ghost_chiave','makepark_chiave']:
   if text.lower()=='skip':
    context.user_data['numero_chiave']=None
    if state=='makepark_chiave':
     context.user_data['state']='makepark_note'
    elif state=='ghost_chiave':
     context.user_data['state']='ghost_note'
    else:
     context.user_data['state']='ritiro_note'
    await update.message.reply_text("📝 Inserisci eventuali NOTE (o scrivi 'skip' per saltare):")
   else:
    try:
     chiave=int(text)
     if 0<=chiave<=999:
      context.user_data['numero_chiave']=chiave
      if state=='makepark_chiave':
       context.user_data['state']='makepark_note'
      elif state=='ghost_chiave':
       context.user_data['state']='ghost_note'
      else:
       context.user_data['state']='ritiro_note'
      await update.message.reply_text("📝 Inserisci eventuali NOTE (o scrivi 'skip' per saltare):")
     else:await update.message.reply_text("❌ Numero chiave non valido! Inserisci un numero da 0 a 999 o 'skip':")
    except ValueError:await update.message.reply_text("❌ Inserisci un numero valido per la chiave o 'skip':")
  elif state in ['ritiro_note','ghost_note','makepark_note']:
   note=text if text.lower()!='skip' else None
   targa=context.user_data['targa']
   cognome=context.user_data['cognome']
   stanza=context.user_data['stanza']
   numero_chiave=context.user_data.get('numero_chiave')
   is_ghost=context.user_data.get('is_ghost',False)
   try:
    conn=sqlite3.connect('carvalet.db')
    cursor=conn.cursor()
    if state=='makepark_note':
     data_custom=context.user_data['data_custom']
     data_sql=datetime.strptime(data_custom,'%d/%m/%Y').strftime('%Y-%m-%d')
     cursor.execute('''INSERT INTO auto (targa,cognome,stanza,numero_chiave,note,stato,data_arrivo,data_park,is_ghost) VALUES (?,?,?,?,?,?,?,?,?)''',(targa,cognome,stanza,numero_chiave,note,'parcheggiata',data_sql,data_sql,1 if is_ghost else 0))
     tipo_msg="🅿️ AUTO GIÀ PARCHEGGIATA REGISTRATA!"
    else:
     if is_ghost:
      numero_progressivo=0
     else:
      numero_progressivo=get_prossimo_numero()
     cursor.execute('''INSERT INTO auto (targa,cognome,stanza,numero_chiave,note,numero_progressivo,is_ghost) VALUES (?,?,?,?,?,?,?)''',(targa,cognome,stanza,numero_chiave,note,numero_progressivo,1 if is_ghost else 0))
     if is_ghost:
      tipo_msg="👻 GHOST CAR REGISTRATA!"
     else:
      tipo_msg="✅ RICHIESTA CREATA!"
    auto_id=cursor.lastrowid
    conn.commit()
    conn.close()
    context.user_data.clear()
    recap_msg=f"{tipo_msg}\n\n🆔 ID: {auto_id}\n🚗 Targa: {targa}\n👤 Cliente: {cognome}\n🏨 Stanza: {stanza}"
    if state=='makepark_note':
     recap_msg+=f"\n📅 Data entrata: {context.user_data.get('data_custom','N/A')}"
     recap_msg+=f"\n🅿️ Stato: PARCHEGGIATA"
    elif is_ghost:
     recap_msg+=f"\n👻 Tipo: GHOST CAR (Staff/Direttore)"
    else:
     recap_msg+=f"\n🔢 Numero: #{numero_progressivo}"
    if numero_chiave is not None:recap_msg+=f"\n🔑 Chiave: {numero_chiave}"
    if note:recap_msg+=f"\n📝 Note: {note}"
    recap_msg+=f"\n\n📅 Registrata il {datetime.now().strftime('%d/%m/%Y alle %H:%M')}"
    await update.message.reply_text(recap_msg)
   except Exception as e:
    logging.error(f"Errore salvataggio: {e}")
    await update.message.reply_text("❌ Errore durante il salvataggio")
    context.user_data.clear()
  elif state=='upload_foto':
   if text.lower()=='fine':
    auto_id=context.user_data.get('foto_auto_id')
    context.user_data.clear()
    if auto_id:
     auto=get_auto_by_id(auto_id)
     if auto:await update.message.reply_text(f"📷 Upload foto completato!\n\n🚗 {auto[1]} - Stanza {auto[3]}")
   else:await update.message.reply_text("📷 Invia le foto dell'auto (una o più foto). Scrivi 'fine' quando hai finito.")
  elif state.startswith('mod_'):
   parts=state.split('_')
   field=parts[1]
   auto_id=int(parts[2])
   if field=='targa':
    targa=text.upper()
    if not validate_targa(targa):
     await update.message.reply_text("❌ Formato targa non valido!\n\nInserisci una targa valida:")
     return
    if update_auto_field(auto_id,'targa',targa):
     auto=get_auto_by_id(auto_id)
     await update.message.reply_text(f"✅ Targa aggiornata a {targa}\n\n🚗 Stanza {auto[3]} - Cliente: {auto[2]}")
    else:await update.message.reply_text("❌ Errore durante l'aggiornamento")
    context.user_data.clear()
   elif field=='cognome':
    if not validate_cognome(text):
     await update.message.reply_text("❌ Cognome non valido!\n\nUsa solo lettere, spazi e apostrofi:")
     return
    if update_auto_field(auto_id,'cognome',text.strip()):
     auto=get_auto_by_id(auto_id)
     await update.message.reply_text(f"✅ Cognome aggiornato a {text.strip()}\n\n🚗 {auto[1]} - Stanza {auto[3]}")
    else:await update.message.reply_text("❌ Errore durante l'aggiornamento")
    context.user_data.clear()
   elif field=='stanza':
    try:
     stanza=int(text)
     if 0<=stanza<=999:
      if update_auto_field(auto_id,'stanza',stanza):
       auto=get_auto_by_id(auto_id)
       await update.message.reply_text(f"✅ Stanza aggiornata a {stanza}\n\n🚗 {auto[1]} - Cliente: {auto[2]}")
      else:await update.message.reply_text("❌ Errore durante l'aggiornamento")
      context.user_data.clear()
     else:await update.message.reply_text("❌ Numero stanza non valido! Inserisci un numero da 0 a 999:")
    except ValueError:await update.message.reply_text("❌ Inserisci un numero valido per la stanza:")
   elif field=='chiave':
    if text.lower()=='rimuovi':value=None
    else:
     try:
      value=int(text)
      if not(0<=value<=999):
       await update.message.reply_text("❌ Numero chiave non valido! Inserisci un numero da 0 a 999 o 'rimuovi':")
       return
     except ValueError:
      await update.message.reply_text("❌ Inserisci un numero valido per la chiave o 'rimuovi':")
      return
    if update_auto_field(auto_id,'numero_chiave',value):
     auto=get_auto_by_id(auto_id)
     text_result="rimossa"if value is None else f"impostata a {value}"
     await update.message.reply_text(f"✅ Chiave {text_result}\n\n🚗 {auto[1]} - Stanza {auto[3]}")
    else:await update.message.reply_text("❌ Errore durante l'aggiornamento")
    context.user_data.clear()
   elif field=='note':
    if text.lower()=='rimuovi':value=None
    else:value=text.strip()
    if update_auto_field(auto_id,'note',value):
     auto=get_auto_by_id(auto_id)
     text_result="rimosse"if value is None else "aggiornate"
     await update.message.reply_text(f"✅ Note {text_result}\n\n🚗 {auto[1]} - Stanza {auto[3]}")
    else:await update.message.reply_text("❌ Errore durante l'aggiornamento")
    context.user_data.clear()
  else:await update.message.reply_text("❓ Comando non riconosciuto\n\nUsa /help per vedere tutti i comandi disponibili.")
 except Exception as e:
  logging.error(f"Errore handle_message: {e}")
  await update.message.reply_text("❌ Si è verificato un errore durante l'elaborazione del messaggio")
  context.user_data.clear()

async def handle_photo(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  if context.user_data.get('state')=='upload_foto':
   auto_id=context.user_data.get('foto_auto_id')
   if auto_id:
    file_id=update.message.photo[-1].file_id
    conn=sqlite3.connect('carvalet.db')
    cursor=conn.cursor()
    cursor.execute('INSERT INTO foto (auto_id,file_id) VALUES (?,?)',(auto_id,file_id))
    cursor.execute('UPDATE auto SET foto_count=foto_count+1 WHERE id=?',(auto_id,))
    conn.commit()
    cursor.execute('SELECT foto_count FROM auto WHERE id=?',(auto_id,))
    foto_count=cursor.fetchone()[0]
    conn.close()
    await update.message.reply_text(f"📷 Foto #{foto_count} salvata! Invia altre foto o scrivi 'fine' per terminare.")
  else:await update.message.reply_text("📷 Per caricare foto, usa prima il comando /foto e seleziona un'auto")
 except Exception as e:
  logging.error(f"Errore handle_photo: {e}")
  await update.message.reply_text("❌ Errore durante il salvataggio della foto")

async def handle_callback_query(update:Update,context:ContextTypes.DEFAULT_TYPE):
 query=update.callback_query
 await query.answer()
 try:
  data=query.data
  if data.startswith('prenota_auto_'):
   auto_id=int(data.split('_')[2])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   context.user_data['auto_id']=auto_id
   context.user_data['state']='prenota_data'
   ghost_text=" 👻" if auto[14] else ""
   await query.edit_message_text(f"📅 PRENOTA PARTENZA\n\n🚗 {auto[1]} - Stanza {auto[3]}{ghost_text}\n👤 Cliente: {auto[2]}\n📍 Stato: {auto[6]}\n\nInserisci la DATA di partenza (formato gg/mm/aaaa):\n\nEsempio: 16/07/2025")
  elif data.startswith('servizi_auto_'):
   auto_id=int(data.split('_')[2])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   keyboard=[
    [InlineKeyboardButton("🌙 Ritiro Notturno",callback_data=f"servizio_{auto_id}_ritiro_notturno")],
    [InlineKeyboardButton("🏠 Garage 10+ giorni",callback_data=f"servizio_{auto_id}_garage_10plus")],
    [InlineKeyboardButton("🚿 Autolavaggio",callback_data=f"servizio_{auto_id}_autolavaggio")]
   ]
   reply_markup=InlineKeyboardMarkup(keyboard)
   ghost_text=" 👻" if auto[14] else ""
   await query.edit_message_text(f"🔧 SERVIZI EXTRA\n\n🚗 {auto[1]} - Stanza {auto[3]}{ghost_text}\n👤 Cliente: {auto[2]}\n\nSeleziona il servizio completato:",reply_markup=reply_markup)
  elif data.startswith('servizio_'):
   parts=data.split('_')
   auto_id=int(parts[1])
   tipo_servizio='_'.join(parts[2:])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   if aggiungi_servizio_extra(auto_id,tipo_servizio):
    servizio_names={'ritiro_notturno':'🌙 Ritiro Notturno','garage_10plus':'🏠 Garage 10+ giorni','autolavaggio':'🚿 Autolavaggio'}
    servizio_nome=servizio_names.get(tipo_servizio,'🔧 Servizio Extra')
    ghost_text=" 👻" if auto[14] else ""
    await query.edit_message_text(f"✅ SERVIZIO REGISTRATO!\n\n{servizio_nome}\n🚗 {auto[1]} - Stanza {auto[3]}{ghost_text}\n👤 Cliente: {auto[2]}\n\n📅 {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
   else:await query.edit_message_text("❌ Errore durante la registrazione del servizio")
  elif data.startswith('recupero_'):
   parts=data.split('_')
   auto_id=int(parts[1])
   tipo_operazione=parts[2] if len(parts)>2 else 'richiesta'
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   keyboard=[[InlineKeyboardButton("⏱️ 15 min ca.",callback_data=f"tempo_{auto_id}_{tipo_operazione}_15")],[InlineKeyboardButton("⏱️ 30 min ca.",callback_data=f"tempo_{auto_id}_{tipo_operazione}_30")],[InlineKeyboardButton("⏱️ 45 min ca.",callback_data=f"tempo_{auto_id}_{tipo_operazione}_45")]]
   reply_markup=InlineKeyboardMarkup(keyboard)
   operazione_text={'richiesta':'PRIMO RITIRO','riconsegna':'RICONSEGNA TEMPORANEA','rientro':'RIENTRO IN PARCHEGGIO'}
   await query.edit_message_text(f"⏰ TEMPO STIMATO {operazione_text.get(tipo_operazione,'OPERAZIONE')}:",reply_markup=reply_markup)
  elif data.startswith('tempo_'):
   parts=data.split('_')
   auto_id=int(parts[1])
   tipo_operazione=parts[2]
   minuti=parts[3]
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   try:
    conn=sqlite3.connect('carvalet.db')
    cursor=conn.cursor()
    if tipo_operazione=='richiesta':
     nuovo_stato='ritiro'
     operazione_desc='PRIMO RITIRO AVVIATO'
    elif tipo_operazione=='riconsegna':
     nuovo_stato='stand-by'
     operazione_desc='RICONSEGNA CONFERMATA'
    elif tipo_operazione=='rientro':
     nuovo_stato='ritiro'
     operazione_desc='RIENTRO AVVIATO'
    cursor.execute('UPDATE auto SET stato=?,tempo_stimato=?,ora_accettazione=CURRENT_TIMESTAMP WHERE id=?',(nuovo_stato,minuti,auto_id))
    conn.commit()
    conn.close()
    ghost_text=" 👻" if auto[14] else ""
    if tipo_operazione=='riconsegna':
     await query.edit_message_text(f"🚪 {operazione_desc}!\n\n🚗 {auto[1]} - Stanza {auto[3]}{ghost_text}\n👤 Cliente: {auto[2]}\n⏰ Tempo stimato: {minuti} minuti\n⏸️ Auto andrà in STAND-BY\n\n📅 {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
    else:
     if auto[14]:
      numero_text="GHOST"
     else:
      numero_text=f"#{auto[11]}"
     await query.edit_message_text(f"✅ {operazione_desc}!\n\n🔢 Auto {numero_text}\n🚗 {auto[1]} - Stanza {auto[3]}{ghost_text}\n👤 Cliente: {auto[2]}\n⏰ Tempo stimato: {minuti} minuti\n\n📅 {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
   except Exception as e:
    logging.error(f"Errore aggiornamento: {e}")
    await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
  elif data.startswith('park_'):
   auto_id=int(data.split('_')[1])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   if update_auto_stato(auto_id,'parcheggiata'):
    ghost_text=" 👻" if auto[14] else ""
    if auto[14]:
     numero_text="GHOST"
    else:
     numero_text=f"#{auto[11]}"
    await query.edit_message_text(f"🅿️ AUTO PARCHEGGIATA!\n\n🔢 Auto {numero_text} completata\n🚗 {auto[1]} - Stanza {auto[3]}{ghost_text}\n👤 Cliente: {auto[2]}\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
   else:await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
  elif data.startswith('partito_'):
   auto_id=int(data.split('_')[1])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   keyboard=[[InlineKeyboardButton("✅ SI - Conferma uscita definitiva",callback_data=f"conferma_partito_{auto_id}")],[InlineKeyboardButton("❌ ANNULLA",callback_data="annulla_partito")]]
   reply_markup=InlineKeyboardMarkup(keyboard)
   ghost_text=" 👻" if auto[14] else ""
   await query.edit_message_text(f"🏁 CONFERMA USCITA DEFINITIVA\n\n🚗 {auto[1]} - Stanza {auto[3]}{ghost_text}\n👤 Cliente: {auto[2]}\n📍 Stato attuale: {auto[6]}\n\n⚠️ L'auto sarà eliminata definitivamente dal sistema!\n\nSei sicuro?",reply_markup=reply_markup)
  elif data.startswith('conferma_partito_'):
   auto_id=int(data.split('_')[2])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   if update_auto_stato(auto_id,'uscita'):
    completa_prenotazione(auto_id)
    ghost_text=" 👻" if auto[14] else ""
    await query.edit_message_text(f"🏁 AUTO PARTITA DEFINITIVAMENTE!\n\n🚗 {auto[1]} - Stanza {auto[3]}{ghost_text}\n👤 Cliente: {auto[2]}\n✅ Auto eliminata dal sistema\n📅 Prenotazione completata (se esistente)\n\n📅 {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
   else:await query.edit_message_text("❌ Errore durante l'eliminazione dell'auto")
  elif data=='annulla_partito':
   await query.edit_message_text("❌ Operazione annullata\n\nL'auto non è stata eliminata.")
  elif data.startswith('riconsegna_'):
   auto_id=int(data.split('_')[1])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   if update_auto_stato(auto_id,'riconsegna'):
    ghost_text=" 👻" if auto[14] else ""
    await query.edit_message_text(f"🚪 RICONSEGNA RICHIESTA!\n\n🚗 {auto[1]} - Stanza {auto[3]}{ghost_text}\n👤 Cliente: {auto[2]}\n\n⏰ Ora il valet deve confermare la riconsegna\n\n📅 {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
   else:await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
  elif data.startswith('rientro_'):
   auto_id=int(data.split('_')[1])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   if update_auto_stato(auto_id,'rientro'):
    ghost_text=" 👻" if auto[14] else ""
    await query.edit_message_text(f"🔄 RIENTRO RICHIESTO!\n\n🚗 {auto[1]} - Stanza {auto[3]}{ghost_text}\n👤 Cliente: {auto[2]}\n\n⏰ Ora il valet deve confermare il rientro\n\n📅 {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
   else:await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
  elif data.startswith('foto_'):
   auto_id=int(data.split('_')[1])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   context.user_data['state']='upload_foto'
   context.user_data['foto_auto_id']=auto_id
   ghost_text=" 👻" if auto[14] else ""
   await query.edit_message_text(f"📷 CARICA FOTO\n\n🚗 {auto[1]} - Stanza {auto[3]}{ghost_text}\n👤 Cliente: {auto[2]}\n\nInvia le foto dell'auto (una o più). Scrivi 'fine' quando terminato.")
  elif data.startswith('modifica_'):
   auto_id=int(data.split('_')[1])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   keyboard=[[InlineKeyboardButton("🚗 Modifica Targa",callback_data=f"mod_targa_{auto_id}")],[InlineKeyboardButton("👤 Modifica Cognome",callback_data=f"mod_cognome_{auto_id}")],[InlineKeyboardButton("🏨 Modifica Stanza",callback_data=f"mod_stanza_{auto_id}")],[InlineKeyboardButton("🔑 Modifica Chiave",callback_data=f"mod_chiave_{auto_id}")],[InlineKeyboardButton("📝 Modifica Note",callback_data=f"mod_note_{auto_id}")]]
   reply_markup=InlineKeyboardMarkup(keyboard)
   chiave_text=f"\n🔑 Chiave: {auto[4]}"if auto[4] else"\n🔑 Chiave: Non assegnata"
   note_text=f"\n📝 Note: {auto[5]}"if auto[5] else"\n📝 Note: Nessuna"
   ghost_text=" 👻" if auto[14] else ""
   await query.edit_message_text(f"✏️ MODIFICA AUTO\n\n🚗 Targa: {auto[1]}{ghost_text}\n👤 Cliente: {auto[2]}\n🏨 Stanza: {auto[3]}{chiave_text}{note_text}\n\nCosa vuoi modificare?",reply_markup=reply_markup)
  elif data.startswith('mostra_foto_'):
   auto_id=int(data.split('_')[2])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   foto_list=get_foto_by_auto_id(auto_id)
   if not foto_list:
    ghost_text=" 👻" if auto[14] else ""
    await query.edit_message_text(f"📷 Nessuna foto trovata\n\n🚗 {auto[1]} - Stanza {auto[3]}{ghost_text}\n👤 Cliente: {auto[2]}")
    return
   ghost_text=" 👻" if auto[14] else ""
   await query.edit_message_text(f"📷 FOTO AUTO\n\n🚗 {auto[1]} - Stanza {auto[3]}{ghost_text}\n👤 Cliente: {auto[2]}\n📊 Stato: {auto[6]}\n📷 Totale foto: {len(foto_list)}")
   max_foto_per_invio=10
   for i,foto in enumerate(foto_list):
    if i>=max_foto_per_invio:
     await update.effective_chat.send_message(f"📷 Mostrate prime {max_foto_per_invio} foto di {len(foto_list)} totali.\nUsa di nuovo il comando per vedere le altre.")
     break
    file_id,data_upload=foto
    try:
     data_formattata=datetime.strptime(data_upload,'%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
     caption=f"📷 Foto #{i+1} - {data_formattata}"
     await update.effective_chat.send_photo(photo=file_id,caption=caption)
    except Exception as e:
     logging.error(f"Errore invio foto {file_id}: {e}")
     await update.effective_chat.send_message(f"❌ Errore caricamento foto #{i+1}")
  elif data.startswith('mod_targa_'):
   auto_id=int(data.split('_')[2])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   context.user_data['state']=f'mod_targa_{auto_id}'
   await query.edit_message_text(f"🚗 MODIFICA TARGA\n\n{auto[1]} - Stanza {auto[3]}\nTarga attuale: {auto[1]}\n\nInserisci nuova targa:")
  elif data.startswith('mod_cognome_'):
   auto_id=int(data.split('_')[2])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   context.user_data['state']=f'mod_cognome_{auto_id}'
   await query.edit_message_text(f"👤 MODIFICA COGNOME\n\n{auto[1]} - Stanza {auto[3]}\nCognome attuale: {auto[2]}\n\nInserisci nuovo cognome:")
  elif data.startswith('mod_stanza_'):
   auto_id=int(data.split('_')[2])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   context.user_data['state']=f'mod_stanza_{auto_id}'
   await query.edit_message_text(f"🏨 MODIFICA STANZA\n\n{auto[1]} - {auto[2]}\nStanza attuale: {auto[3]}\n\nInserisci nuovo numero stanza (0-999):")
  elif data.startswith('mod_chiave_'):
   auto_id=int(data.split('_')[2])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   context.user_data['state']=f'mod_chiave_{auto_id}'
   await query.edit_message_text(f"🔑 MODIFICA CHIAVE\n\n{auto[1]} - Stanza {auto[3]}\nChiave attuale: {auto[4] or 'Non assegnata'}\n\nInserisci nuovo numero chiave (0-999) o scrivi 'rimuovi':")
  elif data.startswith('mod_note_'):
   auto_id=int(data.split('_')[2])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   context.user_data['state']=f'mod_note_{auto_id}'
   await query.edit_message_text(f"📝 MODIFICA NOTE\n\n{auto[1]} - Stanza {auto[3]}\nNote attuali: {auto[5] or 'Nessuna'}\n\nInserisci nuove note o scrivi 'rimuovi':")
 except Exception as e:
  logging.error(f"Errore handle_callback_query: {e}")
  await query.edit_message_text("❌ Errore durante l'elaborazione della richiesta")

def main():
 try:
  TOKEN=os.getenv('TELEGRAM_BOT_TOKEN')
  if not TOKEN:
   logging.error("TELEGRAM_BOT_TOKEN non trovato nelle variabili d'ambiente")
   return
  application=Application.builder().token(TOKEN).build()
  application.add_handler(CommandHandler("start",start))
  application.add_handler(CommandHandler("help",help_command))
  application.add_handler(CommandHandler("annulla",annulla_command))
  application.add_handler(CommandHandler("prenota",prenota_command))
  application.add_handler(CommandHandler("mostra_prenotazioni",mostra_prenotazioni_command))
  application.add_handler(CommandHandler("servizi",servizi_command))
  application.add_handler(CommandHandler("servizi_stats",servizi_stats_command))
  application.add_handler(CommandHandler("vedi_foto",vedi_foto_command))
  application.add_handler(CommandHandler("vedi_recupero",vedi_recupero_command))
  application.add_handler(CommandHandler("ritiro",ritiro_command))
  application.add_handler(CommandHandler("ghostcar",ghostcar_command))
  application.add_handler(CommandHandler("makepark",makepark_command))
  application.add_handler(CommandHandler("riconsegna",riconsegna_command))
  application.add_handler(CommandHandler("rientro",rientro_command))
  application.add_handler(CommandHandler("partito",partito_command))
  application.add_handler(CommandHandler("recupero",recupero_command))
  application.add_handler(CommandHandler("foto",foto_command))
  application.add_handler(CommandHandler("park",park_command))
  application.add_handler(CommandHandler("modifica",modifica_command))
  application.add_handler(CommandHandler("lista_auto",lista_auto_command))
  application.add_handler(CommandHandler("export",export_command))
  application.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,handle_message))
  application.add_handler(MessageHandler(filters.PHOTO,handle_photo))
  application.add_handler(CallbackQueryHandler(handle_callback_query))
  logging.info(f"🚗 {BOT_NAME} v{BOT_VERSION} avviato!")
  logging.info("✅ Sistema gestione auto hotel PROFESSIONALE")
  logging.info("🔧 v5.02: +Sistema Prenotazioni Partenze (data/ora programmata)")
  print(f"🚗 {BOT_NAME} v{BOT_VERSION} avviato!")
  print("✅ Sistema gestione auto hotel PROFESSIONALE")
  print("🔧 v5.02: +Sistema Prenotazioni Partenze (data/ora programmata)")
  application.run_polling(allowed_updates=Update.ALL_TYPES)
 except Exception as e:
  logging.error(f"Errore durante l'avvio del bot: {e}")
  print(f"❌ Errore durante l'avvio: {e}")

if __name__=='__main__':main()
