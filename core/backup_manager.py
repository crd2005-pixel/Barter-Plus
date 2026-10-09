import os
import shutil
import sqlite3
import traceback
from datetime import datetime
from PyQt6.QtCore import QRunnable, QObject, pyqtSignal

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

SCOPES = ['https://www.googleapis.com/auth/drive.file']
FOLDER_NAME = "BarterPlus_Backups"

class BackupSignals(QObject):
    finished = pyqtSignal(bool, str)

class BackupWorker(QRunnable):
    def __init__(self, db_path="barterplus.db"):
        super().__init__()
        self.db_path = db_path
        self.signals = BackupSignals()

    def run(self):
        if not GOOGLE_API_AVAILABLE:
            self.signals.finished.emit(False, "Librerías de Google API no instaladas. Ejecute: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
            return

        try:
            # 1. Copia Segura Local (SQLite Backup API para evitar base bloqueada)
            import tempfile
            temp_dir = tempfile.gettempdir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_backup_path = os.path.join(temp_dir, f"barter_backup_temp_{timestamp}.db")

            if os.path.exists(self.db_path):
                # Usar la API de backup de SQLite garantiza consistencia
                source_conn = sqlite3.connect(self.db_path)
                dest_conn = sqlite3.connect(temp_backup_path)
                with source_conn, dest_conn:
                    source_conn.backup(dest_conn)
                dest_conn.close()
                source_conn.close()
            else:
                self.signals.finished.emit(False, f"No se encontró la base de datos local en: {self.db_path}")
                return

            # 2. Upload a Google Drive
            uploader = GoogleDriveUploader()
            success, msg = uploader.upload_file(temp_backup_path, f"BarterPlus_Backup_{timestamp}.db")

            # 3. Limpieza local del temporal
            try:
                os.remove(temp_backup_path)
            except Exception as e:
                pass # Fail silently on cleanup

            self.signals.finished.emit(success, msg)

        except Exception as e:
            error_msg = traceback.format_exc()
            self.signals.finished.emit(False, f"Error inesperado en Backup:\n{str(e)}")

class GoogleDriveUploader:
    def __init__(self):
        self.creds = None
        self.token_file = 'token.json'
        self.credentials_file = 'credentials.json'

    def authenticate(self) -> bool:
        if os.path.exists(self.token_file):
            self.creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception:
                    # Token refresh failed, need re-auth
                    pass

            if not self.creds or not self.creds.valid:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(f"Falta el archivo {self.credentials_file} para autenticar con Google Drive.")

                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, SCOPES)
                self.creds = flow.run_local_server(port=0)

                with open(self.token_file, 'w') as token:
                    token.write(self.creds.to_json())
        return True

    def _get_or_create_folder(self, service) -> str:
        # Check if folder exists
        query = f"name='{FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        items = results.get('files', [])

        if not items:
            # Create folder
            folder_metadata = {
                'name': FOLDER_NAME,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = service.files().create(body=folder_metadata, fields='id').execute()
            return folder.get('id')
        else:
            return items[0].get('id')

    def upload_file(self, filepath: str, filename: str):
        try:
            self.authenticate()
            service = build('drive', 'v3', credentials=self.creds)

            folder_id = self._get_or_create_folder(service)

            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            media = MediaFileUpload(filepath, mimetype='application/x-sqlite3', resumable=True)

            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()

            # Optional: Rotate backups (keep last 50)
            self._rotate_backups(service, folder_id)

            return True, f"Backup subido correctamente a Google Drive (ID: {file.get('id')})"
        except Exception as e:
            return False, f"Error al subir a Google Drive: {str(e)}"

    def _rotate_backups(self, service, folder_id, limit=50):
        try:
            query = f"'{folder_id}' in parents and trashed=false"
            results = service.files().list(q=query, spaces='drive', fields='files(id, name, createdTime)', orderBy='createdTime desc').execute()
            items = results.get('files', [])

            if len(items) > limit:
                files_to_delete = items[limit:]
                for f in files_to_delete:
                    service.files().delete(fileId=f.get('id')).execute()
        except Exception:
            pass # Fail silently on rotation
