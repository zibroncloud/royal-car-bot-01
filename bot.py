def init_db():
 try:
  conn=sqlite3.connect('carvalet.db')
  cursor=conn.cursor()
  # DATABASE SEMPLIFICATO + CAMPO BOX
  cursor.execute('''CREATE TABLE IF NOT EXISTS auto (
   id INTEGER PRIMARY KEY AUTOINCREMENT,
   cognome TEXT NOT NULL,
   targa TEXT NOT NULL, 
   stanza INTEGER NOT NULL,
   stato TEXT DEFAULT 'richiesta',
   data_arrivo DATE DEFAULT CURRENT_DATE,
   data_partenza DATE,
   is_ghost INTEGER DEFAULT 0,
   numero_box INTEGER
  )''')
  # Aggiungere colonna BOX se non esiste (per DB esistenti)
  try:
   cursor.execute('ALTER TABLE auto ADD COLUMN numero_box INTEGER')
  except:pass  # Colonna già esistente
  
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
  logging.info("Database semplificato inizializzato + campo BOX")
 except Exception as e:logging.error(f"Errore DB: {e}")
