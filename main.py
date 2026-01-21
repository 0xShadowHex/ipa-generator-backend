import os
import shutil
import zipfile
import uuid
import logging
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask

# Logging einrichten
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = "/tmp/ipa_builds"
TEMPLATE_ZIP = "template/template.zip"

if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

def cleanup(path: str):
    """Löscht das Build-Verzeichnis nach dem Download."""
    if os.path.exists(path):
        shutil.rmtree(path)
        logger.info(f"Cleaned up build directory: {path}")

@app.post("/generate-ipa")
async def generate_ipa(request: Request):
    build_id = str(uuid.uuid4())
    build_path = os.path.join(TEMP_DIR, build_id)
    extract_path = os.path.join(build_path, "extracted")
    
    try:
        data = await request.json()
        files = data.get("files", {})
        project_name = data.get("projectName", "Application")
        logger.info(f"Starting build {build_id} for project {project_name}")

        os.makedirs(extract_path, exist_ok=True)

        # 1. Entpacke die Vorlage
        if not os.path.exists(TEMPLATE_ZIP):
            logger.error("Template ZIP not found!")
            return {"error": "Template not found on server"}

        with zipfile.ZipFile(TEMPLATE_ZIP, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        logger.info(f"Extracted template to {extract_path}")

        # 2. Überschreibe die Dateien in der korrekten Struktur
        # Struktur: Payload/Application.app/web/html/index.html etc.
        for file_path, content in files.items():
            filename = os.path.basename(file_path)
            if filename.endswith('.html'):
                target_subpath = "Payload/Application.app/web/html"
            elif filename.endswith('.css'):
                target_subpath = "Payload/Application.app/web/css"
            elif filename.endswith('.js'):
                target_subpath = "Payload/Application.app/web/js"
            else:
                target_subpath = "Payload/Application.app/web"

            target_file = os.path.join(extract_path, target_subpath, filename)
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Updated file: {target_file}")

        # 3. Erstelle die neue IPA (ZIP)
        final_ipa_path = os.path.join(build_path, f"{project_name}.ipa")
        
        with zipfile.ZipFile(final_ipa_path, 'w', zipfile.ZIP_DEFLATED) as new_zip:
            for root, dirs, filenames in os.walk(extract_path):
                for filename in filenames:
                    abs_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(abs_path, extract_path)
                    new_zip.write(abs_path, rel_path)

        # Validierung
        if not os.path.exists(final_ipa_path) or os.path.getsize(final_ipa_path) == 0:
            logger.error("Generated IPA is missing or empty!")
            return {"error": "Failed to generate valid IPA"}

        logger.info(f"Successfully generated IPA: {final_ipa_path} ({os.path.getsize(final_ipa_path)} bytes)")

        # FIX: Verwende BackgroundTask direkt in FileResponse, damit die Datei erst NACH dem Streamen gelöscht wird.
        return FileResponse(
            final_ipa_path,
            media_type="application/octet-stream",
            filename=f"{project_name}.ipa",
            background=BackgroundTask(cleanup, build_path)
        )

    except Exception as e:
        logger.error(f"Error during IPA generation: {str(e)}")
        if os.path.exists(build_path):
            cleanup(build_path)
        return {"error": str(e)}

@app.get("/")
async def root():
    return {"status": "ok", "message": "IPA Generator Backend is running (Streaming Fix Applied)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
