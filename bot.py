#!/usr/bin/env python3
# CarValetBOT v4.3 LIGHT by Zibroncloud
import os,logging,sqlite3,re
from datetime import datetime,date
from telegram import Update,InlineKeyboardButton,InlineKeyboardMarkup
from telegram.ext import Application,CommandHandler,MessageHandler,filters,ContextTypes,CallbackQueryHandler

BOT_VERSION="4.4 LIGHT"
BOT_NAME="CarValetBOT"
logging.basicConfig(format='%(asctime)s-%(levelname)s-%(message)s',level=logging.INFO)

def init_db():
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('''CREATE TABLE IF NOT EXISTS auto (id INTEGER PRIMARY KEY AUTOINCREMENT,targa TEXT NOT NULL,cognome TEXT NOT NULL,stanza INTEGER NOT NULL,numero_chiave INTEGER,note TEXT,stato TEXT DEFAULT 'richiesta',data_arrivo DATE DEFAULT CURRENT_DATE,data_park DATE,data_uscita DATE,foto_count INTEGER DEFAULT 0,numero_progressivo INTEGER,tempo_stimato TEXT,ora_accettazione TIMESTAMP)''')
  cursor.execute('''CREATE TABLE IF NOT EXISTS foto (id INTEGER PRIMARY KEY AUTOINCREMENT,auto_id INTEGER,file_id TEXT NOT NULL,data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY (auto_id) REFERENCES auto (id))''')
  conn.commit()
  conn.close()
  logging.info("Database inizializzato")
 except Exception as e:logging.error(f"Errore DB: {e}")

def get_prossimo_numero():
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  oggi=date.today().strftime('%Y-%m-%d')
  cursor.execute('SELECT MAX(numero_progressivo) FROM auto WHERE date(data_arrivo)=?',(oggi,))
  result=cursor.fetchone()
  conn.close()
  return (result[0] or 0)+1
 except:return 1

init_db()

def validate_targa(targa):
 targa=targa.upper().strip()
 p1=r'^[A-Z]{2}[0-9]{3}[A-Z]{2}$'
 p2=r'^[A-Z0-9]{4,10}$'
 p3=r'^[A-Z0-9]{1,4}[-\s][A-Z0-9]{1,4}[-\s][A-Z0-9]{1,4}$'
 return bool(re.match(p1,targa))or bool(re.match(p2,targa))or bool(re.match(p3,targa.replace(' ','-')))

def validate_cognome(cognome):return bool(re.match(r"^[A-Za-zÀ-ÿ\s']+$",cognome.strip()))

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
  cursor.execute('''SELECT DISTINCT a.id,a.targa,a.cognome,a.stanza,a.stato,a.foto_count FROM auto a INNER JOIN foto f ON a.id=f.auto_id WHERE a.foto_count>0 ORDER BY a.stanza''')
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
/vedi_recupero - Stato recuperi in corso
/riconsegna - Lista auto per riconsegna temporanea
/rientro - Richiesta rientro auto in stand-by
/partenza - Riconsegna finale (uscita definitiva)

🚗 COMANDI VALET:
/recupero - Gestione recuperi (ritiri/riconsegne/rientri)
/foto - Carica foto auto
/vedi_foto - Visualizza foto auto
/park - Conferma auto parcheggiata
/exit - Auto in riconsegna (da qualunque stato dopo ritiro) (da qualunque stato)
/modifica - Modifica TUTTI i dati auto

📊 COMANDI UTILITÀ:
/lista_auto - Auto in parcheggio

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
/vedi_recupero - Vedi tutti i recuperi con tempi stimati
/riconsegna - Richiesta riconsegna temporanea
/rientro - Richiesta rientro auto in stand-by
/partenza - Conferma partenza definitiva

🚗 COMANDI VALET:
/recupero - Gestione completa recuperi (priorità automatica)
/foto - Carica foto dell'auto
/vedi_foto - Visualizza foto per auto/cliente
/park - Conferma auto parcheggiata
/exit - Metti auto in riconsegna (da qualunque stato dopo ritiro)
/modifica - Modifica targa, cognome, stanza, chiave, note

📊 COMANDI UTILITÀ:
/lista_auto - Elenco auto parcheggiate

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

🏁 USCITA DEFINITIVA:
9️⃣ Hotel: /partenza

🎯 STATI AUTO:
📋 richiesta - Primo ritiro richiesto
⚙️ ritiro - Valet sta recuperando/riportando
🅿️ parcheggiata - In parcheggio
🚪 riconsegna - Riconsegna temporanea richiesta
⏸️ stand-by - Auto fuori (cliente l'ha presa)
🔄 rientro - Rientro richiesto
🏁 uscita - Partita definitivamente

🔢 NUMERAZIONE: Auto numerate giornalmente per priorità
🔑 RANGE NUMERI: Stanze e chiavi da 0 a 999
🌍 TARGHE ACCETTATE: Italiane (XX123XX), Europee, con trattini"""
 await update.message.reply_text(msg)

async def annulla_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 state=context.user_data.get('state')
 if state:
  if state.startswith('ritiro_'):op="registrazione auto"
  elif state=='upload_foto':op="caricamento foto"
  elif state.startswith('mod_'):op="modifica auto"
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
     id_auto,targa,cognome,stanza,_,foto_count=auto
     keyboard.append([InlineKeyboardButton(f"{emoji} Stanza {stanza} - {targa} ({cognome}) - 📷 {foto_count} foto",callback_data=f"mostra_foto_{id_auto}")])
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
  cursor.execute('SELECT id,targa,cognome,stanza,stato,numero_progressivo,tempo_stimato,ora_accettazione FROM auto WHERE date(data_arrivo)=? AND stato IN ("richiesta","ritiro","parcheggiata","riconsegna","stand-by","rientro") ORDER BY numero_progressivo',(oggi,))
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("📋 Nessun recupero in corso oggi")
   return
  msg="🔍 STATO RECUPERI DI OGGI:\n\n"
  for auto in auto_list:
   id_auto,targa,cognome,stanza,stato,numero,tempo_stimato,ora_accettazione=auto
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
   msg+=f"{emoji} #{numero} | Stanza {stanza} | {targa} ({cognome})\n    {status_text}\n\n"
  await update.message.reply_text(msg)
 except Exception as e:
  logging.error(f"Errore vedi_recupero: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento dei recuperi")

async def ritiro_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 context.user_data.clear()
 context.user_data['state']='ritiro_targa'
 await update.message.reply_text("🚗 RITIRO AUTO\n\nInserisci la TARGA del veicolo:")

async def riconsegna_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT id,targa,cognome,stanza,numero_chiave FROM auto WHERE stato="parcheggiata" ORDER BY stanza')
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("📋 Nessuna auto in parcheggio")
   return
  keyboard=[]
  for auto in auto_list:
   chiave_text=f" - Chiave: {auto[4]}" if auto[4] else ""
   keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[1]} ({auto[2]}){chiave_text}",callback_data=f"riconsegna_{auto[0]}")])
  reply_markup=InlineKeyboardMarkup(keyboard)
  await update.message.reply_text("🚪 RICONSEGNA TEMPORANEA\n\nSeleziona l'auto (tornerà in stand-by):",reply_markup=reply_markup)
 except Exception as e:
  logging.error(f"Errore riconsegna: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def rientro_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT id,targa,cognome,stanza,numero_chiave FROM auto WHERE stato="stand-by" ORDER BY stanza')
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("📋 Nessuna auto in stand-by")
   return
  keyboard=[]
  for auto in auto_list:
   chiave_text=f" - Chiave: {auto[4]}" if auto[4] else ""
   keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[1]} ({auto[2]}){chiave_text}",callback_data=f"rientro_{auto[0]}")])
  reply_markup=InlineKeyboardMarkup(keyboard)
  await update.message.reply_text("🔄 RIENTRO IN PARCHEGGIO\n\nSeleziona l'auto da far rientrare:",reply_markup=reply_markup)
 except Exception as e:
  logging.error(f"Errore rientro: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def partenza_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT id,targa,cognome,stanza,numero_chiave FROM auto WHERE stato IN ("riconsegna","stand-by") ORDER BY stanza')
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("📋 Nessuna auto pronta per partenza definitiva")
   return
  keyboard=[]
  for auto in auto_list:
   chiave_text=f" - Chiave: {auto[4]}" if auto[4] else ""
   keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[1]} ({auto[2]}){chiave_text}",callback_data=f"partenza_{auto[0]}")])
  reply_markup=InlineKeyboardMarkup(keyboard)
  await update.message.reply_text("🏁 PARTENZA DEFINITIVA\n\nSeleziona l'auto:",reply_markup=reply_markup)
 except Exception as e:
  logging.error(f"Errore partenza: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def recupero_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT id,targa,cognome,stanza,numero_chiave,numero_progressivo,stato FROM auto WHERE stato IN ("richiesta","riconsegna","rientro") ORDER BY numero_progressivo')
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("📋 Nessun recupero da gestire")
   return
  keyboard=[]
  for auto in auto_list:
   chiave_text=f" - Chiave: {auto[4]}" if auto[4] else ""
   if auto[6]=='richiesta':tipo_emoji="📋 RITIRO"
   elif auto[6]=='riconsegna':tipo_emoji="🚪 RICONSEGNA"
   elif auto[6]=='rientro':tipo_emoji="🔄 RIENTRO"
   keyboard.append([InlineKeyboardButton(f"{tipo_emoji} #{auto[5]} - Stanza {auto[3]} - {auto[1]} ({auto[2]}){chiave_text}",callback_data=f"recupero_{auto[0]}_{auto[6]}")])
  reply_markup=InlineKeyboardMarkup(keyboard)
  await update.message.reply_text("⚙️ GESTIONE RECUPERI (Ordine cronologico)\n\nSeleziona l'operazione da gestire:",reply_markup=reply_markup)
 except Exception as e:
  logging.error(f"Errore recupero: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle operazioni")

async def foto_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT id,targa,cognome,stanza FROM auto WHERE stato IN ("ritiro","parcheggiata") ORDER BY stanza')
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("📋 Nessuna auto disponibile per foto")
   return
  keyboard=[]
  for auto in auto_list:
   keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[1]} ({auto[2]})",callback_data=f"foto_{auto[0]}")])
  reply_markup=InlineKeyboardMarkup(keyboard)
  await update.message.reply_text("📷 CARICA FOTO\n\nSeleziona l'auto:",reply_markup=reply_markup)
 except Exception as e:
  logging.error(f"Errore foto: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def park_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT id,targa,cognome,stanza FROM auto WHERE stato="ritiro" ORDER BY stanza')
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("📋 Nessuna auto in ritiro")
   return
  keyboard=[]
  for auto in auto_list:
   keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[1]} ({auto[2]})",callback_data=f"park_{auto[0]}")])
  reply_markup=InlineKeyboardMarkup(keyboard)
  await update.message.reply_text("🅿️ CONFERMA PARCHEGGIO\n\nSeleziona l'auto parcheggiata:",reply_markup=reply_markup)
 except Exception as e:
  logging.error(f"Errore park: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def exit_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT id,targa,cognome,stanza,stato FROM auto WHERE stato IN ("ritiro","parcheggiata","stand-by","rientro","riconsegna") ORDER BY stanza')
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("📋 Nessuna auto disponibile per exit")
   return
  keyboard=[]
  emoji_map={'ritiro':"⚙️",'parcheggiata':"🅿️",'stand-by':"⏸️",'rientro':"🔄",'riconsegna':"🚪"}
  for auto in auto_list:
   emoji=emoji_map.get(auto[4],"❓")
   keyboard.append([InlineKeyboardButton(f"{emoji} Stanza {auto[3]} - {auto[1]} ({auto[2]}) - {auto[4]}",callback_data=f"exit_{auto[0]}")])
  reply_markup=InlineKeyboardMarkup(keyboard)
  await update.message.reply_text("🚪 AUTO IN RICONSEGNA\n\nSeleziona l'auto (da qualunque stato):",reply_markup=reply_markup)
 except Exception as e:
  logging.error(f"Errore exit: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def modifica_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT id,targa,cognome,stanza,numero_chiave,note FROM auto WHERE stato!="uscita" ORDER BY stanza')
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("📋 Nessuna auto da modificare")
   return
  keyboard=[]
  for auto in auto_list:
   chiave_text=f" - Chiave: {auto[4]}" if auto[4] else ""
   keyboard.append([InlineKeyboardButton(f"Stanza {auto[3]} - {auto[1]} ({auto[2]}){chiave_text}",callback_data=f"modifica_{auto[0]}")])
  reply_markup=InlineKeyboardMarkup(keyboard)
  await update.message.reply_text("✏️ MODIFICA AUTO\n\nSeleziona l'auto da modificare:",reply_markup=reply_markup)
 except Exception as e:
  logging.error(f"Errore modifica: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento delle auto")

async def lista_auto_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  cursor.execute('SELECT stanza,cognome,targa,numero_chiave,foto_count FROM auto WHERE stato="parcheggiata" ORDER BY stanza')
  auto_list=cursor.fetchall()
  conn.close()
  if not auto_list:
   await update.message.reply_text("🅿️ Nessuna auto in parcheggio")
   return
  msg="🅿️ AUTO IN PARCHEGGIO:\n\n"
  for auto in auto_list:
   stanza,cognome,targa,chiave,foto_count=auto
   chiave_text=f"Chiave: {chiave}" if chiave else "Chiave: --"
   foto_text=f" 📷 {foto_count}" if foto_count>0 else ""
   msg+=f"{stanza} | {cognome} | {targa} | {chiave_text}{foto_text}\n"
  await update.message.reply_text(msg)
 except Exception as e:
  logging.error(f"Errore lista_auto: {e}")
  await update.message.reply_text("❌ Errore durante il caricamento della lista")

async def handle_message(update:Update,context:ContextTypes.DEFAULT_TYPE):
 try:
  state=context.user_data.get('state')
  text=update.message.text.strip()
  if text.lower() in ['/annulla','/help','/start']:
   if text.lower()=='/annulla':await annulla_command(update,context);return
   elif text.lower()=='/help':await help_command(update,context);return
   elif text.lower()=='/start':await start(update,context);return
  if state=='ritiro_targa':
   targa=text.upper()
   if not validate_targa(targa):
    await update.message.reply_text("❌ Formato targa non valido!\n\nInserisci una targa valida:\n• Italiana: XX123XX\n• Europea: ABC123, 123ABC\n• Con trattini: XX-123-XX")
    return
   context.user_data['targa']=targa
   context.user_data['state']='ritiro_cognome'
   await update.message.reply_text("👤 Inserisci il COGNOME del cliente:")
  elif state=='ritiro_cognome':
   if not validate_cognome(text):
    await update.message.reply_text("❌ Cognome non valido!\n\nUsa solo lettere, spazi e apostrofi:")
    return
   context.user_data['cognome']=text.strip()
   context.user_data['state']='ritiro_stanza'
   await update.message.reply_text("🏨 Inserisci il numero STANZA (0-999):")
  elif state=='ritiro_stanza':
   try:
    stanza=int(text)
    if 0<=stanza<=999:
     context.user_data['stanza']=stanza
     context.user_data['state']='ritiro_chiave'
     await update.message.reply_text("🔑 Inserisci il NUMERO CHIAVE (0-999) o scrivi 'skip' per saltare:")
    else:await update.message.reply_text("❌ Numero stanza non valido! Inserisci un numero da 0 a 999:")
   except ValueError:await update.message.reply_text("❌ Inserisci un numero valido per la stanza:")
  elif state=='ritiro_chiave':
   if text.lower()=='skip':
    context.user_data['numero_chiave']=None
    context.user_data['state']='ritiro_note'
    await update.message.reply_text("📝 Inserisci eventuali NOTE (o scrivi 'skip' per saltare):")
   else:
    try:
     chiave=int(text)
     if 0<=chiave<=999:
      context.user_data['numero_chiave']=chiave
      context.user_data['state']='ritiro_note'
      await update.message.reply_text("📝 Inserisci eventuali NOTE (o scrivi 'skip' per saltare):")
     else:await update.message.reply_text("❌ Numero chiave non valido! Inserisci un numero da 0 a 999 o 'skip':")
    except ValueError:await update.message.reply_text("❌ Inserisci un numero valido per la chiave o 'skip':")
  elif state=='ritiro_note':
   note=text if text.lower()!='skip' else None
   targa=context.user_data['targa']
   cognome=context.user_data['cognome']
   stanza=context.user_data['stanza']
   numero_chiave=context.user_data.get('numero_chiave')
   numero_progressivo=get_prossimo_numero()
   try:
    conn=sqlite3.connect('carvalet.db')
    cursor=conn.cursor()
    cursor.execute('''INSERT INTO auto (targa,cognome,stanza,numero_chiave,note,numero_progressivo) VALUES (?,?,?,?,?,?)''',(targa,cognome,stanza,numero_chiave,note,numero_progressivo))
    auto_id=cursor.lastrowid
    conn.commit()
    conn.close()
    context.user_data.clear()
    recap_msg=f"✅ RICHIESTA CREATA!\n\n🆔 ID: {auto_id}\n🔢 Numero: #{numero_progressivo}\n🚗 Targa: {targa}\n👤 Cliente: {cognome}\n🏨 Stanza: {stanza}"
    if numero_chiave is not None:recap_msg+=f"\n🔑 Chiave: {numero_chiave}"
    if note:recap_msg+=f"\n📝 Note: {note}"
    recap_msg+=f"\n\n📅 Richiesta del {datetime.now().strftime('%d/%m/%Y alle %H:%M')}"
    await update.message.reply_text(recap_msg)
   except Exception as e:
    logging.error(f"Errore salvataggio richiesta: {e}")
    await update.message.reply_text("❌ Errore durante il salvataggio della richiesta")
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
  if data.startswith('recupero_'):
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
    if tipo_operazione=='riconsegna':
     await query.edit_message_text(f"🚪 {operazione_desc}!\n\n🔢 Auto #{auto[11]}\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n⏰ Tempo stimato: {minuti} minuti\n⏸️ Auto andrà in STAND-BY\n\n📅 {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
    else:
     await query.edit_message_text(f"✅ {operazione_desc}!\n\n🔢 Auto #{auto[11]}\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n⏰ Tempo stimato: {minuti} minuti\n\n📅 {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
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
    await query.edit_message_text(f"🅿️ AUTO PARCHEGGIATA!\n\n🔢 Auto #{auto[11]} completata\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
   else:await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
  elif data.startswith('exit_'):
   auto_id=int(data.split('_')[1])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   if update_auto_stato(auto_id,'riconsegna'):
    stato_precedente={'ritiro':'ritiro','parcheggiata':'parcheggio','stand-by':'stand-by','rientro':'rientro','riconsegna':'riconsegna'}
    await query.edit_message_text(f"🚪 AUTO IN RICONSEGNA!\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n📍 Da: {stato_precedente.get(auto[6],'stato')}\n\n⏰ Ora pronta per conferma partenza definitiva\n\n📅 {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
   else:await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
  elif data.startswith('riconsegna_'):
   auto_id=int(data.split('_')[1])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   if update_auto_stato(auto_id,'riconsegna'):
    await query.edit_message_text(f"🚪 RICONSEGNA RICHIESTA!\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n\n⏰ Ora il valet deve confermare la riconsegna\n\n📅 {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
   else:await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
  elif data.startswith('rientro_'):
   auto_id=int(data.split('_')[1])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   if update_auto_stato(auto_id,'rientro'):
    await query.edit_message_text(f"🔄 RIENTRO RICHIESTO!\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n\n⏰ Ora il valet deve confermare il rientro\n\n📅 {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
   else:await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
  elif data.startswith('partenza_'):
   auto_id=int(data.split('_')[1])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   if update_auto_stato(auto_id,'uscita'):
    await query.edit_message_text(f"🏁 PARTENZA CONFERMATA!\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n✅ Auto uscita definitivamente\n\n⏰ {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
   else:await query.edit_message_text("❌ Errore durante l'aggiornamento dello stato")
  elif data.startswith('foto_'):
   auto_id=int(data.split('_')[1])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   context.user_data['state']='upload_foto'
   context.user_data['foto_auto_id']=auto_id
   await query.edit_message_text(f"📷 CARICA FOTO\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n\nInvia le foto dell'auto (una o più). Scrivi 'fine' quando terminato.")
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
   await query.edit_message_text(f"✏️ MODIFICA AUTO\n\n🚗 Targa: {auto[1]}\n👤 Cliente: {auto[2]}\n🏨 Stanza: {auto[3]}{chiave_text}{note_text}\n\nCosa vuoi modificare?",reply_markup=reply_markup)
  elif data.startswith('mostra_foto_'):
   auto_id=int(data.split('_')[2])
   auto=get_auto_by_id(auto_id)
   if not auto:
    await query.edit_message_text("❌ Auto non trovata")
    return
   foto_list=get_foto_by_auto_id(auto_id)
   if not foto_list:
    await query.edit_message_text(f"📷 Nessuna foto trovata\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}")
    return
   await query.edit_message_text(f"📷 FOTO AUTO\n\n🚗 {auto[1]} - Stanza {auto[3]}\n👤 Cliente: {auto[2]}\n📊 Stato: {auto[6]}\n📷 Totale foto: {len(foto_list)}")
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
  application.add_handler(CommandHandler("vedi_foto",vedi_foto_command))
  application.add_handler(CommandHandler("vedi_recupero",vedi_recupero_command))
  application.add_handler(CommandHandler("ritiro",ritiro_command))
  application.add_handler(CommandHandler("riconsegna",riconsegna_command))
  application.add_handler(CommandHandler("rientro",rientro_command))
  application.add_handler(CommandHandler("partenza",partenza_command))
  application.add_handler(CommandHandler("recupero",recupero_command))
  application.add_handler(CommandHandler("foto",foto_command))
  application.add_handler(CommandHandler("park",park_command))
  application.add_handler(CommandHandler("exit",exit_command))
  application.add_handler(CommandHandler("modifica",modifica_command))
  application.add_handler(CommandHandler("lista_auto",lista_auto_command))
  application.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,handle_message))
  application.add_handler(MessageHandler(filters.PHOTO,handle_photo))
  application.add_handler(CallbackQueryHandler(handle_callback_query))
  logging.info(f"🚗 {BOT_NAME} v{BOT_VERSION} avviato!")
  logging.info("✅ Sistema gestione auto hotel attivo")
  logging.info("🔧 v4.3 LIGHT: +Sistema Rientro Auto Completo")
  print(f"🚗 {BOT_NAME} v{BOT_VERSION} avviato!")
  print("✅ Sistema gestione auto hotel attivo")
  print("🔧 v4.3 LIGHT: +Sistema Rientro Auto Completo")
  application.run_polling(allowed_updates=Update.ALL_TYPES)
 except Exception as e:
  logging.error(f"Errore durante l'avvio del bot: {e}")
  print(f"❌ Errore durante l'avvio: {e}")

if __name__=='__main__':main()
